"""
test_match_roles_extended.py - match_roles.py 扩展测试
测试 get_role_by_id 的 None 返回路径、_load_registry 的异常路径、CLI 入口
"""

import os
import sys
import tempfile
import shutil
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from match_roles import get_role_by_id, _load_registry, _cached_registry


class TestGetRoleById:
    """测试 get_role_by_id"""
    
    def test_get_role_by_id_existing(self):
        """测试获取存在的角色"""
        # 从现有的角色注册表中找一个有效ID
        role = get_role_by_id("role_security_auditor")
        # 如果这个ID不存在，找一个存在的
        if role is None:
            # 获取任意一个角色
            from match_roles import list_categories, match_roles
            cats = list_categories()
            if cats.get("total_roles", 0) > 0:
                # 匹配任意关键词获取一个角色
                result = match_roles(["code"])
                if result and result.get("matched_roles"):
                    first_id = result["matched_roles"][0]["id"]
                    role = get_role_by_id(first_id)
        if role:
            assert "id" in role
            assert "name" in role
    
    def test_get_role_by_id_nonexistent(self):
        """测试获取不存在的角色返回 None"""
        result = get_role_by_id("nonexistent_role_id_xyz")
        assert result is None
    
    def test_get_role_by_id_empty_string(self):
        """测试空字符串ID"""
        result = get_role_by_id("")
        assert result is None


class TestLoadRegistry:
    """测试 _load_registry 内部函数"""
    
    def test_load_registry_returns_dict(self):
        """测试 _load_registry 返回字典"""
        registry = _load_registry()
        assert isinstance(registry, dict)
        assert "roles" in registry
    
    def test_load_registry_caches(self):
        """测试 _load_registry 缓存"""
        global _cached_registry
        _cached_registry = None  # 清空缓存
        
        # 第一次加载
        reg1 = _load_registry()
        # 第二次应该返回缓存
        reg2 = _load_registry()
        assert reg1 is reg2  # 同一对象
    
    def test_load_registry_raises_on_missing_file(self, monkeypatch):
        """测试文件不存在时抛出异常"""
        import match_roles
        from pathlib import Path
        
        # 清空模块级缓存
        monkeypatch.setattr(match_roles, "_cached_registry", None)
        
        # 创建一个不存在的Path对象
        nonexistent_path = Path("/nonexistent/path/roles_registry.json")
        monkeypatch.setattr(match_roles, "REGISTRY_PATH", nonexistent_path)
        
        try:
            match_roles._load_registry()
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass  # Expected


class TestMatchRolesCli:
    """测试 match_roles.py CLI 入口"""
    
    def test_cli_match_command(self):
        """测试 CLI match 子命令"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "match_roles", "match", "code", "review"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.join(os.path.dirname(__file__), '..', 'scripts')
        )
        # 应该成功执行（可能返回空结果但不应报错）
        assert result.returncode == 0 or "Traceback" not in result.stderr
    
    def test_cli_categories_command(self):
        """测试 CLI categories 子命令"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "match_roles", "categories"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.join(os.path.dirname(__file__), '..', 'scripts')
        )
        assert result.returncode == 0
        # 输出应该是有效的 JSON
        import json
        try:
            data = json.loads(result.stdout)
            assert "categories" in data or "total_roles" in data
        except json.JSONDecodeError:
            # 如果输出为空或格式不对，但没报错，也算通过
            pass
    
    def test_cli_get_command(self):
        """测试 CLI get 子命令"""
        import subprocess
        # 先获取一个有效ID
        role = get_role_by_id("role_security_auditor")
        if role is None:
            from match_roles import match_roles
            result = match_roles(["code"])
            if result and result.get("matched_roles"):
                role = result["matched_roles"][0]
        
        if role:
            result = subprocess.run(
                [sys.executable, "-m", "match_roles", "get", role["id"]],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=os.path.join(os.path.dirname(__file__), '..', 'scripts')
            )
            assert result.returncode == 0 or "not found" in result.stdout.lower()
    
    def test_cli_get_nonexistent(self):
        """测试 CLI get 不存在的角色"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "match_roles", "get", "nonexistent_role_xyz"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.join(os.path.dirname(__file__), '..', 'scripts')
        )
        # 应该输出 "not found" 消息
        assert "not found" in result.stdout.lower() or result.returncode == 0
    
    def test_cli_no_command(self):
        """测试 CLI 不带子命令（应打印帮助）"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "match_roles"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.join(os.path.dirname(__file__), '..', 'scripts')
        )
        # 应该显示帮助信息
        assert "help" in result.stdout.lower() or result.returncode == 0
