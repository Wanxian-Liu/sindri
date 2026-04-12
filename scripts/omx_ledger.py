"""
omx_ledger.py - OMX执行日志（Ledger）

基于 oh-my-codex runtime.ts ledger部分 移植
负责: 持久化执行日志、inbox、reviews的状态管理

OMX LedgerEntry类型:
- task: 任务相关操作
- worker: Worker相关操作
- review: 审查相关操作
- session: 会话相关操作
- plugin: 插件相关操作
- hook: Hook相关操作
- setup: 设置相关操作
"""

import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from omx_contract import (
    ledger_file, inbox_file, reviews_file,
    ensure_omx_layout, read_json, write_json, get_workspace_root
)

# ============================================================
# 类型定义
# ============================================================

LedgerKind = str  # "task" | "worker" | "review" | "session" | "plugin" | "hook" | "setup"
InboxKind = str   # "inbox" | "review" | "system" | "plugin" | "hook"
InboxStatus = str # "open" | "acknowledged" | "resolved"
ReviewStatus = str # "pending" | "approved" | "changes_requested"

@dataclass
class LedgerEntry:
    """执行日志条目"""
    id: str
    kind: LedgerKind
    action: str
    detail: str
    actor: Optional[str] = None
    task_id: Optional[str] = None
    worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=str)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'LedgerEntry':
        return LedgerEntry(**d)

@dataclass
class InboxItem:
    """消息箱条目"""
    id: str
    kind: InboxKind
    subject: str
    body: str
    from_: Optional[str] = field(default=None, metadata={"json": "from"})
    to: Optional[str] = None
    task_id: Optional[str] = None
    status: InboxStatus = "open"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        d = asdict(self)
        d["from"] = d.pop("from_", None)
        return d

    @staticmethod
    def from_dict(d: dict) -> 'InboxItem':
        if "from" in d:
            d["from_"] = d.pop("from")
        return InboxItem(**d)

@dataclass
class ReviewItem:
    """审查队列条目"""
    id: str
    task_id: str
    reviewer: str
    status: ReviewStatus = "pending"
    summary: str = ""
    notes: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

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

# ============================================================
# Ledger操作
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()

def _gen_id(prefix: str = "ledger") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def load_ledger(root: str) -> List[LedgerEntry]:
    """加载所有ledger条目"""
    ensure_omx_layout(root)
    data = read_json(ledger_file(root), [])
    return [LedgerEntry.from_dict(d) for d in data]

def save_ledger(root: str, entries: List[LedgerEntry]) -> None:
    """保存所有ledger条目"""
    ensure_omx_layout(root)
    write_json(ledger_file(root), [e.to_dict() for e in entries])

def list_ledger(root: str, limit: int = 50) -> List[LedgerEntry]:
    """获取最近N条ledger记录"""
    entries = load_ledger(root)
    return entries[-limit:] if limit > 0 else entries

def append_ledger(
    root: str,
    kind: LedgerKind,
    action: str,
    detail: str,
    actor: Optional[str] = None,
    task_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LedgerEntry:
    """
    追加一条ledger记录
    
    Returns:
        新创建的LedgerEntry
    """
    entry = LedgerEntry(
        id=_gen_id("ledger"),
        kind=kind,
        action=action,
        detail=detail,
        actor=actor,
        task_id=task_id,
        worker_id=worker_id,
        metadata=metadata or {},
        created_at=_now(),
    )
    entries = load_ledger(root)
    entries.append(entry)
    save_ledger(root, entries)
    return entry

# ============================================================
# Inbox操作
# ============================================================

def load_inbox(root: str) -> List[InboxItem]:
    """加载inbox条目"""
    ensure_omx_layout(root)
    data = read_json(inbox_file(root), [])
    return [InboxItem.from_dict(d) for d in data]

def save_inbox(root: str, items: List[InboxItem]) -> None:
    """保存inbox条目"""
    ensure_omx_layout(root)
    write_json(inbox_file(root), [i.to_dict() for i in items])

def list_inbox(root: str, status: Optional[InboxStatus] = None) -> List[InboxItem]:
    """列出inbox，可按status过滤"""
    items = load_inbox(root)
    if status:
        items = [i for i in items if i.status == status]
    return items

def push_inbox_item(
    root: str,
    kind: InboxKind,
    subject: str,
    body: str,
    from_: Optional[str] = None,
    to: Optional[str] = None,
    task_id: Optional[str] = None,
    status: InboxStatus = "open",
) -> InboxItem:
    """
    添加一条inbox消息
    
    Returns:
        新创建的InboxItem
    """
    item = InboxItem(
        id=_gen_id("inbox"),
        kind=kind,
        subject=subject,
        body=body,
        from_=from_,
        to=to,
        task_id=task_id,
        status=status,
        created_at=_now(),
        updated_at=_now(),
    )
    items = load_inbox(root)
    items.append(item)
    save_inbox(root, items)
    return item

def update_inbox_item(
    root: str,
    item_id: str,
    patch: Dict[str, Any],
) -> Optional[InboxItem]:
    """更新inbox条目"""
    items = load_inbox(root)
    for item in items:
        if item.id == item_id:
            for key, value in patch.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            item.updated_at = _now()
            save_inbox(root, items)
            return item
    return None

# ============================================================
# Reviews操作
# ============================================================

def load_reviews(root: str) -> List[ReviewItem]:
    """加载review条目"""
    ensure_omx_layout(root)
    data = read_json(reviews_file(root), [])
    return [ReviewItem.from_dict(d) for d in data]

def save_reviews(root: str, items: List[ReviewItem]) -> None:
    """保存review条目"""
    ensure_omx_layout(root)
    write_json(reviews_file(root), [r.to_dict() for r in items])

def list_reviews(root: str, status: Optional[ReviewStatus] = None) -> List[ReviewItem]:
    """列出reviews，可按status过滤"""
    items = load_reviews(root)
    if status:
        items = [i for i in items if i.status == status]
    return items

def create_review(
    root: str,
    task_id: str,
    reviewer: str,
    summary: str = "",
    notes: Optional[List[str]] = None,
) -> ReviewItem:
    """
    创建审查条目
    
    Returns:
        新创建的ReviewItem
    """
    review = ReviewItem(
        id=_gen_id("review"),
        task_id=task_id,
        reviewer=reviewer,
        status="pending",
        summary=summary,
        notes=notes or [],
        created_at=_now(),
        updated_at=_now(),
    )
    items = load_reviews(root)
    items.append(review)
    save_reviews(root, items)
    
    # 同时记录到ledger
    append_ledger(root, "review", "review_created", f"Review for task {task_id}", 
                  task_id=task_id, metadata={"reviewer": reviewer})
    
    return review

def update_review(
    root: str,
    review_id: str,
    status: Optional[ReviewStatus] = None,
    summary: Optional[str] = None,
    notes: Optional[List[str]] = None,
) -> Optional[ReviewItem]:
    """更新review条目"""
    items = load_reviews(root)
    for item in items:
        if item.id == review_id:
            if status is not None:
                item.status = status
            if summary is not None:
                item.summary = summary
            if notes is not None:
                item.notes = notes
            item.updated_at = _now()
            save_reviews(root, items)
            
            # 记录到ledger
            append_ledger(root, "review", f"review_{status or 'updated'}", 
                         f"Review {review_id} updated", task_id=item.task_id,
                         metadata={"status": status, "summary": summary})
            return item
    return None

# ============================================================
# 便捷函数（使用默认工作区）
# ============================================================

def append_ledger_default(kind: LedgerKind, action: str, detail: str, **kwargs) -> LedgerEntry:
    """使用默认工作区追加ledger"""
    return append_ledger(get_workspace_root(), kind, action, detail, **kwargs)

def push_inbox_default(kind: InboxKind, subject: str, body: str, **kwargs) -> InboxItem:
    """使用默认工作区添加inbox"""
    return push_inbox_item(get_workspace_root(), kind, subject, body, **kwargs)

def create_review_default(task_id: str, reviewer: str, summary: str = "", **kwargs) -> ReviewItem:
    """使用默认工作区创建review"""
    return create_review(get_workspace_root(), task_id, reviewer, summary, **kwargs)

def get_ledger_summary(limit: int = 20) -> Dict[str, Any]:
    """获取ledger摘要统计"""
    root = get_workspace_root()
    entries = load_ledger(root)
    
    # 按kind统计
    kind_counts: Dict[str, int] = {}
    for e in entries:
        kind_counts[e.kind] = kind_counts.get(e.kind, 0) + 1
    
    return {
        "total": len(entries),
        "by_kind": kind_counts,
        "recent": [e.to_dict() for e in entries[-limit:]] if entries else [],
        "first_entry": entries[0].created_at if entries else None,
        "last_entry": entries[-1].created_at if entries else None,
    }
