#!/usr/bin/env python3
"""
test_supplement_gaps.py - 补充测试覆盖缺口
覆盖:
- circuit_breaker.py: can_execute fallback return False, __main__块
- match_roles.py: CLI __main__块
- omx_contract.py: write_json retry logic
- ralph_loop.py: __main__块
"""

import sys
import os
import time
import subprocess
import tempfile
import json
import fcntl
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


# ============================================================
# circuit_breaker.py gaps
# ============================================================

def test_can_execute_fallback_return_false():
    """覆盖 circuit_breaker.py can_execute fallback return False"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    assert cb.can_execute() == True  # CLOSED
    
    cb.state = CircuitState.OPEN
    cb.last_failure_time = time.time()
    cb.recovery_timeout = 9999
    assert cb.can_execute() == False  # OPEN不恢复
    
    cb.state = CircuitState.HALF_OPEN
    cb.half_open_calls = 0
    cb.half_open_max_calls = 3
    assert cb.can_execute() == True  # HALF_OPEN有额度
    
    # 覆盖fallback: 用非枚举值触发最后的return False
    class FakeState:
        value = "totally_fake"
    cb.state = FakeState()
    result = cb.can_execute()
    assert result == False
    cb.state = CircuitState.CLOSED


def test_circuit_breaker_main_block():
    """覆盖 circuit_breaker.py __main__ 块"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "circuit_breaker.py")],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0


# ============================================================
# match_roles.py CLI gaps
# ============================================================

def test_match_roles_cli_categories():
    """覆盖 match_roles.py categories 子命令"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "match_roles.py"), "categories"],
        capture_output=True, text=True, timeout=10, cwd=str(SCRIPT_DIR)
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "categories" in output or "total_roles" in output


def test_match_roles_cli_match_with_args():
    """覆盖 match_roles.py match 子命令"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "match_roles.py"), 
         "match", "backend", "API", "--top-k", "5"],
        capture_output=True, text=True, timeout=10, cwd=str(SCRIPT_DIR)
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "matched_roles" in output


def test_match_roles_cli_get_role():
    """覆盖 match_roles.py get 子命令"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "match_roles.py"),
         "get", "backend-developer"],
        capture_output=True, text=True, timeout=10, cwd=str(SCRIPT_DIR)
    )
    assert result.returncode == 0 or "not found" in result.stdout.lower()


def test_match_roles_cli_no_args():
    """覆盖 match_roles.py 无参数调用"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "match_roles.py")],
        capture_output=True, text=True, timeout=10, cwd=str(SCRIPT_DIR)
    )
    assert result.returncode == 0


# ============================================================
# omx_contract.py gaps
# ============================================================

def test_write_json_retries_on_io_error():
    """覆盖 omx_contract.py write_json retry逻辑"""
    from omx_contract import write_json
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=True) as f:
        path = f.name
    
    call_count = [0]
    def failing_dump(*args, **kwargs):
        call_count[0] += 1
        raise IOError(f"Failure #{call_count[0]}")
    
    with patch('json.dump', side_effect=failing_dump):
        with patch('fcntl.flock', return_value=None):
            with patch('omx_contract.ensure_dir'):
                try:
                    write_json(path, {"test": 1}, retries=3)
                except IOError as e:
                    assert call_count[0] == 3
                    assert "Failure #3" in str(e)
                    return
    assert False, "Should have raised IOError"


def test_read_json_with_retries_fails():
    """覆盖 read_json retry exhaustion"""
    from omx_contract import read_json
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('not valid json{')
        path = f.name
    
    try:
        result = read_json(path, default="fallback", retries=2)
        assert result == "fallback"
    finally:
        os.unlink(path)


def test_list_omx_dirs():
    """覆盖 omx_contract.py list_omx_dirs"""
    from omx_contract import list_omx_dirs, OMX_LAYOUT_DIRS
    with tempfile.TemporaryDirectory() as tmpdir:
        result = list_omx_dirs(tmpdir)
        assert result == OMX_LAYOUT_DIRS


# ============================================================
# ralph_loop.py gaps
# ============================================================

def test_ralph_loop_main_block():
    """覆盖 ralph_loop.py __main__ 块"""
    result = subprocess.run(
        [sys.executable, "-c", f"""
import sys, asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
from ralph_loop import RalphLoop

async def test():
    items = [
        {{"name": "文件存在", "description": "检查", "check_fn": lambda: True}},
        {{"name": "代码可执行", "description": "检查", "check_fn": lambda: True}},
    ]
    verifier = RalphLoop(task_name="测试任务", verify_items=items)
    result = await verifier.run()
    print(f"RESULT: success={{result.success}}")
    return result

asyncio.run(test())
"""],
        capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0


def test_ralph_loop_verify_skill():
    """覆盖 verify_skill 便捷函数"""
    result = subprocess.run(
        [sys.executable, "-c", f"""
import sys, asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
from ralph_loop import verify_skill

async def test():
    items = [{{"name": "检查", "description": "check", "check_fn": lambda: True}}]
    result = await verify_skill(skill_name="TestSkill", verify_items=items)
    print(f"verify_skill: success={{result.success}}")
    return result

asyncio.run(test())
"""],
        capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0


if __name__ == "__main__":
    import traceback
    
    tests = [
        test_can_execute_fallback_return_false,
        test_circuit_breaker_main_block,
        test_match_roles_cli_categories,
        test_match_roles_cli_match_with_args,
        test_match_roles_cli_get_role,
        test_match_roles_cli_no_args,
        test_write_json_retries_on_io_error,
        test_read_json_with_retries_fails,
        test_list_omx_dirs,
        test_ralph_loop_main_block,
        test_ralph_loop_verify_skill,
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
