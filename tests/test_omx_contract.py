"""
test_omx_contract.py - omx_contract.py 路径和工具函数测试
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from omx_contract import (
    omx_dir,
    omx_path,
    state_file,
    tasks_file,
    notes_file,
    session_file,
    memory_file,
    team_file,
    team_log_dir,
    team_log_file,
    reviews_file,
    inbox_file,
    ledger_file,
    hooks_state_file,
    plugins_state_file,
    autoresearch_log_file,
    hook_events_log_file,
    hud_config_file,
    read_json,
    write_json,
    list_omx_dirs,
    get_workspace_root,
    set_workspace_root,
    get_default_omx_paths,
    ensure_omx_layout,
)


class TestPathFunctions:
    """测试 OMX 路径函数"""
    
    def setup_method(self):
        self.root = tempfile.mkdtemp()
    
    def teardown_method(self):
        shutil.rmtree(self.root, ignore_errors=True)
    
    def test_omx_dir(self):
        """测试 omx_dir"""
        path = omx_dir(self.root)
        assert path.endswith(".omx")
        assert self.root in path
    
    def test_omx_path(self):
        """测试 omx_path"""
        path = omx_path(self.root, "state", "tasks.json")
        assert "state" in path
        assert "tasks.json" in path
    
    def test_state_file(self):
        """测试 state_file"""
        path = state_file(self.root, "task")
        assert "task-state.json" in path
    
    def test_tasks_file(self):
        """测试 tasks_file"""
        path = tasks_file(self.root)
        assert "tasks.json" in path
    
    def test_notes_file(self):
        """测试 notes_file"""
        path = notes_file(self.root)
        assert "notepad.json" in path
    
    def test_session_file(self):
        """测试 session_file"""
        path = session_file(self.root)
        assert "current.json" in path
    
    def test_memory_file(self):
        """测试 memory_file"""
        path = memory_file(self.root)
        assert "memory" in path
        path_ns = memory_file(self.root, "custom")
        assert "custom" in path_ns
    
    def test_team_file(self):
        """测试 team_file"""
        path = team_file(self.root)
        assert "team.json" in path
    
    def test_team_log_dir(self):
        """测试 team_log_dir"""
        path = team_log_dir(self.root)
        assert "logs" in path
    
    def test_team_log_file(self):
        """测试 team_log_file"""
        path = team_log_file(self.root, "worker-1")
        assert "worker-1.log" in path
    
    def test_reviews_file(self):
        """测试 reviews_file"""
        path = reviews_file(self.root)
        assert "reviews.json" in path
    
    def test_inbox_file(self):
        """测试 inbox_file"""
        path = inbox_file(self.root)
        assert "inbox.json" in path
    
    def test_ledger_file(self):
        """测试 ledger_file"""
        path = ledger_file(self.root)
        assert "ledger.json" in path
    
    def test_hooks_state_file(self):
        """测试 hooks_state_file"""
        path = hooks_state_file(self.root)
        assert "hooks.json" in path
    
    def test_hud_config_file(self):
        """测试 hud_config_file"""
        path = hud_config_file(self.root)
        assert "hud" in path or "config" in path
    
    def test_plugins_state_file(self):
        """测试 plugins_state_file"""
        path = plugins_state_file(self.root)
        assert "plugins.json" in path
    
    def test_autoresearch_log_file(self):
        """测试 autoresearch_log_file"""
        path = autoresearch_log_file(self.root)
        assert "autoresearch" in path
    
    def test_hook_events_log_file(self):
        """测试 hook_events_log_file"""
        path = hook_events_log_file(self.root)
        assert "hooks.log" in path


class TestJsonOperations:
    """测试 JSON 读写操作"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_write_and_read_json(self):
        """测试基本的 JSON 写入和读取"""
        path = os.path.join(self.temp_dir, "test.json")
        data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        
        write_json(path, data)
        loaded = read_json(path)
        
        assert loaded["key"] == "value"
        assert loaded["number"] == 42
        assert loaded["list"] == [1, 2, 3]
    
    def test_read_json_default(self):
        """测试读取不存在的文件返回默认值"""
        path = os.path.join(self.temp_dir, "nonexistent.json")
        default = {"default": True}
        
        result = read_json(path, default=default)
        assert result == default
    
    def test_read_json_default_on_decode_error(self):
        """测试 JSON 解析错误时返回默认值"""
        path = os.path.join(self.temp_dir, "invalid.json")
        with open(path, 'w') as f:
            f.write("{ invalid json }")
        
        default = {"fallback": True}
        result = read_json(path, default=default)
        assert result == default
    
    def test_write_json_overwrites(self):
        """测试 JSON 写入覆盖旧内容"""
        path = os.path.join(self.temp_dir, "overwrite.json")
        
        write_json(path, {"v": 1})
        write_json(path, {"v": 2})
        
        loaded = read_json(path)
        assert loaded["v"] == 2
    
    def test_write_json_nested_data(self):
        """测试写入嵌套数据结构"""
        path = os.path.join(self.temp_dir, "nested.json")
        data = {
            "outer": {
                "inner": {
                    "deep": [1, {"two": 2}]
                }
            }
        }
        
        write_json(path, data)
        loaded = read_json(path)
        assert loaded["outer"]["inner"]["deep"][1]["two"] == 2


class TestWorkspaceRoot:
    """测试工作区根目录管理"""
    
    def setup_method(self):
        self.original_root = get_workspace_root()
    
    def teardown_method(self):
        set_workspace_root(self.original_root)
    
    def test_get_workspace_root_default(self):
        """测试获取默认工作区根目录"""
        root = get_workspace_root()
        assert root != ""
        assert os.path.isdir(root) or root.startswith(os.path.expanduser("~"))
    
    def test_set_workspace_root(self):
        """测试设置工作区根目录"""
        new_root = tempfile.mkdtemp()
        try:
            set_workspace_root(new_root)
            assert get_workspace_root() == new_root
        finally:
            shutil.rmtree(new_root, ignore_errors=True)
    
    def test_get_default_omx_paths(self):
        """测试获取默认 OMX 路径集合"""
        paths = get_default_omx_paths()
        assert "root" in paths
        assert "omx_dir" in paths
        assert "tasks" in paths
        assert "reviews" in paths
        assert "inbox" in paths
        assert "ledger" in paths


class TestListOmxDirs:
    """测试 list_omx_dirs"""
    
    def test_list_omx_dirs(self):
        """测试列出所有 OMX 目录"""
        dirs = list_omx_dirs(tempfile.mkdtemp())
        assert isinstance(dirs, list)
        assert len(dirs) > 0


class TestEnsureOmxLayout:
    """测试 ensure_omx_layout"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_ensure_omx_layout_creates_dirs(self):
        """测试 ensure_omx_layout 创建必要的目录"""
        ensure_omx_layout(self.temp_dir)
        
        omx = omx_dir(self.temp_dir)
        assert os.path.isdir(omx)
        assert os.path.isdir(os.path.join(omx, "state"))
        assert os.path.isdir(os.path.join(omx, "logs"))
        assert os.path.isdir(os.path.join(omx, "team", "logs"))
    
    def test_ensure_omx_layout_idempotent(self):
        """测试 ensure_omx_layout 是幂等的"""
        ensure_omx_layout(self.temp_dir)
        ensure_omx_layout(self.temp_dir)  # 不应报错
        assert os.path.isdir(omx_dir(self.temp_dir))
