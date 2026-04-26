#!/usr/bin/env python3
"""
test_final_supplement.py - 最终补充测试
覆盖剩余未覆盖代码
"""

import os, sys, time, tempfile, shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


# ============================================================================
# circuit_breaker: __main__ block + retry boundaries
# ============================================================================

def test_circuit_breaker_main_block():
    """覆盖 __main__ 块 (lines 362-394)"""
    from circuit_breaker import CircuitBreaker, CircuitState, ROLE_TIMEOUTS, get_circuit_status, get_all_circuits_status
    
    assert ROLE_TIMEOUTS["researcher"] == 300
    assert ROLE_TIMEOUTS["developer"] == 600
    
    cb = CircuitBreaker("developer")
    assert cb.state == CircuitState.CLOSED
    assert cb.timeout == 600
    
    for i in range(6):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN
    
    cb._transition_to_half_open()
    assert cb.state == CircuitState.HALF_OPEN
    for i in range(3):
        cb.record_success()
    assert cb.state == CircuitState.CLOSED
    
    status = get_circuit_status("developer")
    assert status["role_type"] == "developer"
    assert status["state"] == "closed"
    
    all_status = get_all_circuits_status()
    assert "developer" in all_status


def test_circuit_breaker_call_exception_and_retry():
    """覆盖 call 方法异常触发重试"""
    from circuit_breaker import CircuitBreaker, CircuitOpenError
    
    cb = CircuitBreaker("developer")
    cb.failure_threshold = 100
    count = [0]
    
    def flaky():
        count[0] += 1
        if count[0] < 3:
            raise ValueError("temp")
        return "ok"
    
    with patch.object(cb, '_calculate_delay', return_value=0.01):
        result = cb.call(flaky)
    assert result == "ok"
    assert count[0] == 3


def test_circuit_breaker_can_execute_open_at_recovery():
    """覆盖 OPEN 状态到达恢复时间转换"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer", recovery_timeout=1)
    cb.state = CircuitState.OPEN
    cb.last_failure_time = time.time() - 2
    
    result = cb.can_execute()
    assert result == True
    assert cb.state == CircuitState.HALF_OPEN


# ============================================================================
# match_roles: CLI __main__ block
# ============================================================================

def test_match_roles_cli_main_block():
    """覆盖 CLI __main__ 块 (lines 294-326)"""
    from match_roles import match_roles, list_categories, get_role_by_id
    
    result = match_roles(["backend", "performance"], top_k=3)
    assert "matched_roles" in result
    
    cat_result = list_categories()
    assert "categories" in cat_result
    assert cat_result["total_roles"] > 0
    
    role = get_role_by_id("web-developer")
    if role is not None:
        assert "id" in role
    assert get_role_by_id("nonexistent-xyz") is None


def test_match_roles_string_input():
    """字符串自动转列表"""
    from match_roles import match_roles
    result = match_roles("performance", top_k=3)
    assert "matched_roles" in result


# ============================================================================
# worktree_officer: remaining git operations
# ============================================================================

def test_worktree_officer_setup_project_git_exists(tmp_path):
    """覆盖 git仓库已存在时的 setup_project"""
    from worktree_officer import WorktreeOfficer
    import subprocess
    
    git_dir = tmp_path / "git_repo"
    git_dir.mkdir()
    subprocess.run(["git", "init"], cwd=git_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=git_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=git_dir, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "i"], cwd=git_dir, capture_output=True)
    
    officer = WorktreeOfficer()
    result = officer.setup_project(str(git_dir))
    assert result == True
    assert officer.project_dir == str(git_dir)


def test_worktree_officer_setup_worktree_branch_exists(tmp_path):
    """覆盖分支已存在的 setup_worktree 分支"""
    from worktree_officer import WorktreeOfficer, WorktreeConfig
    import subprocess
    
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init"], cwd=proj, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=proj, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=proj, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "i"], cwd=proj, capture_output=True)
    
    config = WorktreeConfig(base_dir=str(tmp_path / "wt"), project_name="proj")
    officer = WorktreeOfficer(config)
    officer.project_dir = str(proj)
    
    def mock_git(args, cwd=None):
        if args[0] == 'worktree' and args[1] == 'add':
            return (128, "", "exists")
        elif args[0] == 'worktree' and args[1] == 'list':
            return (0, f"{tmp_path}/wt/proj/agent1  agent1\n", "")
        return (0, "", "")
    officer._run_git = mock_git
    
    with patch('os.path.exists', return_value=True):
        with patch.object(officer, 'remove_worktree', return_value=True):
            result = officer.setup_worktree("agent1")
    assert result == str(tmp_path / "wt" / "proj" / "agent1")


def test_worktree_officer_remove_worktree_full(tmp_path):
    """覆盖 remove_worktree 完整清理"""
    from worktree_officer import WorktreeOfficer
    
    officer = WorktreeOfficer()
    wt_dir = tmp_path / "agent1"
    wt_dir.mkdir()
    officer.worktree_map["agent1"] = str(wt_dir)
    
    git_calls = []
    def mock_git(args, cwd=None):
        git_calls.append(args)
        return (0, "", "")
    officer._run_git = mock_git
    
    with patch('shutil.rmtree'):
        result = officer.remove_worktree("agent1")
    assert result == True
    assert "agent1" not in officer.worktree_map
    assert any(args[0] == 'branch' and args[1] == '-D' for args in git_calls)


def test_worktree_officer_remove_from_git_list(tmp_path):
    """覆盖 agent不在map但git list有时"""
    from worktree_officer import WorktreeOfficer
    
    officer = WorktreeOfficer()
    assert "agent1" not in officer.worktree_map
    
    def mock_git(args, cwd=None):
        if args[0] == 'worktree' and args[1] == 'list':
            return (0, f"{tmp_path}/agent1  council/agent1\n", "")
        return (0, "", "")
    officer._run_git = mock_git
    
    with patch('shutil.rmtree'):
        result = officer.remove_worktree("agent1")
    assert result == True


# ============================================================================
# ralph_loop: verify_skill + __main__ block
# ============================================================================

@pytest.mark.anyio
async def test_ralph_verify_skill():
    """覆盖 verify_skill 函数"""
    from ralph_loop import verify_skill, RalphDemoChecks

    demo = RalphDemoChecks()
    items = [{"name": "t1", "check_fn": demo.demo_all_pass_a}]
    result = await verify_skill("test-skill", items)
    assert hasattr(result, 'success')
    assert hasattr(result, 'total_rounds')


@pytest.mark.anyio
async def test_ralph_loop_main_block():
    """覆盖 __main__ 块"""
    from ralph_loop import RalphLoop, RalphDemoChecks

    demo = RalphDemoChecks()
    items = [
        {"name": "f1", "check_fn": demo.demo_all_pass_a},
        {"name": "f2", "check_fn": demo.demo_output_fail},
    ]
    v = RalphLoop(task_name="test", verify_items=items)
    result = await v.run()
    assert result.total_rounds >= 1
    assert result.consecutive_passed < 3


# ============================================================================
# sindris_tmux_manager: remaining exception paths
# ============================================================================

def test_tmux_kill_session_exception(tmp_path):
    """覆盖 kill_session 异常"""
    from sindris_tmux_manager import TmuxManager
    mgr = TmuxManager("s", str(tmp_path))
    mgr._available = True
    with patch('subprocess.run', side_effect=OSError("fail")):
        assert mgr.kill_session() == False


def test_tmux_create_window_exception(tmp_path):
    """覆盖 create_window 异常"""
    from sindris_tmux_manager import TmuxManager
    mgr = TmuxManager("s", str(tmp_path))
    mgr._available = True
    with patch('subprocess.run', side_effect=OSError("fail")):
        assert mgr.create_window("w", "echo") == False


def test_tmux_kill_window_exception(tmp_path):
    """覆盖 kill_window 异常"""
    from sindris_tmux_manager import TmuxManager
    mgr = TmuxManager("s", str(tmp_path))
    mgr._available = True
    with patch('subprocess.run', side_effect=OSError("fail")):
        assert mgr.kill_window("w") == False


def test_tmux_send_keys_exception(tmp_path):
    """覆盖 send_keys 异常"""
    from sindris_tmux_manager import TmuxManager
    mgr = TmuxManager("s", str(tmp_path))
    mgr._available = True
    with patch('subprocess.run', side_effect=OSError("fail")):
        assert mgr.send_keys("w", "cmd") == False


def test_tmux_capture_pane_exception(tmp_path):
    """覆盖 capture_pane 异常"""
    from sindris_tmux_manager import TmuxManager
    mgr = TmuxManager("s", str(tmp_path))
    mgr._available = True
    with patch('subprocess.run', side_effect=OSError("fail")):
        assert mgr.capture_pane("w") == ""


def test_tmux_ensure_session_exception(tmp_path):
    """覆盖 ensure_session 异常"""
    from sindris_tmux_manager import TmuxManager
    mgr = TmuxManager("s", str(tmp_path))
    mgr._available = True
    with patch('subprocess.run') as mock:
        mock.side_effect = [MagicMock(returncode=1), OSError("fail")]
        assert mgr.ensure_session() == False


def test_observe_trust_gate(tmp_path):
    """覆盖 observe trust prompt 检测"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    
    with patch.object(mgr._tmux, 'is_available', return_value=True), \
         patch.object(mgr._tmux, 'ensure_session', return_value=True), \
         patch.object(mgr._tmux, 'create_window', return_value=True):
        w = mgr.create_worker("dev")
        mgr.spawn_worker(w.id, "echo")
    
    w.status = WorkerStatus.SPAWNING
    with patch.object(mgr._tmux, 'is_available', return_value=True), \
         patch.object(mgr._tmux, 'capture_pane', return_value="Do you trust the files in this folder?"):
        s = mgr.observe(w.id)
    assert s == WorkerStatus.TRUST_REQUIRED


def test_observe_ready_detection(tmp_path):
    """覆盖 observe ready 检测"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    
    with patch.object(mgr._tmux, 'is_available', return_value=True), \
         patch.object(mgr._tmux, 'ensure_session', return_value=True), \
         patch.object(mgr._tmux, 'create_window', return_value=True):
        w = mgr.create_worker("dev")
        mgr.spawn_worker(w.id, "echo")
    
    w.status = WorkerStatus.RUNNING
    with patch.object(mgr._tmux, 'is_available', return_value=True), \
         patch.object(mgr._tmux, 'capture_pane', return_value="Ready for your input:"):
        s = mgr.observe(w.id)
    assert s == WorkerStatus.READY


def test_observe_running_cue(tmp_path):
    """覆盖 observe running cue"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    
    with patch.object(mgr._tmux, 'is_available', return_value=True), \
         patch.object(mgr._tmux, 'ensure_session', return_value=True), \
         patch.object(mgr._tmux, 'create_window', return_value=True):
        w = mgr.create_worker("dev")
        mgr.spawn_worker(w.id, "echo")
    
    w.status = WorkerStatus.RUNNING
    w.last_error = "old error"
    with patch.object(mgr._tmux, 'is_available', return_value=True), \
         patch.object(mgr._tmux, 'capture_pane', return_value="Thinking..."):
        mgr.observe(w.id)
    assert w.last_error is None


def test_resolve_trust_wrong_status(tmp_path):
    """覆盖 resolve_trust 状态错误"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    w.status = WorkerStatus.READY
    ok, msg = mgr.resolve_trust(w.id)
    assert ok == False
    assert "not waiting" in msg


def test_heartbeat_with_note(tmp_path):
    """覆盖 heartbeat 带note"""
    from sindris_tmux_manager import SindrisWorkerManager
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    w.status = 4  # RUNNING
    result = mgr.heartbeat(w.id, note="alive")
    assert result == True
    assert w.last_heartbeat_at is not None


def test_reconcile_stale(tmp_path):
    """覆盖 reconcile stale 检测"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    from datetime import datetime, timedelta, timezone
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    w.status = WorkerStatus.RUNNING
    w.lease_expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    stale = mgr.reconcile()
    assert w.id in stale
    assert w.status == WorkerStatus.FAILED


def test_complete_with_result(tmp_path):
    """覆盖 complete 带result"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    w.status = WorkerStatus.RUNNING
    result = mgr.complete(w.id, result="done ok")
    assert result == True
    assert w.status == WorkerStatus.COMPLETED


def test_fail_with_reason(tmp_path):
    """覆盖 fail 带reason"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    w.status = WorkerStatus.RUNNING
    result = mgr.fail(w.id, reason="error msg")
    assert result == True
    assert w.last_error == "error msg"


def test_wait_ready_timeout(tmp_path):
    """覆盖 _wait_for_ready 超时"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    w.status = WorkerStatus.SPAWNING
    w.window_name = w.id
    mgr._tmux._available = True
    with patch.object(mgr, 'observe', return_value=WorkerStatus.RUNNING):
        ok, msg = mgr.send_command(w.id, "cmd", wait_ready=True, timeout=0.5)
    assert ok == False
    assert "timeout" in msg.lower()


def test_create_team(tmp_path):
    """覆盖 create_team 工厂"""
    from sindris_tmux_manager import SindrisWorkerManager, Worker
    specs = [{"role": "dev", "command": "echo dev"}]
    mgr, workers = SindrisWorkerManager.create_team("test team", str(tmp_path), specs)
    assert len(workers) == 1
    assert isinstance(workers[0], Worker)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# Additional tests for remaining uncovered lines
def test_wait_ready_detects_ready(tmp_path):
    """覆盖 _wait_for_ready READY 返回 (line 481)"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    w.status = WorkerStatus.SPAWNING
    w.window_name = w.id
    mgr._tmux._available = True
    
    # First call returns RUNNING, second returns READY
    with patch.object(mgr, 'observe', side_effect=[WorkerStatus.RUNNING, WorkerStatus.READY]):
        ok, msg = mgr.send_command(w.id, "cmd", wait_ready=True, timeout=2.0)
    assert ok == True
    assert "ready" in msg.lower()


def test_wait_ready_detects_failed(tmp_path):
    """覆盖 _wait_for_ready FAILED 返回 (line 483)"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    w.status = WorkerStatus.SPAWNING
    w.window_name = w.id
    mgr._tmux._available = True
    
    with patch.object(mgr, 'observe', return_value=WorkerStatus.FAILED):
        ok, msg = mgr.send_command(w.id, "cmd", wait_ready=True, timeout=2.0)
    assert ok == False
    assert "failed" in msg.lower()


def test_observe_ready_with_trust_error_cleared(tmp_path):
    """覆盖 observe ready检测并清除 trust error (line 523)"""
    from sindris_tmux_manager import SindrisWorkerManager, WorkerStatus
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    
    with patch.object(mgr._tmux, 'is_available', return_value=True), \
         patch.object(mgr._tmux, 'ensure_session', return_value=True), \
         patch.object(mgr._tmux, 'create_window', return_value=True):
        w = mgr.create_worker("dev")
        mgr.spawn_worker(w.id, "echo")
    
    w.status = WorkerStatus.RUNNING
    w.last_error = "trust gate: user approval required"  # Has "trust"
    
    with patch.object(mgr._tmux, 'is_available', return_value=True), \
         patch.object(mgr._tmux, 'capture_pane', return_value="Ready for input:"):
        mgr.observe(w.id)
    
    # last_error should be cleared because it contained "trust"
    assert w.last_error is None


def test_read_logs_file_unreadable(tmp_path):
    """覆盖 read_logs 异常处理 (lines 664-665)"""
    from sindris_tmux_manager import SindrisWorkerManager
    mgr = SindrisWorkerManager("s", str(tmp_path), str(tmp_path / "logs"))
    w = mgr.create_worker("dev")
    
    # Make log file unreadable
    log_path = tmp_path / "logs" / f"{w.id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("log content")
    log_path.chmod(0o000)
    
    try:
        lines = mgr.read_logs(w.id)
        assert lines == []  # Should return empty on error
    finally:
        log_path.chmod(0o644)  # Restore for cleanup


def test_worktree_officer_setup_project_git_init_fails(tmp_path):
    """覆盖 setup_project git init失败 (line 81)"""
    from worktree_officer import WorktreeOfficer
    
    officer = WorktreeOfficer()
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    
    def mock_git(args, cwd=None):
        if args[0] == 'rev-parse' and args[1] == '--git-dir':
            return (128, "", "not a git dir")
        if args[0] == 'init':
            return (128, "", "init failed")
        return (0, "", "")
    officer._run_git = mock_git
    
    result = officer.setup_project(str(test_dir))
    assert result == False
