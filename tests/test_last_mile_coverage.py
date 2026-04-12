#!/usr/bin/env python3
"""
test_last_mile_coverage.py - 覆盖 __main__ 块和边缘重试路径

目标:
- circuit_breaker.py lines 362-394: if __name__ == "__main__" block
- match_roles.py lines 294-326: if __name__ == "__main__" CLI block  
- omx_contract.py lines 150, 169: write_json/read_json retries=0 edge cases
- ralph_loop.py lines 409-428: if __name__ == "__main__" block
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ============================================================
# omx_contract.py edge cases: retries=0
# ============================================================

class TestOmxContractRetryZero:
    """测试 omx_contract.py retries=0 边缘情况"""
    
    def test_read_json_retries_zero_skips_loop(self, tmp_path):
        """Line 150: read_json retries=0 时循环跳过，直接 return default"""
        from omx_contract import read_json
        
        # 创建一个有效的 JSON 文件
        f = tmp_path / "valid.json"
        f.write_text('{"key": "value"}')
        
        # retries=0: 循环体不执行，直接到达最后的 return default
        result = read_json(str(f), default={"default": True}, retries=0)
        assert result == {"default": True}
    
    def test_read_json_retries_zero_file_not_found(self, tmp_path):
        """Line 150: read_json retries=0 且文件不存在时"""
        from omx_contract import read_json
        
        result = read_json(
            str(tmp_path / "nonexistent.json"),
            default={"fallback": "used"},
            retries=0
        )
        assert result == {"fallback": "used"}
    
    def test_write_json_retries_zero_raises(self, tmp_path):
        """Line 169: write_json retries=0 时循环跳过，直接 raise"""
        from omx_contract import write_json
        
        # retries=0 时循环不执行，直接到达最后的 raise IOError
        with pytest.raises(IOError) as exc_info:
            write_json(str(tmp_path / "test.json"), {"key": "value"}, retries=0)
        assert "Failed to write" in str(exc_info.value)


# ============================================================
# CLI __main__ blocks via subprocess
# ============================================================

class TestCircuitBreakerMainBlock:
    """测试 circuit_breaker.py if __name__ == '__main__' 块 (lines 362-394)"""
    
    def test_circuit_breaker_main_block(self):
        """运行 circuit_breaker.py 作为脚本"""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "circuit_breaker.py")],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "CircuitBreaker" in output or "熔断器" in output


class TestMatchRolesMainBlock:
    """测试 match_roles.py if __name__ == '__main__' 块 (lines 294-326)"""
    
    def test_match_roles_main_categories(self):
        """match_roles.py categories 子命令"""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "match_roles.py"), "categories"],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "categories" in data
        assert "total_roles" in data
    
    def test_match_roles_main_get(self):
        """match_roles.py get 子命令"""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "match_roles.py"), "get", "role-001"],
            capture_output=True,
            text=True,
            timeout=10
        )
        # role-001 可能不存在，但 CLI 应该正常执行
        assert result.returncode == 0 or "not found" in result.stdout.lower()
    
    def test_match_roles_main_match(self):
        """match_roles.py match 子命令"""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "match_roles.py"), "match", "testing", "--top-k", "3"],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "matched_roles" in data
    
    def test_match_roles_main_no_args(self):
        """match_roles.py 无参数时打印帮助"""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "match_roles.py")],
            capture_output=True,
            text=True,
            timeout=10
        )
        # argparse 在无参数时打印帮助并退出
        assert result.returncode == 0


class TestRalphLoopMainBlock:
    """测试 ralph_loop.py if __name__ == '__main__' 块 (lines 409-428)"""
    
    def test_ralph_loop_main_block(self):
        """运行 ralph_loop.py 作为脚本"""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ralph_loop.py")],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "Ralph" in output or "验证" in output


# ============================================================
# CircuitBreaker 其他边缘覆盖
# ============================================================

class TestCircuitBreakerEdgeCases:
    """额外的 CircuitBreaker 边缘覆盖"""
    
    def test_get_circuit_status_for_unknown_role(self):
        """get_circuit_status 为未创建的角色返回默认状态"""
        from circuit_breaker import get_circuit_status, _circuit_breakers
        
        # 清理并获取一个从未创建过的角色
        _circuit_breakers.clear()
        status = get_circuit_status("brand_new_role")
        
        assert status["role_type"] == "brand_new_role"
        assert status["state"] == "closed"
        assert status["failures"] == 0
    
    def test_reset_circuit_nonexistent(self):
        """reset_circuit 对不存在的熔断器安全执行"""
        from circuit_breaker import reset_circuit, _circuit_breakers
        
        _circuit_breakers.clear()
        result = reset_circuit("nonexistent_role")
        
        assert result["role_type"] == "nonexistent_role"
        assert result["status"] == "reset"
    
    def test_get_all_circuits_status_empty(self):
        """get_all_circuits_status 在无熔断器时返回空字典"""
        from circuit_breaker import get_all_circuits_status, _circuit_breakers
        
        _circuit_breakers.clear()
        status = get_all_circuits_status()
        assert status == {}


if __name__ == "__main__":
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        capture_output=False
    )
    sys.exit(result.returncode)
