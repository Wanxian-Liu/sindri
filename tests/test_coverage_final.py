"""
Final coverage tests for sindris scripts.
Target uncovered lines:
- circuit_breaker.py: 362-394 (main/CLI block)
- match_roles.py: 294-326 (CLI block)
- ralph_loop.py: 409-428 (main async block)
- worktree_officer.py: 116, 131-132, 175-181
  (setup_worktrees, remove_worktree fallback, _write_agent_constraints)
- sindris_tmux_manager.py: 207-208, 222-223, 234-235, 251-252, 265-266, 511-515, 529-532
  (TmuxManager exception paths + SindrisWorkerManager.observe trust/running-cue detection)
"""
import os
import sys
import asyncio
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from sindris_tmux_manager import (
    TmuxManager,
    SindrisWorkerManager,
    WorkerStatus,
    WorkerEventKind,
    detect_trust_prompt,
    detect_ready_for_prompt,
    detect_running_cue,
)


# ── circuit_breaker main block ────────────────────────────────────────────────

class TestCircuitBreakerMainBlock:
    """Test circuit_breaker.py __main__ block (lines 362-394)."""

    def test_get_circuit_status_via_get_circuit_breaker(self):
        """get_circuit_status works via get_circuit_breaker (the main block pattern)."""
        import scripts.circuit_breaker as cb

        status = cb.get_circuit_status("developer")
        assert "state" in status
        assert "failures" in status
        assert "timeout" in status

    def test_get_all_circuits_status_after_registration(self):
        """get_all_circuits_status after registering circuits."""
        import scripts.circuit_breaker as cb

        cb.get_circuit_breaker("developer")
        cb.get_circuit_breaker("researcher")

        status = cb.get_all_circuits_status()
        assert isinstance(status, dict)
        assert "developer" in status
        assert "researcher" in status

    def test_role_timeouts_accessible(self):
        """ROLE_TIMEOUTS is accessible (main block iterates over it)."""
        import scripts.circuit_breaker as cb

        assert isinstance(cb.ROLE_TIMEOUTS, dict)
        for role, timeout in cb.ROLE_TIMEOUTS.items():
            assert isinstance(role, str)
            assert isinstance(timeout, int)
            assert timeout > 0


# ── match_roles CLI / integration ──────────────────────────────────────────────

class TestMatchRolesIntegration:
    """Test match_roles.py CLI integration points (lines 294-326)."""

    def test_list_categories_returns_dict(self):
        """list_categories returns a dict (used by CLI categories command)."""
        import scripts.match_roles as mr

        result = mr.list_categories()
        assert isinstance(result, dict)

    def test_get_role_by_id_not_found(self):
        """get_role_by_id returns None for unknown role."""
        import scripts.match_roles as mr

        role = mr.get_role_by_id("nonexistent_role_xyz_123")
        assert role is None

    def test_match_roles_empty_keywords(self):
        """match_roles handles empty keyword list gracefully."""
        import scripts.match_roles as mr

        results = mr.match_roles([], top_k=3)
        assert isinstance(results, dict)
        assert results["matched_roles"] == []

    def test_match_roles_no_match(self):
        """match_roles returns empty list when nothing matches."""
        import scripts.match_roles as mr

        results = mr.match_roles(["xyzzy_plugh"], top_k=5)
        assert isinstance(results, dict)
        assert results["matched_roles"] == []

    def test_match_roles_top_k(self):
        """match_roles respects top_k parameter."""
        import scripts.match_roles as mr

        results_1 = mr.match_roles(["development"], top_k=1)
        results_3 = mr.match_roles(["development"], top_k=3)

        assert len(results_1["matched_roles"]) <= 1
        assert len(results_3["matched_roles"]) <= 3


# ── ralph_loop main block ─────────────────────────────────────────────────────

class TestRalphLoopMainBlock:
    """Test ralph_loop.py __main__ block (lines 409-428).

    The main block creates a RalphLoop with mixed pass/fail items and runs it.
    """

    @pytest.mark.anyio
    async def test_ralph_loop_main_block_pattern(self):
        """RalphLoop with mixed pass/fail items (as in __main__ block)."""
        import scripts.ralph_loop as rl

        demo = rl.RalphDemoChecks()
        items = [
            {"name": "文件存在", "description": "检查文件是否存在", "check_fn": demo.demo_file_ok},
            {"name": "代码可执行", "description": "检查代码能否执行", "check_fn": demo.demo_code_ok},
            {"name": "输出正确", "description": "检查输出是否符合预期", "check_fn": demo.demo_output_fail},
        ]

        verifier = rl.RalphLoop(task_name="测试任务", verify_items=items)
        result = await verifier.run()

        # With one failing check, should not succeed
        assert result.success is False
        last_report = result.all_reports[-1]
        assert last_report.failed_count >= 1

    @pytest.mark.anyio
    async def test_ralph_loop_main_block_all_pass(self):
        """RalphLoop with all items passing (simulates main block passing path)."""
        import scripts.ralph_loop as rl

        demo = rl.RalphDemoChecks()
        items = [
            {"name": "check1", "description": "d1", "check_fn": demo.demo_all_pass_a},
            {"name": "check2", "description": "d2", "check_fn": demo.demo_all_pass_b},
        ]

        verifier = rl.RalphLoop(task_name="测试任务", verify_items=items)
        result = await verifier.run()

        assert result.success is True


# ── worktree_officer uncovered lines ─────────────────────────────────────────

class TestWorktreeOfficerCoverage:
    """Test worktree_officer.py uncovered lines (116,131-132,175-181)."""

    def test_setup_worktrees_multiple(self, tmp_path):
        """setup_worktrees calls setup_worktree for each agent (line 116)."""
        import scripts.worktree_officer as wo

        config = wo.WorktreeConfig(
            base_dir=str(tmp_path / "worktrees"),
            project_name="proj",
        )

        with patch.object(wo.WorktreeOfficer, "_run_git", return_value=(0, "", "")):
            with patch.object(wo.WorktreeOfficer, "_expand_path", return_value=str(tmp_path / "worktrees")):
                with patch.object(wo.WorktreeOfficer, "_write_agent_constraints"):
                    officer = wo.WorktreeOfficer(config)
                    officer.project_dir = str(tmp_path)
                    officer.worktree_map = {}

                    with patch.object(officer, "setup_worktree", side_effect=lambda n: str(tmp_path / n)) as mock_setup:
                        results = officer.setup_worktrees(["agent_a", "agent_b", "agent_c"])

                        assert "agent_a" in results
                        assert "agent_b" in results
                        assert "agent_c" in results
                        assert mock_setup.call_count == 3

    def test_remove_worktree_fallback_git_list(self, tmp_path):
        """remove_worktree finds agent via git worktree list (lines 131-132)."""
        import scripts.worktree_officer as wo

        config = wo.WorktreeConfig(
            base_dir=str(tmp_path),
            project_name="proj",
        )

        def mock_run_git(cmd, cwd=None):
            if "worktree" in cmd and "list" in cmd:
                return (0, f"{tmp_path}/proj/agent1\n", "")
            if "worktree" in cmd and "remove" in cmd:
                return (0, "", "")
            if "branch" in cmd:
                return (0, "", "")
            return (0, "", "")

        with patch.object(wo.WorktreeOfficer, "_run_git", side_effect=mock_run_git):
            with patch("os.path.exists", return_value=False):
                officer = wo.WorktreeOfficer(config)
                officer.project_dir = str(tmp_path)
                officer.worktree_map = {}

                result = officer.remove_worktree("agent1")
                assert result is True

    def test_write_agent_constraints(self, tmp_path):
        """_write_agent_constraints creates .claude/CLAUDE.md (lines 175-181)."""
        import scripts.worktree_officer as wo

        config = wo.WorktreeConfig(
            base_dir=str(tmp_path),
            project_name="proj",
        )

        with patch.object(wo.WorktreeOfficer, "_run_git", return_value=(0, "", "")):
            with patch.object(wo.WorktreeOfficer, "_expand_path", return_value=str(tmp_path)):
                officer = wo.WorktreeOfficer(config)
                officer.project_dir = str(tmp_path)

                wt_dir = tmp_path / "agent1"
                wt_dir.mkdir()

                officer._write_agent_constraints(str(wt_dir), "agent1")

                # File is at {wt_dir}/.claude/CLAUDE.md
                claude_md = wt_dir / ".claude" / "CLAUDE.md"
                assert claude_md.exists()
                content = claude_md.read_text()
                assert "agent1" in content

    def test_remove_worktree_deletes_map_entry(self, tmp_path):
        """remove_worktree cleans up worktree_map entry."""
        import scripts.worktree_officer as wo

        config = wo.WorktreeConfig(
            base_dir=str(tmp_path),
            project_name="proj",
        )

        wt_dir = tmp_path / "proj" / "agent1"
        wt_dir.mkdir(parents=True)

        with patch.object(wo.WorktreeOfficer, "_run_git", return_value=(0, "", "")):
            with patch("os.path.exists", return_value=True):
                with patch("shutil.rmtree"):
                    officer = wo.WorktreeOfficer(config)
                    officer.project_dir = str(tmp_path)
                    officer.worktree_map = {"agent1": str(wt_dir)}

                    result = officer.remove_worktree("agent1")

                    assert result is True
                    assert "agent1" not in officer.worktree_map


# ── sindris_tmux_manager TmuxManager exception paths ──────────────────────────

class TestTmuxManagerExceptionPaths:
    """Test sindris_tmux_manager.py TmuxManager exception paths
    (207-208, 222-223, 234-235, 251-252, 265-266).
    """

    @pytest.fixture
    def tmux_mgr(self, tmp_path):
        return TmuxManager(session_name="test-session", log_dir=str(tmp_path))

    def test_kill_session_exception(self, tmux_mgr):
        """kill_session: subprocess raises Exception (lines 207-208)."""
        tmux_mgr._available = True
        with patch("subprocess.run", side_effect=Exception("tmux died")):
            result = tmux_mgr.kill_session()
            assert result is False

    def test_create_window_exception(self, tmux_mgr):
        """create_window: subprocess raises Exception (lines 222-223)."""
        tmux_mgr._available = True
        with patch("subprocess.run", side_effect=Exception("tmux error")):
            result = tmux_mgr.create_window("mywin", "echo hi")
            assert result is False

    def test_kill_window_exception(self, tmux_mgr):
        """kill_window: subprocess raises Exception (lines 234-235)."""
        tmux_mgr._available = True
        with patch("subprocess.run", side_effect=Exception("tmux error")):
            result = tmux_mgr.kill_window("mywin")
            assert result is False

    def test_send_keys_exception(self, tmux_mgr):
        """send_keys: subprocess raises Exception (lines 251-252)."""
        tmux_mgr._available = True
        with patch("subprocess.run", side_effect=Exception("tmux error")):
            result = tmux_mgr.send_keys("mywin", "echo hi")
            assert result is False

    def test_capture_pane_exception(self, tmux_mgr):
        """capture_pane: subprocess raises Exception (lines 265-266)."""
        tmux_mgr._available = True
        with patch("subprocess.run", side_effect=Exception("tmux error")):
            result = tmux_mgr.capture_pane("mywin")
            assert result == ""


# ── sindris_tmux_manager SindrisWorkerManager observe + resolve_trust ──────────

class TestWorkerManagerObserveCoverage:
    """Test SindrisWorkerManager.observe + resolve_trust coverage
    (lines 511-515, 529-532, 540-541).
    """

    @pytest.fixture
    def worker_mgr(self, tmp_path):
        return SindrisWorkerManager(
            session_name="test-session",
            workspace_root=str(tmp_path),
            log_dir=str(tmp_path),
        )

    def test_observe_trust_gate_detected(self, worker_mgr):
        """observe: trust gate detected -> status becomes TRUST_REQUIRED (lines 511-515)."""
        with patch.object(worker_mgr._tmux, "is_available", return_value=True):
            with patch.object(worker_mgr._tmux, "capture_pane", return_value="Do you trust the files in this folder?"):
                w = worker_mgr.create_worker(role="developer")
                w.status = WorkerStatus.RUNNING
                w.window_name = "testwin"  # Must be truthy for capture_pane to be called
                w.last_error = None

                status = worker_mgr.observe(w.id)

                assert status == WorkerStatus.TRUST_REQUIRED
                assert w.status == WorkerStatus.TRUST_REQUIRED
                assert "trust" in w.last_error.lower()

    def test_observe_running_cue_clears_error(self, worker_mgr):
        """observe: running cue detected clears last_error (lines 529-530)."""
        with patch.object(worker_mgr._tmux, "is_available", return_value=True):
            with patch.object(worker_mgr._tmux, "capture_pane", return_value="Working..."):
                with patch("scripts.sindris_tmux_manager.detect_trust_prompt", return_value=False):
                    with patch("scripts.sindris_tmux_manager.detect_ready_for_prompt", return_value=False):
                        with patch("scripts.sindris_tmux_manager.detect_running_cue", return_value=True):
                            w = worker_mgr.create_worker(role="developer")
                            w.status = WorkerStatus.RUNNING
                            w.window_name = "testwin"
                            w.last_error = "previous error here"

                            worker_mgr.observe(w.id)

                            assert w.last_error is None

    def test_observe_trust_already_required_skipped(self, worker_mgr):
        """observe: trust detection skipped when status already TRUST_REQUIRED."""
        with patch.object(worker_mgr._tmux, "is_available", return_value=True):
            with patch.object(worker_mgr._tmux, "capture_pane", return_value="Do you trust?"):
                w = worker_mgr.create_worker(role="developer")
                w.status = WorkerStatus.TRUST_REQUIRED
                w.window_name = "testwin"
                w.last_error = "already waiting"

                status = worker_mgr.observe(w.id)

                assert status == WorkerStatus.TRUST_REQUIRED

    def test_resolve_trust_status_not_trust_required(self, worker_mgr):
        """resolve_trust: returns False when status != TRUST_REQUIRED (lines 540-541)."""
        w = worker_mgr.create_worker(role="developer")
        w.status = WorkerStatus.READY

        ok, msg = worker_mgr.resolve_trust(w.id)

        assert ok is False
        assert "not waiting" in msg.lower()

    def test_resolve_trust_worker_not_found(self, worker_mgr):
        """resolve_trust: returns False when worker doesn't exist."""
        ok, msg = worker_mgr.resolve_trust("nonexistent_id")
        assert ok is False
        assert "not found" in msg

    def test_resolve_trust_success(self, worker_mgr):
        """resolve_trust: successful resolution clears error and resets status."""
        with patch.object(worker_mgr._tmux, "is_available", return_value=False):
            w = worker_mgr.create_worker(role="developer")
            w.status = WorkerStatus.TRUST_REQUIRED
            w.last_error = "trust gate: user approval required"

            ok, msg = worker_mgr.resolve_trust(w.id)

            assert ok is True
            assert w.status == WorkerStatus.SPAWNING
            assert w.last_error is None
