#!/usr/bin/env python3
"""test_sindris_tmux_manager_supplement.py - sindris_tmux_manager supplement tests"""

import sys, os, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from sindris_tmux_manager import (
    SindrisWorkerManager, TmuxManager, WorkerStatus, WorkerEventKind,
    detect_trust_prompt, detect_ready_for_prompt, detect_running_cue,
)

def make_tmux_manager(log_dir=None):
    if log_dir is None:
        log_dir = tempfile.mkdtemp()
    return TmuxManager(session_name="test-session", log_dir=log_dir)

def make_manager(log_dir=None):
    if log_dir is None:
        log_dir = tempfile.mkdtemp()
    return SindrisWorkerManager(
        session_name="test-session", workspace_root="/tmp/test-workspace", log_dir=log_dir,
    )

class TestTmuxManagerExceptionHandlers:
    def test_create_window_exception(self):
        mgr = make_tmux_manager()
        mgr._available = True
        with patch('subprocess.run', side_effect=Exception("subprocess error")):
            result = mgr.create_window("test-window", "echo hello")
            assert result is False

    def test_kill_window_exception(self):
        mgr = make_tmux_manager()
        mgr._available = True
        with patch('subprocess.run', side_effect=Exception("subprocess error")):
            result = mgr.kill_window("test-window")
            assert result is False

    def test_send_keys_exception(self):
        mgr = make_tmux_manager()
        mgr._available = True
        with patch('subprocess.run', side_effect=Exception("subprocess error")):
            result = mgr.send_keys("test-window", "echo hello")
            assert result is False

    def test_send_keys_no_enter(self):
        mgr = make_tmux_manager()
        mgr._available = True
        with patch('subprocess.run') as mock_run:
            result = mgr.send_keys("test-window", "partial command", enter=False)
            assert result is True
            assert 'Enter' not in mock_run.call_args[0][0]

    def test_capture_pane_exception(self):
        mgr = make_tmux_manager()
        mgr._available = True
        with patch('subprocess.run', side_effect=Exception("subprocess error")):
            result = mgr.capture_pane("test-window")
            assert result == ""

    def test_capture_pane_success(self):
        mgr = make_tmux_manager()
        mgr._available = True
        mock_result = MagicMock()
        mock_result.stdout = "screen output here"
        with patch('subprocess.run', return_value=mock_result):
            result = mgr.capture_pane("test-window", lines=100)
            assert result == "screen output here"

    def test_capture_pane_with_lines_param(self):
        mgr = make_tmux_manager()
        mgr._available = True
        mock_result = MagicMock()
        mock_result.stdout = "output"
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            mgr.capture_pane("test-window", lines=50)
            call_args = mock_run.call_args[0][0]
            assert '-S' in call_args
            assert '-50' in call_args

class TestObserveBranches:
    def test_observe_trust_prompt_on_non_trust_worker(self):
        mgr = make_manager()
        w = mgr.create_worker(role="developer")
        w.status = WorkerStatus.RUNNING
        w.window_name = "test-window"
        trust_screen = "Do you trust the files in this folder?"
        with patch.object(mgr._tmux, 'is_available', return_value=True),              patch.object(mgr._tmux, 'capture_pane', return_value=trust_screen):
            result = mgr.observe(w.id)
            assert result == WorkerStatus.TRUST_REQUIRED

    def test_observe_trust_prompt_already_trust_required(self):
        mgr = make_manager()
        w = mgr.create_worker(role="developer")
        w.status = WorkerStatus.TRUST_REQUIRED
        trust_screen = "Do you trust the files in this folder?"
        with patch.object(mgr._tmux, 'is_available', return_value=True),              patch.object(mgr._tmux, 'capture_pane', return_value=trust_screen):
            result = mgr.observe(w.id)
            assert result == WorkerStatus.TRUST_REQUIRED

    def test_observe_running_cue_on_running_worker(self):
        mgr = make_manager()
        w = mgr.create_worker(role="developer")
        w.status = WorkerStatus.RUNNING
        w.last_error = "some previous error"
        w.window_name = "test-window"
        running_screen = "Thinking..."
        with patch.object(mgr._tmux, 'is_available', return_value=True),              patch.object(mgr._tmux, 'capture_pane', return_value=running_screen):
            result = mgr.observe(w.id)
            assert w.last_error is None

    def test_observe_spawning_ready_transition(self):
        mgr = make_manager()
        w = mgr.create_worker(role="developer")
        w.status = WorkerStatus.SPAWNING
        w.window_name = "test-window"
        ready_screen = "Ready for input"
        with patch.object(mgr._tmux, 'is_available', return_value=True),              patch.object(mgr._tmux, 'capture_pane', return_value=ready_screen):
            result = mgr.observe(w.id)
            assert result == WorkerStatus.READY

class TestResolveTrustBranches:
    def test_resolve_trust_worker_not_in_trust_required(self):
        mgr = make_manager()
        w = mgr.create_worker(role="developer")
        w.status = WorkerStatus.RUNNING
        result, msg = mgr.resolve_trust(w.id)
        assert result is False
        assert "not waiting on trust" in msg

class TestSendCommandBranches:
    def test_send_command_tmux_unavailable_mock_mode(self):
        mgr = make_manager()
        w = mgr.create_worker(role="developer")
        w.status = WorkerStatus.READY
        with patch.object(mgr._tmux, 'is_available', return_value=False):
            result, msg = mgr.send_command(w.id, "echo hello")
            assert result is True
            assert "mock" in msg.lower() or "dispatched" in msg.lower()

    def test_send_command_with_wait_ready_timeout(self):
        mgr = make_manager()
        w = mgr.create_worker(role="developer")
        w.status = WorkerStatus.SPAWNING
        with patch.object(mgr._tmux, 'is_available', return_value=False),              patch.object(mgr, 'observe', return_value=WorkerStatus.SPAWNING),              patch('time.sleep'):
            result, msg = mgr.send_command(w.id, "echo hello", wait_ready=True, timeout=0.1)
            assert result is False
            assert "timeout" in msg.lower()

    def test_send_command_not_ready_fails(self):
        mgr = make_manager()
        w = mgr.create_worker(role="developer")
        w.status = WorkerStatus.TRUST_REQUIRED
        with patch.object(mgr._tmux, 'is_available', return_value=False):
            result, msg = mgr.send_command(w.id, "echo hello", wait_ready=True, timeout=1.0)
            assert result is False
