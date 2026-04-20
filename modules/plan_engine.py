"""
plan_engine.py - 任务规划引擎

职责：
1. 任务分解（decompose） - 调用TaskDecomposer
2. 角色匹配（role_match） - 调用RoleMatcher
3. FastPath缓存 - 相似任务复用成功规划
4. 熔断决策 - 失败过多时跳过或降级

约束：
- 参考OpenClaw原生能力
- 不与sessions_spawn冲突（sessions_spawn是subagent管理，PlanEngine是规划层）
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
    CLOSED = "closed"      # 正常：放行
    OPEN = "open"          # 熔断：拒绝/降级
    HALF_OPEN = "half_open"  # 半开：试探恢复


@dataclass
class Subtask:
    """子任务结构"""
    phase: str           # round1/round2/round3
    role: str            # 角色名
    title: str           # 子任务标题
    verify: List[str]    # 验证点
    timeout: int = 300  # 超时秒数（默认300s）
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
    
    规则：
    - 失败率 > threshold 在 window内 → OPEN
    - OPEN状态持续 duration 秒 → HALF_OPEN
    - HALF_OPEN 成功 → CLOSED
    - HALF_OPEN 失败 → OPEN（重新计时）
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
    
    相似任务复用成功规划，避免重复规划开销
    
    策略：
    - 任务文本hash匹配
    - 精确匹配优先，模糊匹配次之
    - 记录命中率，用于判断是否降级到简单策略
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
                        # TTL过期，删除
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
        # 归一化：去除多余空白、转小写
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


class PlanEngine:
    """
    任务规划引擎
    
    整合：
    1. TaskDecomposer - 任务分解
    2. RoleMatcher - 角色匹配
    3. FastPathCache - 缓存加速
    4. CircuitBreaker - 熔断保护
    
    流程：
    plan(task) → 检查缓存 → 熔断检查 → 分解+匹配 → 缓存结果 → 返回Plan
    """
    
    def __init__(
        self,
        workspace_root: str,
        cache_dir: Optional[str] = None,
        failure_threshold: float = 0.5,
        circuit_open_duration: int = 30,
    ):
        self.workspace_root = workspace_root
        
        # 核心组件
        self.role_matcher = RoleMatcher(workspace_root)
        self.task_decomposer = TaskDecomposer(workspace_root)
        
        # 缓存和熔断
        self.fastpath = FastPathCache(cache_dir=cache_dir)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            open_duration=circuit_open_duration,
        )
        
        # 统计
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "circuit_breaks": 0,
            "planning_errors": 0,
        }
        self._stats_lock = Lock()
    
    def plan(self, task: str, use_cache: bool = True, allow_fallback: bool = True) -> Plan:
        """
        生成任务规划
        
        Args:
            task: 原始任务描述
            use_cache: 是否使用FastPath缓存
            allow_fallback: 熔断时是否降级执行
        
        Returns:
            Plan对象，包含subtasks、matched_roles等信息
        """
        task_id = self._generate_task_id(task)
        
        with self._stats_lock:
            self._stats["total_requests"] += 1
        
        # 1. FastPath缓存检查
        if use_cache:
            cached = self.fastpath.get(task)
            if cached:
                with self._stats_lock:
                    self._stats["cache_hits"] += 1
                
                plan = Plan(
                    task_id=task_id,
                    original_task=task,
                    subtasks=[self._dict_to_subtask(s) for s in cached.get("subtasks", [])],
                    matched_roles=cached.get("matched_roles", []),
                    cache_hit=True,
                )
                logger.info(f"[PlanEngine] FastPath hit for task: {task[:50]}...")
                return plan
        
        # 2. 熔断检查
        if not self.circuit_breaker.is_allowed():
            with self._stats_lock:
                self._stats["circuit_breaks"] += 1
            
            logger.warning(f"[PlanEngine] Circuit breaker OPEN, using fallback")
            
            if allow_fallback:
                # 降级：返回简单的一阶段规划
                return self._fallback_plan(task_id, task)
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            # 3. 任务分解 + 角色匹配
            subtasks, matched_roles = self._decompose_and_match(task)
            
            # 4. 构建Plan
            plan = Plan(
                task_id=task_id,
                original_task=task,
                subtasks=subtasks,
                matched_roles=[m.role for m in matched_roles],
                cache_hit=False,
            )
            
            # 5. 缓存结果
            self.fastpath.set(task, {
                "subtasks": [self._subtask_to_dict(s) for s in subtasks],
                "matched_roles": [m.role for m in matched_roles],
            })
            
            # 6. 记录成功
            self.circuit_breaker.record_success()
            
            return plan
            
        except Exception as e:
            # 7. 记录失败
            self.circuit_breaker.record_failure()
            
            with self._stats_lock:
                self._stats["planning_errors"] += 1
            
            logger.error(f"[PlanEngine] Planning failed: {e}")
            
            if allow_fallback:
                return self._fallback_plan(task_id, task)
            else:
                raise
    
    def _decompose_and_match(self, task: str) -> Tuple[List[Subtask], List[Any]]:
        """
        分解任务并匹配角色
        
        Returns:
            (subtasks, role_matches)
        """
        # 角色匹配（调用RoleMatcher）
        role_matches = self.role_matcher.match(task)
        
        # 获取角色列表（用于TaskDecomposer）
        roles = [m.role for m in role_matches] if role_matches else []
        
        # 任务分解（调用TaskDecomposer）
        # TaskDecomposer.get_roles会再次调用RoleMatcher，所以这里用它的结果
        # 但我们已经有了role_matches，直接用它
        
        # 决定Round阶段
        subtasks = self._create_subtasks(task, roles, role_matches)
        
        return subtasks, role_matches
    
    def _create_subtasks(
        self,
        task: str,
        roles: List[Dict],
        role_matches: List[Any],
    ) -> List[Subtask]:
        """根据角色和任务创建子任务"""
        subtasks = []
        
        # 根据匹配到的角色数量决定Round
        if not role_matches:
            # 无匹配，使用单角色
            subtasks.append(Subtask(
                phase="round1",
                role="Senior Developer",
                title=f"执行: {task[:80]}",
                verify=["任务完成"],
                timeout=300,
            ))
            return subtasks
        
        # 多角色：按Round分配
        # Round1: 规划角色（通常第一个）
        # Round2: 开发角色
        # Round3: 测试角色
        
        round_map = {
            "round1": [],
            "round2": [],
            "round3": [],
        }
        
        for i, match in enumerate(role_matches):
            role = match.role
            role_name = role.get("name", "Unknown")
            role_id = role.get("id", "")
            source = getattr(match, 'source', 'unknown')
            
            # 根据source决定Round
            if source in ("fixed_team", "vector"):
                if i == 0 and any(kw in role_id.lower() for kw in ["architect", "manager", "lead"]):
                    phase = "round1"
                elif i <= 2 and any(kw in role_id.lower() for kw in ["developer", "engineer", "implement"]):
                    phase = "round2"
                else:
                    phase = "round3"
            else:
                # audit/evolution团队，按顺序
                phase = f"round{(i % 3) + 1}"
            
            round_map[phase].append((role_name, role))
        
        # 生成subtasks
        if round_map["round1"]:
            role_name, role = round_map["round1"][0]
            subtasks.append(Subtask(
                phase="round1",
                role=role_name,
                title=f"规划: {task[:80]}",
                verify=["规划完成", "架构设计合理"],
                timeout=300,
                metadata={"role_id": role.get("id"), "source": getattr(role_matches[0], 'source', 'unknown')},
            ))
        
        if round_map["round2"]:
            role_name, role = round_map["round2"][0]
            subtasks.append(Subtask(
                phase="round2",
                role=role_name,
                title=f"执行: {task[:80]}",
                verify=["代码实现完成", "通过基本测试"],
                timeout=300,
                metadata={"role_id": role.get("id")},
            ))
        
        if round_map["round3"]:
            role_name, role = round_map["round3"][0]
            subtasks.append(Subtask(
                phase="round3",
                role=role_name,
                title=f"审查: {task[:80]}",
                verify=["审查通过", "质量合格"],
                timeout=300,
                metadata={"role_id": role.get("id")},
            ))
        
        # 如果没有任何subtask，添加一个默认的
        if not subtasks:
            subtasks.append(Subtask(
                phase="round1",
                role=roles[0].get("name", "Developer") if roles else "Developer",
                title=f"执行: {task[:80]}",
                verify=["任务完成"],
                timeout=300,
            ))
        
        return subtasks
    
    def _fallback_plan(self, task_id: str, task: str) -> Plan:
        """降级规划：简单单阶段"""
        return Plan(
            task_id=task_id,
            original_task=task,
            subtasks=[
                Subtask(
                    phase="round1",
                    role="Senior Developer",
                    title=f"[FALLBACK] {task[:80]}",
                    verify=["基本完成"],
                    timeout=300,
                )
            ],
            matched_roles=[],
            cache_hit=False,
            circuit_broken=True,
        )
    
    def _generate_task_id(self, task: str) -> str:
        """生成任务ID"""
        return hashlib.sha256(task.encode()).hexdigest()[:12]
    
    def _subtask_to_dict(self, s: Subtask) -> Dict:
        """Subtask转dict（用于缓存）"""
        return {
            "phase": s.phase,
            "role": s.role,
            "title": s.title,
            "verify": s.verify,
            "timeout": s.timeout,
            "metadata": s.metadata,
        }
    
    def _dict_to_subtask(self, d: Dict) -> Subtask:
        """dict转Subtask（用于读取缓存）"""
        return Subtask(
            phase=d["phase"],
            role=d["role"],
            title=d["title"],
            verify=d.get("verify", []),
            timeout=d.get("timeout", 300),
            metadata=d.get("metadata", {}),
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._stats_lock:
            stats = dict(self._stats)
        
        stats["circuit_breaker"] = self.circuit_breaker.get_stats()
        stats["cache_size"] = len(self.fastpath._cache)
        
        return stats
    
    def record_execution_result(self, task_id: str, success: bool) -> None:
        """记录执行结果（用于未来优化）"""
        if success:
            self.circuit_breaker.record_success()
        else:
            self.circuit_breaker.record_failure()


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass


# 便捷函数
def create_plan_engine(
    workspace_root: str,
    cache_dir: Optional[str] = None,
) -> PlanEngine:
    """创建PlanEngine实例"""
    return PlanEngine(
        workspace_root=workspace_root,
        cache_dir=cache_dir,
    )


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
