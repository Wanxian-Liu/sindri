"""
test_omx_ledger_ops.py - omx_ledger.py 文件操作测试
测试 load_ledger, save_ledger, append_ledger, inbox操作, review操作等
"""

import os
import sys
import tempfile
import shutil
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from omx_ledger import (
    LedgerEntry,
    InboxItem,
    ReviewItem,
    LedgerKind,
    InboxKind,
    InboxStatus,
    ReviewStatus,
    load_ledger,
    save_ledger,
    list_ledger,
    append_ledger,
    load_inbox,
    save_inbox,
    list_inbox,
    push_inbox_item,
    update_inbox_item,
    load_reviews,
    save_reviews,
    list_reviews,
    create_review,
    update_review,
    append_ledger_default,
    push_inbox_default,
    create_review_default,
    get_ledger_summary,
)
from omx_contract import ensure_omx_layout, set_workspace_root


class TestLedgerOperations:
    """测试 ledger 文件操作"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_ledger_empty(self):
        """测试加载空的ledger"""
        entries = load_ledger(self.temp_dir)
        assert entries == []
    
    def test_save_and_load_ledger(self):
        """测试保存和加载ledger"""
        entries = [
            LedgerEntry(id="e1", kind="task", action="create", detail="Test 1"),
            LedgerEntry(id="e2", kind="worker", action="spawn", detail="Worker 1"),
        ]
        save_ledger(self.temp_dir, entries)
        loaded = load_ledger(self.temp_dir)
        assert len(loaded) == 2
        assert loaded[0].id == "e1"
        assert loaded[1].kind == "worker"
    
    def test_list_ledger_limit(self):
        """测试 list_ledger limit 参数"""
        entries = [LedgerEntry(id=f"e{i}", kind="task", action="x", detail=f"D{i}") 
                   for i in range(60)]
        save_ledger(self.temp_dir, entries)
        
        # limit=0 返回全部
        all_entries = list_ledger(self.temp_dir, limit=0)
        assert len(all_entries) == 60
        
        # limit=50 返回最近50条
        recent = list_ledger(self.temp_dir, limit=50)
        assert len(recent) == 50
    
    def test_append_ledger(self):
        """测试追加ledger条目"""
        entry = append_ledger(
            self.temp_dir,
            kind="task",
            action="create",
            detail="Task created",
            actor="tester",
            task_id="task-123",
            worker_id="w-456",
            metadata={"priority": "high"}
        )
        assert entry.id.startswith("ledger_")
        assert entry.kind == "task"
        assert entry.detail == "Task created"
        assert entry.actor == "tester"
        
        # 验证持久化
        entries = load_ledger(self.temp_dir)
        assert len(entries) == 1
        assert entries[0].task_id == "task-123"
    
    def test_append_multiple_ledger(self):
        """测试追加多条ledger"""
        for i in range(5):
            append_ledger(self.temp_dir, kind="task", action="x", detail=f"D{i}")
        
        entries = load_ledger(self.temp_dir)
        assert len(entries) == 5
    
    def test_append_ledger_default_workspace(self, monkeypatch):
        """测试使用默认工作区的 append_ledger_default"""
        import os
        monkeypatch.setenv("SINDRIS_WORKSPACE", self.temp_dir)
        
        # 需要 mock get_workspace_root
        from omx_contract import set_workspace_root
        set_workspace_root(self.temp_dir)
        
        entry = append_ledger_default(kind="task", action="test", detail="Test default")
        assert entry.kind == "task"


class TestInboxOperations:
    """测试 inbox 文件操作"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_inbox_empty(self):
        """测试加载空的inbox"""
        items = load_inbox(self.temp_dir)
        assert items == []
    
    def test_save_and_load_inbox(self):
        """测试保存和加载inbox"""
        items = [
            InboxItem(id="i1", kind="inbox", subject="Test 1", body="Body 1"),
            InboxItem(id="i2", kind="review", subject="Review 1", body="Body 2"),
        ]
        save_inbox(self.temp_dir, items)
        loaded = load_inbox(self.temp_dir)
        assert len(loaded) == 2
    
    def test_list_inbox_no_filter(self):
        """测试列出全部inbox（无过滤）"""
        items = [
            InboxItem(id="i1", kind="inbox", subject="S1", body="B1", status="open"),
            InboxItem(id="i2", kind="inbox", subject="S2", body="B2", status="resolved"),
        ]
        save_inbox(self.temp_dir, items)
        
        all_items = list_inbox(self.temp_dir)
        assert len(all_items) == 2
    
    def test_list_inbox_with_status_filter(self):
        """测试按status过滤list_inbox"""
        items = [
            InboxItem(id="i1", kind="inbox", subject="S1", body="B1", status="open"),
            InboxItem(id="i2", kind="inbox", subject="S2", body="B2", status="resolved"),
            InboxItem(id="i3", kind="inbox", subject="S3", body="B3", status="acknowledged"),
        ]
        save_inbox(self.temp_dir, items)
        
        open_items = list_inbox(self.temp_dir, status="open")
        assert len(open_items) == 1
        assert open_items[0].id == "i1"
        
        resolved_items = list_inbox(self.temp_dir, status="resolved")
        assert len(resolved_items) == 1
    
    def test_push_inbox_item(self):
        """测试推送inbox条目"""
        item = push_inbox_item(
            self.temp_dir,
            kind="inbox",
            subject="New task",
            body="Please review",
            from_="author",
            to="reviewer",
            task_id="task-789",
            status="open",
        )
        assert item.id.startswith("inbox_")
        assert item.subject == "New task"
        assert item.from_ == "author"
        assert item.to == "reviewer"
        assert item.task_id == "task-789"
        assert item.status == "open"
        
        # 验证持久化
        items = load_inbox(self.temp_dir)
        assert len(items) == 1
        assert items[0].subject == "New task"
    
    def test_push_multiple_inbox_items(self):
        """测试推送多条inbox"""
        for i in range(3):
            push_inbox_item(self.temp_dir, kind="inbox", subject=f"S{i}", body=f"B{i}")
        
        items = load_inbox(self.temp_dir)
        assert len(items) == 3
    
    def test_update_inbox_item(self):
        """测试更新inbox条目"""
        item = push_inbox_item(
            self.temp_dir, kind="inbox", subject="Original", body="Body"
        )
        
        updated = update_inbox_item(
            self.temp_dir,
            item.id,
            {"status": "acknowledged", "subject": "Updated"}
        )
        assert updated is not None
        assert updated.status == "acknowledged"
        assert updated.subject == "Updated"
    
    def test_update_inbox_item_not_found(self):
        """测试更新不存在的inbox条目"""
        result = update_inbox_item(self.temp_dir, "nonexistent", {"status": "resolved"})
        assert result is None
    
    def test_push_inbox_default_workspace(self):
        """测试使用默认工作区的 push_inbox_default"""
        from omx_contract import set_workspace_root
        set_workspace_root(self.temp_dir)
        
        item = push_inbox_default(kind="inbox", subject="Test", body="Body")
        assert item.kind == "inbox"


class TestReviewOperations:
    """测试 review 文件操作"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_reviews_empty(self):
        """测试加载空的reviews"""
        items = load_reviews(self.temp_dir)
        assert items == []
    
    def test_save_and_load_reviews(self):
        """测试保存和加载reviews"""
        items = [
            ReviewItem(id="r1", task_id="t1", reviewer="rev1", status="pending"),
            ReviewItem(id="r2", task_id="t2", reviewer="rev2", status="approved"),
        ]
        save_reviews(self.temp_dir, items)
        loaded = load_reviews(self.temp_dir)
        assert len(loaded) == 2
    
    def test_list_reviews_no_filter(self):
        """测试列出全部reviews（无过滤）"""
        items = [
            ReviewItem(id="r1", task_id="t1", reviewer="rev1", status="pending"),
            ReviewItem(id="r2", task_id="t2", reviewer="rev2", status="approved"),
        ]
        save_reviews(self.temp_dir, items)
        
        all_reviews = list_reviews(self.temp_dir)
        assert len(all_reviews) == 2
    
    def test_list_reviews_with_status_filter(self):
        """测试按status过滤list_reviews"""
        items = [
            ReviewItem(id="r1", task_id="t1", reviewer="rev1", status="pending"),
            ReviewItem(id="r2", task_id="t2", reviewer="rev2", status="approved"),
            ReviewItem(id="r3", task_id="t3", reviewer="rev3", status="pending"),
        ]
        save_reviews(self.temp_dir, items)
        
        pending = list_reviews(self.temp_dir, status="pending")
        assert len(pending) == 2
        
        approved = list_reviews(self.temp_dir, status="approved")
        assert len(approved) == 1
    
    def test_create_review(self):
        """测试创建review条目"""
        review = create_review(
            self.temp_dir,
            task_id="task-001",
            reviewer="reviewer-1",
            summary="Initial review",
            notes=["Note 1", "Note 2"]
        )
        assert review.id.startswith("review_")
        assert review.task_id == "task-001"
        assert review.reviewer == "reviewer-1"
        assert review.status == "pending"
        assert review.summary == "Initial review"
        assert len(review.notes) == 2
        
        # 验证持久化
        reviews = load_reviews(self.temp_dir)
        assert len(reviews) == 1
        
        # 验证ledger记录
        ledger_entries = load_ledger(self.temp_dir)
        ledger_task = [e for e in ledger_entries if e.kind == "review"]
        assert len(ledger_task) == 1
    
    def test_update_review(self):
        """测试更新review条目"""
        review = create_review(
            self.temp_dir,
            task_id="task-002",
            reviewer="reviewer-2",
            summary="Original"
        )
        
        updated = update_review(
            self.temp_dir,
            review.id,
            status="approved",
            summary="Updated summary",
            notes=["New note"]
        )
        assert updated is not None
        assert updated.status == "approved"
        assert updated.summary == "Updated summary"
        assert updated.notes == ["New note"]
    
    def test_update_review_partial(self):
        """测试部分更新review"""
        review = create_review(
            self.temp_dir,
            task_id="task-003",
            reviewer="reviewer-3",
            summary="Original"
        )
        
        # 只更新status
        updated = update_review(self.temp_dir, review.id, status="changes_requested")
        assert updated.status == "changes_requested"
        assert updated.summary == "Original"  # 未更新的保持不变
    
    def test_update_review_not_found(self):
        """测试更新不存在的review"""
        result = update_review(self.temp_dir, "nonexistent", status="approved")
        assert result is None
    
    def test_create_review_default_workspace(self):
        """测试使用默认工作区的 create_review_default"""
        from omx_contract import set_workspace_root
        set_workspace_root(self.temp_dir)
        
        review = create_review_default(task_id="task-x", reviewer="rev-x", summary="Test")
        assert review.task_id == "task-x"


class TestGetLedgerSummary:
    """测试 get_ledger_summary 函数"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
        # set workspace root for default functions
        set_workspace_root(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_summary_empty(self):
        """测试空ledger的摘要"""
        summary = get_ledger_summary(limit=20)
        assert summary["total"] == 0
        assert summary["by_kind"] == {}
        assert summary["recent"] == []
        assert summary["first_entry"] is None
        assert summary["last_entry"] is None
    
    def test_summary_with_entries(self):
        """测试有条目的ledger摘要"""
        append_ledger(self.temp_dir, kind="task", action="a", detail="d1")
        append_ledger(self.temp_dir, kind="task", action="b", detail="d2")
        append_ledger(self.temp_dir, kind="worker", action="c", detail="d3")
        
        summary = get_ledger_summary(limit=2)
        assert summary["total"] == 3
        assert summary["by_kind"]["task"] == 2
        assert summary["by_kind"]["worker"] == 1
        assert len(summary["recent"]) == 2  # limit=2
        assert summary["first_entry"] is not None
        assert summary["last_entry"] is not None
