#!/usr/bin/env python3
"""sindris_executor 输入与任务类型识别边界测试。"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sindris_executor import SindrisExecutor


@pytest.fixture
def executor(tmp_path):
    return SindrisExecutor(workspace_root=str(tmp_path))


def test_identify_task_type_repair_role_not_fix(executor):
    """「修复角色」应归为 role_improvement，避免被「修复」误判为 fix。"""
    assert executor._identify_task_type("修复角色：补齐触发词") == "role_improvement"


def test_identify_task_type_none_and_empty(executor):
    assert executor._identify_task_type(None) == "other"
    assert executor._identify_task_type("") == "other"
    assert executor._identify_task_type("   ") == "other"


def test_mark_subtask_started_records_trace_context(executor):
    subtask = {
        "task_id": "st_1",
        "role": "Developer",
        "_trace_id": "trace_abc",
        "_run_id": "run_123",
        "_child_session_key": "child_xyz",
    }
    executor.mark_subtask_started(subtask, session_key="legacy_session")

    summary = executor.get_execution_summary()
    assert summary["states"]["st_1"]["trace"]["trace_id"] == "trace_abc"
    assert summary["states"]["st_1"]["trace"]["run_id"] == "run_123"
    assert summary["states"]["st_1"]["session"] == "child_xyz"


def test_record_spawn_result_uses_openclaw_fields(executor):
    executor.record_spawn_result(
        task_id="st_spawn",
        trace_id="trace_spawn",
        run_id="run_456",
        child_session_key="child_456",
        context="fork",
    )

    summary = executor.get_execution_summary()
    trace_meta = summary["states"]["st_spawn"]["trace"]
    assert trace_meta["trace_id"] == "trace_spawn"
    assert trace_meta["run_id"] == "run_456"
    assert trace_meta["child_session_key"] == "child_456"
    assert trace_meta["context"] == "fork"
    assert summary["trace_runtime"]["trace_spawn"]["spawns"] == 1


def test_record_yield_boundary_counts(executor):
    executor.record_yield_boundary(trace_id="trace_y", phase="before_yield")
    executor.record_yield_boundary(trace_id="trace_y", phase="after_yield")
    summary = executor.get_execution_summary()
    assert summary["trace_runtime"]["trace_y"]["yields"] == 2


@pytest.mark.anyio
async def test_plan_rejects_none_and_empty(executor):
    r = await executor.plan(None)
    assert r["success"] is False
    assert "空" in r.get("error", "")

    r2 = await executor.plan("")
    assert r2["success"] is False


@pytest.mark.anyio
async def test_execute_emits_trace_id_and_propagates_to_actions(executor):
    fake_plan = {
        "success": True,
        "subtasks": [
            {"task_id": "a1", "title": "Task A", "role": "Developer"},
            {"task_id": "a2", "title": "Task B", "role": "QA"},
        ],
    }

    async def _fake_plan(task, team=None):  # noqa: ANN001
        return fake_plan

    executor.plan = _fake_plan
    executor.omx._last_task_id = "omx_task_1"
    executor.omx.on_round2_start = lambda task_id, actions: None
    executor.omx.on_action_start = lambda action_id: None

    result = await executor.execute("test task")

    assert result["_execution_mode"] == "manual_spawn"
    assert result["_trace_id"].startswith("trace_")
    assert all(a["trace_id"] == result["_trace_id"] for a in result["_omx_actions"])
    assert all(s["_trace_id"] == result["_trace_id"] for s in result["subtasks"])
