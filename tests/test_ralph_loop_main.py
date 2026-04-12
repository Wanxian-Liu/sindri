"""
Test ralph_loop.py __main__ block
"""
import sys
import os
import subprocess
import asyncio
import pytest
from pathlib import Path

SCRIPT_DIR = Path("/home/rayliu/.openclaw/skills/sindris/scripts")


class TestRalphLoopMain:
    """Test ralph_loop.py __main__ block"""

    def test_main_runs_without_error(self):
        """Test that ralph_loop __main__ runs successfully"""
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
import asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
import ralph_loop

async def test():
    items = [
        {{"name": "文件存在", "description": "检查文件是否存在", "check_fn": lambda: True}},
        {{"name": "代码可执行", "description": "检查代码能否执行", "check_fn": lambda: True}},
    ]
    verifier = ralph_loop.RalphLoop(task_name="测试任务", verify_items=items)
    result = await verifier.run()
    print(f"RESULT: success={{result.success}}, rounds={{result.total_rounds}}")
    return result

result = asyncio.run(test())
print("RalphLoop __main__ test completed")
"""],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "RalphLoop __main__ test completed" in result.stdout

    def test_verify_skill_convenience_function(self):
        """Test verify_skill convenience function"""
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
import asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
import ralph_loop

async def test():
    items = [
        {{"name": "文件存在", "description": "检查", "check_fn": lambda: True}},
    ]
    result = await ralph_loop.verify_skill(skill_name="TestSkill", verify_items=items)
    print(f"verify_skill: success={{result.success}}")
    return result

asyncio.run(test())
print("verify_skill test completed")
"""],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "verify_skill test completed" in result.stdout


class TestRalphLoopEdgeCases:
    """Test edge cases in ralph_loop.py"""

    def test_ralph_loop_async_check_fn(self):
        """Test RalphLoop with async check function"""
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
import asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
import ralph_loop

async def async_check():
    return True

async def test():
    items = [
        {{"name": "异步检查", "description": "async check", "check_fn": async_check}},
    ]
    verifier = ralph_loop.RalphLoop(task_name="异步测试", verify_items=items)
    result = await verifier.run()
    print(f"async check: success={{result.success}}")
    return result

asyncio.run(test())
print("async check test completed")
"""],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "async check test completed" in result.stdout

    def test_ralph_loop_add_verify_item(self):
        """Test add_verify_item method"""
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
import asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
import ralph_loop

async def test():
    verifier = ralph_loop.RalphLoop(task_name="动态添加测试")
    verifier.add_verify_item(name="动态项", description="added dynamically", check_fn=lambda: True)
    result = await verifier.run()
    print(f"add item: items_count={{len(result.all_reports[0].items)}}")
    return result

asyncio.run(test())
print("add_verify_item test completed")
"""],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "add_verify_item test completed" in result.stdout

    def test_ralph_loop_with_execute_fn(self):
        """Test RalphLoop with execute_fn"""
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
import asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
import ralph_loop

async def execute_fn(error_feedback=None):
    print("execute_fn called")

async def test():
    items = [
        {{"name": "检查1", "description": "check1", "check_fn": lambda: True}},
    ]
    verifier = ralph_loop.RalphLoop(
        task_name="执行测试",
        verify_items=items,
        execute_fn=execute_fn
    )
    result = await verifier.run()
    print(f"with execute_fn: success={{result.success}}")
    return result

asyncio.run(test())
print("execute_fn test completed")
"""],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "execute_fn test completed" in result.stdout

    def test_ralph_loop_on_round_complete_callback(self):
        """Test RalphLoop with on_round_complete callback"""
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
import asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
import ralph_loop

callback_called = False

def on_round(report):
    global callback_called
    callback_called = True
    print(f"callback: round={{report.round_num}}")

async def test():
    items = [
        {{"name": "检查1", "description": "check1", "check_fn": lambda: True}},
    ]
    verifier = ralph_loop.RalphLoop(
        task_name="回调测试",
        verify_items=items,
        on_round_complete=on_round
    )
    result = await verifier.run()
    print(f"callback called: {{callback_called}}")
    return result

asyncio.run(test())
print("callback test completed")
"""],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "callback test completed" in result.stdout

    def test_ralph_result_attributes(self):
        """Test RalphResult dataclass has expected attributes"""
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
import asyncio
sys.path.insert(0, '{SCRIPT_DIR}')
import ralph_loop

async def test():
    items = [
        {{"name": "检查", "description": "check", "check_fn": lambda: True}},
    ]
    verifier = ralph_loop.RalphLoop(task_name="属性测试", verify_items=items)
    r = await verifier.run()
    
    attrs = ['success', 'total_rounds', 'consecutive_passed',
             'final_report', 'all_reports', 'error_feedback']
    for attr in attrs:
        assert hasattr(r, attr), f"Missing attribute: {{attr}}"
    
    print(f"Attributes check passed")
    return r

asyncio.run(test())
print("attributes test completed")
"""],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "attributes test completed" in result.stdout
