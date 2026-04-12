"""
Tests for uncovered __main__ blocks and CLI entry points.
Coverage targets:
  - circuit_breaker.py lines 362-394 (__main__ test block)
  - match_roles.py lines 294-326 (CLI at bottom of file)
  - ralph_loop.py lines 409-428 (__main__ test block)
"""
import os
import subprocess
import sys
import pytest


SINDRI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCircuitBreakerMainBlock:
    """Cover circuit_breaker.py __main__ block (lines 362-394)"""

    def test_main_runs_without_error(self):
        """Run circuit_breaker.py __main__ block inline"""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, 'scripts')
from circuit_breaker import (
    get_all_circuits_status, get_circuit_status,
    CircuitBreaker, ROLE_TIMEOUTS
)

print("=== CircuitBreaker 测试 ===")
print("角色超时配置:")
for role, timeout in ROLE_TIMEOUTS.items():
    print(f"  {role}: {timeout}s")

cb = CircuitBreaker("developer")
print(f"创建 developer 熔断器: state={cb.state.value}, timeout={cb.timeout}s, failures={cb.failures}")

print("测试状态转换:")
for i in range(6):
    cb.record_failure()
    print(f"  failure #{i+1}: state={cb.state.value}, failures={cb.failures}")

print("测试半开恢复:")
cb._transition_to_half_open()
print(f"  转换到半开: state={cb.state.value}")
for i in range(3):
    cb.record_success()
    print(f"  success #{i+1}: state={cb.state.value}")

print("熔断器状态:")
status = get_circuit_status("developer")
for k, v in status.items():
    print(f"  {k}: {v}")

all_status = get_all_circuits_status()
print(f"所有熔断器: {list(all_status.keys())}")
"""],
            cwd="scripts",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = result.stdout
        assert "=== CircuitBreaker 测试 ===" in output
        assert "developer" in output
        assert "failure #6" in output
        assert "半开" in output or "half" in output.lower()
        assert "state=" in output

    def test_get_all_circuits_status(self):
        """Cover get_all_circuits_status()"""
        import sys
        sys.path.insert(0, "scripts")
        from circuit_breaker import get_all_circuits_status, get_circuit_breaker, reset_circuit
        
        reset_circuit("test-role-all")
        cb = get_circuit_breaker("test-role-all")
        
        status = get_all_circuits_status()
        assert isinstance(status, dict)
        assert "test-role-all" in status
        info = status["test-role-all"]
        assert "state" in info
        assert "failures" in info


class TestMatchRolesCLI:
    """Cover match_roles.py CLI block (lines 294-326)"""
    
    def _run(self, args):
        return subprocess.run(
            [sys.executable, "-m", "scripts.match_roles"] + args,
            cwd=SINDRI_ROOT,
            capture_output=True,
            text=True,
        )

    def test_match_subcommand(self):
        """Test match subcommand"""
        result = self._run(["match", "api", "test"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        import json
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_categories_subcommand(self):
        """Test categories subcommand"""
        result = self._run(["categories"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        import json
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "categories" in data

    def test_get_subcommand_valid_role(self):
        """Test get subcommand with valid role_id"""
        result = self._run(["get", "academic_psychologist"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        import json
        role = json.loads(result.stdout)
        assert "id" in role

    def test_get_subcommand_invalid_role(self):
        """Test get subcommand with invalid role_id"""
        result = self._run(["get", "nonexistent_role_xyz"])
        assert result.returncode == 0
        assert "not found" in result.stdout.lower()

    def test_match_with_categories_filter(self):
        """Test match with --categories filter"""
        result = self._run(["match", "code", "--categories", "developer", "-k", "3"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_match_with_top_k(self):
        """Test match with -k flag"""
        result = self._run(["match", "test", "-k", "1"])
        assert result.returncode == 0, f"stderr: {result.stderr}"


class TestRalphLoopMainBlock:
    """Cover ralph_loop.py __main__ block (lines 409-428)"""

    def test_ralph_loop_main_runs(self):
        """Run ralph_loop.py __main__ async test block"""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
import asyncio
sys.path.insert(0, 'scripts')
from ralph_loop import RalphLoop

async def test():
    items = [
        {"name": "文件存在", "description": "检查文件是否存在", "check_fn": lambda: True},
        {"name": "代码可执行", "description": "检查代码能否执行", "check_fn": lambda: True},
        {"name": "输出正确", "description": "检查输出是否符合预期", "check_fn": lambda: False},
    ]
    verifier = RalphLoop(task_name="测试任务", verify_items=items)
    result = await verifier.run()
    print(f"最终结果: {'通过' if result.success else '未通过'}")
    print(f"total_rounds={result.total_rounds}, consecutive_passed={result.consecutive_passed}")
    return result

r = asyncio.run(test())
print(f"success={r.success}")
"""],
            cwd="scripts",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "最终结果:" in result.stdout
        assert "success=" in result.stdout
