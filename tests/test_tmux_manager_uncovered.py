"""
Tests for uncovered lines in sindris_tmux_manager.py.
Coverage targets:
  - Lines 207-208, 222-223, 234-235, 251-252, 265-266: exception handlers
  - Lines 511-515: TRUST_REQUIRED status transition in observe()
  - Lines 529-532: RUNNING cue detection + return in observe()
"""
import sys
sys.path.insert(0, "scripts")

import tempfile
import shutil
from unittest.mock import patch, MagicMock

import pytest

from sindris_tmux_manager import (
    TmuxManager, SindrisWorkerManager, WorkerStatus, WorkerEventKind,
    detect_trust_prompt, detect_ready_for_prompt, detect_running_cue,
)


class TestTmuxManagerExceptionHandlers:
    """Cover exception handlers when is_available() returns True but subprocess fails"""

    def test_kill_session_exception_handler(self):
        """Lines 207-208: except Exception in kill_session"""
        mgr = TmuxManager("test-session")
        with patch.object(mgr, 'is_available', return_value=True):
            with patch('subprocess.run', side_effect=OSError("tmux died")):
                result = mgr.kill_session()
                assert result is False

    def test_create_window_exception_handler(self):
        """Lines 222-223: except Exception in create_window"""
        mgr = TmuxManager("test-session")
        with patch.object(mgr, 'is_available', return_value=True):
            with patch('subprocess.run', side_effect=OSError("tmux died")):
                result = mgr.create_window("test-win", "echo hello")
                assert result is False

    def test_kill_window_exception_handler(self):
        """Lines 234-235: except Exception in kill_window"""
        mgr = TmuxManager("test-session")
        with patch.object(mgr, 'is_available', return_value=True):
            with patch('subprocess.run', side_effect=OSError("tmux died")):
                result = mgr.kill_window("test-win")
                assert result is False

    def test_send_keys_exception_handler(self):
        """Lines 251-252: except Exception in send_keys"""
        mgr = TmuxManager("test-session")
        with patch.object(mgr, 'is_available', return_value=True):
            with patch('subprocess.run', side_effect=OSError("tmux died")):
                result = mgr.send_keys("test-win", "hello")
                assert result is False

    def test_capture_pane_exception_handler(self):
        """Lines 265-266: except Exception in capture_pane returns empty string"""
        mgr = TmuxManager("test-session")
        with patch.object(mgr, 'is_available', return_value=True):
            with patch('subprocess.run', side_effect=OSError("tmux died")):
                result = mgr.capture_pane("test-win")
                assert result == ""


class TestObserveStatusTransitions:
    """Cover status transition branches in observe() method"""

    def _make_mgr_and_worker(self, role="test-worker"):
        tmp = tempfile.mkdtemp()
        mgr = SindrisWorkerManager("test-session", workspace_root=tmp)
        w = mgr.create_worker(role)
        w.window_name = "test-win"
        return mgr, w, tmp

    def test_trust_required_transition(self):
        """Lines 511-515: Worker in non-TRUST state but screen shows trust prompt"""
        mgr, w, tmp = self._make_mgr_and_worker()
        try:
            w.status = WorkerStatus.RUNNING
            mock_tmux = MagicMock()
            mock_tmux.is_available.return_value = True
            mock_tmux.capture_pane.return_value = "Do you trust the files in this folder?"
            mgr._tmux = mock_tmux
            status = mgr.observe(w.id)
            assert status == WorkerStatus.TRUST_REQUIRED
            assert w.status == WorkerStatus.TRUST_REQUIRED
            assert "trust" in w.last_error.lower()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_ready_detection_from_spawning(self):
        """Ready detection: SPAWNING -> READY"""
        mgr, w, tmp = self._make_mgr_and_worker()
        try:
            w.status = WorkerStatus.SPAWNING
            mock_tmux = MagicMock()
            mock_tmux.is_available.return_value = True
            mock_tmux.capture_pane.return_value = "Ready for prompt."
            mgr._tmux = mock_tmux
            status = mgr.observe(w.id)
            assert status == WorkerStatus.READY
            assert w.status == WorkerStatus.READY
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_ready_detection_from_running(self):
        """Ready detection: RUNNING -> READY"""
        mgr, w, tmp = self._make_mgr_and_worker()
        try:
            w.status = WorkerStatus.RUNNING
            w.last_error = "some error"
            mock_tmux = MagicMock()
            mock_tmux.is_available.return_value = True
            mock_tmux.capture_pane.return_value = "Ready for prompt."
            mgr._tmux = mock_tmux
            status = mgr.observe(w.id)
            assert status == WorkerStatus.READY
            # last_error is only cleared if it contains 'trust'
            assert w.last_error == "some error"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_running_cue_detection(self):
        """Lines 529-532: RUNNING state with running cue clears last_error"""
        mgr, w, tmp = self._make_mgr_and_worker()
        try:
            w.status = WorkerStatus.RUNNING
            w.last_error = "previous error"
            mock_tmux = MagicMock()
            mock_tmux.is_available.return_value = True
            mock_tmux.capture_pane.return_value = "Thinking..."
            mgr._tmux = mock_tmux
            status = mgr.observe(w.id)
            assert status == WorkerStatus.RUNNING
            assert w.last_error is None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_screen_returns_current_status(self):
        """No screen output returns current status unchanged"""
        mgr, w, tmp = self._make_mgr_and_worker()
        try:
            w.status = WorkerStatus.RUNNING
            mock_tmux = MagicMock()
            mock_tmux.is_available.return_value = True
            mock_tmux.capture_pane.return_value = ""
            mgr._tmux = mock_tmux
            status = mgr.observe(w.id)
            assert status == WorkerStatus.RUNNING
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_observe_unknown_worker_returns_failed(self):
        """observe() with unknown worker_id returns FAILED"""
        tmp = tempfile.mkdtemp()
        try:
            mgr = SindrisWorkerManager("test-session", workspace_root=tmp)
            status = mgr.observe("nonexistent-id")
            assert status == WorkerStatus.FAILED
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
