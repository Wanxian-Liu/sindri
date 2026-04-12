#!/usr/bin/env python3
"""
test_worktree_officer_supplement.py - WorktreeOfficer补充测试
覆盖: _run_git超时/异常处理, setup_worktree边界条件, remove_worktree等
"""

import sys
import os
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from worktree_officer import WorktreeOfficer, WorktreeConfig


class TestRunGitExceptionHandling:
    """测试_run_git异常处理"""
    
    def test_git_timeout_returns_error_code(self):
        """覆盖subprocess.TimeoutExpired处理"""
        officer = WorktreeOfficer()
        officer.project_dir = "/tmp/test"
        
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("git", 30)):
            code, stdout, stderr = officer._run_git(['status'])
            assert code == -1
            assert stdout == ""
            assert "timeout" in stderr.lower()
    
    def test_git_generic_exception_returns_error(self):
        """覆盖通用异常处理"""
        officer = WorktreeOfficer()
        officer.project_dir = "/tmp/test"
        
        with patch('subprocess.run', side_effect=OSError("Permission denied")):
            code, stdout, stderr = officer._run_git(['status'])
            assert code == -1
            assert "Permission denied" in stderr


class TestValidateAgentName:
    """测试_validate_agent_name"""
    
    def test_valid_alphanumeric(self):
        """测试字母数字"""
        officer = WorktreeOfficer()
        assert officer._validate_agent_name("agent1") == True
        assert officer._validate_agent_name("test123") == True
    
    def test_valid_with_underscore(self):
        """测试下划线"""
        officer = WorktreeOfficer()
        assert officer._validate_agent_name("my_agent") == True
    
    def test_valid_with_hyphen(self):
        """测试连字符"""
        officer = WorktreeOfficer()
        assert officer._validate_agent_name("my-agent") == True
    
    def test_invalid_with_space(self):
        """测试空格"""
        officer = WorktreeOfficer()
        assert officer._validate_agent_name("my agent") == False
    
    def test_invalid_with_dot(self):
        """测试点号"""
        officer = WorktreeOfficer()
        assert officer._validate_agent_name("agent.1") == False
    
    def test_invalid_empty(self):
        """测试空字符串"""
        officer = WorktreeOfficer()
        assert officer._validate_agent_name("") == False


class TestSetupWorktreeValidation:
    """测试setup_worktree边界条件"""
    
    def test_worktree_setup_validates_agent_name(self):
        """覆盖无效agent名称在setup_worktree时被检测"""
        officer = WorktreeOfficer()
        
        try:
            officer.setup_worktree("invalid agent")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid agent name" in str(e)
    
    def test_worktree_setup_requires_project(self):
        """覆盖未初始化项目时抛出错误"""
        officer = WorktreeOfficer()
        officer.project_dir = None
        
        try:
            officer.setup_worktree("agent1")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "not initialized" in str(e)
    
    def test_worktree_creates_and_maps(self):
        """覆盖成功创建worktree并记录映射"""
        with tempfile.TemporaryDirectory() as tmpdir:
            officer = WorktreeOfficer()
            officer.project_dir = tmpdir
            
            def mock_run_git(args, cwd=None):
                if args[0] == 'worktree' and 'add' in args:
                    return (0, f"Creating worktree", "")
                return (0, "", "")
            
            officer._run_git = mock_run_git
            officer.config.base_dir = os.path.join(tmpdir, "worktrees")
            result = officer.setup_worktree("agent1")
            assert "agent1" in officer.worktree_map


class TestSetupWorktrees:
    """测试setup_worktrees批量创建"""
    
    def test_empty_list_returns_empty_dict(self):
        """测试空列表返回空字典"""
        officer = WorktreeOfficer()
        result = officer.setup_worktrees([])
        assert result == {}
    
    def test_multiple_agents_partial_failure(self):
        """测试多个agent部分失败"""
        officer = WorktreeOfficer()
        officer.project_dir = "/tmp/test"
        
        def mock_run_git(args, cwd=None):
            if args[0] == 'worktree' and 'add' in args:
                return (1, "", "branch already exists")
            elif args[0] == 'worktree' and 'list' in args:
                return (1, "", "not found")
            return (0, "", "")
        
        officer._run_git = mock_run_git
        result = officer.setup_worktrees(["agent1", "agent2"])
        assert result == {}


class TestRemoveWorktree:
    """测试remove_worktree"""
    
    def test_remove_from_map(self):
        """测试从map中移除"""
        officer = WorktreeOfficer()
        officer.worktree_map["agent1"] = "/tmp/test_agent"
        
        with patch.object(officer, '_run_git', return_value=(0, "", "")), \
             patch('shutil.rmtree'):
            result = officer.remove_worktree("agent1")
            assert result == True
            assert "agent1" not in officer.worktree_map
    
    def test_remove_nonexistent_returns_true(self):
        """测试移除不存在的agent返回True"""
        officer = WorktreeOfficer()
        with patch.object(officer, '_run_git', return_value=(0, "", "")):
            result = officer.remove_worktree("nonexistent")
            assert result == True


class TestCleanupAll:
    """测试cleanup_all"""
    
    def test_empty_cleanup(self):
        """测试空清理"""
        officer = WorktreeOfficer()
        result = officer.cleanup_all()
        assert result == 0
    
    def test_cleanup_multiple(self):
        """测试清理多个"""
        officer = WorktreeOfficer()
        officer.worktree_map["a1"] = "/tmp/a1"
        officer.worktree_map["a2"] = "/tmp/a2"
        officer.worktree_map["a3"] = "/tmp/a3"
        
        with patch.object(officer, 'remove_worktree', return_value=True):
            result = officer.cleanup_all()
            assert result == 3


class TestWriteAgentConstraints:
    """测试_write_agent_constraints"""
    
    def test_creates_nested_claude_dir(self):
        """测试创建.claude目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            officer = WorktreeOfficer()
            wt_dir = os.path.join(tmpdir, "agent1")
            os.makedirs(wt_dir)
            
            officer._write_agent_constraints(wt_dir, "test_agent")
            
            expected = os.path.join(wt_dir, ".claude", "CLAUDE.md")
            assert os.path.exists(expected)
            
            with open(expected) as f:
                content = f.read()
                assert "test_agent" in content
                assert "Workspace Boundary" in content


class TestExpandPath:
    """测试_expand_path"""
    
    def test_expand_env_var(self):
        """测试环境变量展开"""
        officer = WorktreeOfficer()
        
        with patch.dict(os.environ, {'MY_TEST_VAR': 'test_value'}):
            result = officer._expand_path("$MY_TEST_VAR/subpath")
            assert "test_value" in result
    
    def test_expand_home(self):
        """测试~展开"""
        officer = WorktreeOfficer()
        result = officer._expand_path("~/test/path")
        assert result.startswith(os.path.expanduser("~"))


class TestGetStatus:
    """测试get_status"""
    
    def test_status_reflects_worktree_count(self):
        """测试状态反映worktree数量"""
        officer = WorktreeOfficer()
        officer.worktree_map = {"a1": "/p1", "a2": "/p2"}
        
        status = officer.get_status()
        assert status["worktree_count"] == 2


class TestWorktreeConfig:
    """测试WorktreeConfig"""
    
    def test_default_values(self):
        """测试默认配置值"""
        config = WorktreeConfig()
        assert config.base_dir == "~/.openclaw/worktrees"
        assert config.project_name == "default"
        assert config.auto_cleanup == True


class TestCreateWorktreeOfficer:
    """测试create_worktree_officer快捷函数"""
    
    def test_creates_officer_with_given_config(self):
        """测试使用给定配置创建officer"""
        officer = WorktreeOfficer(WorktreeConfig(
            base_dir="/custom/base",
            project_name="custom_proj"
        ))
        assert officer.config.base_dir == "/custom/base"
        assert officer.config.project_name == "custom_proj"


if __name__ == "__main__":
    print("运行WorktreeOfficer补充测试...")
    
    test_classes = [
        TestRunGitExceptionHandling,
        TestValidateAgentName,
        TestSetupWorktreeValidation,
        TestSetupWorktrees,
        TestRemoveWorktree,
        TestCleanupAll,
        TestWriteAgentConstraints,
        TestExpandPath,
        TestGetStatus,
        TestWorktreeConfig,
        TestCreateWorktreeOfficer,
    ]
    
    passed = 0
    failed = 0
    
    for cls in test_classes:
        print(f"\n{cls.__name__}:")
        instance = cls()
        for method in dir(instance):
            if method.startswith("test_"):
                try:
                    getattr(instance, method)()
                    print(f"  ✅ {method}")
                    passed += 1
                except Exception as e:
                    print(f"  ❌ {method}: {e}")
                    failed += 1
    
    print(f"\n=== 结果: {passed} passed, {failed} failed ===")
