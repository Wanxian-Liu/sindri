"""
Test omx_contract.py write_json retry/failure edge case
"""
import sys
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

SCRIPT_DIR = Path("/home/rayliu/.openclaw/skills/sindris/scripts")
sys.path.insert(0, str(SCRIPT_DIR))


class TestOmxContractWriteJsonRetry:
    """Test omx_contract.py write_json retry and failure cases"""

    def test_write_json_raises_after_retries(self, tmp_path):
        """Test write_json raises IOError after all retries fail"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        
        with patch("builtins.open", side_effect=OSError("Disk full")):
            with pytest.raises(IOError) as exc_info:
                omx_contract.write_json(str(tmp_path / "test.json"), {"key": "value"})
            assert "Failed to write" in str(exc_info.value) or "Disk full" in str(exc_info.value)

    def test_read_json_returns_default_on_decode_error(self, tmp_path):
        """Test read_json returns default on JSON decode error"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{ invalid json }")
        
        result = omx_contract.read_json(str(bad_file), default={"default": True})
        assert result == {"default": True}

    def test_read_json_returns_default_on_not_found(self, tmp_path):
        """Test read_json returns default when file not found"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        
        result = omx_contract.read_json(str(tmp_path / "nonexistent.json"), default={"default": True})
        assert result == {"default": True}

    def test_omx_dir(self):
        """Test omx_dir returns correct path"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        path = omx_contract.omx_dir("/project/root")
        assert path == "/project/root/.omx"

    def test_omx_path(self):
        """Test omx_path returns correct nested path"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        path = omx_contract.omx_path("/project/root", "state", "tasks.json")
        assert path == "/project/root/.omx/state/tasks.json"

    def test_state_file(self):
        """Test state_file returns correct path"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        path = omx_contract.state_file("/project/root", "planner")
        assert path == "/project/root/.omx/state/planner-state.json"

    def test_ensure_omx_layout_creates_dirs(self, tmp_path):
        """Test ensure_omx_layout creates all required directories"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        
        omx_contract.ensure_omx_layout(str(tmp_path))
        omx_dir = tmp_path / ".omx"
        
        assert omx_dir.exists()
        for entry in omx_contract.OMX_LAYOUT_DIRS:
            assert (omx_dir / entry).exists(), f"Missing dir: {entry}"

    def test_list_omx_dirs(self):
        """Test list_omx_dirs returns expected list"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        dirs = omx_contract.list_omx_dirs("/tmp")
        assert "state" in dirs
        assert "sessions" in dirs
        assert "plans" in dirs
        assert "research" in dirs
        assert "team" in dirs
        assert "logs" in dirs
        assert "memory" in dirs

    def test_workspace_root_default(self):
        """Test get_workspace_root returns default path"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        omx_contract._workspace_root = None
        root = omx_contract.get_workspace_root()
        assert ".openclaw/workspace" in root

    def test_set_workspace_root(self):
        """Test set_workspace_root updates the root"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        omx_contract.set_workspace_root("/custom/path")
        assert omx_contract.get_workspace_root() == "/custom/path"
        omx_contract._workspace_root = None

    def test_get_default_omx_paths(self):
        """Test get_default_omx_paths returns expected keys"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        omx_contract._workspace_root = "/test"
        paths = omx_contract.get_default_omx_paths()
        assert "root" in paths
        assert "omx_dir" in paths
        assert "tasks" in paths
        assert "reviews" in paths
        assert "inbox" in paths
        assert "ledger" in paths
        assert "team" in paths
        assert "hud_config" in paths

    def test_write_json_success(self, tmp_path):
        """Test write_json succeeds and creates valid JSON"""
        if 'omx_contract' in sys.modules:
            del sys.modules['omx_contract']
        import omx_contract
        
        test_file = tmp_path / "test.json"
        data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        
        omx_contract.write_json(str(test_file), data)
        
        result = omx_contract.read_json(str(test_file))
        assert result == data
