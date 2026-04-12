"""
test_omx_reviews_ops.py - omx_reviews.py 操作测试
测试 review 相关文件操作
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from omx_reviews import (
    ReviewItem,
    ReviewResult,
    load_reviews,
    save_reviews,
    list_reviews,
    create_review,
    get_review,
    update_review,
    submit_review_result,
    get_reviews_for_task,
    is_task_approved,
    create_review_default,
    submit_review_result_default,
    list_reviews_default,
    is_task_approved_default,
    get_review_summary,
    get_review_summary_default,
    create_action_review,
    approve_action,
    request_changes_for_action,
)
from omx_contract import ensure_omx_layout, set_workspace_root


class TestReviewDatatypes:
    """测试 ReviewItem 和 ReviewResult 数据类型"""
    
    def test_review_item_to_dict(self):
        """测试 ReviewItem.to_dict()"""
        item = ReviewItem(
            id="r1",
            task_id="t1",
            reviewer="rev1",
            status="pending",
            summary="Test",
            notes=["n1", "n2"]
        )
        d = item.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "r1"
        assert d["status"] == "pending"
    
    def test_review_item_from_dict(self):
        """测试 ReviewItem.from_dict()"""
        data = {
            "id": "r2",
            "task_id": "t2",
            "reviewer": "rev2",
            "status": "approved",
            "summary": "Summary",
            "notes": ["n1"],
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        item = ReviewItem.from_dict(data)
        assert item.id == "r2"
        assert item.status == "approved"


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
            ReviewItem(id="r1", task_id="t1", reviewer="rev1", status="pending", summary=""),
            ReviewItem(id="r2", task_id="t2", reviewer="rev2", status="approved", summary="OK"),
        ]
        save_reviews(self.temp_dir, items)
        loaded = load_reviews(self.temp_dir)
        assert len(loaded) == 2
    
    def test_list_reviews_no_filter(self):
        """测试无过滤列出reviews"""
        items = [
            ReviewItem(id="r1", task_id="t1", reviewer="rev1", status="pending", summary=""),
            ReviewItem(id="r2", task_id="t2", reviewer="rev2", status="approved", summary="OK"),
        ]
        save_reviews(self.temp_dir, items)
        
        all_items = list_reviews(self.temp_dir)
        assert len(all_items) == 2
    
    def test_list_reviews_status_filter(self):
        """测试按status过滤"""
        items = [
            ReviewItem(id="r1", task_id="t1", reviewer="rev1", status="pending", summary=""),
            ReviewItem(id="r2", task_id="t2", reviewer="rev2", status="approved", summary="OK"),
            ReviewItem(id="r3", task_id="t3", reviewer="rev3", status="pending", summary=""),
        ]
        save_reviews(self.temp_dir, items)
        
        pending = list_reviews(self.temp_dir, status="pending")
        assert len(pending) == 2
        
        approved = list_reviews(self.temp_dir, status="approved")
        assert len(approved) == 1
    
    def test_list_reviews_reviewer_filter(self):
        """测试按reviewer过滤"""
        items = [
            ReviewItem(id="r1", task_id="t1", reviewer="alice", status="pending", summary=""),
            ReviewItem(id="r2", task_id="t2", reviewer="bob", status="pending", summary=""),
            ReviewItem(id="r3", task_id="t3", reviewer="alice", status="pending", summary=""),
        ]
        save_reviews(self.temp_dir, items)
        
        alice_reviews = list_reviews(self.temp_dir, reviewer="alice")
        assert len(alice_reviews) == 2
    
    def test_list_reviews_task_id_filter(self):
        """测试按task_id过滤"""
        items = [
            ReviewItem(id="r1", task_id="task-A", reviewer="rev1", status="pending", summary=""),
            ReviewItem(id="r2", task_id="task-B", reviewer="rev2", status="pending", summary=""),
        ]
        save_reviews(self.temp_dir, items)
        
        task_a_reviews = list_reviews(self.temp_dir, task_id="task-A")
        assert len(task_a_reviews) == 1
        assert task_a_reviews[0].id == "r1"
    
    def test_list_reviews_multiple_filters(self):
        """测试多条件过滤"""
        items = [
            ReviewItem(id="r1", task_id="t1", reviewer="alice", status="pending", summary=""),
            ReviewItem(id="r2", task_id="t2", reviewer="alice", status="approved", summary="OK"),
            ReviewItem(id="r3", task_id="t3", reviewer="bob", status="pending", summary=""),
        ]
        save_reviews(self.temp_dir, items)
        
        result = list_reviews(self.temp_dir, status="pending", reviewer="alice")
        assert len(result) == 1
        assert result[0].id == "r1"


class TestReviewCrud:
    """测试 Review CRUD 操作"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_review(self):
        """测试创建review"""
        review = create_review(
            self.temp_dir,
            task_id="task-001",
            reviewer="reviewer-1",
            summary="Initial review"
        )
        assert review.id.startswith("review_")
        assert review.task_id == "task-001"
        assert review.reviewer == "reviewer-1"
        assert review.status == "pending"
        
        # 验证持久化
        reviews = load_reviews(self.temp_dir)
        assert len(reviews) == 1
    
    def test_create_review_with_notes(self):
        """测试创建带notes的review（通过update_review）"""
        review = create_review(
            self.temp_dir,
            task_id="task-002",
            reviewer="reviewer-2",
            summary="With notes",
        )
        # notes 需要通过 update_review 添加
        updated = update_review(
            self.temp_dir,
            review.id,
            {"notes": ["Note 1", "Note 2"]}
        )
        assert len(updated.notes) == 2
    
    def test_get_review(self):
        """测试获取指定review"""
        review = create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="Test")
        found = get_review(self.temp_dir, review.id)
        assert found is not None
        assert found.id == review.id
    
    def test_get_review_not_found(self):
        """测试获取不存在的review"""
        result = get_review(self.temp_dir, "nonexistent")
        assert result is None
    
    def test_update_review_status(self):
        """测试更新review状态"""
        review = create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="Test")
        
        updated = update_review(
            self.temp_dir,
            review.id,
            {"status": "approved"}
        )
        assert updated is not None
        assert updated.status == "approved"
    
    def test_update_review_summary(self):
        """测试更新review摘要"""
        review = create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="Old")
        
        updated = update_review(
            self.temp_dir,
            review.id,
            {"summary": "New summary"}
        )
        assert updated.summary == "New summary"
    
    def test_update_review_notes(self):
        """测试更新review notes"""
        review = create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="Test")
        
        updated = update_review(
            self.temp_dir,
            review.id,
            {"notes": ["New note 1", "New note 2"]}
        )
        assert len(updated.notes) == 2
    
    def test_update_review_multiple_fields(self):
        """测试同时更新多个字段"""
        review = create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="Old")
        
        updated = update_review(
            self.temp_dir,
            review.id,
            {"status": "changes_requested", "summary": "Needs work", "notes": ["Fix X"]}
        )
        assert updated.status == "changes_requested"
        assert updated.summary == "Needs work"
        assert updated.notes == ["Fix X"]
    
    def test_update_review_not_found(self):
        """测试更新不存在的review"""
        result = update_review(self.temp_dir, "nonexistent", {"status": "approved"})
        assert result is None


class TestSubmitReviewResult:
    """测试 submit_review_result"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_submit_approved(self):
        """测试提交 approved 结果"""
        review = create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="Test")
        
        result = submit_review_result(
            self.temp_dir,
            review.id,
            status="approved",
            summary="Looks good",
            notes=["Approved by reviewer"]
        )
        assert result is not None
        assert result.status == "approved"
        assert result.summary == "Looks good"
        assert result.approved_at is not None
        assert result.changes_requested_at is None
    
    def test_submit_changes_requested(self):
        """测试提交 changes_requested 结果"""
        review = create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="Test")
        
        result = submit_review_result(
            self.temp_dir,
            review.id,
            status="changes_requested",
            summary="Needs changes",
            notes=["Fix the bug", "Update docs"]
        )
        assert result is not None
        assert result.status == "changes_requested"
        assert result.changes_requested_at is not None
        assert result.approved_at is None
    
    def test_submit_review_not_found(self):
        """测试提交不存在的review"""
        result = submit_review_result(
            self.temp_dir,
            "nonexistent",
            status="approved",
            summary="Test"
        )
        assert result is None


class TestGetReviewsForTask:
    """测试 get_reviews_for_task"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_reviews_for_task(self):
        """测试获取任务的所有review"""
        create_review(self.temp_dir, task_id="task-A", reviewer="r1", summary="")
        create_review(self.temp_dir, task_id="task-A", reviewer="r2", summary="")
        create_review(self.temp_dir, task_id="task-B", reviewer="r3", summary="")
        
        task_a_reviews = get_reviews_for_task(self.temp_dir, "task-A")
        assert len(task_a_reviews) == 2
    
    def test_get_reviews_for_task_none(self):
        """测试获取没有review的任务"""
        reviews = get_reviews_for_task(self.temp_dir, "nonexistent")
        assert reviews == []


class TestIsTaskApproved:
    """测试 is_task_approved"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_task_not_approved(self):
        """测试任务未批准"""
        create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="Test")
        assert is_task_approved(self.temp_dir, "t1") is False
    
    def test_task_approved(self):
        """测试任务已批准"""
        review = create_review(self.temp_dir, task_id="t2", reviewer="r1", summary="Test")
        submit_review_result(self.temp_dir, review.id, "approved", "OK")
        assert is_task_approved(self.temp_dir, "t2") is True
    
    def test_task_with_no_reviews(self):
        """测试没有review的任务"""
        assert is_task_approved(self.temp_dir, "nonexistent") is False


class TestDefaultWorkspace:
    """测试默认工作区便捷函数"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
        set_workspace_root(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_review_default(self):
        """测试 create_review_default"""
        review = create_review_default(task_id="t1", reviewer="r1", summary="Test")
        assert review.task_id == "t1"
    
    def test_submit_review_result_default(self):
        """测试 submit_review_result_default"""
        review = create_review_default(task_id="t1", reviewer="r1", summary="Test")
        result = submit_review_result_default(review.id, "approved", summary="OK")
        assert result is not None
        assert result.status == "approved"
    
    def test_list_reviews_default(self):
        """测试 list_reviews_default"""
        create_review_default(task_id="t1", reviewer="r1", summary="")
        reviews = list_reviews_default(status="pending")
        assert len(reviews) == 1
    
    def test_is_task_approved_default(self):
        """测试 is_task_approved_default"""
        assert is_task_approved_default("nonexistent") is False


class TestGetReviewSummary:
    """测试 get_review_summary"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_summary_empty(self):
        """测试空reviews的摘要"""
        summary = get_review_summary(self.temp_dir)
        assert summary["total"] == 0
        # by_status 总是包含所有状态，值为0
        assert summary["by_status"]["pending"] == 0
        assert summary["by_status"]["approved"] == 0
        assert summary["by_status"]["changes_requested"] == 0
    
    def test_summary_with_reviews(self):
        """测试有reviews的摘要"""
        r1 = create_review(self.temp_dir, task_id="t1", reviewer="r1", summary="")
        create_review(self.temp_dir, task_id="t2", reviewer="r2", summary="")
        submit_review_result(self.temp_dir, r1.id, "approved", "OK")
        
        summary = get_review_summary(self.temp_dir)
        assert summary["total"] == 2
        assert summary["by_status"]["pending"] == 1
        assert summary["by_status"]["approved"] == 1


class TestSindrisIntegration:
    """测试与sindris集成的便捷函数"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_action_review(self):
        """测试为sindris动作创建review"""
        review = create_action_review(
            self.temp_dir,
            action_id="action-001",
            action_name="implement_feature_x",
            reviewer="Reviewer"
        )
        assert review.task_id == "action-001"
        assert review.reviewer == "Reviewer"
        assert review.status == "pending"
    
    def test_approve_action(self):
        """测试批准sindris动作"""
        review = create_action_review(
            self.temp_dir, action_id="act-001", action_name="test"
        )
        result = approve_action(self.temp_dir, "act-001", notes=["LGTM"])
        assert result is not None
        assert result.status == "approved"
    
    def test_approve_action_not_found(self):
        """测试批准不存在的动作"""
        result = approve_action(self.temp_dir, "nonexistent")
        assert result is None
    
    def test_request_changes_for_action(self):
        """测试要求动作修改"""
        review = create_action_review(
            self.temp_dir, action_id="act-002", action_name="test"
        )
        result = request_changes_for_action(
            self.temp_dir,
            "act-002",
            change_notes=["Please fix the bug", "Update tests"]
        )
        assert result is not None
        assert result.status == "changes_requested"
    
    def test_request_changes_for_action_not_found(self):
        """测试对不存在的动作请求修改"""
        result = request_changes_for_action(
            self.temp_dir,
            "nonexistent",
            change_notes=["Fix it"]
        )
        assert result is None
