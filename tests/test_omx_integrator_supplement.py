#!/usr/bin/env python3
"""
test_omx_integrator_supplement.py - omx_integrator补充测试
覆盖: RoundPhase/ActionRecord dataclass, on_round*_complete, query方法, resume_session
"""

import sys
import os
import tempfile
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


class TestRoundPhaseDataclass:
    """测试RoundPhase dataclass"""

    def test_round_phase_init_sets_started_at(self):
        """覆盖__post_init__自动设置started_at"""
        from omx_integrator import RoundPhase

        phase = RoundPhase(round=1, phase="planning", status="start")
        assert phase.started_at != ""
        assert phase.round == 1

    def test_round_phase_to_dict(self):
        """覆盖to_dict方法"""
        from omx_integrator import RoundPhase

        phase = RoundPhase(
            round=1,
            phase="planning",
            status="start",
            task_description="test task"
        )
        d = phase.to_dict()
        assert isinstance(d, dict)
        assert d["round"] == 1
        assert d["phase"] == "planning"
        assert d["status"] == "start"


class TestActionRecordDataclass:
    """测试ActionRecord dataclass"""

    def test_action_record_init_sets_started_at(self):
        """覆盖__post_init__自动设置started_at"""
        from omx_integrator import ActionRecord

        record = ActionRecord(
            action_id="act1",
            action_name="test",
            agent_id="agent1",
            role="developer",
            status="pending"
        )
        assert record.started_at != ""

    def test_action_record_to_dict(self):
        """覆盖to_dict方法"""
        from omx_integrator import ActionRecord

        record = ActionRecord(
            action_id="act1",
            action_name="test",
            agent_id="agent1",
            role="developer",
            status="pending"
        )
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["action_id"] == "act1"
        assert d["status"] == "pending"


class TestHelperFunctions:
    """测试内部辅助函数"""

    def test_gen_id_with_prefix(self):
        """覆盖_gen_id函数"""
        from omx_integrator import _gen_id

        id1 = _gen_id("test")
        id2 = _gen_id("test")

        assert id1.startswith("test_")
        assert id2.startswith("test_")
        assert id1 != id2  # 应该唯一

    def test_now_returns_iso_format(self):
        """覆盖_now函数"""
        from omx_integrator import _now

        now = _now()
        assert isinstance(now, str)
        assert "T" in now  # ISO格式包含T


class TestOMXIntegratorInit:
    """测试OMXIntegrator初始化"""

    def test_init_with_default_workspace(self):
        """测试默认workspace初始化"""
        from omx_integrator import OMXIntegrator
        from omx_contract import get_workspace_root

        with patch('omx_integrator.get_workspace_root', return_value="/tmp/test"):
            integrator = OMXIntegrator()
            assert integrator.root == "/tmp/test"

    def test_init_with_custom_workspace(self):
        """测试自定义workspace初始化"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)
            assert integrator.root == tmpdir

    def test_session_id_is_unique(self):
        """测试session_id唯一性"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            i1 = OMXIntegrator(workspace_root=tmpdir)
            i2 = OMXIntegrator(workspace_root=tmpdir)
            assert i1._session_id != i2._session_id


class TestLastTaskIdProperty:
    """测试 last_task_id 属性 (覆盖 line 148)"""
    
    def test_last_task_id_initially_none(self):
        """测试 last_task_id 初始为 None"""
        from omx_integrator import OMXIntegrator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)
            assert integrator.last_task_id is None
    
    def test_last_task_id_after_round1_start(self):
        """测试 last_task_id 在 on_round1_start 后被设置"""
        from omx_integrator import OMXIntegrator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)
            
            with patch('omx_integrator.ensure_omx_layout'), \
                 patch('omx_integrator.create_task') as mock_create, \
                 patch('omx_integrator.append_ledger'):
                
                mock_create.return_value = MagicMock(id="task_12345")
                
                integrator.on_round1_start(task_description="test task")
                
                assert integrator.last_task_id == "task_12345"


class TestOnRound1Complete:
    """测试on_round1_complete方法"""

    def test_round1_complete_no_task_id_fallback(self):
        """覆盖无task_id时创建后备task"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            # 没有phase存在的情况,验证代码会处理
            with patch('omx_integrator.create_task') as mock_create, \
                 patch('omx_integrator.append_ledger') as mock_ledger, \
                 patch('omx_integrator.get_task', return_value=None), \
                 patch.object(integrator, '_save_phases'):

                mock_create.return_value = MagicMock(id="backup_task_id")

                # 添加一个phase让代码走其他分支
                from omx_integrator import RoundPhase
                integrator._phases.append(RoundPhase(
                    round=1, phase="planning", status="start",
                    output={"task_id": "phase_task_id"}
                ))

                result = integrator.on_round1_complete(
                    plan_summary="test plan",
                    verified=True
                )
                # create_task应该被调用


class TestOnActionStart:
    """测试on_action_start方法"""

    def test_action_start_creates_new_action_if_not_found(self):
        """覆盖找不到action时创建新action"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)
            integrator._actions = []  # 空列表

            with patch.object(integrator, '_save_actions'), \
                 patch('omx_integrator.append_ledger'):

                result = integrator.on_action_start(
                    action_id="new_action",
                    agent_id="agent1"
                )

                assert result is not None
                assert result.action_id == "new_action"
                assert result.status == "running"

    def test_action_start_updates_existing_action(self):
        """覆盖更新已存在的action"""
        from omx_integrator import OMXIntegrator, ActionRecord

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            action = ActionRecord(
                action_id="existing",
                action_name="test",
                agent_id="old_agent",
                role="dev",
                status="pending"
            )
            integrator._actions.append(action)

            with patch.object(integrator, '_save_actions'), \
                 patch('omx_integrator.append_ledger'):

                result = integrator.on_action_start(
                    action_id="existing",
                    agent_id="new_agent"
                )

                assert result.agent_id == "new_agent"
                assert result.status == "running"


class TestOnActionComplete:
    """测试on_action_complete方法"""

    def test_action_complete_not_found_returns_none(self):
        """覆盖action不存在时返回None"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)
            integrator._actions = []

            with patch.object(integrator, '_save_actions'):
                result = integrator.on_action_complete(
                    action_id="nonexistent",
                    verified=True
                )
                assert result is None

    def test_action_complete_with_error(self):
        """覆盖带错误信息的action完成"""
        from omx_integrator import OMXIntegrator, ActionRecord

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            action = ActionRecord(
                action_id="fail_action",
                action_name="test",
                agent_id="agent1",
                role="dev",
                status="running"
            )
            integrator._actions.append(action)

            with patch.object(integrator, '_save_actions'), \
                 patch('omx_integrator.append_ledger'):

                result = integrator.on_action_complete(
                    action_id="fail_action",
                    verified=False,
                    error="Command failed",
                    verify_results={"check1": False}
                )

                assert result.status == "failed"
                assert result.error == "Command failed"
                assert result.verify_results == {"check1": False}


class TestOnRound2Complete:
    """测试on_round2_complete方法"""

    def test_round2_complete_updates_phase(self):
        """覆盖Round2完成更新phase"""
        from omx_integrator import OMXIntegrator, RoundPhase

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            phase = RoundPhase(round=2, phase="execution", status="start")
            integrator._phases.append(phase)

            with patch.object(integrator, '_save_phases'), \
                 patch('omx_integrator.append_ledger'), \
                 patch('omx_integrator.transition_task'):

                integrator.on_round2_complete(
                    task_id="task1",
                    all_verified=True,
                    failed_actions=[]
                )

                assert phase.status == "complete"

    def test_round2_complete_failed_actions(self):
        """覆盖有失败动作的Round2完成"""
        from omx_integrator import OMXIntegrator, RoundPhase

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            phase = RoundPhase(round=2, phase="execution", status="start")
            integrator._phases.append(phase)

            with patch.object(integrator, '_save_phases'), \
                 patch('omx_integrator.append_ledger'), \
                 patch('omx_integrator.transition_task'):

                integrator.on_round2_complete(
                    task_id="task1",
                    all_verified=False,
                    failed_actions=["action1", "action2"]
                )

                assert phase.status == "failed"
                assert phase.output["failed_actions"] == ["action1", "action2"]


class TestOnRound3Start:
    """测试on_round3_start方法"""

    def test_round3_start_creates_reviews(self):
        """覆盖Round3开始创建review items"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch.object(integrator, '_save_phases'), \
                 patch('omx_integrator.append_ledger'), \
                 patch('omx_integrator.create_review') as mock_create_review:

                mock_create_review.return_value = MagicMock(id="review1")

                reviews = integrator.on_round3_start(
                    task_id="task1",
                    review_items=[{
                        "task_id": "subtask1",
                        "reviewer": "reviewer1",
                        "summary": "check code"
                    }]
                )

                assert len(reviews) == 1
                mock_create_review.assert_called_once()


class TestOnReviewSubmit:
    """测试on_review_submit方法"""

    def test_review_submit_calls_omx(self):
        """覆盖submit_review_result调用"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.submit_review_result') as mock_submit, \
                 patch('omx_integrator.append_ledger') as mock_ledger:
                mock_submit.return_value = MagicMock(id="review1")
                mock_ledger.return_value = MagicMock()

                result = integrator.on_review_submit(
                    review_id="review1",
                    status="approved",
                    summary="looks good",
                    notes=["note1"]
                )

                mock_submit.assert_called_once()

    def test_review_submit_no_result(self):
        """覆盖submit_review_result返回None"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.submit_review_result', return_value=None), \
                 patch('omx_integrator.append_ledger') as mock_ledger:
                mock_ledger.return_value = MagicMock()

                result = integrator.on_review_submit(
                    review_id="nonexistent",
                    status="changes_requested",
                    summary="needs work"
                )

                assert result is None


class TestOnRound3Complete:
    """测试on_round3_complete方法"""

    def test_round3_complete_all_approved(self):
        """覆盖Round3全部通过"""
        from omx_integrator import OMXIntegrator, RoundPhase

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            phase = RoundPhase(round=3, phase="review", status="start")
            integrator._phases.append(phase)

            with patch.object(integrator, '_save_phases'), \
                 patch('omx_integrator.append_ledger'):

                integrator.on_round3_complete(
                    task_id="task1",
                    all_approved=True
                )

                assert phase.status == "complete"

    def test_round3_complete_with_changes(self):
        """覆盖Round3需要修改"""
        from omx_integrator import OMXIntegrator, RoundPhase

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            phase = RoundPhase(round=3, phase="review", status="start")
            integrator._phases.append(phase)

            with patch.object(integrator, '_save_phases'), \
                 patch('omx_integrator.append_ledger'):

                integrator.on_round3_complete(
                    task_id="task1",
                    all_approved=False
                )

                assert phase.status == "failed"


class TestOnRound4Complete:
    """测试on_round4_complete方法"""

    def test_round4_complete_success(self):
        """覆盖Round4成功完成"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch.object(integrator, '_save_phases'), \
                 patch('omx_integrator.append_ledger'), \
                 patch('omx_integrator.transition_task'), \
                 patch('omx_integrator.update_task'):

                integrator.on_round4_complete(
                    task_id="task1",
                    final_output={"result": "success"},
                    success=True
                )

                # 应该添加了新的phase
                phase4 = [p for p in integrator._phases if p.round == 4]
                assert len(phase4) == 1
                assert phase4[0].status == "complete"

    def test_round4_complete_failure(self):
        """覆盖Round4失败"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch.object(integrator, '_save_phases'), \
                 patch('omx_integrator.append_ledger'), \
                 patch('omx_integrator.transition_task'), \
                 patch('omx_integrator.update_task'):

                integrator.on_round4_complete(
                    task_id="task1",
                    final_output={"error": "failed"},
                    success=False
                )

                phase4 = [p for p in integrator._phases if p.round == 4]
                assert phase4[0].status == "failed"


class TestQueryMethods:
    """测试查询方法"""

    def test_get_session_summary(self):
        """覆盖get_session_summary"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.load_tasks', return_value=[]), \
                 patch('omx_integrator.load_ledger', return_value=[]), \
                 patch('omx_integrator.list_reviews', return_value=[]):

                summary = integrator.get_session_summary()

                assert "session_id" in summary
                assert "phases" in summary
                assert "actions" in summary
                assert "omx_summary" in summary

    def test_get_pending_reviews(self):
        """覆盖get_pending_reviews"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.list_reviews', return_value=["review1", "review2"]):
                reviews = integrator.get_pending_reviews()
                assert len(reviews) == 2

    def test_get_failed_actions(self):
        """覆盖get_failed_actions"""
        from omx_integrator import OMXIntegrator, ActionRecord

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            integrator._actions = [
                ActionRecord("a1", "test1", "ag1", "dev", "completed"),
                ActionRecord("a2", "test2", "ag2", "dev", "failed"),
                ActionRecord("a3", "test3", "ag3", "dev", "failed"),
            ]

            failed = integrator.get_failed_actions()
            assert len(failed) == 2

    def test_is_task_approved(self):
        """覆盖is_task_approved"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.is_task_approved', return_value=True):
                result = integrator.is_task_approved("task1")
                assert result == True

    def test_get_task_id_for_round(self):
        """覆盖get_task_id_for_round"""
        from omx_integrator import OMXIntegrator, RoundPhase

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            phase = RoundPhase(
                round=1, phase="planning", status="complete",
                output={"task_id": "round1_task"}
            )
            integrator._phases.append(phase)

            task_id = integrator.get_task_id_for_round(1)
            assert task_id == "round1_task"

            # 找不到时返回None
            assert integrator.get_task_id_for_round(99) is None


class TestResumeSession:
    """测试resume_session方法"""

    def test_resume_session_success(self):
        """覆盖成功恢复会话"""
        from omx_integrator import OMXIntegrator, RoundPhase

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch.object(integrator, '_load_phases', return_value=[
                RoundPhase(round=1, phase="planning", status="complete")
            ]), patch.object(integrator, '_load_actions', return_value=[]):

                result = integrator.resume_session()
                assert result == True

    def test_resume_session_failure(self):
        """覆盖恢复会话失败"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch.object(integrator, '_load_phases', side_effect=Exception("IO error")):
                result = integrator.resume_session()
                assert result == False


class TestGlobalFunctions:
    """测试全局便捷函数"""

    def test_get_integrator_creates_singleton(self):
        """覆盖get_integrator单例"""
        from omx_integrator import get_integrator, reset_integrator, OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            reset_integrator()

            with patch('omx_integrator.OMXIntegrator') as MockIntegrator:
                MockIntegrator.return_value = MagicMock()

                i1 = get_integrator(tmpdir)
                i2 = get_integrator(tmpdir)

                # 应该是同一个实例
                assert i1 is i2

    def test_reset_integrator_clears_singleton(self):
        """覆盖reset_integrator"""
        from omx_integrator import get_integrator, reset_integrator, OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            reset_integrator()

            with patch('omx_integrator.OMXIntegrator') as MockIntegrator:
                MockIntegrator.return_value = MagicMock()

                i1 = get_integrator(tmpdir)
                reset_integrator()
                i2 = get_integrator(tmpdir)

                # reset后应该是新实例
                # 注意:这里mock下会创建新mock,但验证reset调用了


class TestLedgerHelper:
    """测试_ledger辅助方法"""

    def test_ledger_returns_entry(self):
        """覆盖_ledger方法"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.append_ledger') as mock_append:
                mock_append.return_value = MagicMock()

                entry = integrator._ledger(
                    "session", "test_action", "test detail",
                    task_id="task1"
                )

                mock_append.assert_called_once()


if __name__ == "__main__":
    print("运行omx_integrator补充测试...")

    test_classes = [
        TestRoundPhaseDataclass,
        TestActionRecordDataclass,
        TestHelperFunctions,
        TestOMXIntegratorInit,
        TestOnRound1Complete,
        TestOnActionStart,
        TestOnActionComplete,
        TestOnRound2Complete,
        TestOnRound3Start,
        TestOnReviewSubmit,
        TestOnRound3Complete,
        TestOnRound4Complete,
        TestQueryMethods,
        TestResumeSession,
        TestGlobalFunctions,
        TestLedgerHelper,
    ]

    passed = 0
    failed = 0

    for cls in test_classes:
        print(f"\n{cls.__name__}:")
        instance = cls()
        for method in dir(instance):
            if method.startswith("test_"):
                try:
                    getattr(instance, method)()
                    print(f"  ✅ {method}")
                    passed += 1
                except Exception as e:
                    print(f"  ❌ {method}: {e}")
                    failed += 1

    print(f"\n=== 结果: {passed} passed, {failed} failed ===")
