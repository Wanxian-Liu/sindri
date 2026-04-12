"""
omx_tasks.py - OMX任务图系统

基于 oh-my-codex tasks.ts 移植
负责: 任务状态机、创建、更新、依赖管理

任务状态流转:
  pending → queued → in_progress → review → completed
                ↓           ↓
            blocked      failed → 可重试回 queued
"""

import uuid
import fcntl
import os
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from omx_contract import (
    tasks_file, ensure_omx_layout, read_json, write_json, get_workspace_root, omx_dir
)

# 进程内线程锁（保护 tasks.json 的读改写原子性）
_task_lock = threading.RLock()

def _update_task_locked(root, task_id, patch):
    """真正的update逻辑（调用者必须已持有_task_lock）"""
    tasks = load_tasks(root)
    for task in tasks:
        if task.id == task_id:
            for key, value in patch.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = _now()
            save_tasks(root, tasks)
            return task
    return None

def _get_task_locked(root, task_id):
    """真正的get逻辑（调用者必须已持有_task_lock）"""
    tasks = load_tasks(root)
    for t in tasks:
        if t.id == task_id:
            return t
    return None

# ============================================================
# 类型定义
# ============================================================

TaskStatus = str  # "pending" | "queued" | "in_progress" | "blocked" | "review" | "completed" | "cancelled" | "failed"
TaskPriority = str # "low" | "medium" | "high"

@dataclass
class TaskEvent:
    """任务历史事件"""
    status: TaskStatus
    at: str
    by: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'TaskEvent':
        return TaskEvent(**d)

@dataclass
class Task:
    """任务"""
    id: str
    title: str
    kind: str
    phase: str
    status: TaskStatus
    priority: TaskPriority
    owner: Optional[str] = None
    verify: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    review_status: str = "none"  # "none" | "pending" | "approved" | "changes_requested"
    claimed_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    history: List[Dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        # 确保history是dict列表
        if self.history and isinstance(self.history[0], TaskEvent):
            self.history = [h.to_dict() if isinstance(h, TaskEvent) else h for h in self.history]

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: dict) -> 'Task':
        return Task(**d)

@dataclass
class CreateTaskInput:
    """创建任务的输入"""
    title: str
    kind: str = "general"
    phase: str = "default"
    priority: TaskPriority = "medium"
    verify: Optional[List[str]] = None
    notes: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[str]] = None

    def to_dict(self) -> dict:
        return asdict(self)

# ============================================================
# 内部函数
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()

def _gen_id(prefix: str = "task") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

# ============================================================
# 任务操作
# ============================================================

def load_tasks(root: str) -> List[Task]:
    """加载所有任务"""
    ensure_omx_layout(root)
    data = read_json(tasks_file(root), [])
    return [Task.from_dict(d) for d in data]

def save_tasks(root: str, tasks: List[Task]) -> None:
    """保存所有任务"""
    ensure_omx_layout(root)
    write_json(tasks_file(root), [t.to_dict() for t in tasks])

def create_task(root: str, input: CreateTaskInput) -> Task:
    """
    创建新任务（线程安全）
    
    Returns:
        新创建的Task
    """
    task = Task(
        id=_gen_id("task"),
        title=input.title,
        kind=input.kind,
        phase=input.phase,
        status="pending",
        priority=input.priority,
        verify=input.verify or [],
        notes=input.notes or [],
        metadata=input.metadata or {},
        dependencies=input.dependencies or [],
        blockers=[],
        review_status="none",
        created_at=_now(),
        updated_at=_now(),
        history=[{"status": "pending", "at": _now()}],
    )
    with _task_lock:
        tasks = load_tasks(root)
        tasks.append(task)
        save_tasks(root, tasks)
    return task

def get_task(root: str, task_id: str) -> Optional[Task]:
    """获取指定任务（线程安全）"""
    with _task_lock:
        return _get_task_locked(root, task_id)

def update_task(
    root: str,
    task_id: str,
    patch: Dict[str, Any],
) -> Optional[Task]:
    """更新任务字段（原子操作：线程递归锁）"""
    with _task_lock:
        return _update_task_locked(root, task_id, patch)

def transition_task(
    root: str,
    task_id: str,
    new_status: TaskStatus,
    by: Optional[str] = None,
    note: Optional[str] = None,
) -> Optional[Task]:
    """
    状态转换任务（原子操作：线程递归锁）
    
    Returns:
        更新后的Task或None
    """
    with _task_lock:
        task = _get_task_locked(root, task_id)
        if not task:
            return None

        old_status = task.status
        patch = {
            "status": new_status,
            "history": task.history + [{"status": new_status, "at": _now(), "by": by, "note": note}],
        }

        # 特殊状态处理
        if new_status == "in_progress" and not task.claimed_at:
            patch["claimed_at"] = _now()
        elif new_status == "completed":
            patch["completed_at"] = _now()

        updated = _update_task_locked(root, task_id, patch)

        # 记录到ledger
        from omx_ledger import append_ledger
        append_ledger(root, "task", f"task_{new_status}",
                      f"Task {task_id}: {old_status} → {new_status}",
                      task_id=task_id, metadata={"old_status": old_status, "new_status": new_status})

        return updated

def delete_task(root: str, task_id: str) -> bool:
    """删除任务"""
    tasks = load_tasks(root)
    new_tasks = [t for t in tasks if t.id != task_id]
    if len(new_tasks) == len(tasks):
        return False
    save_tasks(root, new_tasks)
    return True

def list_tasks(
    root: str,
    status: Optional[TaskStatus] = None,
    owner: Optional[str] = None,
    phase: Optional[str] = None,
) -> List[Task]:
    """列出任务，可多条件过滤"""
    tasks = load_tasks(root)
    if status:
        tasks = [t for t in tasks if t.status == status]
    if owner:
        tasks = [t for t in tasks if t.owner == owner]
    if phase:
        tasks = [t for t in tasks if t.phase == phase]
    return tasks

def get_task_graph(root: str) -> Dict[str, Any]:
    """获取任务图统计"""
    tasks = load_tasks(root)
    
    # 按状态统计
    status_counts: Dict[TaskStatus, int] = {}
    for t in tasks:
        status_counts[t.status] = status_counts.get(t.status, 0) + 1
    
    # 按阶段统计
    phase_counts: Dict[str, int] = {}
    for t in tasks:
        phase_counts[t.phase] = phase_counts.get(t.phase, 0) + 1
    
    return {
        "total": len(tasks),
        "by_status": status_counts,
        "by_phase": phase_counts,
        "tasks": [t.to_dict() for t in tasks],
    }

# ============================================================
# 便捷函数（使用默认工作区）
# ============================================================

def create_task_default(title: str, **kwargs) -> Task:
    """使用默认工作区创建任务"""
    return create_task(get_workspace_root(), CreateTaskInput(title=title, **kwargs))

def get_task_default(task_id: str) -> Optional[Task]:
    """使用默认工作区获取任务"""
    return get_task(get_workspace_root(), task_id)

def update_task_default(task_id: str, **kwargs) -> Optional[Task]:
    """使用默认工作区更新任务"""
    return update_task(get_workspace_root(), task_id, kwargs)

def transition_task_default(task_id: str, new_status: TaskStatus, **kwargs) -> Optional[Task]:
    """使用默认工作区转换任务状态"""
    return transition_task(get_workspace_root(), task_id, new_status, **kwargs)

def list_tasks_default(**kwargs) -> List[Task]:
    """使用默认工作区列出任务"""
    return list_tasks(get_workspace_root(), **kwargs)

def get_task_graph_default() -> Dict[str, Any]:
    """使用默认工作区获取任务图"""
    return get_task_graph(get_workspace_root())
