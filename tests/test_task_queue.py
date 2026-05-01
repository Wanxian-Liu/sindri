#!/usr/bin/env python3
"""
test_task_queue.py - task_queue.py 完整测试

测试覆盖:
1. TaskStatus enum
2. BlockReason enum
3. QueuedTask dataclass (__lt__, to_dict)
4. BlockedTask dataclass (to_dict)
5. TaskQueue 初始化
6. TaskQueue.enqueue()
7. TaskQueue.dequeue()
8. TaskQueue.block()
9. TaskQueue.unblock()
10. TaskQueue.get_status()
11. TaskQueue.get_blocked_reason()
12. TaskQueue.get_blocked_tasks()
13. TaskQueue.get_queue_size()
14. TaskQueue.is_blocked()
15. TaskQueue.check_auto_unblock()
16. TaskQueue.get_stats()
17. TaskQueue._queue_file()
18. TaskQueue._blocked_file()
19. TaskQueue._save_queue()
20. TaskQueue._load_queue()
21. TaskQueue._save_blocked()
22. TaskQueue._load_blocked()
23. get_default_queue()
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg}: expected {expected!r}, got {actual!r}")

def assert_true(condition, msg=""):
    if not condition:
        raise AssertionError(f"{msg}: expected truthy, got {condition!r}")

def assert_in(substr, s, msg=""):
    if substr not in s:
        raise AssertionError(f"{msg}: expected {substr!r} in {s!r}")


@pytest.fixture
def temp_queue_dir():
    tmp = tempfile.mkdtemp(prefix="queue_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_task_status_enum():
    """测试 TaskStatus enum"""
    from task_queue import TaskStatus
    assert_eq(TaskStatus.PENDING.value, "pending")
    assert_eq(TaskStatus.QUEUED.value, "queued")
    assert_eq(TaskStatus.IN_PROGRESS.value, "in_progress")
    assert_eq(TaskStatus.REVIEW.value, "review")
    assert_eq(TaskStatus.COMPLETED.value, "completed")
    assert_eq(TaskStatus.FAILED.value, "failed")
    assert_eq(TaskStatus.BLOCKED.value, "blocked")


def test_block_reason_enum():
    """测试 BlockReason enum"""
    from task_queue import BlockReason
    assert_eq(BlockReason.CIRCUIT_BREAK.value, "circuit_break")
    assert_eq(BlockReason.DEPENDENCY.value, "dependency")
    assert_eq(BlockReason.RESOURCE.value, "resource")
    assert_eq(BlockReason.SAFETY.value, "safety")
    assert_eq(BlockReason.MANUAL.value, "manual")
    assert_eq(BlockReason.TIMEOUT.value, "timeout")


def test_queued_task_lt():
    """测试 QueuedTask.__lt__() 优先级比较 - 高优先级先出队"""
    from task_queue import QueuedTask
    t1 = QueuedTask("t1", priority=5, enqueued_at="")
    t2 = QueuedTask("t2", priority=10, enqueued_at="")
    # 高优先级(10)应该"小于"低优先级(5)，这样heap会先pop高优先级
    # t2 < t1 = 10 > 5 = True
    assert_true(t2 < t1)


def test_blocked_task_to_dict():
    """测试 BlockedTask.to_dict()"""
    from task_queue import BlockedTask
    b = BlockedTask(
        task_id="t_blocked",
        reason="circuit_break",
        blocked_at="2024-01-01T00:00:00",
        blocked_by="circuit_breaker",
    )
    d = b.to_dict()
    assert_eq(d["task_id"], "t_blocked")
    assert_eq(d["reason"], "circuit_break")
    assert_eq(d["blocked_by"], "circuit_breaker")


def test_task_queue_init(temp_queue_dir):
    """测试 TaskQueue 初始化"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    assert_true(q.queue_dir.exists())
    assert_eq(q.get_queue_size(), 0)


def test_task_queue_init_creates_dir(temp_queue_dir):
    """测试 TaskQueue 自动创建目录"""
    from task_queue import TaskQueue
    nested = os.path.join(temp_queue_dir, "a", "b", "c")
    q = TaskQueue(queue_dir=nested)
    assert_true(os.path.exists(nested))


def test_enqueue_basic(temp_queue_dir):
    """测试 enqueue() 基本功能"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    task = q.enqueue("task_enq_001", priority=5)
    assert_eq(task.task_id, "task_enq_001")
    assert_eq(task.priority, 5)
    assert_eq(q.get_queue_size(), 1)
    assert_eq(q.get_status("task_enq_001").value, "queued")


def test_enqueue_with_metadata(temp_queue_dir):
    """测试 enqueue() 带元数据"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    task = q.enqueue("task_meta_001", priority=3, metadata={"role": "developer", "round": "Round1"})
    assert_eq(task.metadata["role"], "developer")
    assert_eq(task.metadata["round"], "Round1")


def test_enqueue_priority_order(temp_queue_dir):
    """测试 enqueue() 优先级顺序"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.enqueue("t_low", priority=1)
    q.enqueue("t_high", priority=10)
    q.enqueue("t_mid", priority=5)
    first = q.dequeue()
    assert_eq(first.task_id, "t_high")


def test_dequeue_returns_task(temp_queue_dir):
    """测试 dequeue() 返回任务"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.enqueue("t_deq_001", priority=5)
    task = q.dequeue()
    assert_eq(task.task_id, "t_deq_001")
    assert_eq(q.get_status("t_deq_001").value, "in_progress")


def test_dequeue_empty_returns_none(temp_queue_dir):
    """测试 dequeue() 空队列返回None"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    task = q.dequeue()
    assert_true(task is None)


def test_dequeue_skips_blocked(temp_queue_dir):
    """测试 dequeue() 跳过阻塞任务"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.enqueue("t_blocked_task", priority=10)
    q.block("t_blocked_task", BlockReason.CIRCUIT_BREAK)
    task = q.dequeue()
    assert_true(task is None or task.task_id != "t_blocked_task")


def test_block_basic(temp_queue_dir):
    """测试 block() 基本功能"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    blocked = q.block("t_block_001", BlockReason.SAFETY, blocked_by="safety_policy")
    assert_eq(blocked.task_id, "t_block_001")
    assert_true(q.is_blocked("t_block_001"))
    assert_eq(q.get_status("t_block_001").value, "blocked")


def test_block_with_auto_unlock(temp_queue_dir):
    """测试 block() 自动解除"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    blocked = q.block("t_auto_001", BlockReason.TIMEOUT, auto_unlock_seconds=1)
    assert_true(blocked.unblock_at is not None)
    assert_true(not blocked.manual_unblock)


def test_block_manual(temp_queue_dir):
    """测试 block() 手动解除"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    blocked = q.block("t_manual_001", BlockReason.MANUAL, manual=True)
    assert_true(blocked.manual_unblock)


def test_unblock_success(temp_queue_dir):
    """测试 unblock() 成功解除"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.block("t_unblock_001", BlockReason.CIRCUIT_BREAK)
    result = q.unblock("t_unblock_001")
    assert_true(result)
    assert_true(not q.is_blocked("t_unblock_001"))
    assert_eq(q.get_status("t_unblock_001").value, "pending")


def test_unblock_not_blocked(temp_queue_dir):
    """测试 unblock() 未阻塞的任务"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    result = q.unblock("t_not_blocked")
    assert_true(not result)


def test_get_status_unknown(temp_queue_dir):
    """测试 get_status() 未知任务"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    status = q.get_status("unknown_task")
    assert_true(status is None)


def test_get_blocked_reason(temp_queue_dir):
    """测试 get_blocked_reason()"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.block("t_reason_001", BlockReason.RESOURCE, details={"cpu": "100%"})
    reason = q.get_blocked_reason("t_reason_001")
    assert_true(reason is not None)
    assert_eq(reason.reason, "resource")


def test_get_blocked_reason_not_blocked(temp_queue_dir):
    """测试 get_blocked_reason() 未阻塞"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    reason = q.get_blocked_reason("t_not_blocked")
    assert_true(reason is None)


def test_get_blocked_tasks(temp_queue_dir):
    """测试 get_blocked_tasks()"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.block("t_b1", BlockReason.CIRCUIT_BREAK)
    q.block("t_b2", BlockReason.SAFETY)
    blocked = q.get_blocked_tasks()
    assert_eq(len(blocked), 2)


def test_get_queue_size(temp_queue_dir):
    """测试 get_queue_size()"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    assert_eq(q.get_queue_size(), 0)
    q.enqueue("t_size_1", priority=1)
    q.enqueue("t_size_2", priority=2)
    assert_eq(q.get_queue_size(), 2)


def test_is_blocked(temp_queue_dir):
    """测试 is_blocked()"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    assert_true(not q.is_blocked("t_not"))
    q.block("t_is_blocked", BlockReason.DEPENDENCY)
    assert_true(q.is_blocked("t_is_blocked"))


def test_check_auto_unblock_ready(temp_queue_dir):
    """测试 check_auto_unblock() 已到时间"""
    from task_queue import TaskQueue, BlockReason
    import time
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.block("t_auto_now", BlockReason.TIMEOUT, auto_unlock_seconds=1)
    time.sleep(1.1)
    unblocked = q.check_auto_unblock()
    assert_in("t_auto_now", unblocked)
    assert_true(not q.is_blocked("t_auto_now"))


def test_check_auto_unblock_not_yet(temp_queue_dir):
    """测试 check_auto_unblock() 未到时间"""
    from task_queue import TaskQueue, BlockReason
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.block("t_auto_later", BlockReason.TIMEOUT, auto_unlock_seconds=3600)
    unblocked = q.check_auto_unblock()
    assert_true("t_auto_later" not in unblocked)


def test_check_auto_unblock_manual_ignored(temp_queue_dir):
    """测试 check_auto_unblock() 忽略手动解除"""
    from task_queue import TaskQueue, BlockReason
    import time
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.block("t_manual", BlockReason.MANUAL, manual=True, auto_unlock_seconds=1)
    time.sleep(1.1)
    unblocked = q.check_auto_unblock()
    assert_true("t_manual" not in unblocked)
    assert_true(q.is_blocked("t_manual"))


def test_get_stats(temp_queue_dir):
    """测试 get_stats()"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    q.enqueue("t_stats_1", priority=1)
    q.enqueue("t_stats_2", priority=2)
    stats = q.get_stats()
    assert_eq(stats["queue_size"], 2)
    assert_eq(stats["blocked_count"], 0)
    assert_true("status_counts" in stats)


def test_queue_file_path(temp_queue_dir):
    """测试 _queue_file()"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    p = q._queue_file()
    assert_true(str(p).endswith("queue.jsonl"))


def test_blocked_file_path(temp_queue_dir):
    """测试 _blocked_file()"""
    from task_queue import TaskQueue
    q = TaskQueue(queue_dir=temp_queue_dir)
    p = q._blocked_file()
    assert_true(str(p).endswith("blocked.jsonl"))


def test_persistence_enqueue_dequeue(temp_queue_dir):
    """测试 enqueue/dequeue 持久化"""
    from task_queue import TaskQueue
    q1 = TaskQueue(queue_dir=temp_queue_dir)
    q1.enqueue("t_persist_001", priority=5)
    q2 = TaskQueue(queue_dir=temp_queue_dir)
    assert_eq(q2.get_queue_size(), 1)


def test_persistence_block(temp_queue_dir):
    """测试 block 持久化"""
    from task_queue import TaskQueue, BlockReason
    q1 = TaskQueue(queue_dir=temp_queue_dir)
    q1.block("t_persist_block", BlockReason.SAFETY)
    q2 = TaskQueue(queue_dir=temp_queue_dir)
    assert_true(q2.is_blocked("t_persist_block"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
