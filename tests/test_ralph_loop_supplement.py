#!/usr/bin/env python3
"""
test_ralph_loop_supplement.py - RalphLoop 补充测试

覆盖:
- ralph_loop.py lines 367-368: verify_skill 函数
- ralph_loop.py lines 409-428: if __name__ == "__main__" 测试块
"""

import sys
import os
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ralph_loop import (
    RalphLoop, RalphResult, verify_skill,
    VerificationStatus, RoundState, RoundReport,
)


def test_verify_skill_convenience_function():
    """测试 verify_skill 便捷函数"""
    async def run_test():
        items = [
            {
                "name": "测试通过",
                "description": "这个测试会通过",
                "check_fn": lambda: True,
            },
        ]
        
        result = await verify_skill(
            skill_name="TestSkill",
            verify_items=items,
        )
        
        assert isinstance(result, RalphResult)
        assert result.success == True
        assert result.consecutive_passed >= 3
        return True
    
    success = asyncio.run(run_test())
    assert success


def test_verify_skill_with_execute_fn():
    """测试 verify_skill 带执行函数"""
    async def run_test():
        execute_called = []
        
        async def my_execute(error_feedback=None):
            execute_called.append(True)
        
        items = [
            {
                "name": "验证项1",
                "check_fn": lambda: True,
            },
        ]
        
        result = await verify_skill(
            skill_name="SkillWithExecute",
            verify_items=items,
            execute_fn=my_execute,
        )
        
        assert len(execute_called) >= 1  # execute被调用至少一次
        assert isinstance(result, RalphResult)
        return True
    
    success = asyncio.run(run_test())
    assert success


def test_verify_skill_all_pass():
    """测试 verify_skill 全部验证通过"""
    async def run_test():
        items = [
            {"name": "check1", "check_fn": lambda: True},
            {"name": "check2", "check_fn": lambda: True},
            {"name": "check3", "check_fn": lambda: True},
        ]
        
        result = await verify_skill(
            skill_name="AllPassSkill",
            verify_items=items,
        )
        
        # 3轮连续通过后Ralph会停止
        assert isinstance(result, RalphResult)
        assert result.consecutive_passed >= 1
        return True
    
    success = asyncio.run(run_test())
    assert success


def test_verify_skill_all_fail():
    """测试 verify_skill 全部验证失败"""
    async def run_test():
        items = [
            {"name": "fail1", "check_fn": lambda: False},
            {"name": "fail2", "check_fn": lambda: False},
        ]
        
        result = await verify_skill(
            skill_name="AllFailSkill",
            verify_items=items,
        )
        
        assert isinstance(result, RalphResult)
        # 失败时consecutive_passed应该为0
        assert result.consecutive_passed == 0
        return True
    
    success = asyncio.run(run_test())
    assert success


def test_verify_skill_max_rounds():
    """测试 verify_skill 达到最大轮数"""
    async def run_test():
        items = [
            {"name": "sometimes_fail", "check_fn": lambda: False},  # 永远失败
        ]
        
        result = await verify_skill(
            skill_name="MaxRoundsSkill",
            verify_items=items,
        )
        
        assert isinstance(result, RalphResult)
        # 应该达到最大轮数
        assert result.total_rounds == RalphLoop.MAX_ROUNDS
        return True
    
    success = asyncio.run(run_test())
    assert success


def test_ralph_loop_async_check_fn():
    """测试 RalphLoop 支持异步验证函数"""
    async def run_test():
        async def async_check():
            await asyncio.sleep(0.001)
            return True
        
        items = [
            {"name": "async_check", "check_fn": async_check},
        ]
        
        verifier = RalphLoop(
            task_name="AsyncCheckTask",
            verify_items=items,
        )
        
        result = await verifier.run()
        assert isinstance(result, RalphResult)
        return True
    
    success = asyncio.run(run_test())
    assert success


def test_ralph_result_attributes():
    """测试 RalphResult 包含所有必需属性"""
    async def run_test():
        items = [
            {"name": "check", "check_fn": lambda: True},
        ]
        
        result = await verify_skill("AttrsTest", verify_items=items)
        
        # 检查所有属性都存在
        assert hasattr(result, "success")
        assert hasattr(result, "total_rounds")
        assert hasattr(result, "consecutive_passed")
        assert hasattr(result, "final_report")
        assert hasattr(result, "all_reports")
        assert hasattr(result, "error_feedback")
        
        # final_report应该是RoundReport
        if result.final_report:
            assert hasattr(result.final_report, "round_num")
            assert hasattr(result.final_report, "state")
            assert hasattr(result.final_report, "conclusion")
        
        return True
    
    success = asyncio.run(run_test())
    assert success


def test_print_round_report_with_optimizations():
    """测试 _print_round_report 输出优化建议 (覆盖 lines 367-368)"""
    r = RalphLoop(task_name="优化测试")
    report = RoundReport(
        round_num=1,
        state=RoundState.COMPLETED,
        start_time="2024-01-01T00:00:00",
        end_time="2024-01-01T00:00:01",
        items=[],
        passed_count=1,
        failed_count=0,
        optimizations=["优化1: 使用缓存", "优化2: 减少API调用"],
        conclusion="通过",
    )
    # 不应抛出
    r._print_round_report(report)


if __name__ == "__main__":
    import traceback
    
    tests = [
        test_verify_skill_convenience_function,
        test_verify_skill_with_execute_fn,
        test_verify_skill_all_pass,
        test_verify_skill_all_fail,
        test_verify_skill_max_rounds,
        test_ralph_loop_async_check_fn,
        test_ralph_result_attributes,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            if asyncio.iscoroutinefunction(test):
                asyncio.run(test())
            else:
                test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
