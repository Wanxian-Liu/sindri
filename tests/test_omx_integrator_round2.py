#!/usr/bin/env python3
"""
test_omx_integrator_round2.py - omx_integrator Round2测试
覆盖: on_round2_start, on_round1_complete elif分支, _load_phases, _load_actions
"""

import sys
import os
import tempfile
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


class TestOnRound2Start:
    """测试on_round2_start方法"""

    def test_round2_start_basic(self):
        """覆盖on_round2_start基本功能"""
        from omx_integrator import OMXIntegrator, RoundPhase

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch.object(integrator, '_save_phases'), \
                 patch.object(integrator, '_save_actions'), \
                 patch('omx_integrator.append_ledger'):

                session_id = integrator.on_round2_start(
                    task_id="task1",
                    actions=[{"action_id": "a1", "action_name": "do thing"}]
                )

                assert session_id == integrator._session_id
                assert len(integrator._phases) == 1
                assert integrator._phases[0].round == 2
                assert integrator._phases[0].phase == "execution"
                assert integrator._phases[0].status == "start"
                assert len(integrator._actions) == 1
                assert integrator._actions[0].action_id == "a1"

    def test_round2_start_multiple_actions(self):
        """覆盖on_round2_start多个actions"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch.object(integrator, '_save_phases'), \
                 patch.object(integrator, '_save_actions'), \
                 patch('omx_integrator.append_ledger'):

                actions = [
                    {"action_id": "a1", "action_name": "task 1", "agent_id": "agent1", "role": "dev"},
                    {"action_id": "a2", "action_name": "task 2", "agent_id": "agent2", "role": "reviewer"},
                ]
                integrator.on_round2_start(task_id="task1", actions=actions)

                assert len(integrator._actions) == 2
                assert integrator._actions[0].role == "dev"
                assert integrator._actions[1].agent_id == "agent2"

    def test_round2_start_no_actions(self):
        """覆盖on_round2_start无actions"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch.object(integrator, '_save_phases'), \
                 patch.object(integrator, '_save_actions'), \
                 patch('omx_integrator.append_ledger'):

                session_id = integrator.on_round2_start(task_id="task1")

                assert session_id == integrator._session_id
                assert len(integrator._phases) == 1
                assert integrator._phases[0].output == {"actions": []}
                assert len(integrator._actions) == 0


class TestOnRound1CompleteElifBranch:
    """测试on_round1_complete的elif plan_summary分支（无phase_task_id时）"""

    def test_round1_complete_fallback_creates_task(self):
        """覆盖无phase_task_id但有plan_summary时创建后备task"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.create_task') as mock_create, \
                 patch('omx_integrator.append_ledger') as mock_ledger, \
                 patch.object(integrator, '_save_phases'):

                mock_task = MagicMock()
                mock_task.id = "fallback_task_id"
                mock_create.return_value = mock_task

                # 不添加任何phase，这样phase_task_id永远为None
                result = integrator.on_round1_complete(
                    plan_summary="This is a test plan summary",
                    verified=True
                )

                # create_task应该被调用（后备分支）
                mock_create.assert_called_once()
                call_args = mock_create.call_args
                assert call_args[0][0] == tmpdir  # root
                task_input = call_args[0][1]
                assert task_input.kind == "sindris_plan"
                assert task_input.phase == "round1"
                assert "test plan" in task_input.title
                assert result is mock_task

    def test_round1_complete_no_phase_no_summary_returns_none(self):
        """覆盖既无phase也无plan_summary的情况"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.append_ledger') as mock_ledger, \
                 patch.object(integrator, '_save_phases'):

                result = integrator.on_round1_complete(
                    plan_summary="",
                    verified=True
                )

                # 既没有phase_task_id也没有plan_summary可创建后备，返回None
                assert result is None


class TestLoadPhasesAndActions:
    """测试_load_phases和_load_actions方法"""

    def test_load_phases_with_data(self):
        """覆盖_load_phases从磁盘加载"""
        from omx_integrator import OMXIntegrator, RoundPhase

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            # 先创建一个phase保存
            phase = RoundPhase(round=1, phase="planning", status="start")
            integrator._phases.append(phase)
            integrator._save_phases()

            # 重新创建integrator加载
            integrator2 = OMXIntegrator(workspace_root=tmpdir)
            loaded = integrator2._load_phases()

            assert len(loaded) == 1
            assert loaded[0].round == 1
            assert loaded[0].phase == "planning"

    def test_load_actions_with_data(self):
        """覆盖_load_actions从磁盘加载"""
        from omx_integrator import OMXIntegrator, ActionRecord

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            # 先创建action保存
            action = ActionRecord(
                action_id="test_action",
                action_name="Test",
                agent_id="agent1",
                role="dev",
                status="pending"
            )
            integrator._actions.append(action)
            integrator._save_actions()

            # 重新创建integrator加载
            integrator2 = OMXIntegrator(workspace_root=tmpdir)
            loaded = integrator2._load_actions()

            assert len(loaded) == 1
            assert loaded[0].action_id == "test_action"
            assert loaded[0].role == "dev"


class TestOnRound1StartWithTaskId:
    """测试on_round1_start的task_id分支"""

    def test_round1_start_with_existing_task(self):
        """覆盖on_round1_start传入已有task_id"""
        from omx_integrator import OMXIntegrator

        with tempfile.TemporaryDirectory() as tmpdir:
            integrator = OMXIntegrator(workspace_root=tmpdir)

            with patch('omx_integrator.get_task') as mock_get, \
                 patch.object(integrator, '_save_phases'), \
                 patch('omx_integrator.append_ledger'):

                mock_task = MagicMock()
                mock_task.id = "existing_task"
                mock_get.return_value = mock_task

                session_id = integrator.on_round1_start(
                    task_description="Test task",
                    task_id="existing_task",
                    matched_roles=["developer"]
                )

                # get_task应该被调用
                mock_get.assert_called_once_with(tmpdir, "existing_task")
