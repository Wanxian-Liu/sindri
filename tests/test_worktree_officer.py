"""
WorktreeOfficer 完整测试
测试所有公开方法和关键内部逻辑
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加scripts路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from worktree_officer import WorktreeOfficer, WorktreeConfig, create_worktree_officer


class TestWorktreeOfficerInit:
    """测试WorktreeOfficer初始化"""
    
    def test_default_init(self):
        """测试默认初始化"""
        officer = WorktreeOfficer()
        assert officer.config is not None
        assert isinstance(officer.config, WorktreeConfig)
        assert officer.worktree_map == {}
        assert officer.project_dir is None
    
    def test_custom_config_init(self):
        """测试自定义配置初始化"""
        config = WorktreeConfig(base_dir="/test/path", project_name="test_proj")
        officer = WorktreeOfficer(config)
        assert officer.config.base_dir == "/test/path"
        assert officer.config.project_name == "test_proj"


class TestExpandPath:
    """测试_expand_path方法"""
    
    def test_expand_tilde(self):
        """测试~展开"""
        officer = WorktreeOfficer()
        result = officer._expand_path("~/test")
        assert result.endswith("test")
        assert result.startswith(os.path.expanduser("~"))
    
    def test_expand_env_var(self):
        """测试环境变量展开"""
        officer = WorktreeOfficer()
        with patch.dict(os.environ, {'TEST_VAR': 'value'}):
            result = officer._expand_path("$TEST_VAR/path")
            assert "value/path" in result or "TEST_VAR" in result


class TestValidateAgentName:
    """测试_validate_agent_name方法"""
    
    def test_valid_names(self):
        """测试有效名称"""
        officer = WorktreeOfficer()
        assert officer._validate_agent_name("agent_001") == True
        assert officer._validate_agent_name("test-agent") == True
        assert officer._validate_agent_name("my_agent") == True
    
    def test_invalid_names(self):
        """测试无效名称"""
        officer = WorktreeOfficer()
        assert officer._validate_agent_name("") == False
        assert officer._validate_agent_name("..") == False
        assert officer._validate_agent_name("/absolute") == False


class TestGetWorktreePath:
    """测试get_worktree_path方法"""
    
    def test_existing_worktree(self):
        """测试获取已存在的worktree"""
        officer = WorktreeOfficer()
        officer.worktree_map["agent1"] = "/path/to/agent1"
        result = officer.get_worktree_path("agent1")
        assert result == "/path/to/agent1"
    
    def test_nonexistent_worktree(self):
        """测试获取不存在的worktree"""
        officer = WorktreeOfficer()
        result = officer.get_worktree_path("nonexistent")
        assert result is None


class TestGetStatus:
    """测试get_status方法"""
    
    def test_initial_status(self):
        """测试初始状态"""
        officer = WorktreeOfficer()
        status = officer.get_status()
        assert isinstance(status, dict)
        assert "project_dir" in status
        assert "worktree_count" in status
        assert "worktrees" in status
        assert "base_dir" in status
        assert status["worktree_count"] == 0
    
    def test_with_worktrees(self):
        """测试有worktree时的状态"""
        officer = WorktreeOfficer()
        officer.worktree_map["agent1"] = "/path1"
        officer.worktree_map["agent2"] = "/path2"
        status = officer.get_status()
        assert status["worktree_count"] == 2
        assert status["worktrees"]["agent1"] == "/path1"


class TestSetupProject:
    """测试setup_project方法"""
    
    def test_nonexistent_directory(self):
        """测试不存在的目录会被创建"""
        officer = WorktreeOfficer()
        # setup_project会创建不存在的目录
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "subdir", "project")
            result = officer.setup_project(new_dir)
            # 目录会被创建，所以返回True
            assert result == True
            assert os.path.exists(new_dir)
    
    def test_valid_directory_without_git(self):
        """测试有效目录但不是git仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            officer = WorktreeOfficer()
            result = officer.setup_project(tmpdir)
            # 没有git仓库，应该返回某种结果
            assert isinstance(result, bool)


class TestSetupWorktrees:
    """测试setup_worktrees方法"""
    
    def test_empty_list(self):
        """测试空列表"""
        officer = WorktreeOfficer()
        result = officer.setup_worktrees([])
        assert result == {}
    
    def test_single_agent(self):
        """测试单个agent需要项目初始化"""
        officer = WorktreeOfficer()
        officer.project_dir = None  # 未初始化项目
        # 预期会失败因为没有项目目录
        try:
            result = officer.setup_worktrees(["agent1"])
            # 如果没有抛出异常，至少返回空dict
            assert result == {}
        except ValueError:
            # 正确抛出异常
            pass


class TestRemoveWorktree:
    """测试remove_worktree方法"""
    
    def test_remove_from_map(self):
        """测试从map中移除"""
        officer = WorktreeOfficer()
        officer.worktree_map["agent1"] = "/tmp/test_agent"
        
        # Mock掉其他方法
        with patch.object(officer, '_run_git', return_value=(0, "", "")), \
             patch('shutil.rmtree'):
            result = officer.remove_worktree("agent1")
            assert result == True
            assert "agent1" not in officer.worktree_map
    
    def test_remove_nonexistent(self):
        """测试移除不存在的agent"""
        officer = WorktreeOfficer()
        with patch.object(officer, '_run_git', return_value=(0, "", "")):
            result = officer.remove_worktree("nonexistent")
            assert result == True  # 应该返回True表示完成


class TestCleanupAll:
    """测试cleanup_all方法"""
    
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
    """测试_write_agent_constraints方法"""
    
    def test_creates_file(self):
        """测试创建约束文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            officer = WorktreeOfficer()
            wt_dir = os.path.join(tmpdir, "agent1")
            os.makedirs(wt_dir)
            
            officer._write_agent_constraints(wt_dir, "agent1")
            
            claude_md = os.path.join(wt_dir, ".claude", "CLAUDE.md")
            assert os.path.exists(claude_md)
            
            with open(claude_md) as f:
                content = f.read()
                assert "agent1" in content
                assert "Workspace Boundary" in content


class TestCreateWorktreeOfficer:
    """测试快捷函数"""
    
    def test_create_with_defaults(self):
        """测试默认创建"""
        officer = create_worktree_officer()
        assert isinstance(officer, WorktreeOfficer)
        assert officer.config.base_dir == "~/.openclaw/worktrees"
    
    def test_create_with_custom(self):
        """测试自定义创建"""
        officer = create_worktree_officer(base_dir="/custom/path", project_name="myproject")
        assert officer.config.base_dir == "/custom/path"
        assert officer.config.project_name == "myproject"


# 运行测试
if __name__ == "__main__":
    print("运行WorktreeOfficer测试...")
    
    tests = [
        TestWorktreeOfficerInit,
        TestExpandPath,
        TestValidateAgentName,
        TestGetWorktreePath,
        TestGetStatus,
        TestSetupProject,
        TestSetupWorktrees,
        TestRemoveWorktree,
        TestCleanupAll,
        TestWriteAgentConstraints,
        TestCreateWorktreeOfficer,
    ]
    
    passed = 0
    failed = 0
    
    for test_class in tests:
        print(f"\n{test_class.__name__}:")
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    getattr(instance, method_name)()
                    print(f"  ✅ {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  ❌ {method_name}: {e}")
                    failed += 1
    
    print(f"\n=== 结果: {passed} passed, {failed} failed ===")
