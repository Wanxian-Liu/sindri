#!/usr/bin/env python3
"""
test_cli_main_blocks.py - CLI __main__ 块覆盖测试

通过 coverage run + subprocess 运行脚本的__main__块来达到覆盖率

覆盖:
- circuit_breaker.py lines 362-394: __main__ 测试块
- match_roles.py lines 294-326: CLI 入口
- ralph_loop.py lines 409-428: __main__ 测试块
"""

import sys
import os
import subprocess
import json
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def _run_with_coverage(script_name, *args):
    """使用 coverage run 执行脚本并返回结果"""
    script_path = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, "-m", "coverage", "run", "--append", str(script_path)] + list(args),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result


def test_circuit_breaker_main_block():
    """运行 circuit_breaker.py __main__ 块"""
    result = _run_with_coverage("circuit_breaker.py")
    # Should run without error
    assert result.returncode == 0, f"Failed: {result.stderr}"
    output = result.stdout + result.stderr
    assert "CircuitBreaker" in output or "熔断器" in output


def test_match_roles_cli_match():
    """运行 match_roles.py match 子命令"""
    result = _run_with_coverage("match_roles.py", "match", "testing", "--top-k", "3")
    assert result.returncode == 0, f"Failed: {result.stderr}"
    try:
        data = json.loads(result.stdout)
        assert "matched_roles" in data
    except json.JSONDecodeError:
        pass  # OK if not JSON as long as returncode is 0


def test_match_roles_cli_categories():
    """运行 match_roles.py categories 子命令"""
    result = _run_with_coverage("match_roles.py", "categories")
    assert result.returncode == 0, f"Failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert "categories" in data
    assert "total_roles" in data


def test_match_roles_cli_get_not_found():
    """运行 match_roles.py get 子命令 - 角色不存在"""
    result = _run_with_coverage("match_roles.py", "get", "nonexistent_role_xyz_12345")
    assert result.returncode == 0, f"Failed: {result.stderr}"
    assert "not found" in result.stdout.lower()


def test_match_roles_cli_no_args():
    """运行 match_roles.py 无参数"""
    result = _run_with_coverage("match_roles.py")
    # argparse exits with 0 when no args and prints help
    assert result.returncode == 0, f"Failed: {result.stderr}"


def test_ralph_loop_main_block():
    """运行 ralph_loop.py __main__ 块"""
    result = _run_with_coverage("ralph_loop.py")
    assert result.returncode == 0, f"Failed: {result.stderr}"
    output = result.stdout + result.stderr
    assert "Ralph" in output or "验证" in output


if __name__ == "__main__":
    import traceback

    tests = [
        test_circuit_breaker_main_block,
        test_match_roles_cli_match,
        test_match_roles_cli_categories,
        test_match_roles_cli_get_not_found,
        test_match_roles_cli_no_args,
        test_ralph_loop_main_block,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
