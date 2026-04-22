"""
plan_engine.py - 任务规划引擎

职责:
1. 任务分解(decompose) - 调用TaskDecomposer
2. 角色匹配(role_match) - 调用RoleMatcher
3. FastPath缓存 - 相似任务复用成功规划
4. 熔断决策 - 失败过多时跳过或降级

约束:
- 参考OpenClaw原生能力
- 不与sessions_spawn冲突(sessions_spawn是subagent管理,PlanEngine是规划层)
- 300秒超时足够
"""

import os
import json
import hashlib
import time
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

from .role_matcher import RoleMatcher
from .task_decomposer import TaskDecomposer, Task

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """熔断状态"""
    CLOSED = "closed"      # 正常:放行
    OPEN = "open"          # 熔断:拒绝/降级
    HALF_OPEN = "half_open"  # 半开:试探恢复


@dataclass
class Subtask:
    """子任务结构"""
    phase: str           # round1/round2/round3
    role: str            # 角色名
    title: str           # 子任务标题
    verify: List[str]    # 验证点
    timeout: int = 300  # 超时秒数(默认300s)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """规划结果"""
    task_id: str
    original_task: str
    subtasks: List[Subtask]
    matched_roles: List[Dict]  # RoleMatch结果
    cache_hit: bool = False
    circuit_broken: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FastPathEntry:
    """FastPath缓存条目"""
    plan: Dict
    task_hash: str
    created_at: float
    hit_count: int = 0


class CircuitBreaker:
    """
    熔断器

    规则:
    - 失败率 > threshold 在 window内 → OPEN
    - OPEN状态持续 duration 秒 → HALF_OPEN
    - HALF_OPEN 成功 → CLOSED
    - HALF_OPEN 失败 → OPEN(重新计时)
    """

    def __init__(
        self,
        failure_threshold: float = 0.5,
        window_seconds: int = 60,
        open_duration: int = 30,
        half_open_success_threshold: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.open_duration = open_duration
        self.half_open_success_threshold = half_open_success_threshold

        self._state = CircuitState.CLOSED
        self._failures: List[float] = []
        self._successes: List[float] = []
        self._last_failure_time: Optional[float] = None
        self._half_open_attempts: int = 0
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """获取当前熔断状态"""
        with self._lock:
            now = time.time()

            if self._state == CircuitState.OPEN:
                # 检查是否需要转换到HALF_OPEN
                if self._last_failure_time and (now - self._last_failure_time) >= self.open_duration:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_attempts = 0
                    logger.info("[CircuitBreaker] OPEN → HALF_OPEN")

            return self._state

    def record_success(self) -> None:
        """记录成功"""
        with self._lock:
            now = time.time()
            self._successes.append(now)
            self._prune_old(now)

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_attempts += 1
                if self._half_open_attempts >= self.half_open_success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failures.clear()
                    logger.info("[CircuitBreaker] HALF_OPEN → CLOSED (success)")

    def record_failure(self) -> None:
        """记录失败"""
        with self._lock:
            now = time.time()
            self._failures.append(now)
            self._last_failure_time = now
            self._prune_old(now)

            # 检查是否需要打开熔断
            if self._should_open():
                self._state = CircuitState.OPEN
                logger.warning(f"[CircuitBreaker] CLOSED → OPEN (failure rate: {self._get_failure_rate():.2%})")

    def _prune_old(self, now: float) -> None:
        """清理过期的记录"""
        cutoff = now - self.window_seconds
        self._failures = [t for t in self._failures if t > cutoff]
        self._successes = [t for t in self._successes if t > cutoff]

    def _should_open(self) -> bool:
        """判断是否应该打开熔断"""
        total = len(self._failures) + len(self._successes)
        if total == 0:
            return False
        return len(self._failures) / total >= self.failure_threshold

    def _get_failure_rate(self) -> float:
        """获取当前失败率"""
        total = len(self._failures) + len(self._successes)
        if total == 0:
            return 0.0
        return len(self._failures) / total

    def is_allowed(self) -> bool:
        """是否允许执行"""
        return self.state != CircuitState.OPEN

    def get_stats(self) -> Dict[str, Any]:
        """获取熔断器统计"""
        with self._lock:
            return {
                "state": self.state.value,
                "failures": len(self._failures),
                "successes": len(self._successes),
                "failure_rate": self._get_failure_rate(),
            }


class FastPathCache:
    """
    FastPath缓存

    相似任务复用成功规划,避免重复规划开销

    策略:
    - 任务文本hash匹配
    - 精确匹配优先,模糊匹配次之
    - 记录命中率,用于判断是否降级到简单策略
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_entries: int = 200,
        ttl_seconds: int = 3600,
    ):
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.openclaw/skills/sindris/cache")

        self.cache_dir = cache_dir
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds

        os.makedirs(self.cache_dir, exist_ok=True)

        self._cache: Dict[str, FastPathEntry] = {}
        self._lock = Lock()
        self._load_cache()

    def _cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        safe_key = hashlib.sha256(key.encode()).hexdigest()[:16]
        return os.path.join(self.cache_dir, f"plan_{safe_key}.json")

    def _load_cache(self) -> None:
        """从磁盘加载缓存"""
        try:
            for fname in os.listdir(self.cache_dir):
                if not fname.startswith("plan_") or not fname.endswith(".json"):
                    continue

                fpath = os.path.join(self.cache_dir, fname)
                try:
                    with open(fpath) as f:
                        data = json.load(f)

                    entry = FastPathEntry(
                        plan=data["plan"],
                        task_hash=data["task_hash"],
                        created_at=data["created_at"],
                        hit_count=data.get("hit_count", 0),
                    )

                    # 检查TTL
                    if time.time() - entry.created_at < self.ttl_seconds:
                        self._cache[fname] = entry
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"[FastPathCache] Failed to load cache: {e}")

    def _save_entry(self, key: str, entry: FastPathEntry) -> None:
        """保存缓存条目到磁盘"""
        try:
            fpath = self._cache_path(key)
            with open(fpath, 'w') as f:
                json.dump({
                    "plan": entry.plan,
                    "task_hash": entry.task_hash,
                    "created_at": entry.created_at,
                    "hit_count": entry.hit_count,
                }, f)
        except Exception as e:
            logger.warning(f"[FastPathCache] Failed to save entry: {e}")

    def get(self, task: str) -> Optional[Dict]:
        """获取缓存的规划"""
        task_hash = self._hash_task(task)

        with self._lock:
            # 精确匹配
            for entry in self._cache.values():
                if entry.task_hash == task_hash:
                    # 检查TTL
                    if time.time() - entry.created_at < self.ttl_seconds:
                        entry.hit_count += 1
                        logger.info(f"[FastPathCache] HIT (exact): {task[:50]}... (hit_count={entry.hit_count})")
                        return entry.plan
                    else:
                        # TTL过期,删除
                        pass

            return None

    def set(self, task: str, plan: Dict) -> None:
        """保存规划到缓存"""
        task_hash = self._hash_task(task)

        with self._lock:
            # 检查是否需要淘汰旧条目
            if len(self._cache) >= self.max_entries:
                self._evict_lru()

            key = f"plan_{hashlib.sha256(task_hash.encode()).hexdigest()[:16]}"
            entry = FastPathEntry(
                plan=plan,
                task_hash=task_hash,
                created_at=time.time(),
                hit_count=0,
            )
            self._cache[key] = entry

        self._save_entry(key, entry)
        logger.info(f"[FastPathCache] Stored plan for task: {task[:50]}...")

    def _hash_task(self, task: str) -> str:
        """生成任务hash"""
        # 归一化:去除多余空白、转小写
        normalized = " ".join(task.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _evict_lru(self) -> None:
        """淘汰最少使用的条目"""
        if not self._cache:
            return

        # 淘汰hit_count最低的条目
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].hit_count)
        del self._cache[lru_key]

        # 删除磁盘文件
        try:
            os.remove(os.path.join(self.cache_dir, lru_key))
        except Exception:
            pass
class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass



# 导出
__all__ = [
    "PlanEngine",
    "Plan",
    "Subtask",
    "FastPathCache",
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerOpenError",
    "create_plan_engine",
]
