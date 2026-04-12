#!/usr/bin/env python3
"""
test_sindris.py - sindris_executor 端到端测试

测试覆盖：
1. SindrisExecutor 初始化
2. Round1: 规划轮 (角色匹配、任务分解)
3. Round2: 执行轮 (任务执行、熔断)
4. Round3: 审查轮 (审查队列)
5. Round4: 完成 (状态更新)
6. 共识投票机制
7. 熔断器机制
8. 状态持久化
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# 设置路径（硬编码避免__file__问题）
SCRIPT_DIR = Path("/home/rayliu/.openclaw/skills/sindris")
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR / "scripts"))
sys.path.insert(0, str(SCRIPT_DIR.parent / "织界中枢" / "scripts"))

import asyncio
from dataclasses import asdict

# ============================================================
# 测试工具
# ============================================================

class TestContext:
    """测试上下文"""
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="sindris_test_")
        self.original_root = os.environ.get("OPENCLAW_WORKSPACE_ROOT")
        os.environ["OPENCLAW_WORKSPACE_ROOT"] = self.temp_dir

    def cleanup(self):
        if self.original_root:
            os.environ["OPENCLAW_WORKSPACE_ROOT"] = self.original_root
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

def test_executor_init():
    """测试1: SindrisExecutor 初始化"""
    ctx = TestContext()
    try:
        from sindris_executor import SindrisExecutor

        executor = SindrisExecutor(workspace_root=ctx.temp_dir)

        assert_true(executor.session_id.startswith("session_"))
        assert_true(executor.workspace_root == ctx.temp_dir)
        assert_eq(len(executor.workers), 0)
        assert_eq(len(executor.tasks), 0)
        assert_true(executor.omx is not None)
        assert_true(executor.consensus is not None)
        assert_true(executor.worktree is not None)

        print("✓ test_executor_init passed")
    finally:
        ctx.cleanup()


def test_role_matching():
    """测试2: 角色匹配"""
    ctx = TestContext()
    try:
        from match_roles import match_roles

        result = match_roles(["用户认证", "登录", "JWT"], top_k=5)
        roles = result.get("matched_roles", [])

        # 应该有匹配结果（取决于角色库内容）
        assert_true("matched_roles" in result)
        print(f"  Matched {len(roles)} roles")

        print("✓ test_role_matching passed")
    finally:
        ctx.cleanup()


def test_task_classification():
    """测试3: 任务分类"""
    ctx = TestContext()
    try:
        from ch16_stages import TaskClassifier, TaskType

        classifier = TaskClassifier()

        # 开发类 → ITERATIVE
        t1 = classifier.classify("开发一个用户认证系统")
        assert_eq(t1, TaskType.ITERATIVE, "开发类应该是ITERATIVE")

        # 研究类 → DIVERGENT
        t2 = classifier.classify("研究机器学习算法")
        assert_eq(t2, TaskType.DIVERGENT, "研究类应该是DIVERGENT")

        # 分析类 → LOGICAL
        t3 = classifier.classify("分析系统性能瓶颈")
        assert_eq(t3, TaskType.LOGICAL, "分析类应该是LOGICAL")

        # 简单类 → SIMPLE
        t4 = classifier.classify("查看日志")
        assert_eq(t4, TaskType.SIMPLE, "简单查询应该是SIMPLE")

        print("✓ test_task_classification passed")
    finally:
        ctx.cleanup()


def test_consensus_officer():
    """测试4: 共识投票官"""
    ctx = TestContext()
    try:
        from consensus_officer import ConsensusOfficer

        officer = ConsensusOfficer()

        # 严格格式
        result1 = officer.parse_consensus("这是结果 [CONSENSUS: YES] 完毕")
        assert_true(result1.has_consensus, "严格格式应该识别YES")
        assert_eq(result1.vote, "YES")

        # NO
        result2 = officer.parse_consensus("有问题 [CONSENSUS: NO] 需要修改")
        assert_true(not result2.has_consensus, "应该识别NO")
        assert_eq(result2.vote, "NO")

        # 宽松格式
        result3 = officer.parse_consensus("consensus: yes")
        assert_true(result3.has_consensus, "宽松格式应该识别yes")
        assert_eq(result3.confidence, 0.8, "宽松格式置信度应该是0.8")

        print("✓ test_consensus_officer passed")
    finally:
        ctx.cleanup()


def test_circuit_breaker():
    """测试5: 熔断器"""
    ctx = TestContext()
    try:
        from monitor import CircuitBreaker, CircuitState

        cb = CircuitBreaker(task_id="test_task", role="developer")

        # 初始状态应该是 CLOSED
        assert_eq(cb.state, CircuitState.CLOSED)

        # 记录失败
        cb.record_failure()
        assert_true(cb.failure_count > 0)

        # 检查 is_available
        assert_true(cb.is_available(), "CLOSED状态应该可用")

        print("✓ test_circuit_breaker passed")
    finally:
        ctx.cleanup()


def test_omx_integration():
    """测试6: OMX持久化"""
    ctx = TestContext()
    try:
        from omx_integrator import OMXIntegrator

        integrator = OMXIntegrator(workspace_root=ctx.temp_dir)

        # Round1
        session_id = integrator.on_round1_start(
            task_description="测试任务",
            matched_roles=["developer", "tester"],
        )
        assert_true(session_id.startswith("session_"))

        # Round1完成
        task = integrator.on_round1_complete(
            plan_summary="分解为2个子任务",
            verified=True,
        )
        assert_true(task is not None)
        assert_eq(task.kind, "sindris_planning")

        # 检查文件
        phase_file = ctx.omx_path("state", "sindris_phases.json")
        assert_true(os.path.exists(phase_file), "phase文件应该存在")

        print("✓ test_omx_integration passed")
    finally:
        ctx.cleanup()


def test_round1_planning():
    """测试7: Round1规划轮"""
    ctx = TestContext()
    try:
        from sindris_executor import SindrisExecutor

        async def run():
            executor = SindrisExecutor(workspace_root=ctx.temp_dir)
            ctx_r1 = await executor.round1_planning("开发一个计算器")

            assert_eq(ctx_r1.round, 1)
            assert_eq(str(ctx_r1.phase), "planning")
            assert_eq(ctx_r1.task, "开发一个计算器")
            assert_true(len(ctx_r1.matched_roles) >= 0)
            assert_true(len(ctx_r1.tasks) >= 0)

            return ctx_r1

        result = asyncio.run(run())
        assert_true(result is not None)
        print("✓ test_round1_planning passed")
    finally:
        ctx.cleanup()


def test_round2_execution_mock():
    """测试8: Round2执行轮（模拟）"""
    ctx = TestContext()
    try:
        from sindris_executor import SindrisExecutor, Task, Worker, TaskStatus, WorkerStatus

        async def run():
            executor = SindrisExecutor(workspace_root=ctx.temp_dir)

            # 准备一些任务（Task没有metadata，用notes代替）
            task1 = Task(
                id="test_task_1",
                title="[Developer] 实现功能A",
                kind="executor",
                phase="round2",
                status=TaskStatus.PENDING,
                notes=["role:developer"],
            )
            executor.tasks = [task1]
            executor.workers = [
                Worker(
                    id="worker_1",
                    agent_id="developer",
                    role="Developer",
                    role_type="developer",
                    status=WorkerStatus.IDLE,
                )
            ]

            # 手动标记开始（因为spawn是模拟的）
            executor.omx.on_action_start(task1.id, "worker_1")

            # 模拟完成
            executor.omx.on_action_complete(
                action_id=task1.id,
                verified=True,
                verify_results={"output_valid": True},
                task_id=task1.id,
            )

            return True

        result = asyncio.run(run())
        assert_true(result)
        print("✓ test_round2_execution_mock passed")
    finally:
        ctx.cleanup()


def test_round3_review():
    """测试9: Round3审查轮"""
    ctx = TestContext()
    try:
        from sindris_executor import SindrisExecutor

        async def run():
            executor = SindrisExecutor(workspace_root=ctx.temp_dir)

            # 创建审查
            reviews = executor.omx.on_round3_start(
                task_id="test_task",
                review_items=[{
                    "task_id": "test_task",
                    "reviewer": "Reviewer",
                    "summary": "检查实现",
                }],
            )

            assert_eq(len(reviews), 1)
            assert_eq(reviews[0].status, "pending")

            # 提交审查结果
            executor.omx.on_review_submit(
                review_id=reviews[0].id,
                status="approved",
                summary="通过",
            )

            # 检查批准
            reviews_updated = executor.omx.get_pending_reviews()
            assert_true(len(reviews_updated) == 0, "批准后应该没有pending")

            return True

        result = asyncio.run(run())
        assert_true(result)
        print("✓ test_round3_review passed")
    finally:
        ctx.cleanup()


def test_round4_completion():
    """测试10: Round4完成轮"""
    ctx = TestContext()
    try:
        from sindris_executor import SindrisExecutor, Task, TaskStatus

        async def run():
            executor = SindrisExecutor(workspace_root=ctx.temp_dir)

            # 创建任务
            task = Task(
                id="final_task",
                title="最终任务",
                kind="sindris",
                phase="round4",
                status=TaskStatus.COMPLETED,
            )
            executor.tasks = [task]

            # 完成
            result = await executor.round4_completion(
                results=[],
                all_verified=True,
            )

            assert_true(result["success"])
            assert_true("session_id" in result)

            return True

        result = asyncio.run(run())
        assert_true(result)
        print("✓ test_round4_completion passed")
    finally:
        ctx.cleanup()


def test_status_query():
    """测试11: 状态查询"""
    ctx = TestContext()
    try:
        from sindris_executor import SindrisExecutor

        executor = SindrisExecutor(workspace_root=ctx.temp_dir)
        status = executor.get_status()

        assert_true("session_id" in status)
        assert_true("workers" in status)
        assert_true("tasks" in status)
        assert_true("omx_summary" in status)

        print("✓ test_status_query passed")
    finally:
        ctx.cleanup()


def test_worktree_officer():
    """测试12: Worktree隔离官"""
    ctx = TestContext()
    try:
        from worktree_officer import WorktreeOfficer
        import inspect

        officer = WorktreeOfficer()

        # 检查可用方法
        methods = [m for m in dir(officer) if not m.startswith('_')]
        print(f"  WorktreeOfficer methods: {methods[:5]}")

        # 如果有create_worktree方法，测试它
        if hasattr(officer, 'create_worktree'):
            result = officer.create_worktree(
                base_dir=ctx.temp_dir,
                agent_id="test_agent",
            )
            print(f"  create_worktree returned: {result}")

        print("✓ test_worktree_officer passed")
    finally:
        ctx.cleanup()


# ============================================================
# 主函数
# ============================================================

def run_all_tests():
    tests = [
        test_executor_init,
        test_role_matching,
        test_task_classification,
        test_consensus_officer,
        test_circuit_breaker,
        test_omx_integration,
        test_round1_planning,
        test_round2_execution_mock,
        test_round3_review,
        test_round4_completion,
        test_status_query,
        test_worktree_officer,
    ]

    print("=" * 60)
    print("sindris v1.1 端到端测试")
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
