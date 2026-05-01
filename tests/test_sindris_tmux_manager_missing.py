#!/usr/bin/env python3
"""test_sindris_tmux_manager_missing.py - sindris_tmux_manager 补充测试"""
import os, sys
from pathlib import Path
import tempfile
import pytest
from unittest.mock import patch, MagicMock

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR / "scripts"))

from sindris_tmux_manager import (
    SindrisWorkerManager,
    WorkerStatus,
    detect_trust_prompt,
    detect_ready_for_prompt,
    detect_running_cue,
)

def test_detect_trust_prompt_folder():
    screen = "Do you trust the files in this folder? [y/N]"
    assert detect_trust_prompt(screen) == True

def test_detect_trust_prompt_allow():
    screen = "Allow and continue? [y/N]"
    assert detect_trust_prompt(screen) == True

def test_detect_trust_prompt_yes_proceed():
    screen = "Yes, proceed with execution"
    assert detect_trust_prompt(screen) == True

def test_detect_trust_prompt_no_match():
    screen = "This is normal operation, ready for input"
    assert detect_trust_prompt(screen) == False

def test_detect_ready_for_prompt_ready_for_input():
    screen = "Ready for your input"
    assert detect_ready_for_prompt(screen) == True

def test_detect_ready_for_prompt_send_message():
    screen = "Ready to send a message"
    assert detect_ready_for_prompt(screen) == True

def test_detect_ready_for_prompt_prompt_char():
    screen = "some previous output› "
    assert detect_ready_for_prompt(screen) == True

def test_detect_ready_for_prompt_no_match():
    screen = "processing something..."
    assert detect_ready_for_prompt(screen) == False

def test_detect_running_cue_thinking():
    screen = "Thinking..."
    assert detect_running_cue(screen) == True

def test_detect_running_cue_working():
    screen = "Working on it..."
    assert detect_running_cue(screen) == True

def test_detect_running_cue_running_tests():
    screen = "Running tests for auth module..."
    assert detect_running_cue(screen) == True

def test_detect_running_cue_no_match():
    screen = "Idle and ready"
    assert detect_running_cue(screen) == False

@pytest.fixture
def worker_mgr(tmp_path):
    return SindrisWorkerManager(
        session_name="test-session",
        workspace_root="/tmp",
        log_dir=str(tmp_path / "logs"),
    )

def test_create_window_on_tmux(worker_mgr):
    """Test create_window on the underlying TmuxManager"""
    worker_mgr._tmux.is_available = MagicMock(return_value=False)
    result = worker_mgr._tmux.create_window("test_win", "echo hello")
    assert result == False

@patch("subprocess.run")
def test_kill_window_on_tmux(mock_run, worker_mgr):
    """Test kill_window on the underlying TmuxManager"""
    mock_run.return_value = MagicMock(returncode=0)
    worker_mgr._tmux.is_available = MagicMock(return_value=True)
    result = worker_mgr._tmux.kill_window("test_win")
    assert result == True

@patch("subprocess.run")
def test_send_keys_on_tmux(mock_run, worker_mgr):
    """Test send_keys on the underlying TmuxManager"""
    mock_run.return_value = MagicMock(returncode=0)
    worker_mgr._tmux.is_available = MagicMock(return_value=True)
    result = worker_mgr._tmux.send_keys("test_win", "hello", enter=True)
    assert result == True
    call_args = mock_run.call_args[0][0]
    assert "Enter" in call_args

def test_capture_pane_on_tmux_unavailable(worker_mgr):
    """Test capture_pane on underlying TmuxManager when unavailable"""
    worker_mgr._tmux.is_available = MagicMock(return_value=False)
    result = worker_mgr._tmux.capture_pane("test_win")
    assert result == ""

@patch("subprocess.run")
def test_capture_pane_on_tmux_success(mock_run, worker_mgr):
    """Test capture_pane on underlying TmuxManager"""
    mock_run.return_value = MagicMock(stdout="some output", returncode=0)
    worker_mgr._tmux.is_available = MagicMock(return_value=True)
    result = worker_mgr._tmux.capture_pane("test_win", lines=100)
    assert result == "some output"

def test_resolve_trust_worker_not_found(worker_mgr):
    """Test resolve_trust when worker does not exist"""
    ok, msg = worker_mgr.resolve_trust("nonexistent")
    assert ok == False
    assert "not found" in msg

def test_resolve_trust_wrong_status(worker_mgr):
    """Test resolve_trust when worker status is not TRUST_REQUIRED"""
    w = worker_mgr.create_worker(role="test_role", agent_id="w1")
    w.status = WorkerStatus.READY
    ok, msg = worker_mgr.resolve_trust(w.id)
    assert ok == False
    assert "not waiting" in msg

def test_resolve_trust_success(worker_mgr):
    """Test resolve_trust successfully resolves a trust gate"""
    w = worker_mgr.create_worker(role="test_role", agent_id="w1")
    w.status = WorkerStatus.TRUST_REQUIRED
    w.window_name = "test_win"
    worker_mgr._tmux.is_available = MagicMock(return_value=True)
    with patch.object(worker_mgr._tmux, "send_keys", return_value=True):
        ok, msg = worker_mgr.resolve_trust(w.id)
        assert ok == True
        assert "resolved" in msg
        assert w.status == WorkerStatus.SPAWNING

def test_heartbeat_worker_not_found(worker_mgr):
    """Test heartbeat when worker does not exist"""
    result = worker_mgr.heartbeat("nonexistent")
    assert result == False

def test_heartbeat_success(worker_mgr):
    """Test heartbeat successfully records heartbeat"""
    w = worker_mgr.create_worker(role="test_role", agent_id="w1")
    result = worker_mgr.heartbeat(w.id, note="alive")
    assert result == True

def test_create_worker_returns_worker(worker_mgr):
    """Test create_worker creates a Worker object"""
    w = worker_mgr.create_worker(role="developer", agent_id="dev1")
    assert w is not None
    assert w.role == "developer"
    assert w.agent_id == "dev1"
    assert w.status == WorkerStatus.SPAWNING

def test_get_worker(worker_mgr):
    """Test get_worker returns correct worker"""
    w = worker_mgr.create_worker(role="tester", agent_id="t1")
    found = worker_mgr.get_worker(w.id)
    assert found is w

def test_get_worker_not_found(worker_mgr):
    """Test get_worker returns None for unknown worker"""
    found = worker_mgr.get_worker("unknown-id")
    assert found is None

def test_list_workers(worker_mgr):
    """Test list_workers returns all workers"""
    w1 = worker_mgr.create_worker(role="dev", agent_id="dev1")
    w2 = worker_mgr.create_worker(role="tester", agent_id="test1")
    workers = worker_mgr.list_workers()
    assert len(workers) == 2
