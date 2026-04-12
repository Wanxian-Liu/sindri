"""
omx_ledger.py 单元测试
测试 OMX 数据类型定义和基础方法
"""

import os
import sys
import tempfile
from dataclasses import asdict

# 添加scripts路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from omx_ledger import (
    LedgerEntry,
    InboxItem,
    ReviewItem,
    _now,
    _gen_id,
)


class TestLedgerEntry:
    """测试LedgerEntry数据类"""
    
    def test_create_basic(self):
        """测试基本创建"""
        entry = LedgerEntry(
            id="test-1",
            kind="task",
            action="create",
            detail="Test task",
            actor="tester"
        )
        assert entry.id == "test-1"
        assert entry.kind == "task"
        assert entry.action == "create"
        assert entry.detail == "Test task"
        assert entry.actor == "tester"
        assert entry.created_at  # 自动生成时间戳
    
    def test_to_dict(self):
        """测试转字典"""
        entry = LedgerEntry(
            id="test-2",
            kind="worker",
            action="spawn",
            detail="Worker spawned"
        )
        d = entry.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "test-2"
        assert d["kind"] == "worker"
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "id": "test-3",
            "kind": "review",
            "action": "submit",
            "detail": "Review submitted",
            "actor": "reviewer",
            "task_id": None,
            "worker_id": None,
            "metadata": {},
            "created_at": "2026-01-01T00:00:00"
        }
        entry = LedgerEntry.from_dict(data)
        assert entry.id == "test-3"
        assert entry.kind == "review"
        assert entry.created_at == "2026-01-01T00:00:00"
    
    def test_default_created_at(self):
        """测试默认时间戳"""
        entry = LedgerEntry(id="t1", kind="task", action="x", detail="d")
        assert entry.created_at != ""
    
    def test_with_task_id(self):
        """测试带task_id"""
        entry = LedgerEntry(
            id="t2",
            kind="task",
            action="update",
            detail="Task updated",
            task_id="task-123"
        )
        assert entry.task_id == "task-123"
    
    def test_with_worker_id(self):
        """测试带worker_id"""
        entry = LedgerEntry(
            id="t3",
            kind="worker",
            action="spawn",
            detail="Worker spawned",
            worker_id="w-456"
        )
        assert entry.worker_id == "w-456"
    
    def test_with_metadata(self):
        """测试带metadata"""
        entry = LedgerEntry(
            id="t4",
            kind="task",
            action="x",
            detail="d",
            metadata={"key": "value", "count": 42}
        )
        assert entry.metadata["key"] == "value"
        assert entry.metadata["count"] == 42


class TestInboxItem:
    """测试InboxItem数据类"""
    
    def test_create_basic(self):
        """测试基本创建"""
        item = InboxItem(
            id="inbox-1",
            kind="inbox",
            subject="Test",
            body="Body"
        )
        assert item.id == "inbox-1"
        assert item.status == "open"
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "id": "inbox-2",
            "kind": "review",
            "subject": "Review needed",
            "body": "Please review",
            "from_": "author",
            "to": "reviewer",
            "task_id": "task-1",
            "status": "acknowledged",
            "created_at": "",
            "updated_at": ""
        }
        item = InboxItem(**data)
        assert item.id == "inbox-2"
        assert item.status == "acknowledged"
    
    def test_default_status(self):
        """测试默认状态"""
        item = InboxItem(id="i1", kind="inbox", subject="T", body="B")
        assert item.status == "open"
    
    def test_default_timestamps(self):
        """测试默认时间戳"""
        item = InboxItem(id="i2", kind="inbox", subject="T", body="B")
        assert item.created_at != ""
        assert item.updated_at != ""
    
    def test_from_with_underscore(self):
        """测试from字段的json映射"""
        item = InboxItem(
            id="i3",
            kind="inbox",
            subject="T",
            body="B",
            from_="sender"
        )
        assert item.from_ == "sender"
    
    def test_to_field(self):
        """测试to字段"""
        item = InboxItem(
            id="i4",
            kind="inbox",
            subject="T",
            body="B",
            to="receiver"
        )
        assert item.to == "receiver"
    
    def test_to_dict(self):
        """测试转字典"""
        item = InboxItem(
            id="i5",
            kind="inbox",
            subject="Test",
            body="Body"
        )
        d = item.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "i5"
        # from_ should be converted to "from" in output
        assert "from" in d
    
    def test_from_dict_with_from_key(self):
        """测试从包含'from'键的字典创建"""
        data = {
            "id": "i6",
            "kind": "inbox",
            "subject": "Test",
            "body": "Body",
            "from": "sender",
            "status": "open"
        }
        item = InboxItem.from_dict(data)
        assert item.from_ == "sender"


class TestReviewItem:
    """测试ReviewItem数据类"""
    
    def test_create_basic(self):
        """测试基本创建"""
        item = ReviewItem(
            id="review-1",
            task_id="task-1",
            reviewer="reviewer-1"
        )
        assert item.id == "review-1"
        assert item.task_id == "task-1"
        assert item.reviewer == "reviewer-1"
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "id": "r2",
            "task_id": "t2",
            "reviewer": "rev2",
            "status": "approved",
            "created_at": "",
            "updated_at": ""
        }
        item = ReviewItem(**data)
        assert item.id == "r2"
        assert item.status == "approved"
    
    def test_default_status_pending(self):
        """测试默认状态为pending"""
        item = ReviewItem(id="r3", task_id="t3", reviewer="rev3")
        assert item.status == "pending"
    
    def test_to_dict(self):
        """测试转字典"""
        item = ReviewItem(
            id="r4",
            task_id="t4",
            reviewer="rev4"
        )
        d = item.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "r4"
    
    def test_with_summary_and_notes(self):
        """测试带summary和notes"""
        item = ReviewItem(
            id="r5",
            task_id="t5",
            reviewer="rev5",
            summary="Looks good",
            notes=["Note 1", "Note 2"]
        )
        assert item.summary == "Looks good"
        assert len(item.notes) == 2


class TestHelperFunctions:
    """测试辅助函数"""
    
    def test_now(self):
        """测试_now函数返回ISO格式时间戳"""
        result = _now()
        assert isinstance(result, str)
        assert "T" in result  # ISO format
    
    def test_gen_id_default(self):
        """测试_gen_id默认前缀"""
        id1 = _gen_id()
        id2 = _gen_id()
        assert id1.startswith("ledger_")
        assert id2.startswith("ledger_")
        assert id1 != id2  # Should be unique
    
    def test_gen_id_custom_prefix(self):
        """测试_gen_id自定义前缀"""
        id1 = _gen_id("custom")
        assert id1.startswith("custom_")
    
    def test_gen_id_uniqueness(self):
        """测试_gen_id生成唯一ID"""
        ids = [_gen_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique


# 运行测试
if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v"],
        capture_output=False
    )
    sys.exit(result.returncode)
