"""
task_queue.py - 任务队列和阻塞状态管理模块

功能:
  1. 任务队列管理（优先级调度）
  2. blocked状态追踪
  3. 阻塞原因记录
  4. 自动解除机制

基于 oh-my-codex 任务状态机设计:
  pending → queued → in_progress → review → completed/failed/blocked
"""

import asyncio
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path
import heapq
import threading

# ============================================================
# 类型定义
# ============================================================

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 等待中
    QUEUED = "queued"         # 已入队
    IN_PROGRESS = "in_progress"  # 执行中
    REVIEW = "review"          # 审查中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"         # 失败
    BLOCKED = "blocked"       # 阻塞

class BlockReason(Enum):
    """阻塞原因"""
    CIRCUIT_BREAK = "circuit_break"      # 熔断触发
    DEPENDENCY = "dependency"            # 依赖未完成
    RESOURCE = "resource"                # 资源不足
    SAFETY = "safety"                    # 安全拦截
    MANUAL = "manual"                   # 手动阻塞
    TIMEOUT = "timeout"                 # 超时

@dataclass
class QueuedTask:
    """队列任务"""
    task_id: str
    priority: int  # 优先级，数字越大优先级越高
    enqueued_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        # 优先级队列：优先级高的先出队
        return self.priority > other.priority

@dataclass
class BlockedTask:
    """阻塞任务"""
    task_id: str
    reason: str
    blocked_at: str
    blocked_by: Optional[str] = None  # 被谁阻塞
    dependency_task_id: Optional[str] = None  # 依赖的任务ID
    unblock_at: Optional[str] = None  # 自动解除时间
    manual_unblock: bool = False  # 是否需要手动解除
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)

# ============================================================
# TaskQueue 主类
# ============================================================

class TaskQueue:
    """
    任务队列管理器
    
    使用方法:
        queue = TaskQueue()
        queue.enqueue(task_id="task_001", priority=5)
        next_task = queue.dequeue()
    """

    def __init__(self, queue_dir: Optional[str] = None):
        """
        初始化TaskQueue
        
        Args:
            queue_dir: 队列持久化目录
        """
        if queue_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sindris_root = os.path.dirname(script_dir)
            queue_dir = os.path.join(sindris_root, ".omx", "queue")
        
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # 优先级队列
        self._queue: List[QueuedTask] = []
        
        # 阻塞任务映射
        self._blocked: Dict[str, BlockedTask] = {}
        
        # 任务状态映射
        self._status: Dict[str, TaskStatus] = {}
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 加载已有队列
        self._load_queue()
        self._load_blocked()

    def enqueue(
        self,
        task_id: str,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> QueuedTask:
        """
        入队任务
        
        Args:
            task_id: 任务ID
            priority: 优先级（0-10，10最高）
            metadata: 额外元数据
            
        Returns:
            QueuedTask: 入队的任务
        """
        with self._lock:
            task = QueuedTask(
                task_id=task_id,
                priority=priority,
                enqueued_at=datetime.now().isoformat(),
                metadata=metadata or {}
            )
            
            heapq.heappush(self._queue, task)
            self._status[task_id] = TaskStatus.QUEUED
            
            self._save_queue()
            
            return task

    def dequeue(self) -> Optional[QueuedTask]:
        """
        出队最高优先级任务
        
        Returns:
            QueuedTask或None（队列空）
        """
        with self._lock:
            while self._queue:
                task = heapq.heappop(self._queue)
                # 检查是否被阻塞
                if task.task_id in self._blocked:
                    # 被阻塞，重新放回队列尾部或丢弃
                    continue
                self._status[task.task_id] = TaskStatus.IN_PROGRESS
                self._save_queue()
                return task
            
            return None

    def block(
        self,
        task_id: str,
        reason: BlockReason,
        blocked_by: Optional[str] = None,
        dependency_task_id: Optional[str] = None,
        auto_unlock_seconds: Optional[int] = None,
        manual: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> BlockedTask:
        """
        阻塞任务
        
        Args:
            task_id: 任务ID
            reason: 阻塞原因
            blocked_by: 阻塞者（如角色名称）
            dependency_task_id: 依赖的任务ID
            auto_unlock_seconds: 自动解除秒数
            manual: 是否需要手动解除
            details: 额外详情
            
        Returns:
            BlockedTask: 创建的阻塞记录
        """
        with self._lock:
            # 计算自动解除时间
            unblock_at = None
            if auto_unlock_seconds:
                from datetime import timedelta
                dt = datetime.now() + timedelta(seconds=auto_unlock_seconds)
                unblock_at = dt.isoformat()
            
            blocked = BlockedTask(
                task_id=task_id,
                reason=reason.value,
                blocked_at=datetime.now().isoformat(),
                blocked_by=blocked_by,
                dependency_task_id=dependency_task_id,
                unblock_at=unblock_at,
                manual_unblock=manual,
                details=details or {}
            )
            
            self._blocked[task_id] = blocked
            self._status[task_id] = TaskStatus.BLOCKED
            
            self._save_blocked()
            
            return blocked

    def unblock(self, task_id: str) -> bool:
        """
        解除任务阻塞
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功解除
        """
        with self._lock:
            if task_id not in self._blocked:
                return False
            
            del self._blocked[task_id]
            self._status[task_id] = TaskStatus.PENDING
            
            self._save_blocked()
            
            return True

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        return self._status.get(task_id)

    def get_blocked_reason(self, task_id: str) -> Optional[BlockedTask]:
        """获取任务阻塞原因"""
        return self._blocked.get(task_id)

    def get_blocked_tasks(self) -> List[BlockedTask]:
        """获取所有阻塞任务"""
        return list(self._blocked.values())

    def get_queue_size(self) -> int:
        """获取队列大小"""
        return len(self._queue)

    def is_blocked(self, task_id: str) -> bool:
        """检查任务是否被阻塞"""
        return task_id in self._blocked

    def check_auto_unblock(self) -> List[str]:
        """
        检查自动解除的任务
        
        Returns:
            List[str]: 已自动解除的任务ID列表
        """
        with self._lock:
            now = datetime.now()
            to_unblock = []
            
            for task_id, blocked in self._blocked.items():
                if blocked.unblock_at and not blocked.manual_unblock:
                    unblock_time = datetime.fromisoformat(blocked.unblock_at)
                    if now >= unblock_time:
                        to_unblock.append(task_id)
            
            # 执行解除
            for task_id in to_unblock:
                del self._blocked[task_id]
                self._status[task_id] = TaskStatus.PENDING
            
            if to_unblock:
                self._save_blocked()
            
            return to_unblock

    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        with self._lock:
            status_counts = {}
            for status in TaskStatus:
                status_counts[status.value] = sum(1 for s in self._status.values() if s == status)
            
            return {
                "queue_size": len(self._queue),
                "blocked_count": len(self._blocked),
                "status_counts": status_counts,
            }

    # ==================== 持久化 ====================

    def _queue_file(self) -> Path:
        return self.queue_dir / "queue.jsonl"

    def _blocked_file(self) -> Path:
        return self.queue_dir / "blocked.jsonl"

    def _save_queue(self):
        """保存队列到文件"""
        file_path = self._queue_file()
        with open(file_path, "w", encoding="utf-8") as f:
            for task in self._queue:
                f.write(json.dumps(task.__dict__, ensure_ascii=False) + "\n")

    def _load_queue(self):
        """从文件加载队列"""
        file_path = self._queue_file()
        if not file_path.exists():
            return
        
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    task = QueuedTask(**data)
                    heapq.heappush(self._queue, task)
                except (json.JSONDecodeError, TypeError):
                    continue

    def _save_blocked(self):
        """保存阻塞列表到文件"""
        file_path = self._blocked_file()
        with open(file_path, "w", encoding="utf-8") as f:
            for blocked in self._blocked.values():
                f.write(json.dumps(blocked.to_dict(), ensure_ascii=False) + "\n")

    def _load_blocked(self):
        """从文件加载阻塞列表"""
        file_path = self._blocked_file()
        if not file_path.exists():
            return
        
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    blocked = BlockedTask(**data)
                    self._blocked[blocked.task_id] = blocked
                    self._status[blocked.task_id] = TaskStatus.BLOCKED
                except (json.JSONDecodeError, TypeError):
                    continue


# ============================================================
# 便捷函数
# ============================================================

import json
import os

_default_queue: Optional[TaskQueue] = None

def get_default_queue() -> TaskQueue:
    """获取默认TaskQueue实例"""
    global _default_queue
    if _default_queue is None:
        _default_queue = TaskQueue()
    return _default_queue


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("TaskQueue 单元测试")
    print("=" * 60)
    
    queue = TaskQueue(queue_dir="/tmp/sindris_queue_test")
    
    # 入队测试
    queue.enqueue("task_001", priority=5)
    queue.enqueue("task_002", priority=3)
    queue.enqueue("task_003", priority=8)  # 最高优先级
    print(f"✅ 入队3个任务，队列大小: {queue.get_queue_size()}")
    
    # 出队测试
    task = queue.dequeue()
    print(f"✅ 出队: {task.task_id} (priority={task.priority})")
    
    # 阻塞测试
    queue.block("task_002", BlockReason.CIRCUIT_BREAK, blocked_by="developer")
    print(f"✅ 阻塞task_002: {queue.is_blocked('task_002')}")
    
    # 状态检查
    print(f"✅ task_002状态: {queue.get_status('task_002').value}")
    
    # 解除阻塞
    queue.unblock("task_002")
    print(f"✅ 解除阻塞后: {queue.is_blocked('task_002')}")
    
    # 统计
    print(f"✅ 队列统计: {queue.get_stats()}")
    
    print("=" * 60)
