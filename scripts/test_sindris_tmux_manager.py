#!/usr/bin/env python3
"""
test_sindris_tmux_manager.py - Tests for sindris_tmux_manager

Run: python test_sindris_tmux_manager.py
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from sindris_tmux_manager import (
    SindrisWorkerManager,
    TmuxManager,
    WorkerStatus,
    WorkerEventKind,
    detect_trust_prompt,
    detect_ready_for_prompt,
    detect_running_cue,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def tmux_available() -> bool:
    try:
        r = subprocess.run(["tmux", "list-sessions"],
                          capture_output=True, timeout=5, check=False)
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# TmuxManager tests
# ---------------------------------------------------------------------------

class TestTmuxManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmux_ok = tmux_available()

    def test_is_available(self):
        m = TmuxManager("test-session-xxx")
        # tmux command exists; just check the manager's own detection
        result = m.is_available()
        self.assertIsInstance(result, bool)

    def test_session_lifecycle(self):
        if not self.tmux_ok:
            self.skipTest("tmux not available")
        sess = f"test-sindris-{os.getpid()}"
        m = TmuxManager(sess)
        # ensure
        ok = m.ensure_session()
        self.assertTrue(ok)
        # kill
        m.kill_session()
        # confirm gone
        r = subprocess.run(["tmux", "has-session", "-t", sess],
                          capture_output=True, check=False)
        self.assertNotEqual(r.returncode, 0)


# ---------------------------------------------------------------------------
# SindrisWorkerManager tests
# ---------------------------------------------------------------------------

class TestSindrisWorkerManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmux_ok = tmux_ok_static = tmux_available()
        cls._tmpdir = tempfile.mkdtemp(prefix="sindris-test-")
        cls._sess = f"sindris-test-{os.getpid()}"
        cls._mgr = SindrisWorkerManager(
            session_name=cls._sess,
            workspace_root=cls._tmpdir,
            log_dir=cls._tmpdir,
        )

    @classmethod
    def tearDownClass(cls):
        if cls.tmux_ok:
            try:
                subprocess.run(["tmux", "kill-session", "-t", cls._sess],
                              capture_output=True, timeout=5, check=False)
            except Exception:
                pass
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def tearDown(self):
        # kill all workers
        for w in list(self._mgr._workers.values()):
            self._mgr.terminate(w.id)
        # clean tmux windows
        if self.tmux_ok:
            for w in self._mgr._workers.values():
                if w.window_name:
                    try:
                        subprocess.run(
                            ["tmux", "kill-window", "-t",
                             f"{self._sess}:{w.window_name}"],
                            capture_output=True, timeout=5, check=False,
                        )
                    except Exception:
                        pass

    def test_backend_query(self):
        self.assertIn(self._mgr.backend_kind, ("tmux", "mock"))
        self.assertIsInstance(self._mgr.backend_available, bool)

    def test_create_worker(self):
        w = self._mgr.create_worker(role="researcher", agent_id="agent-1")
        self.assertIsNotNone(w.id)
        self.assertEqual(w.role, "researcher")
        self.assertEqual(w.agent_id, "agent-1")
        self.assertEqual(w.status, WorkerStatus.SPAWNING)
        self.assertTrue(Path(w.log_file).exists())

    def test_spawn_and_list(self):
        w = self._mgr.create_worker(role="developer")
        ok = self._mgr.spawn_worker(w.id, "printf 'hello\\n'; sleep 60")
        self.assertTrue(ok)
        workers = self._mgr.list_workers()
        self.assertGreaterEqual(len(workers), 1)
        self.assertTrue(any(x["id"] == w.id for x in workers))

    def test_spawn_mock_mode(self):
        if self.tmux_ok:
            self.skipTest("tmux available, skip mock test")
        w = self._mgr.create_worker(role="tester")
        ok = self._mgr.spawn_worker(w.id, "echo hello")
        self.assertTrue(ok)
        w2 = self._mgr.get_worker(w.id)
        self.assertEqual(w2.status, WorkerStatus.READY)

    def test_send_command(self):
        w = self._mgr.create_worker(role="dev")
        self._mgr.spawn_worker(w.id)
        ok, msg = self._mgr.send_command(w.id, "echo test123", wait_ready=False)
        self.assertTrue(ok, msg)

    def test_heartbeat(self):
        w = self._mgr.create_worker(role="dev")
        self._mgr.spawn_worker(w.id)
        hb = self._mgr.heartbeat(w.id, "alive")
        self.assertTrue(hb)
        logs = self._mgr.read_logs(w.id)
        self.assertTrue(any("heartbeat" in l for l in logs))

    def test_complete(self):
        w = self._mgr.create_worker(role="dev")
        self._mgr.spawn_worker(w.id)
        ok = self._mgr.complete(w.id, "all done")
        self.assertTrue(ok)
        w2 = self._mgr.get_worker(w.id)
        self.assertEqual(w2.status, WorkerStatus.COMPLETED)

    def test_fail(self):
        w = self._mgr.create_worker(role="dev")
        self._mgr.spawn_worker(w.id)
        ok = self._mgr.fail(w.id, "something broke")
        self.assertTrue(ok)
        w2 = self._mgr.get_worker(w.id)
        self.assertEqual(w2.status, WorkerStatus.FAILED)
        self.assertIn("broke", w2.last_error)

    def test_terminate(self):
        w = self._mgr.create_worker(role="dev")
        self._mgr.spawn_worker(w.id)
        ok = self._mgr.terminate(w.id)
        self.assertTrue(ok)
        w2 = self._mgr.get_worker(w.id)
        self.assertEqual(w2.status, WorkerStatus.FAILED)

    def test_factory_create_team(self):
        specs = [
            {"role": "researcher"},
            {"role": "developer"},
            {"role": "reviewer"},
        ]
        mgr, workers = SindrisWorkerManager.create_team(
            team_name="test-team-alpha",
            workspace_root=self._tmpdir,
            worker_specs=specs,
        )
        self.assertEqual(len(workers), 3)
        for w in workers:
            self.assertIsNotNone(w.id)
            self.assertEqual(w.status, WorkerStatus.SPAWNING)
        mgr.shutdown()

    def test_reconcile_stale(self):
        w = self._mgr.create_worker(role="dev")
        self._mgr.spawn_worker(w.id)
        # Manually set lease to past
        from datetime import datetime, timezone, timedelta
        w.lease_expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()
        w.status = WorkerStatus.RUNNING
        stale = self._mgr.reconcile()
        self.assertIn(w.id, stale)
        w2 = self._mgr.get_worker(w.id)
        self.assertEqual(w2.status, WorkerStatus.FAILED)

    def test_shutdown(self):
        specs = [{"role": "researcher"}, {"role": "developer"}]
        mgr, workers = SindrisWorkerManager.create_team(
            team_name="shutdown-test",
            workspace_root=self._tmpdir,
            worker_specs=specs,
        )
        count = mgr.shutdown()
        self.assertEqual(count, 2)


# ---------------------------------------------------------------------------
# Detection pattern tests
# ---------------------------------------------------------------------------

class TestDetectionPatterns(unittest.TestCase):

    def test_trust_prompt(self):
        cases = [
            ("Do you trust the files in this folder?", True),
            ("Trust the files in this folder", True),
            ("Allow and continue", True),
            ("Yes, proceed", True),
            ("All good, ready to go", False),
            ("", False),
        ]
        for text, expected in cases:
            self.assertEqual(detect_trust_prompt(text), expected, f"failed: {text!r}")

    def test_ready_for_prompt(self):
        cases = [
            ("Ready for input\n>", True),
            ("Ready for your input", True),
            ("Ready for prompt", True),
            ("Send a message", True),
            ("│ >", True),
            ("❯", True),
            ("›", True),
            ("/tmp/repo $", False),  # shell prompt
            ("user@host $ ls", False),
            ("", False),
        ]
        for text, expected in cases:
            self.assertEqual(detect_ready_for_prompt(text), expected, f"failed: {text!r}")

    def test_running_cue(self):
        cases = [
            ("Thinking...", True),
            ("Working on it", True),
            ("Running tests", True),
            ("Analyzing files", True),
            ("done!", False),
        ]
        for text, expected in cases:
            self.assertEqual(detect_running_cue(text), expected, f"failed: {text!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
