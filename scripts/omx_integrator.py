"""
omx_integrator.py - OMX × sindris Round1-4 深度集成器

集成方案:
  Round1 (规划轮): omx_tasks 记录任务分解
  Round2 (执行轮): omx_ledger 记录执行日志
  Round3 (审查轮): omx_reviews 记录审查队列
  Round4 (完成):   omx_tasks 更新任务状态 + omx_ledger 记录完成

设计原则:
  1. 非侵入式: 不修改现有OMX模块，只调用其API
  2. 向后兼容: sindris流程可独立运行，不依赖OMX
  3. 幂等性: 重复调用安全，不重复创建
  4. 状态持久化: 所有状态变更立即写入磁盘

使用示例:
  from omx_integrator import OMXIntegrator, get_integrator

  integrator = OMXIntegrator(workspace_root="/path/to/workspace")
  integrator.on_round1_start(task_description="...")
  ...
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from omx_contract import (
    omx_dir, ensure_omx_layout, read_json, write_json,
    get_workspace_root, set_workspace_root,
    tasks_file, ledger_file, reviews_file,
)
from omx_ledger import (
    LedgerEntry, LedgerKind,
    append_ledger, load_ledger, save_ledger,
    push_inbox_item, load_inbox,
)
from omx_tasks import (
    Task, TaskStatus, CreateTaskInput,
    create_task, get_task, update_task, transition_task,
    load_tasks, save_tasks,
)
from omx_reviews import (
    ReviewItem, ReviewStatus,
    create_review, get_review, update_review, submit_review_result,
    list_reviews, is_task_approved,
)

# ============================================================
# 类型定义
# ============================================================

@dataclass
class RoundPhase:
    """Round阶段记录"""
    round: int           # 1, 2, 3, 4
    phase: str            # "planning" | "execution" | "review" | "completion"
    status: str           # "start" | "complete" | "failed"
    task_description: Optional[str] = None
    output: Optional[Dict] = None
    error: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class ActionRecord:
    """动作执行记录"""
    action_id: str
    action_name: str
    agent_id: str
    role: str
    status: str              # "pending" | "running" | "completed" | "failed"
    verify_checks: List[str] = field(default_factory=list)
    verify_results: Dict[str, bool] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

# ============================================================
# 内部函数
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()

def _gen_id(prefix: str = "rec") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def _workspace_phase_file(root: str) -> str:
    """Round阶段文件: .omx/state/sindris_phases.json"""
    from omx_contract import omx_path
    return omx_path(root, "state", "sindris_phases.json")

def _workspace_actions_file(root: str) -> str:
    """动作记录文件: .omx/state/sindris_actions.json"""
    from omx_contract import omx_path
    return omx_path(root, "state", "sindris_actions.json")

# ============================================================
# OMXIntegrator 主体
# ============================================================

class OMXIntegrator:
    """
    OMX × sindris Round1-4 深度集成器

    使用方法:
        integrator = OMXIntegrator(workspace_root="/path/to/root")
        integrator.on_round1_start(task_description="...")
        # ... 规划角色匹配后 ...
        integrator.on_round1_complete(matched_roles=[...], plan_summary="...")
    """

    def __init__(self, workspace_root: Optional[str] = None):
        """
        初始化集成器

        Args:
            workspace_root: 工作区根目录，默认使用OMX的默认工作区
        """
        if workspace_root is None:
            workspace_root = get_workspace_root()

        self.root = workspace_root
        self._session_id = _gen_id("session")
        self._last_task_id: Optional[str] = None  # 最近创建的task_id
        self._phases: List[RoundPhase] = []
        self._actions: List[ActionRecord] = []

    @property
    def last_task_id(self) -> Optional[str]:
        """最近一次on_round1_start创建的task_id（用于传递给on_round1_complete）"""
        return self._last_task_id

        # 初始化OMX布局
        ensure_omx_layout(self.root)

    # --------------------- 工具方法 ---------------------

    def _load_phases(self) -> List[RoundPhase]:
        """从磁盘加载阶段记录"""
        data = read_json(_workspace_phase_file(self.root), [])
        return [RoundPhase(**d) for d in data]

    def _save_phases(self) -> None:
        """保存阶段记录到磁盘"""
        write_json(_workspace_phase_file(self.root), [p.to_dict() for p in self._phases])

    def _load_actions(self) -> List[ActionRecord]:
        """从磁盘加载动作记录"""
        data = read_json(_workspace_actions_file(self.root), [])
        return [ActionRecord(**d) for d in data]

    def _save_actions(self) -> None:
        """保存动作记录到磁盘"""
        write_json(_workspace_actions_file(self.root), [a.to_dict() for a in self._actions])

    def _ledger(self, kind: LedgerKind, action: str, detail: str, **kwargs) -> LedgerEntry:
        """快捷ledger写入"""
        return append_ledger(self.root, kind, action, detail, **kwargs)

    # --------------------- Round1: 规划轮 ---------------------

    def on_round1_start(
        self,
        task_description: str,
        task_id: Optional[str] = None,
        matched_roles: Optional[List[str]] = None,
    ) -> str:
        """
        Round1 开始

        Args:
            task_description: 任务描述
            task_id: 可选的任务ID（用于关联OMX任务）
            matched_roles: 匹配的角色列表

        Returns:
            session_id 用于追踪
        """
        # 创建或关联OMX任务
        if task_id:
            task = get_task(self.root, task_id)
        else:
            task_input = CreateTaskInput(
                title=task_description[:100],
                kind="sindris_planning",
                phase="round1",
                priority="high",
                metadata={
                    "session_id": self._session_id,
                    "matched_roles": matched_roles or [],
                }
            )
            task = create_task(self.root, task_input)
            task_id = task.id

        # 追踪最近创建的task_id（供外部获取）
        self._last_task_id = task_id

        # 记录phase
        phase = RoundPhase(
            round=1,
            phase="planning",
            status="start",
            task_description=task_description,
            output={"task_id": task_id, "matched_roles": matched_roles or []},
            started_at=_now(),
        )
        self._phases.append(phase)
        self._save_phases()

        # Ledger记录
        self._ledger(
            "session", "round1_start",
            f"Sindri's Round1 started: {task_description[:80]}",
            task_id=task_id,
            metadata={
                "session_id": self._session_id,
                "matched_roles": matched_roles or [],
                "task_id": task_id,
            }
        )

        return self._session_id  # 返回session_id（backward compatible）

    def on_round1_complete(
        self,
        plan_summary: str,
        task_id: Optional[str] = None,
        verified: bool = True,
        verification_notes: Optional[List[str]] = None,
    ) -> Optional[Task]:
        """
        Round1 完成

        Args:
            plan_summary: 规划摘要
            task_id: OMX任务ID（可选，如果不提供则从phase output自动获取）
            verified: 是否通过验收
            verification_notes: 验收备注

        Returns:
            更新后的Task或None
        """
        # 找到对应的phase
        phase_task_id = None
        for phase in reversed(self._phases):
            if phase.round == 1 and phase.status == "start":
                phase.status = "complete" if verified else "failed"
                phase.completed_at = _now()
                phase.output = phase.output or {}
                phase.output["plan_summary"] = plan_summary
                phase.output["verified"] = verified
                self._save_phases()
                # 始终从phase output获取task_id（传入的task_id可能是错的类型，如session_id）
                phase_task_id = phase.output.get("task_id")
                break

        # 更新/创建OMX任务
        task = None
        if phase_task_id:
            task = get_task(self.root, phase_task_id)
            if task:
                update_task(self.root, phase_task_id, {
                    "status": "completed" if verified else "failed",
                    "notes": task.notes + [f"Round1: {plan_summary}"],
                    "metadata": {
                        **task.metadata,
                        "round1_verified": verified,
                        "verification_notes": verification_notes or [],
                    }
                })
                transition_task(self.root, phase_task_id, "completed" if verified else "failed")
                # 重新获取以返回最新状态
                task = get_task(self.root, phase_task_id)
        elif plan_summary:
            # 无task_id时创建一个（仅作为后备）
            task_input = CreateTaskInput(
                title=f"Round1 Plan: {plan_summary[:80]}",
                kind="sindris_plan",
                phase="round1",
                priority="high",
                notes=[plan_summary],
                metadata={"round1_verified": verified},
            )
            task = create_task(self.root, task_input)

        # Ledger记录
        self._ledger(
            "session", "round1_complete",
            f"Sindri's Round1 completed: {plan_summary[:80]}",
            task_id=phase_task_id or (task.id if task else None),
            metadata={
                "session_id": self._session_id,
                "verified": verified,
                "plan_summary": plan_summary[:200],
            }
        )

        return task

    # --------------------- Round2: 执行轮 ---------------------

    def on_round2_start(
        self,
        task_id: Optional[str] = None,
        actions: Optional[List[Dict]] = None,
    ) -> str:
        """
        Round2 开始

        Args:
            task_id: 关联的OMX任务ID
            actions: 动作计划列表 [{"action_id": "...", "action_name": "...", "agent_id": "...", "role": "..."}]

        Returns:
            phase_id
        """
        phase = RoundPhase(
            round=2,
            phase="execution",
            status="start",
            task_description=task_id,
            output={"actions": actions or []},
            started_at=_now(),
        )
        self._phases.append(phase)
        self._save_phases()

        # 创建动作记录
        for a in (actions or []):
            action_rec = ActionRecord(
                action_id=a.get("action_id", _gen_id("action")),
                action_name=a.get("action_name", ""),
                agent_id=a.get("agent_id", ""),
                role=a.get("role", ""),
                status="pending",
                started_at=_now(),
            )
            self._actions.append(action_rec)
        self._save_actions()

        # Ledger记录
        self._ledger(
            "session", "round2_start",
            f"Sindri's Round2 started with {len(actions or [])} actions",
            task_id=task_id,
            metadata={
                "session_id": self._session_id,
                "action_count": len(actions or []),
            }
        )

        return self._session_id

    def on_action_start(
        self,
        action_id: str,
        agent_id: Optional[str] = None,
    ) -> Optional[ActionRecord]:
        """
        动作开始执行

        Args:
            action_id: 动作ID
            agent_id: 执行的agent ID

        Returns:
            ActionRecord或None
        """
        for action in self._actions:
            if action.action_id == action_id:
                action.status = "running"
                action.started_at = _now()
                if agent_id:
                    action.agent_id = agent_id
                self._save_actions()

                self._ledger(
                    "task", "action_start",
                    f"Action {action_id} started by {agent_id}",
                    metadata={
                        "session_id": self._session_id,
                        "action_id": action_id,
                        "agent_id": agent_id,
                    }
                )
                return action

        # 未找到，创建一个新的
        action_rec = ActionRecord(
            action_id=action_id,
            action_name=action_id,
            agent_id=agent_id or "",
            role="",
            status="running",
        )
        self._actions.append(action_rec)
        self._save_actions()
        return action_rec

    def on_action_complete(
        self,
        action_id: str,
        verified: bool,
        verify_results: Optional[Dict[str, bool]] = None,
        error: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Optional[ActionRecord]:
        """
        动作执行完成

        Args:
            action_id: 动作ID
            verified: 是否通过验收
            verify_results: 验收检查项结果
            error: 错误信息（如果有）
            task_id: 关联的任务ID

        Returns:
            更新后的ActionRecord或None
        """
        for action in self._actions:
            if action.action_id == action_id:
                action.status = "completed" if verified else "failed"
                action.completed_at = _now()
                action.verify_results = verify_results or {}
                if error:
                    action.error = error
                self._save_actions()

                self._ledger(
                    "task", "action_complete",
                    f"Action {action_id} {'verified' if verified else 'failed'}",
                    task_id=task_id,
                    metadata={
                        "session_id": self._session_id,
                        "action_id": action_id,
                        "verified": verified,
                        "verify_results": verify_results or {},
                    }
                )
                return action

        return None

    def on_round2_complete(
        self,
        task_id: Optional[str] = None,
        all_verified: bool = True,
        failed_actions: Optional[List[str]] = None,
    ) -> None:
        """
        Round2 完成

        Args:
            task_id: 关联的OMX任务ID
            all_verified: 所有动作是否都通过验收
            failed_actions: 失败的动作ID列表
        """
        # 更新phase
        for phase in reversed(self._phases):
            if phase.round == 2 and phase.status == "start":
                phase.status = "complete" if all_verified else "failed"
                phase.completed_at = _now()
                phase.output = phase.output or {}
                phase.output["all_verified"] = all_verified
                phase.output["failed_actions"] = failed_actions or []
                self._save_phases()
                break

        # Ledger记录
        self._ledger(
            "session", "round2_complete",
            f"Sindri's Round2 {'completed' if all_verified else 'failed'}",
            task_id=task_id,
            metadata={
                "session_id": self._session_id,
                "all_verified": all_verified,
                "failed_actions": failed_actions or [],
                "total_actions": len(self._actions),
            }
        )

        # 如果有任务，更新状态
        if task_id and all_verified:
            transition_task(self.root, task_id, "completed")

    # --------------------- Round3: 审查轮 ---------------------

    def on_round3_start(
        self,
        task_id: Optional[str] = None,
        review_items: Optional[List[Dict]] = None,
    ) -> List[ReviewItem]:
        """
        Round3 开始，创建审查队列

        Args:
            task_id: 关联的OMX任务ID
            review_items: 审查项列表 [{"task_id": "...", "reviewer": "...", "summary": "..."}]

        Returns:
            创建的ReviewItem列表
        """
        phase = RoundPhase(
            round=3,
            phase="review",
            status="start",
            task_description=task_id,
            output={"review_items": review_items or []},
            started_at=_now(),
        )
        self._phases.append(phase)
        self._save_phases()

        reviews = []
        for item in (review_items or []):
            review = create_review(
                self.root,
                task_id=item.get("task_id", item.get("action_id", "")),
                reviewer=item.get("reviewer", "Reviewer"),
                summary=item.get("summary", ""),
            )
            reviews.append(review)

        # Ledger记录
        self._ledger(
            "review", "round3_start",
            f"Sindri's Round3 started with {len(reviews)} reviews",
            task_id=task_id,
            metadata={
                "session_id": self._session_id,
                "review_count": len(reviews),
            }
        )

        return reviews

    def on_review_submit(
        self,
        review_id: str,
        status: ReviewStatus,
        summary: str = "",
        notes: Optional[List[str]] = None,
    ) -> Optional[ReviewItem]:
        """
        提交审查结果

        Args:
            review_id: 审查ID
            status: 审查结果 ("approved" | "changes_requested")
            summary: 审查摘要
            notes: 审查备注

        Returns:
            更新后的ReviewItem或None
        """
        review = submit_review_result(
            self.root,
            review_id=review_id,
            status=status,
            summary=summary,
            notes=notes or [],
        )

        if review:
            self._ledger(
                "review", f"review_{status}",
                f"Review {review_id} {status}",
                task_id=review.task_id,
                metadata={
                    "session_id": self._session_id,
                    "review_id": review_id,
                    "status": status,
                }
            )

        return review

    def on_round3_complete(
        self,
        task_id: Optional[str] = None,
        all_approved: bool = True,
    ) -> None:
        """
        Round3 完成

        Args:
            task_id: 关联的OMX任务ID
            all_approved: 是否全部通过审查
        """
        # 更新phase
        for phase in reversed(self._phases):
            if phase.round == 3 and phase.status == "start":
                phase.status = "complete" if all_approved else "failed"
                phase.completed_at = _now()
                phase.output = phase.output or {}
                phase.output["all_approved"] = all_approved
                self._save_phases()
                break

        # Ledger记录
        self._ledger(
            "review", "round3_complete",
            f"Sindri's Round3 {'completed' if all_approved else 'failed'}",
            task_id=task_id,
            metadata={
                "session_id": self._session_id,
                "all_approved": all_approved,
            }
        )

    # --------------------- Round4: 完成 ---------------------

    def on_round4_complete(
        self,
        task_id: Optional[str] = None,
        final_output: Optional[Dict] = None,
        success: bool = True,
    ) -> None:
        """
        Round4 完成，最终交付

        Args:
            task_id: 关联的OMX任务ID
            final_output: 最终输出摘要
            success: 是否成功完成
        """
        # 更新phase
        phase = RoundPhase(
            round=4,
            phase="completion",
            status="complete" if success else "failed",
            task_description=task_id,
            output=final_output or {},
            started_at=_now(),
            completed_at=_now(),
        )
        self._phases.append(phase)
        self._save_phases()

        # 更新任务状态
        if task_id:
            final_status: TaskStatus = "completed" if success else "failed"
            transition_task(self.root, task_id, final_status)
            update_task(self.root, task_id, {
                "result": str(final_output or {}),
                "metadata": {
                    "round4_completed": True,
                    "session_id": self._session_id,
                }
            })

        # Ledger记录
        self._ledger(
            "session", "session_end",
            f"Sindri's session {self._session_id} {'completed' if success else 'failed'}",
            task_id=task_id,
            metadata={
                "session_id": self._session_id,
                "success": success,
                "final_output": final_output or {},
                "total_phases": len(self._phases),
                "total_actions": len(self._actions),
            }
        )

    # --------------------- 查询方法 ---------------------

    def get_session_summary(self) -> Dict[str, Any]:
        """获取会话摘要"""
        return {
            "session_id": self._session_id,
            "root": self.root,
            "phases": [p.to_dict() for p in self._phases],
            "actions": [a.to_dict() for a in self._actions],
            "omx_summary": {
                "tasks": len(load_tasks(self.root)),
                "ledger_entries": len(load_ledger(self.root)),
                "pending_reviews": len(list_reviews(self.root, status="pending")),
            }
        }

    def get_pending_reviews(self) -> List[ReviewItem]:
        """获取待审查列表"""
        return list_reviews(self.root, status="pending")

    def get_failed_actions(self) -> List[ActionRecord]:
        """获取失败的动作列表"""
        return [a for a in self._actions if a.status == "failed"]

    def is_task_approved(self, task_id: str) -> bool:
        """检查任务是否通过审查"""
        return is_task_approved(self.root, task_id)

    def resume_session(self) -> bool:
        """
        从磁盘恢复会话状态

        Returns:
            是否成功恢复
        """
        try:
            self._phases = self._load_phases()
            self._actions = self._load_actions()
            return True
        except Exception:
            return False

    def get_task_id_for_round(self, round_num: int) -> Optional[str]:
        """获取指定Round关联的任务ID"""
        for phase in self._phases:
            if phase.round == round_num and phase.output:
                return phase.output.get("task_id")
        return None


# ============================================================
# 全局便捷函数
# ============================================================

_default_integrator: Optional[OMXIntegrator] = None

def get_integrator(workspace_root: Optional[str] = None) -> OMXIntegrator:
    """
    获取全局OMXIntegrator实例（单例）

    Args:
        workspace_root: 可选的workspace根目录

    Returns:
        OMXIntegrator实例
    """
    global _default_integrator
    if _default_integrator is None:
        _default_integrator = OMXIntegrator(workspace_root)
    return _default_integrator

def reset_integrator() -> None:
    """重置全局实例"""
    global _default_integrator
    _default_integrator = None
