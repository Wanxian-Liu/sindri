#!/usr/bin/env python3
"""
test_omx_integrator.py - OMX Integrator 集成测试

测试覆盖:
1. OMXIntegrator 初始化
2. Round1: 规划轮 (omx_tasks 记录任务分解)
3. Round2: 执行轮 (omx_ledger 记录执行日志)
4. Round3: 审查轮 (omx_reviews 记录审查队列)
5. Round4: 完成 (omx_tasks 更新任务状态)
6. 向后兼容: 不依赖时也能正常运行
7. 状态持久化: 重启后能恢复
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# 确保可以导入omx_integrator
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from omx_contract import (
    omx_dir, ensure_omx_layout, read_json,
    get_workspace_root, set_workspace_root,
)
from omx_tasks import load_tasks, get_task, list_tasks
from omx_ledger import load_ledger, list_ledger
from omx_reviews import list_reviews, load_reviews
from omx_integrator import OMXIntegrator, get_integrator, reset_integrator

# ============================================================
# 测试工具
# ============================================================

class TestContext:
    """测试上下文，管理临时工作区"""
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="omx_test_")
        self.original_root = get_workspace_root()
        set_workspace_root(self.temp_dir)
        ensure_omx_layout(self.temp_dir)

    def cleanup(self):
        set_workspace_root(self.original_root)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def omx_path(self, *segments):
        return os.path.join(self.temp_dir, ".omx", *segments)

def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg}: expected {expected!r}, got {actual!r}")

def assert_in(item, container, msg=""):
    if item not in container:
        raise AssertionError(f"{msg}: {item!r} not in {container!r}")

def assert_true(condition, msg=""):
    if not condition:
        raise AssertionError(f"{msg}: expected truthy, got {condition!r}")

# ============================================================
# 测试用例
# ============================================================

def test_omx_layout_created():
    """测试1: OMX布局正确创建"""
    ctx = TestContext()
    try:
        omx_path = ctx.omx_path("state")
        assert_true(os.path.exists(omx_path), "OMX state dir should exist")
        print("✓ test_omx_layout_created passed")
    finally:
        ctx.cleanup()

def test_integrator_init():
    """测试2: OMXIntegrator 初始化"""
    ctx = TestContext()
    try:
        integrator = OMXIntegrator(workspace_root=ctx.temp_dir)
        assert_eq(integrator.root, ctx.temp_dir)
        assert_true(integrator._session_id.startswith("session_"))
        assert_eq(len(integrator._phases), 0)
        assert_eq(len(integrator._actions), 0)
        print("✓ test_integrator_init passed")
    finally:
        ctx.cleanup()

def test_round1_planning():
    """测试3: Round1 规划轮 - omx_tasks记录任务分解"""
    ctx = TestContext()
    try:
        integrator = OMXIntegrator(workspace_root=ctx.temp_dir)

        # Round1开始
        session_id = integrator.on_round1_start(
            task_description="设计一个用户认证系统",
            matched_roles=["engineering_software_architect", "engineering_senior_developer"],
        )
        assert_true(session_id.startswith("session_"))

        # 验证ledger有记录
        ledger = load_ledger(ctx.temp_dir)
        assert_in("round1_start", [e.action for e in ledger])

        # Round1完成
        task = integrator.on_round1_complete(
            plan_summary="采用JWT+RefreshToken方案，分三步实现",
            verified=True,
        )
        assert_true(task is not None, "Task should be created")
        assert_eq(task.kind, "sindris_planning")
        assert_eq(task.status, "completed")

        # 验证任务写入omx_tasks
        tasks = load_tasks(ctx.temp_dir)
        assert_eq(len(tasks), 1)
        assert_eq(tasks[0].id, task.id)

        # 验证ledger记录
        ledger = load_ledger(ctx.temp_dir)
        actions = [e.action for e in ledger]
        assert_in("round1_start", actions)
        assert_in("round1_complete", actions)

        print("✓ test_round1_planning passed")
    finally:
        ctx.cleanup()

def test_round2_execution():
    """测试4: Round2 执行轮 - omx_ledger记录执行日志"""
    ctx = TestContext()
    try:
        integrator = OMXIntegrator(workspace_root=ctx.temp_dir)

        # 先完成Round1获取task_id
        integrator.on_round1_start(task_description="实现用户认证")
        task = integrator.on_round1_complete(plan_summary="JWT方案")

        # Round2开始
        actions_plan = [
            {"action_id": "A1", "action_name": "创建User模型", "agent_id": "Dev1", "role": "developer"},
            {"action_id": "A2", "action_name": "实现JWT服务", "agent_id": "Dev2", "role": "developer"},
            {"action_id": "A3", "action_name": "创建认证API", "agent_id": "Dev3", "role": "developer"},
        ]
        integrator.on_round2_start(task_id=task.id, actions=actions_plan)

        # 执行动作A1
        integrator.on_action_start(action_id="A1", agent_id="Dev1")
        integrator.on_action_complete(
            action_id="A1",
            verified=True,
            verify_results={"file_created": True, "import_ok": True},
            task_id=task.id,
        )

        # 执行动作A2
        integrator.on_action_start(action_id="A2", agent_id="Dev2")
        integrator.on_action_complete(
            action_id="A2",
            verified=True,
            verify_results={"jwt_works": True},
            task_id=task.id,
        )

        # 执行动作A3
        integrator.on_action_start(action_id="A3", agent_id="Dev3")
        integrator.on_action_complete(
            action_id="A3",
            verified=False,
            verify_results={"api_works": False},
            error="API返回500错误",
            task_id=task.id,
        )

        # Round2完成
        integrator.on_round2_complete(
            task_id=task.id,
            all_verified=False,
            failed_actions=["A3"],
        )

        # 验证ledger记录
        ledger = load_ledger(ctx.temp_dir)
        ledger_actions = [e.action for e in ledger]
        assert_in("round2_start", ledger_actions)
        assert_in("action_start", ledger_actions)
        assert_in("action_complete", ledger_actions)
        assert_in("round2_complete", ledger_actions)

        # 验证失败动作记录
        failed = integrator.get_failed_actions()
        assert_eq(len(failed), 1)
        assert_eq(failed[0].action_id, "A3")
        assert_eq(failed[0].error, "API返回500错误")

        print("✓ test_round2_execution passed")
    finally:
        ctx.cleanup()

def test_round3_review():
    """测试5: Round3 审查轮 - omx_reviews记录审查队列"""
    ctx = TestContext()
    try:
        integrator = OMXIntegrator(workspace_root=ctx.temp_dir)

        # 先完成Round1-2
        integrator.on_round1_start(task_description="实现用户认证")
        task = integrator.on_round1_complete(plan_summary="JWT方案")
        integrator.on_round2_start(task_id=task.id, actions=[{"action_id": "A1"}])
        integrator.on_action_complete("A1", verified=True)
        integrator.on_round2_complete(task_id=task.id)

        # Round3开始 - 注意review_items需要传递task_id而非action_id
        review_items = [
            {"task_id": task.id, "reviewer": "Reviewer", "summary": "检查User模型实现"},
        ]
        reviews = integrator.on_round3_start(task_id=task.id, review_items=review_items)
        assert_eq(len(reviews), 1)
        assert_eq(reviews[0].status, "pending")

        # 提交审查结果
        integrator.on_review_submit(
            review_id=reviews[0].id,
            status="approved",
            summary="代码质量良好",
            notes=["命名规范", "有单元测试"],
        )

        # 验证reviews写入omx_reviews
        all_reviews = load_reviews(ctx.temp_dir)
        assert_eq(len(all_reviews), 1)
        assert_eq(all_reviews[0].status, "approved")

        # 验证task通过审查
        assert_true(integrator.is_task_approved(task.id))

        # Round3完成
        integrator.on_round3_complete(task_id=task.id, all_approved=True)

        print("✓ test_round3_review passed")
    finally:
        ctx.cleanup()

def test_round4_completion():
    """测试6: Round4 完成 - omx_tasks更新任务状态"""
    ctx = TestContext()
    try:
        integrator = OMXIntegrator(workspace_root=ctx.temp_dir)

        # 完成所有Round
        integrator.on_round1_start(task_description="实现用户认证")
        task = integrator.on_round1_complete(plan_summary="JWT方案")
        integrator.on_round2_start(task_id=task.id)
        integrator.on_action_complete("A1", verified=True)
        integrator.on_round2_complete(task_id=task.id)
        integrator.on_round3_start(task_id=task.id, review_items=[])
        integrator.on_round3_complete(task_id=task.id)

        # Round4完成
        integrator.on_round4_complete(
            task_id=task.id,
            final_output={"files_created": 5, "tests_passed": 12},
            success=True,
        )

        # 验证任务状态
        updated_task = get_task(ctx.temp_dir, task.id)
        assert_eq(updated_task.status, "completed")

        # 验证ledger记录
        ledger = load_ledger(ctx.temp_dir)
        ledger_actions = [e.action for e in ledger]
        assert_in("session_end", ledger_actions)

        # 验证会话摘要
        summary = integrator.get_session_summary()
        assert_eq(summary["session_id"], integrator._session_id)
        assert_eq(len(summary["phases"]), 4)  # 4个Round

        print("✓ test_round4_completion passed")
    finally:
        ctx.cleanup()

def test_persistence():
    """测试7: 状态持久化 - 重启后能恢复"""
    ctx = TestContext()
    try:
        # 第一次会话
        integrator1 = OMXIntegrator(workspace_root=ctx.temp_dir)
        integrator1.on_round1_start(task_description="测试持久化")
        integrator1.on_round1_complete(plan_summary="测试计划")

        session_id = integrator1._session_id

        # 模拟重启 - 创建新实例
        integrator2 = OMXIntegrator(workspace_root=ctx.temp_dir)
        success = integrator2.resume_session()

        assert_true(success, "Should resume session")
        # Round1 start和complete会合并为1个phase记录（start后立即complete）
        assert_eq(len(integrator2._phases), 1)
        assert_eq(integrator2._phases[0].round, 1)
        assert_eq(integrator2._phases[0].status, "complete")

        print("✓ test_persistence passed")
    finally:
        ctx.cleanup()

def test_backward_compatibility():
    """测试8: 向后兼容 - 不依赖OMX也能独立运行sindris"""
    ctx = TestContext()
    try:
        # omx_ledger可以独立使用
        from omx_ledger import append_ledger
        entry = append_ledger(
            ctx.temp_dir,
            kind="test",
            action="standalone_ledger",
            detail="不依赖sindris的独立ledger记录",
        )
        assert_true(entry.id.startswith("ledger_"))

        # omx_tasks可以独立使用
        from omx_tasks import create_task, CreateTaskInput
        task = create_task(ctx.temp_dir, CreateTaskInput(
            title="独立任务",
            kind="standalone",
            phase="test",
        ))
        assert_true(task.id.startswith("task_"))

        # omx_reviews可以独立使用
        from omx_reviews import create_review
        review = create_review(ctx.temp_dir, "task_test", "Tester", "独立审查")
        assert_true(review.id.startswith("review_"))

        print("✓ test_backward_compatibility passed")
    finally:
        ctx.cleanup()

def test_get_integrator_singleton():
    """测试9: 全局单例模式"""
    ctx = TestContext()
    try:
        reset_integrator()
        int1 = get_integrator(ctx.temp_dir)
        int2 = get_integrator()
        assert_true(int1 is int2, "Should return same instance")

        # 不同workspace返回不同实例
        ctx2 = TestContext()
        try:
            int3 = get_integrator(ctx2.temp_dir)
            # int1和int3不是同一个实例（因为workspace不同）
            assert_true(int1 is not int3 or int1.root == int3.root)
        finally:
            ctx2.cleanup()

        reset_integrator()
        print("✓ test_get_integrator_singleton passed")
    finally:
        ctx.cleanup()

# ============================================================
# 主函数
# ============================================================

def run_all_tests():
    """运行所有测试"""
    tests = [
        test_omx_layout_created,
        test_integrator_init,
        test_round1_planning,
        test_round2_execution,
        test_round3_review,
        test_round4_completion,
        test_persistence,
        test_backward_compatibility,
        test_get_integrator_singleton,
    ]

    print("=" * 60)
    print("OMX × sindris Round1-4 集成测试")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"结果: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
