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


@pytest.mark.anyio
async def test_plan_rejects_none_and_empty(executor):
    r = await executor.plan(None)
    assert r["success"] is False
    assert "空" in r.get("error", "")

    r2 = await executor.plan("")
    assert r2["success"] is False
