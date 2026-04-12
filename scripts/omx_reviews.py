"""
omx_reviews.py - OMX审查队列系统

基于 oh-my-codex reviews.ts 移植
功能: 独立审查队列替代sindris的简陋共识投票

审查流程:
  1. Executor完成切片 → 创建ReviewItem
  2. Reviewer领取审查 → review_status=pending
  3. 审查通过 → review_status=approved
  4. 需修改 → review_status=changes_requested + notes

与sindris共识投票的区别:
  - 共识投票: 所有角色都同意才算过
  - 审查队列: 专门的Reviewer角色负责，有明确审查标准
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from omx_contract import (
    reviews_file, ensure_omx_layout, read_json, write_json, get_workspace_root
)
from omx_ledger import append_ledger

# ============================================================
# 类型定义
# ============================================================

ReviewStatus = str  # "pending" | "approved" | "changes_requested"

@dataclass
class ReviewItem:
    """审查条目"""
    id: str
    task_id: str
    reviewer: str
    status: ReviewStatus
    summary: str
    notes: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    approved_at: Optional[str] = None
    changes_requested_at: Optional[str] = None

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'ReviewItem':
        return ReviewItem(**d)

@dataclass
class ReviewResult:
    """审查结果"""
    review_id: str
    task_id: str
    status: ReviewStatus
    summary: str
    notes: List[str]
    approved_at: Optional[str] = None
    changes_requested_at: Optional[str] = None

# ============================================================
# 内部函数
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()

def _gen_id(prefix: str = "review") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

# ============================================================
# Review操作
# ============================================================

def load_reviews(root: str) -> List[ReviewItem]:
    """加载所有review"""
    ensure_omx_layout(root)
    data = read_json(reviews_file(root), [])
    return [ReviewItem.from_dict(d) for d in data]

def save_reviews(root: str, reviews: List[ReviewItem]) -> None:
    """保存所有review"""
    ensure_omx_layout(root)
    write_json(reviews_file(root), [r.to_dict() for r in reviews])

def create_review(
    root: str,
    task_id: str,
    reviewer: str,
    summary: str = "",
) -> ReviewItem:
    """
    创建审查条目
    
    Args:
        root: 工作区根目录
        task_id: 关联的任务ID
        reviewer: 审查者角色/用户
        summary: 审查摘要
    
    Returns:
        新创建的ReviewItem
    """
    review = ReviewItem(
        id=_gen_id("review"),
        task_id=task_id,
        reviewer=reviewer,
        status="pending",
        summary=summary,
        notes=[],
        created_at=_now(),
        updated_at=_now(),
    )
    reviews = load_reviews(root)
    reviews.append(review)
    save_reviews(root, reviews)
    
    # 记录到ledger
    append_ledger(root, "review", "review_created",
                  f"Review created for task {task_id} by {reviewer}",
                  task_id=task_id,
                  metadata={"reviewer": reviewer, "review_id": review.id})
    
    return review

def get_review(root: str, review_id: str) -> Optional[ReviewItem]:
    """获取指定review"""
    reviews = load_reviews(root)
    for r in reviews:
        if r.id == review_id:
            return r
    return None

def update_review(
    root: str,
    review_id: str,
    patch: Dict[str, Any],
) -> Optional[ReviewItem]:
    """更新review字段"""
    reviews = load_reviews(root)
    for review in reviews:
        if review.id == review_id:
            for key, value in patch.items():
                if hasattr(review, key):
                    setattr(review, key, value)
            review.updated_at = _now()
            save_reviews(root, reviews)
            return review
    return None

def submit_review_result(
    root: str,
    review_id: str,
    status: ReviewStatus,
    summary: str = "",
    notes: Optional[List[str]] = None,
) -> Optional[ReviewItem]:
    """
    提交审查结果
    
    Args:
        root: 工作区根目录
        review_id: Review ID
        status: 审查结果 ("approved" | "changes_requested")
        summary: 审查摘要
        notes: 审查备注
    
    Returns:
        更新后的ReviewItem或None
    """
    review = get_review(root, review_id)
    if not review:
        return None
    
    now = _now()
    patch: Dict[str, Any] = {
        "status": status,
        "summary": summary,
        "notes": notes or [],
        "updated_at": now,
    }
    
    if status == "approved":
        patch["approved_at"] = now
    elif status == "changes_requested":
        patch["changes_requested_at"] = now
    
    updated = update_review(root, review_id, patch)
    
    # 记录到ledger
    append_ledger(root, "review", f"review_{status}",
                  f"Review {review_id} {status}: {summary}",
                  task_id=review.task_id,
                  metadata={"status": status, "reviewer": review.reviewer})
    
    return updated

def list_reviews(
    root: str,
    status: Optional[ReviewStatus] = None,
    reviewer: Optional[str] = None,
    task_id: Optional[str] = None,
) -> List[ReviewItem]:
    """列出reviews，支持多条件过滤"""
    reviews = load_reviews(root)
    if status:
        reviews = [r for r in reviews if r.status == status]
    if reviewer:
        reviews = [r for r in reviews if r.reviewer == reviewer]
    if task_id:
        reviews = [r for r in reviews if r.task_id == task_id]
    return reviews

def get_reviews_for_task(root: str, task_id: str) -> List[ReviewItem]:
    """获取任务的所有审查"""
    return list_reviews(root, task_id=task_id)

def is_task_approved(root: str, task_id: str) -> bool:
    """检查任务是否已通过审查"""
    reviews = get_reviews_for_task(root, task_id)
    if not reviews:
        return False
    # 任务通过审查: 至少有一个approved，且没有pending/changes_requested
    has_approved = any(r.status == "approved" for r in reviews)
    has_pending = any(r.status == "pending" for r in reviews)
    has_changes = any(r.status == "changes_requested" for r in reviews)
    return has_approved and not has_pending and not has_changes

def get_review_summary(root: str) -> Dict[str, Any]:
    """获取审查统计摘要"""
    reviews = load_reviews(root)
    
    status_counts: Dict[ReviewStatus, int] = {"pending": 0, "approved": 0, "changes_requested": 0}
    for r in reviews:
        if r.status in status_counts:
            status_counts[r.status] += 1
    
    return {
        "total": len(reviews),
        "by_status": status_counts,
        "pending_reviews": [r.to_dict() for r in reviews if r.status == "pending"],
        "recent_approved": [r.to_dict() for r in reviews if r.status == "approved"][-10:],
    }

# ============================================================
# 便捷函数（使用默认工作区）
# ============================================================

def create_review_default(task_id: str, reviewer: str, summary: str = "") -> ReviewItem:
    """使用默认工作区创建审查"""
    return create_review(get_workspace_root(), task_id, reviewer, summary)

def submit_review_result_default(review_id: str, status: ReviewStatus, **kwargs) -> Optional[ReviewItem]:
    """使用默认工作区提交审查结果"""
    return submit_review_result(get_workspace_root(), review_id, status, **kwargs)

def list_reviews_default(**kwargs) -> List[ReviewItem]:
    """使用默认工作区列出审查"""
    return list_reviews(get_workspace_root(), **kwargs)

def is_task_approved_default(task_id: str) -> bool:
    """使用默认工作区检查任务是否通过审查"""
    return is_task_approved(get_workspace_root(), task_id)

def get_review_summary_default() -> Dict[str, Any]:
    """使用默认工作区获取审查统计"""
    return get_review_summary(get_workspace_root())

# ============================================================
# 与sindris集成的便捷函数
# ============================================================

def create_action_review(
    root: str,
    action_id: str,
    action_name: str,
    reviewer: str = "Reviewer",
) -> ReviewItem:
    """
    为sindris的动作创建审查
    
    这是将审查队列与sindris集成的关键函数
    """
    return create_review(root, action_id, reviewer, f"Review for action: {action_name}")

def approve_action(
    root: str,
    action_id: str,
    notes: Optional[List[str]] = None,
) -> Optional[ReviewItem]:
    """批准sindris动作"""
    reviews = list_reviews(root, task_id=action_id)
    for r in reviews:
        if r.status == "pending":
            return submit_review_result(root, r.id, "approved", 
                                       f"Action {action_id} approved", 
                                       notes or [])
    return None

def request_changes_for_action(
    root: str,
    action_id: str,
    change_notes: List[str],
) -> Optional[ReviewItem]:
    """要求sindris动作修改"""
    reviews = list_reviews(root, task_id=action_id)
    for r in reviews:
        if r.status == "pending":
            return submit_review_result(root, r.id, "changes_requested",
                                       f"Changes requested for {action_id}",
                                       change_notes)
    return None
