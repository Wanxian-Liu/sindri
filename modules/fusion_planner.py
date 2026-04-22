"""
fusion_planner.py - 融合规划器

整合老架构 RoleMatcher（4层fallback）+ 新架构 PlanEngine（缓存+熔断）

融合策略：
1. RoleMatcher.match() 的4层fallback策略（优先）：
   - 固定团队 → 向量相似度 → claim覆盖 → 关键词备用
   - 叠加 TaskClassifier + RoleHierarchicalMatcher
2. PlanEngine 的缓存+熔断能力（增强）：
   - FastPathCache 避免重复规划
   - CircuitBreaker 防止雪崩

融合逻辑 _decompose_and_match()：
- 第1层：RoleMatcher.match() 获取角色候选（4层fallback）
- 第2层：TaskDecomposer.decompose_by_round() 按Round生成Task
- 第3层：融合为 Subtask，返回 (subtasks, role_matches)
"""

import os
import json
import hashlib
import time
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from threading import Lock

from .role_matcher import RoleMatcher, RoleMatch
from .task_decomposer import TaskDecomposer, Task
from .plan_engine import FastPathCache, CircuitState, Plan, Subtask
# 使用scripts/circuit_breaker.py的完整CircuitBreaker（有ROLE_TIMEOUTS）
import sys
sys.path.insert(0, str(__file__.rsplit('/', 2)[0]))
try:
    from scripts.circuit_breaker import CircuitBreaker
except ImportError:
    from .plan_engine import CircuitBreaker  # 回退到plan_engine版本

# OMX集成（延迟导入以支持可选依赖）
_OMXIntegrator = None

def _get_omx_integrator(workspace_root: str):
    global _OMXIntegrator
    if _OMXIntegrator is None:
        try:
            import os
            import sys
            # P2-7 Fix: 使用append而非insert(0)，避免破坏全局模块搜索顺序
            # 确保父目录(sindris/)在sys.path，使 from scripts.omx_integrator 可用
            _sindris_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _sindris_root not in sys.path:
                sys.path.append(_sindris_root)
            from scripts.omx_integrator import OMXIntegrator
            _OMXIntegrator = OMXIntegrator(workspace_root)
        except ImportError:
            return None
    return _OMXIntegrator

logger = logging.getLogger(__name__)


@dataclass
class FusionPlan:
    """融合规划结果"""
    task_id: str
    original_task: str
    subtasks: List[Subtask]           # PlanEngine格式（用于sessions_spawn）
    tasks: List[Task]                 # TaskDecomposer格式（原始Task）
    matched_roles: List[Dict]         # RoleMatch.role 结果
    role_matches: List[RoleMatch]      # 原始RoleMatch对象（含source/similarity）
    cache_hit: bool = False
    circuit_broken: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class FusionPlanner:
    """
    融合规划器
    
    整合：
    - RoleMatcher（老架构4层fallback）
    - TaskDecomposer（Round分解）
    - FastPathCache（新架构缓存）
    - CircuitBreaker（新架构熔断）
    
    融合流程：
      plan(task)
        ├─ FastPathCache.get()        [缓存层]
        ├─ CircuitBreaker.is_allowed() [熔断层]
        ├─ _decompose_and_match()     [融合核心]
        │    ├─ RoleMatcher.match()   [角色匹配：4层fallback]
        │    ├─ TaskDecomposer.get_roles()   [角色获取]
        │    └─ TaskDecomposer.decompose_by_round() [Round分解]
        ├─ FastPathCache.set()        [缓存存储]
        └─ return FusionPlan
    """

    # 熔断配置
    DEFAULT_FAILURE_THRESHOLD = 0.5    # 50% 失败率阈值
    DEFAULT_WINDOW_SECONDS = 60       # 60秒窗口
    DEFAULT_OPEN_DURATION = 30         # 30秒熔断持续
    DEFAULT_CACHE_TTL = 3600           # 1小时缓存

    def __init__(
        self,
        workspace_root: str,
        cache_dir: Optional[str] = None,
        failure_threshold: float = DEFAULT_FAILURE_THRESHOLD,
        circuit_open_duration: int = DEFAULT_OPEN_DURATION,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        use_omx: bool = True,
    ):
        self.workspace_root = workspace_root
        self.use_omx = use_omx

        # ── 核心组件（老架构）────────────────────────────
        self.role_matcher = RoleMatcher(workspace_root)
        self.task_decomposer = TaskDecomposer(workspace_root)

        # ── 增强组件（新架构）────────────────────────────
        self.fastpath = FastPathCache(
            cache_dir=cache_dir,
            ttl_seconds=cache_ttl,
        )
        # P2-001 Fix: 使用scripts/circuit_breaker.py的完整CircuitBreaker（含ROLE_TIMEOUTS角色超时配置）
        self.circuit_breaker = CircuitBreaker(
            role_type="planner",  # 使用完整版CircuitBreaker，需要role_type参数
            failure_threshold=failure_threshold,
            recovery_timeout=circuit_open_duration,
        )

        # ── OMX集成 ───────────────────────────────────
        self._omx_integrator = _get_omx_integrator(workspace_root) if use_omx else None

        # ── 统计 ───────────────────────────────────────
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "circuit_breaks": 0,
            "planning_errors": 0,
            "fallback_uses": 0,
        }
        self._stats_lock = Lock()

    def plan(
        self,
        task: str,
        use_cache: bool = True,
        allow_fallback: bool = True,
    ) -> FusionPlan:
        """
        生成融合规划

        Args:
            task: 原始任务描述
            use_cache: 是否使用FastPath缓存
            allow_fallback: 熔断时是否降级执行

        Returns:
            FusionPlan对象
        """
        task_id = self._generate_task_id(task)

        with self._stats_lock:
            self._stats["total_requests"] += 1

        # P0-3 Fix: OMX Round1 Start移到"即将执行角色匹配"时，而非进入plan()时
        # 这样 role_matches 不会是 None，OMX事件携带真实的角色信息
        omx_task_id = None  # 延迟初始化

        # ── 第1层：缓存检查 ──────────────────────────────
        if use_cache:
            cached = self.fastpath.get(task)
            if cached:
                with self._stats_lock:
                    self._stats["cache_hits"] += 1
                logger.info(f"[FusionPlanner] FastPath HIT: {task[:50]}...")
                plan = self._restore_fusion_plan(task_id, task, cached)
                # P0-3 Fix: Cache HIT时也发送完整的OMX事件（含角色信息）
                self._omx_track("round1_complete", task=task, task_id=None, verified=True,
                                plan_summary=f"Cache HIT for {task[:50]}...",
                                role_matches=plan.role_matches if hasattr(plan, 'role_matches') else None)
                return plan

        # ── 第2层：熔断检查 ──────────────────────────────
        if not self.circuit_breaker.can_execute():
            with self._stats_lock:
                self._stats["circuit_breaks"] += 1
            logger.warning("[FusionPlanner] Circuit breaker OPEN, using fallback")
            # P2-3 Fix: 传递实际task_id而非None，使OMX事件可正确追踪
            circuit_omx_task_id = self._omx_track("round1_start", task=task, task_id=task_id, role_matches=None)
            self._omx_track("round1_complete", task=task, task_id=circuit_omx_task_id, verified=False, plan_summary="Circuit breaker open")

            if allow_fallback:
                # P2-1/P2-3 Fix: 在fallback路径中使用捕获的omx_task_id
                self._omx_track("fallback_start", task=task, task_id=circuit_omx_task_id, reason="circuit_breaker_open")
                fallback_plan = self._fallback_plan(task_id, task)
                self._omx_track("fallback_complete", task=task, task_id=circuit_omx_task_id, verified=False,
                                 plan_summary=f"Fallback plan: {len(fallback_plan.subtasks)} subtask(s)",
                                 reason="circuit_breaker_open", subtask_count=len(fallback_plan.subtasks))
                return fallback_plan
            else:
                # 使用scripts/circuit_breaker.py的异常（统一使用完整版）
                from scripts.circuit_breaker import CircuitOpenError
                raise CircuitOpenError("Circuit breaker is open")

        try:
            # ── 第3层：融合分解+匹配 ────────────────────
            # P0-3 Fix: OMX Round1 Start在角色匹配完成后才发出，此时role_matches已知
            # 先执行角色匹配（不重复调用role_matcher.match）
            # _decompose_and_match内部会调用role_matcher.match，所以先触发OMX再调用
            _pre_role_matches = self.role_matcher.match(task)
            logger.info(f"[FusionPlanner] Pre-check: {len(_pre_role_matches)} roles matched")
            # P2-1 Fix: 传递实际task_id而非None，使OMX事件可正确追踪
            omx_task_id = self._omx_track("round1_start", task=task, task_id=task_id, role_matches=_pre_role_matches)

            result = self._decompose_and_match(task, precomputed_role_matches=_pre_role_matches)
            subtasks, tasks, role_matches = result

            # 构建FusionPlan
            plan = FusionPlan(
                task_id=task_id,
                original_task=task,
                subtasks=subtasks,
                tasks=tasks,
                matched_roles=[m.role for m in role_matches],
                role_matches=role_matches,
                cache_hit=False,
            )

            # ── 第4层：缓存存储 ──────────────────────────
            self.fastpath.set(task, self._fusion_plan_to_dict(plan))
            self.circuit_breaker.record_success()

            # ── OMX Round1 Complete（携带完整role_matches）──────
            plan_summary = f"{len(subtasks)} subtasks across {[s.phase for s in subtasks]}"
            self._omx_track("round1_complete", task=task, task_id=omx_task_id, verified=True,
                            plan_summary=plan_summary, role_matches=role_matches)

            return plan

        except Exception as e:
            self.circuit_breaker.record_failure()

            logger.error(f"[FusionPlanner] Planning failed: {e}")
            # P2-3 Fix: 传递实际task_id而非None，使OMX事件可正确追踪
            error_omx_task_id = self._omx_track("round1_start", task=task, task_id=task_id, role_matches=None)
            self._omx_track("round1_complete", task=task, task_id=error_omx_task_id, verified=False, plan_summary=f"Planning error: {e}")

            if allow_fallback:
                with self._stats_lock:
                    # P2-4 Fix: fallback_uses只在fallback路径计数，不与planning_errors重叠
                    self._stats["fallback_uses"] += 1
                # P2-3 Fix: 在fallback路径中使用捕获的omx_task_id
                error_reason = f"planning_error: {e}"
                self._omx_track("fallback_start", task=task, task_id=error_omx_task_id, reason=error_reason)
                fallback_plan = self._fallback_plan(task_id, task)
                self._omx_track("fallback_complete", task=task, task_id=error_omx_task_id, verified=False,
                                 plan_summary=f"Fallback plan: {len(fallback_plan.subtasks)} subtask(s)",
                                 reason=error_reason, subtask_count=len(fallback_plan.subtasks))
                return fallback_plan
            else:
                with self._stats_lock:
                    # P2-4 Fix: 只有在不允许fallback时才算真正的planning_errors
                    self._stats["planning_errors"] += 1
                raise

    def _decompose_and_match(self, task: str,
                                  precomputed_role_matches: List[Any] = None) -> Tuple[List[Subtask], List[Task], List[RoleMatch]]:
        """
        融合分解+匹配核心逻辑

        融合了：
        - RoleMatcher.match() 的4层fallback（固定团队→向量→claim→关键词）
        - TaskDecomposer.decompose_by_round() 的Round分解

        Args:
            task: 原始任务
            precomputed_role_matches: 预计算的角色匹配结果（避免重复调用role_matcher）

        Returns:
            (subtasks, tasks, role_matches)
        """
        # ── Step 1: 角色匹配（4层fallback来自RoleMatcher）──
        # P0-3 Fix: 如果外部已预计算，直接复用，避免重复调用
        if precomputed_role_matches is not None:
            role_matches = precomputed_role_matches
            logger.info(f"[FusionPlanner] Using precomputed {len(role_matches)} role_matches")
        else:
            role_matches = self.role_matcher.match(task)
            logger.info(f"[FusionPlanner] RoleMatcher returned {len(role_matches)} roles")

        for rm in role_matches:
            logger.info(f"  → {rm.role.get('name')} (source={rm.source}, sim={rm.similarity:.2f})")

        # ── Step 2: 获取角色列表 ──────────────────────────
        # TaskDecomposer.get_roles() 会再次调用RoleMatcher
        # 这里直接用已匹配的结果（避免重复调用）
        auto_roles = [m.role for m in role_matches]
        roles = self.task_decomposer.get_roles(task, auto_roles)

        # ── Step 3: 按Round分解任务 ─────────────────────
        round_tasks = self.task_decomposer.decompose_by_round(task, roles)

        # 展平为 Task 列表
        all_tasks: List[Task] = []
        for phase in ("round1", "round2", "round3"):
            all_tasks.extend(round_tasks.get(phase, []))

        # ── Step 4: 转换为 Subtask 格式（用于sessions_spawn）──
        subtasks = self._tasks_to_subtasks(all_tasks, role_matches)

        return subtasks, all_tasks, role_matches

    def _tasks_to_subtasks(
        self,
        tasks: List[Task],
        role_matches: List[RoleMatch],
    ) -> List[Subtask]:
        """
        将 Task 列表转换为 Subtask 列表

        Task（TaskDecomposer）→ Subtask（PlanEngine/sessions_spawn）
        """
        subtasks = []

        for i, task in enumerate(tasks):
            phase = task.phase  # round1/round2/round3
            role_from_meta = task.metadata.get("role", {})
            role_name = role_from_meta.get("name", task.metadata.get("role", {}).get("name", "Developer"))
            role_id = role_from_meta.get("id", "")

            # 优先级+阶段映射：按phase(round)分配合理timeout
            # round1=规划(300s), round2=执行(600s), round3=审查(180s)
            # 注意：phase实际存储的是round标识符(round1/round2/round3)，不是语义化的阶段名
            phase_timeout_map = {
                "round1": 300,
                "round2": 600,
                "round3": 180,
                "verification": 180,
            }
            timeout = phase_timeout_map.get(phase, 300)

            subtasks.append(Subtask(
                phase=phase,
                role=role_name,
                title=task.title,
                verify=task.verify,
                timeout=timeout,
                metadata={
                    "task_id": task.id,
                    "kind": task.kind,
                    "role_id": role_id,
                    "priority": task.priority,
                    "source": "task_decomposer",
                },
            ))

        # 如果没有任何subtask，添加默认
        if not subtasks:
            subtasks.append(Subtask(
                phase="round1",
                role="Developer",
                title=f"执行: {tasks[0].title if tasks else '任务'}",
                verify=["任务完成"],
                timeout=300,
                metadata={"source": "default"},
            ))

        return subtasks

    def _fallback_plan(self, task_id: str, task: str) -> FusionPlan:
        """降级规划：简单单阶段"""
        return FusionPlan(
            task_id=task_id,
            original_task=task,
            subtasks=[
                Subtask(
                    phase="round1",
                    role="Senior Developer",
                    title=f"[FALLBACK] {task[:80]}",
                    verify=["基本完成"],
                    timeout=300,
                    metadata={"source": "fallback"},
                )
            ],
            tasks=[],
            matched_roles=[],
            role_matches=[],  # FP-001 Fix: 空列表替代无效语法
            cache_hit=False,
            circuit_broken=True,
        )

    def _restore_fusion_plan(
        self,
        task_id: str,
        task: str,
        cached: Dict,
    ) -> FusionPlan:
        """从缓存恢复FusionPlan"""
        return FusionPlan(
            task_id=task_id,
            original_task=task,
            subtasks=[self._dict_to_subtask(s) for s in cached.get("subtasks", [])],
            tasks=[self._dict_to_task(t) for t in cached.get("tasks", [])],
            matched_roles=cached.get("matched_roles", []),
            role_matches=[],  # FP-001 Fix: 缓存不保留RoleMatch对象
            cache_hit=True,
        )

    def _fusion_plan_to_dict(self, plan: FusionPlan) -> Dict:
        """FusionPlan转dict（用于缓存）"""
        return {
            "subtasks": [self._subtask_to_dict(s) for s in plan.subtasks],
            "tasks": [self._task_to_dict(t) for t in plan.tasks],
            "matched_roles": plan.matched_roles,
        }

    def _subtask_to_dict(self, s: Subtask) -> Dict:
        return {
            "phase": s.phase,
            "role": s.role,
            "title": s.title,
            "verify": s.verify,
            "timeout": s.timeout,
            "metadata": s.metadata,
        }

    def _dict_to_subtask(self, d: Dict) -> Subtask:
        return Subtask(
            phase=d["phase"],
            role=d["role"],
            title=d["title"],
            verify=d.get("verify", []),
            timeout=d.get("timeout", 300),
            metadata=d.get("metadata", {}),
        )

    def _task_to_dict(self, t: Task) -> Dict:
        return {
            "id": t.id,
            "title": t.title,
            "kind": t.kind,
            "phase": t.phase,
            "priority": t.priority,
            "verify": t.verify,
            "metadata": t.metadata,
        }

    def _dict_to_task(self, d: Dict) -> Task:
        return Task(
            id=d["id"],
            title=d["title"],
            kind=d["kind"],
            phase=d["phase"],
            priority=d["priority"],
            verify=d.get("verify", []),
            metadata=d.get("metadata", {}),
        )

    def _generate_task_id(self, task: str) -> str:
        """生成任务ID"""
        return hashlib.sha256(task.encode()).hexdigest()[:12]

    # ── 兼容RoleMatcher的claim接口 ─────────────────────────

    def claim(self, task: str, role_id: str) -> None:
        """代理到RoleMatcher.claim"""
        self.role_matcher.claim(task, role_id)

    def release(self, task: str) -> None:
        """代理到RoleMatcher.release"""
        self.role_matcher.release(task)

    # ── 统计 ──────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._stats_lock:
            stats = dict(self._stats)
        stats["circuit_breaker"] = self.circuit_breaker.get_stats()
        stats["cache_size"] = len(self.fastpath._cache)
        return stats

    def record_execution_result(self, task_id: str, success: bool) -> None:
        """记录执行结果"""
        if success:
            self.circuit_breaker.record_success()
        else:
            self.circuit_breaker.record_failure()

    def _omx_track(self, event: str, **kwargs) -> Any:
        """
        OMX事件跟踪（仅当 use_omx=True 时生效）

        Events:
            round1_start:   规划开始，调用 on_round1_start
            round1_complete: 规划完成，调用 on_round1_complete
        """
        if not self.use_omx or self._omx_integrator is None:
            return None

        task = kwargs.get("task", "")
        task_id = kwargs.get("task_id")
        role_matches = kwargs.get("role_matches")
        verified = kwargs.get("verified", True)
        plan_summary = kwargs.get("plan_summary", "")

        try:
            if event == "round1_start":
                matched_roles = [m.role.get("name", "") for m in role_matches] if role_matches else None
                return self._omx_integrator.on_round1_start(
                    task_description=task,
                    task_id=task_id,
                    matched_roles=matched_roles,
                )
            elif event == "round1_complete":
                return self._omx_integrator.on_round1_complete(
                    plan_summary=plan_summary,
                    task_id=task_id,
                    verified=verified,
                )
            elif event == "fallback_start":
                return self._omx_integrator.on_fallback_start(
                    task_description=task,
                    task_id=task_id,
                    reason=kwargs.get("reason", "unknown"),
                )
            elif event == "fallback_complete":
                return self._omx_integrator.on_fallback_complete(
                    plan_summary=plan_summary,
                    task_id=task_id,
                    reason=kwargs.get("reason", "unknown"),
                    subtask_count=kwargs.get("subtask_count", 1),
                )
        except Exception as e:
            logger.warning(f"[FusionPlanner] OMX track failed for {event}: {e}")
        return None


# ── 便捷函数 ─────────────────────────────────────────────

def create_fusion_planner(
    workspace_root: str,
    cache_dir: Optional[str] = None,
) -> FusionPlanner:
    """创建FusionPlanner实例"""
    return FusionPlanner(workspace_root=workspace_root, cache_dir=cache_dir)


# ── 导出 ─────────────────────────────────────────────────

__all__ = [
    "FusionPlanner",
    "FusionPlan",
    "create_fusion_planner",
]
