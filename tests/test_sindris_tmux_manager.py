"""
test_sindris_tmux_manager.py - SindrisTmuxManager 完整测试
测试所有公开方法、状态转换、事件溯源和Worker生命周期
"""

import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

# 添加scripts路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from sindris_tmux_manager import (
    WorkerStatus,
    WorkerEventKind,
    WorkerEvent,
    Worker,
    TmuxManager,
    SindrisWorkerManager,
    detect_trust_prompt,
    detect_ready_for_prompt,
    detect_running_cue,
    _TRUST_PATTERNS,
    _READY_PATTERNS,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_log_dir(tmp_path):
    """临时日志目录"""
    return str(tmp_path / "logs")


@pytest.fixture
def tmux_manager(temp_log_dir):
    """TmuxManager实例"""
    return TmuxManager(session_name="test-session", log_dir=temp_log_dir)


@pytest.fixture
def worker_manager(temp_log_dir):
    """SindrisWorkerManager实例"""
    return SindrisWorkerManager(
        session_name="test-session",
        workspace_root="/tmp/test-workspace",
        log_dir=temp_log_dir,
    )


@pytest.fixture
def mock_worker():
    """模拟Worker对象"""
    return Worker(
        id="w_test123",
        role="developer",
        agent_id="agent_001",
        status=WorkerStatus.SPAWNING,
        command=None,
        log_file="/tmp/test.log",
    )


# ============================================================================
# Test WorkerStatus Enum
# ============================================================================

class TestWorkerStatus:
    """测试WorkerStatus枚举"""

    def test_all_statuses(self):
        """所有状态值"""
        assert WorkerStatus.SPAWNING.value is not None
        assert WorkerStatus.TRUST_REQUIRED.value is not None
        assert WorkerStatus.READY.value is not None
        assert WorkerStatus.RUNNING.value is not None
        assert WorkerStatus.COMPLETED.value is not None
        assert WorkerStatus.FAILED.value is not None

    def test_status_names(self):
        """状态名称"""
        assert WorkerStatus.SPAWNING.name == "SPAWNING"
        assert WorkerStatus.TRUST_REQUIRED.name == "TRUST_REQUIRED"
        assert WorkerStatus.READY.name == "READY"
        assert WorkerStatus.RUNNING.name == "RUNNING"
        assert WorkerStatus.COMPLETED.name == "COMPLETED"
        assert WorkerStatus.FAILED.name == "FAILED"


# ============================================================================
# Test WorkerEventKind Enum
# ============================================================================

class TestWorkerEventKind:
    """测试WorkerEventKind枚举"""

    def test_all_event_kinds(self):
        """所有事件类型"""
        assert WorkerEventKind.SPAWNED.value is not None
        assert WorkerEventKind.TRUST_REQUIRED.value is not None
        assert WorkerEventKind.TRUST_RESOLVED.value is not None
        assert WorkerEventKind.READY.value is not None
        assert WorkerEventKind.PROMPT_SENT.value is not None
        assert WorkerEventKind.PROMPT_MISDELIVERED.value is not None
        assert WorkerEventKind.RUNNING.value is not None
        assert WorkerEventKind.HEARTBEAT.value is not None
        assert WorkerEventKind.COMPLETED.value is not None
        assert WorkerEventKind.FAILED.value is not None
        assert WorkerEventKind.RESTARTED.value is not None
        assert WorkerEventKind.TERMINATED.value is not None


# ============================================================================
# Test WorkerEvent
# ============================================================================

class TestWorkerEvent:
    """测试WorkerEvent"""

    def test_event_creation(self):
        """创建事件"""
        event = WorkerEvent(
            seq=1,
            kind=WorkerEventKind.SPAWNED,
            status=WorkerStatus.SPAWNING,
            detail="test event",
            timestamp="2024-01-01T00:00:00+00:00",
        )
        assert event.seq == 1
        assert event.kind == WorkerEventKind.SPAWNED
        assert event.detail == "test event"

    def test_to_line(self):
        """转换为日志行"""
        event = WorkerEvent(
            seq=1,
            kind=WorkerEventKind.READY,
            status=WorkerStatus.READY,
            detail="worker ready",
            timestamp="2024-01-01T00:00:00+00:00",
        )
        line = event.to_line()
        assert "READY" in line
        assert "worker ready" in line
        assert "2024-01-01" in line


# ============================================================================
# Test Worker Model
# ============================================================================

class TestWorker:
    """测试Worker模型"""

    def test_worker_creation(self, mock_worker):
        """创建Worker"""
        assert mock_worker.id == "w_test123"
        assert mock_worker.role == "developer"
        assert mock_worker.agent_id == "agent_001"
        assert mock_worker.status == WorkerStatus.SPAWNING
        assert mock_worker.command is None
        assert mock_worker.log_file == "/tmp/test.log"
        assert mock_worker.window_name is None
        assert mock_worker.session_name is None
        assert mock_worker.lease_expires_at is None
        assert mock_worker.last_heartbeat_at is None
        assert mock_worker.assigned_task_ids == []
        assert mock_worker.events == []
        assert mock_worker.last_error is None

    def test_now_iso(self, mock_worker):
        """生成ISO时间戳"""
        ts = mock_worker.now_iso()
        assert "T" in ts  # ISO格式
        assert "+" in ts or "Z" in ts  # 时区

    def test_push_event(self, mock_worker):
        """添加事件"""
        mock_worker.push_event(WorkerEventKind.READY, "ready for work")
        assert len(mock_worker.events) == 1
        assert mock_worker.events[0].kind == WorkerEventKind.READY
        assert mock_worker.events[0].detail == "ready for work"
        assert mock_worker.events[0].seq == 1

    def test_push_multiple_events_seq(self, mock_worker):
        """多事件序号递增"""
        mock_worker.push_event(WorkerEventKind.SPAWNED, "spawned")
        mock_worker.push_event(WorkerEventKind.READY, "ready")
        mock_worker.push_event(WorkerEventKind.RUNNING, "running")

        assert mock_worker.events[0].seq == 1
        assert mock_worker.events[1].seq == 2
        assert mock_worker.events[2].seq == 3

    def test_push_event_with_status_change(self, mock_worker):
        """带状态变化的事件"""
        mock_worker.push_event(
            WorkerEventKind.TRUST_REQUIRED,
            "trust needed",
            new_status=WorkerStatus.TRUST_REQUIRED,
        )
        assert mock_worker.events[0].status == WorkerStatus.TRUST_REQUIRED

    def test_is_stale_no_lease(self, mock_worker):
        """无租约不过期"""
        mock_worker.lease_expires_at = None
        assert mock_worker.is_stale() is False

    def test_is_stale_lease_not_expired(self, mock_worker):
        """租约未过期"""
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_worker.lease_expires_at = future
        mock_worker.status = WorkerStatus.RUNNING
        assert mock_worker.is_stale() is False

    def test_is_stale_lease_expired(self, mock_worker):
        """租约已过期"""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_worker.lease_expires_at = past
        mock_worker.status = WorkerStatus.RUNNING
        assert mock_worker.is_stale() is True

    def test_is_stale_non_running(self, mock_worker):
        """非运行状态不过期"""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_worker.lease_expires_at = past
        mock_worker.status = WorkerStatus.READY
        assert mock_worker.is_stale() is False

    def test_mark_heartbeat(self, mock_worker):
        """标记心跳"""
        mock_worker.mark_heartbeat()
        assert mock_worker.last_heartbeat_at is not None
        assert mock_worker.status == WorkerStatus.SPAWNING  # 不变

    def test_mark_heartbeat_failed_to_ready(self, mock_worker):
        """失败状态收到心跳转为ready"""
        mock_worker.status = WorkerStatus.FAILED
        mock_worker.mark_heartbeat()
        assert mock_worker.status == WorkerStatus.READY

    def test_append_log(self, mock_worker, tmp_path):
        """追加日志"""
        log_file = tmp_path / "test_worker.log"
        mock_worker.log_file = str(log_file)

        mock_worker.append_log("test line 1")
        mock_worker.append_log("test line 2")

        content = log_file.read_text()
        assert "test line 1" in content
        assert "test line 2" in content

    def test_summary(self, mock_worker):
        """摘要信息"""
        summary = mock_worker.summary()
        assert summary["id"] == "w_test123"
        assert summary["role"] == "developer"
        assert summary["status"] == "SPAWNING"
        assert summary["window"] is None
        assert summary["stale"] is False
        assert summary["events_count"] == 0


# ============================================================================
# Test TmuxManager
# ============================================================================

class TestTmuxManager:
    """测试TmuxManager"""

    def test_init(self, tmux_manager):
        """初始化"""
        assert tmux_manager.session_name == "test-session"
        assert tmux_manager._available is None

    def test_is_available_true(self, tmux_manager):
        """tmux可用"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = tmux_manager.is_available()
            assert result is True
            assert tmux_manager._available is True

    def test_is_available_false(self, tmux_manager):
        """tmux不可用"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = tmux_manager.is_available()
            assert result is False
            assert tmux_manager._available is False

    def test_is_available_cached(self, tmux_manager):
        """结果被缓存"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            result = tmux_manager.is_available()
            assert result is True
            mock_run.assert_not_called()

    def test_ensure_session_not_available(self, tmux_manager):
        """tmux不可用时ensure_session返回False"""
        tmux_manager._available = False
        result = tmux_manager.ensure_session()
        assert result is False

    def test_ensure_session_exists(self, tmux_manager):
        """会话已存在"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = tmux_manager.ensure_session()
            assert result is True

    def test_ensure_session_creates_new(self, tmux_manager):
        """创建新会话"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            # 第一次has-session失败，第二次new-session成功
            mock_run.side_effect = [
                MagicMock(returncode=1),  # has-session fails
                MagicMock(returncode=0),  # new-session succeeds
            ]
            result = tmux_manager.ensure_session()
            assert result is True
            assert mock_run.call_count == 2

    def test_ensure_session_exception(self, tmux_manager):
        """ensure_session异常处理"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("test error")
            result = tmux_manager.ensure_session()
            assert result is False

    def test_kill_session(self, tmux_manager):
        """杀死会话"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            result = tmux_manager.kill_session()
            assert result is True
            mock_run.assert_called_once()

    def test_kill_session_not_available(self, tmux_manager):
        """tmux不可用时kill_session返回False"""
        tmux_manager._available = False
        result = tmux_manager.kill_session()
        assert result is False

    def test_create_window(self, tmux_manager):
        """创建窗口"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = tmux_manager.create_window("my-window", "echo hello")
            assert result is True

    def test_create_window_not_available(self, tmux_manager):
        """tmux不可用时create_window返回False"""
        tmux_manager._available = False
        result = tmux_manager.create_window("my-window", "echo hello")
        assert result is False

    def test_create_window_failure(self, tmux_manager):
        """创建窗口失败"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = tmux_manager.create_window("my-window", "echo hello")
            assert result is False

    def test_kill_window(self, tmux_manager):
        """杀死窗口"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            result = tmux_manager.kill_window("my-window")
            assert result is True

    def test_kill_window_not_available(self, tmux_manager):
        """tmux不可用时kill_window返回False"""
        tmux_manager._available = False
        result = tmux_manager.kill_window("my-window")
        assert result is False

    def test_send_keys(self, tmux_manager):
        """发送按键"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            result = tmux_manager.send_keys("my-window", "echo hello", enter=True)
            assert result is True

    def test_send_keys_no_enter(self, tmux_manager):
        """发送按键不带Enter"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            result = tmux_manager.send_keys("my-window", "text", enter=False)
            assert result is True

    def test_send_keys_not_available(self, tmux_manager):
        """tmux不可用时send_keys返回False"""
        tmux_manager._available = False
        result = tmux_manager.send_keys("my-window", "text")
        assert result is False

    def test_capture_pane(self, tmux_manager):
        """捕获窗格输出"""
        tmux_manager._available = True
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="line1\nline2\n")
            result = tmux_manager.capture_pane("my-window", lines=100)
            assert result == "line1\nline2\n"

    def test_capture_pane_not_available(self, tmux_manager):
        """tmux不可用时capture_pane返回空字符串"""
        tmux_manager._available = False
        result = tmux_manager.capture_pane("my-window")
        assert result == ""


# ============================================================================
# Test Trust/Ready Detection
# ============================================================================

class TestTrustDetection:
    """测试信任提示检测"""

    def test_detect_trust_prompt_do_you_trust(self):
        """检测do you trust"""
        assert detect_trust_prompt("Do you trust the files in this folder?") is True

    def test_detect_trust_prompt_allow_continue(self):
        """检测allow and continue"""
        assert detect_trust_prompt("Allow and continue?") is True

    def test_detect_trust_prompt_yes_proceed(self):
        """检测yes proceed"""
        assert detect_trust_prompt("Yes, proceed") is True

    def test_detect_trust_prompt_negative(self):
        """不匹配的内容"""
        assert detect_trust_prompt("Hello world") is False
        assert detect_trust_prompt("Ready for input") is False

    def test_trust_patterns_case_insensitive(self):
        """模式大小写不敏感"""
        # Full phrase required: "do you trust the files in this folder"
        assert detect_trust_prompt("Do you trust the files in this folder") is True
        assert detect_trust_prompt("trust this folder") is True


class TestReadyDetection:
    """测试就绪检测"""

    def test_detect_ready_ready_for_input(self):
        """检测ready for input"""
        assert detect_ready_for_prompt("Ready for input") is True

    def test_detect_ready_ready_for_prompt(self):
        """检测ready for prompt"""
        assert detect_ready_for_prompt("Ready for prompt") is True

    def test_detect_ready_send_message(self):
        """检测send a message"""
        assert detect_ready_for_prompt("Send a message") is True

    def test_detect_ready_shell_prompt_negative(self):
        """shell提示符不是ready"""
        assert detect_ready_for_prompt("$ ") is False
        assert detect_ready_for_prompt("# ") is False
        assert detect_ready_for_prompt("localhost $") is False

    def test_detect_ready_vi_indicators(self):
        """Vi风格指示符是ready - 注意strip()会移除尾随空格"""
        assert detect_ready_for_prompt("│ ›") is True
        assert detect_ready_for_prompt("│ ❯") is True
        assert detect_ready_for_prompt("❯") is True
        assert detect_ready_for_prompt("›") is True
        # "> " - 注意strip后变成">"，所以需要用完整的prefix
        assert detect_ready_for_prompt("│ >") is True

    def test_detect_ready_empty_negative(self):
        """空字符串不是ready"""
        assert detect_ready_for_prompt("") is False
        assert detect_ready_for_prompt("   ") is False

    def test_detect_ready_last_line_only(self):
        """只检查最后一行"""
        content = "some output\nsecond line\nthird line"
        # 默认最后一行不是shell提示符也不是vi指示符
        assert detect_ready_for_prompt(content) is False


class TestRunningDetection:
    """测试运行中检测"""

    def test_detect_running_thinking(self):
        """检测thinking"""
        assert detect_running_cue("thinking...") is True
        assert detect_running_cue("Thinking") is True

    def test_detect_running_working(self):
        """检测working"""
        assert detect_running_cue("Working on it...") is True

    def test_detect_running_running_tests(self):
        """检测running tests"""
        assert detect_running_cue("Running tests...") is True

    def test_detect_running_inspecting(self):
        """检测inspecting"""
        assert detect_running_cue("Inspecting files...") is True

    def test_detect_running_analyzing(self):
        """检测analyzing"""
        assert detect_running_cue("Analyzing...") is True

    def test_detect_running_negative(self):
        """非运行内容"""
        assert detect_running_cue("Done!") is False
        assert detect_running_cue("Ready for input") is False


# ============================================================================
# Test SindrisWorkerManager Init
# ============================================================================

class TestSindrisWorkerManagerInit:
    """测试SindrisWorkerManager初始化"""

    def test_init(self, worker_manager, temp_log_dir):
        """基本初始化"""
        assert worker_manager.workspace_root == "/tmp/test-workspace"
        assert worker_manager.log_dir == Path(temp_log_dir)
        assert worker_manager._workers == {}
        assert worker_manager._tmux is not None

    def test_backend_kind_tmux_available(self, worker_manager):
        """tmux可用时返回tmux"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            assert worker_manager.backend_kind == "tmux"

    def test_backend_kind_mock(self, worker_manager):
        """tmux不可用时返回mock"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=False):
            assert worker_manager.backend_kind == "mock"

    def test_backend_available(self, worker_manager):
        """backend_available委托给tmux"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            assert worker_manager.backend_available is True

        with patch.object(worker_manager._tmux, 'is_available', return_value=False):
            assert worker_manager.backend_available is False


# ============================================================================
# Test Worker Registry
# ============================================================================

class TestWorkerRegistry:
    """测试worker注册"""

    def test_list_workers_empty(self, worker_manager):
        """空时返回空列表"""
        assert worker_manager.list_workers() == []

    def test_list_workers_with_workers(self, worker_manager):
        """有worker时返回摘要列表"""
        w = worker_manager.create_worker(role="developer")
        workers = worker_manager.list_workers()
        assert len(workers) == 1
        assert workers[0]["id"] == w.id

    def test_get_worker_exists(self, worker_manager):
        """获取存在的worker"""
        w = worker_manager.create_worker(role="researcher")
        retrieved = worker_manager.get_worker(w.id)
        assert retrieved is w

    def test_get_worker_not_exists(self, worker_manager):
        """获取不存在的worker返回None"""
        assert worker_manager.get_worker("nonexistent") is None


# ============================================================================
# Test Worker Creation
# ============================================================================

class TestWorkerCreation:
    """测试worker创建"""

    def test_create_worker_basic(self, worker_manager, temp_log_dir):
        """创建基础worker"""
        w = worker_manager.create_worker(role="developer")

        assert w.id.startswith("w_")
        assert w.role == "developer"
        assert w.agent_id.startswith("w_")
        assert w.status == WorkerStatus.SPAWNING
        assert w.command is None
        assert temp_log_dir in w.log_file
        assert w.window_name is None
        assert w.session_name == "test-session"

    def test_create_worker_with_agent_id(self, worker_manager):
        """创建带agent_id的worker"""
        w = worker_manager.create_worker(role="verifier", agent_id="my-agent")
        assert w.agent_id == "my-agent"

    def test_create_worker_log_file_created(self, worker_manager, temp_log_dir):
        """日志文件被创建"""
        w = worker_manager.create_worker(role="recorder")
        assert Path(w.log_file).exists()

    def test_create_worker_events_logged(self, worker_manager):
        """创建事件被记录"""
        w = worker_manager.create_worker(role="tester")
        assert len(w.events) == 1  # SPAWNED
        assert w.events[0].kind == WorkerEventKind.SPAWNED

    def test_create_worker_in_registry(self, worker_manager):
        """worker被加入注册表"""
        w = worker_manager.create_worker(role="tester")
        assert w.id in worker_manager._workers


# ============================================================================
# Test Worker Spawning
# ============================================================================

class TestWorkerSpawning:
    """测试worker生成"""

    def test_spawn_worker_not_in_registry(self, worker_manager):
        """spawn不存在的worker失败"""
        result = worker_manager.spawn_worker("nonexistent")
        assert result is False

    def test_spawn_worker_tmux_available(self, worker_manager):
        """tmux可用时spawn"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            with patch.object(worker_manager._tmux, 'ensure_session', return_value=True):
                with patch.object(worker_manager._tmux, 'create_window', return_value=True):
                    w = worker_manager.create_worker(role="developer")
                    result = worker_manager.spawn_worker(w.id)

                    assert result is True
                    assert w.window_name == w.id
                    assert w.status == WorkerStatus.SPAWNING

    def test_spawn_worker_tmux_create_fails(self, worker_manager):
        """tmux窗口创建失败"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            with patch.object(worker_manager._tmux, 'ensure_session', return_value=True):
                with patch.object(worker_manager._tmux, 'create_window', return_value=False):
                    w = worker_manager.create_worker(role="developer")
                    result = worker_manager.spawn_worker(w.id)

                    assert result is False
                    assert w.status == WorkerStatus.FAILED
                    assert w.last_error is not None

    def test_spawn_worker_mock_mode(self, worker_manager):
        """mock模式spawn"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=False):
            w = worker_manager.create_worker(role="developer")
            result = worker_manager.spawn_worker(w.id)

            assert result is True
            assert w.status == WorkerStatus.READY
            assert w.window_name is None

    def test_spawn_worker_with_command(self, worker_manager):
        """spawn带自定义命令"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=False):
            w = worker_manager.create_worker(role="developer")
            result = worker_manager.spawn_worker(w.id, command="echo hello")

            assert result is True
            assert w.command == "echo hello"


# ============================================================================
# Test Command Dispatch
# ============================================================================

class TestCommandDispatch:
    """测试命令发送"""

    def test_send_command_worker_not_found(self, worker_manager):
        """worker不存在"""
        result, msg = worker_manager.send_command("nonexistent", "echo test")
        assert result is False
        assert "not found" in msg

    def test_send_command_wrong_status(self, worker_manager):
        """worker状态不对"""
        w = worker_manager.create_worker(role="developer")
        w.status = WorkerStatus.COMPLETED

        result, msg = worker_manager.send_command(w.id, "echo test")
        assert result is False
        assert "not ready" in msg

    def test_send_command_success(self, worker_manager):
        """发送命令成功"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=False):
            w = worker_manager.create_worker(role="developer")
            w.status = WorkerStatus.READY

            result, msg = worker_manager.send_command(w.id, "echo hello")

            assert result is True
            assert "dispatched" in msg
            assert w.status == WorkerStatus.RUNNING
            assert w.lease_expires_at is not None

    def test_send_command_with_tmux(self, worker_manager):
        """通过tmux发送命令"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            with patch.object(worker_manager._tmux, 'send_keys', return_value=True) as mock_send:
                w = worker_manager.create_worker(role="developer")
                w.status = WorkerStatus.READY
                w.window_name = "my-window"

                result, msg = worker_manager.send_command(w.id, "echo hello")

                assert result is True
                mock_send.assert_called_once()

    def test_send_command_wait_ready_timeout(self, worker_manager):
        """等待ready超时"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=False):
            w = worker_manager.create_worker(role="developer")
            w.status = WorkerStatus.READY

            # mock observe返回非ready状态
            with patch.object(worker_manager, 'observe', return_value=WorkerStatus.RUNNING):
                result, msg = worker_manager.send_command(
                    w.id, "echo", wait_ready=True, timeout=0.5
                )

            assert result is False
            assert "timeout" in msg.lower()


# ============================================================================
# Test Observation
# ============================================================================

class TestObservation:
    """测试观察功能"""

    def test_observe_worker_not_found(self, worker_manager):
        """观察不存在的worker"""
        result = worker_manager.observe("nonexistent")
        assert result == WorkerStatus.FAILED

    def test_observe_no_screen_mock_mode(self, worker_manager):
        """mock模式无screen返回原状态"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=False):
            w = worker_manager.create_worker(role="developer")
            w.status = WorkerStatus.SPAWNING

            result = worker_manager.observe(w.id)
            assert result == WorkerStatus.SPAWNING

    def test_observe_returns_status(self, worker_manager):
        """observe方法返回worker状态"""
        w = worker_manager.create_worker(role="developer")
        w.status = WorkerStatus.RUNNING

        result = worker_manager.observe(w.id)

        # observe返回当前状态（mock模式下screen为空）
        assert result == WorkerStatus.RUNNING

    def test_observe_with_empty_screen(self, worker_manager):
        """observe处理空screen"""
        w = worker_manager.create_worker(role="developer")
        w.status = WorkerStatus.SPAWNING

        result = worker_manager.observe(w.id)

        # 空screen时返回当前状态
        assert result == WorkerStatus.SPAWNING


# ============================================================================
# Test Trust Resolution
# ============================================================================

class TestTrustResolution:
    """测试信任解决"""

    def test_resolve_trust_worker_not_found(self, worker_manager):
        """worker不存在"""
        result, msg = worker_manager.resolve_trust("nonexistent")
        assert result is False
        assert "not found" in msg

    def test_resolve_trust_wrong_status(self, worker_manager):
        """worker状态不对"""
        w = worker_manager.create_worker(role="developer")
        w.status = WorkerStatus.READY

        result, msg = worker_manager.resolve_trust(w.id)
        assert result is False
        assert "not waiting" in msg.lower()

    def test_resolve_trust_success_mock(self, worker_manager):
        """mock模式解决信任"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=False):
            w = worker_manager.create_worker(role="developer")
            w.status = WorkerStatus.TRUST_REQUIRED
            w.last_error = "trust needed"

            result, msg = worker_manager.resolve_trust(w.id)

            assert result is True
            assert "trust resolved" in msg.lower()
            assert w.status == WorkerStatus.SPAWNING
            assert w.last_error is None

    def test_resolve_trust_with_tmux(self, worker_manager):
        """通过tmux发送y"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            with patch.object(worker_manager._tmux, 'send_keys', return_value=True) as mock_send:
                w = worker_manager.create_worker(role="developer")
                w.status = WorkerStatus.TRUST_REQUIRED
                w.window_name = "my-window"

                result, msg = worker_manager.resolve_trust(w.id)

                assert result is True
                mock_send.assert_called_once()


# ============================================================================
# Test Heartbeat
# ============================================================================

class TestHeartbeat:
    """测试心跳"""

    def test_heartbeat_worker_not_found(self, worker_manager):
        """worker不存在"""
        result = worker_manager.heartbeat("nonexistent")
        assert result is False

    def test_heartbeat_success(self, worker_manager):
        """心跳成功"""
        w = worker_manager.create_worker(role="developer")

        result = worker_manager.heartbeat(w.id, note="still alive")

        assert result is True
        assert w.last_heartbeat_at is not None
        assert len(w.events) >= 1


# ============================================================================
# Test Reconcile
# ============================================================================

class TestReconcile:
    """测试协调"""

    def test_reconcile_no_stale(self, worker_manager):
        """无过期worker"""
        w = worker_manager.create_worker(role="developer")
        w.lease_expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        w.status = WorkerStatus.RUNNING

        stale = worker_manager.reconcile()

        assert stale == []
        assert w.status == WorkerStatus.RUNNING

    def test_reconcile_stale_worker(self, worker_manager):
        """有过期worker"""
        w = worker_manager.create_worker(role="developer")
        w.lease_expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        w.status = WorkerStatus.RUNNING

        stale = worker_manager.reconcile()

        assert w.id in stale
        assert w.status == WorkerStatus.FAILED
        assert "lease expired" in w.last_error.lower()


# ============================================================================
# Test Lifecycle
# ============================================================================

class TestLifecycle:
    """测试生命周期"""

    def test_complete_worker_not_found(self, worker_manager):
        """完成不存在的worker"""
        result = worker_manager.complete("nonexistent")
        assert result is False

    def test_complete_success(self, worker_manager):
        """完成worker"""
        w = worker_manager.create_worker(role="developer")

        result = worker_manager.complete(w.id, result="all done")

        assert result is True
        assert w.status == WorkerStatus.COMPLETED
        assert w.lease_expires_at is None

    def test_fail_worker_not_found(self, worker_manager):
        """失败不存在的worker"""
        result = worker_manager.fail("nonexistent")
        assert result is False

    def test_fail_success(self, worker_manager):
        """失败worker"""
        w = worker_manager.create_worker(role="developer")

        result = worker_manager.fail(w.id, reason="something broke")

        assert result is True
        assert w.status == WorkerStatus.FAILED
        assert w.last_error == "something broke"

    def test_restart_worker_not_found(self, worker_manager):
        """重启不存在的worker"""
        result = worker_manager.restart_worker("nonexistent")
        assert result is False

    def test_restart_with_tmux(self, worker_manager):
        """tmux模式下重启"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            with patch.object(worker_manager._tmux, 'kill_window', return_value=True):
                with patch.object(worker_manager._tmux, 'ensure_session', return_value=True):
                    with patch.object(worker_manager._tmux, 'create_window', return_value=True):
                        w = worker_manager.create_worker(role="developer")
                        w.window_name = "old-window"
                        w.command = "echo test"

                        result = worker_manager.restart_worker(w.id)

                        assert result is True
                        assert w.status == WorkerStatus.SPAWNING

    def test_terminate_not_found(self, worker_manager):
        """终止不存在的worker"""
        result = worker_manager.terminate("nonexistent")
        assert result is False

    def test_terminate_with_tmux(self, worker_manager):
        """tmux模式下终止"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            with patch.object(worker_manager._tmux, 'kill_window', return_value=True):
                w = worker_manager.create_worker(role="developer")
                w.window_name = "my-window"

                result = worker_manager.terminate(w.id)

                assert result is True
                assert w.status == WorkerStatus.FAILED


# ============================================================================
# Test Shutdown
# ============================================================================

class TestShutdown:
    """测试关闭"""

    def test_shutdown_no_workers(self, worker_manager):
        """无worker时关闭"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            with patch.object(worker_manager._tmux, 'kill_session', return_value=True):
                count = worker_manager.shutdown()
                assert count == 0

    def test_shutdown_with_workers(self, worker_manager):
        """有worker时关闭"""
        with patch.object(worker_manager._tmux, 'is_available', return_value=True):
            with patch.object(worker_manager._tmux, 'kill_window', return_value=True):
                with patch.object(worker_manager._tmux, 'kill_session', return_value=True):
                    worker_manager.create_worker(role="dev1")
                    worker_manager.create_worker(role="dev2")

                    count = worker_manager.shutdown()

                    assert count == 2


# ============================================================================
# Test Log Access
# ============================================================================

class TestLogAccess:
    """测试日志访问"""

    def test_read_logs_not_found(self, worker_manager):
        """读取不存在worker的日志"""
        logs = worker_manager.read_logs("nonexistent")
        assert logs == []

    def test_read_logs_empty(self, worker_manager, tmp_path):
        """读取空日志"""
        log_file = tmp_path / "empty.log"
        log_file.touch()

        w = worker_manager.create_worker(role="developer")
        w.log_file = str(log_file)

        logs = worker_manager.read_logs(w.id)
        assert logs == []

    def test_read_logs_with_content(self, worker_manager, tmp_path):
        """读取有内容的日志"""
        log_file = tmp_path / "content.log"
        log_file.write_text("line1\nline2\nline3\n")

        w = worker_manager.create_worker(role="developer")
        w.log_file = str(log_file)

        logs = worker_manager.read_logs(w.id)

        assert len(logs) == 3
        assert "line1" in logs[0]

    def test_read_logs_limit(self, worker_manager, tmp_path):
        """读取日志限制行数"""
        log_file = tmp_path / "limit.log"
        log_file.write_text("\n".join(f"line{i}" for i in range(100)))

        w = worker_manager.create_worker(role="developer")
        w.log_file = str(log_file)

        logs = worker_manager.read_logs(w.id, limit=10)

        assert len(logs) == 10


# ============================================================================
# Test Factory
# ============================================================================

class TestFactory:
    """测试工厂方法"""

    def test_create_team(self, worker_manager, temp_log_dir):
        """创建团队"""
        specs = [
            {"role": "developer"},
            {"role": "researcher"},
        ]

        mgr, workers = SindrisWorkerManager.create_team(
            team_name="Test Team",
            workspace_root="/tmp",
            worker_specs=specs,
        )

        assert len(workers) == 2
        assert workers[0].role == "developer"
        assert workers[1].role == "researcher"
        assert mgr is not None

    def test_create_team_with_agent_id(self, worker_manager):
        """创建团队带agent_id"""
        specs = [
            {"role": "dev1", "agent_id": "custom-agent"},
        ]

        _, workers = SindrisWorkerManager.create_team(
            team_name="Custom Team",
            workspace_root="/tmp",
            worker_specs=specs,
        )

        assert workers[0].agent_id == "custom-agent"

    def test_create_team_name_slug(self, worker_manager):
        """团队名转换为slug"""
        specs = [{"role": "dev"}]

        mgr, _ = SindrisWorkerManager.create_team(
            team_name="My Test Team 123",
            workspace_root="/tmp",
            worker_specs=specs,
        )

        assert "sindris-" in mgr._tmux.session_name

    def test_create_team_with_command(self, worker_manager):
        """创建团队带命令"""
        specs = [
            {"role": "dev", "command": "echo hello"},
        ]

        _, workers = SindrisWorkerManager.create_team(
            team_name="Cmd Team",
            workspace_root="/tmp",
            worker_specs=specs,
        )

        assert workers[0].command == "echo hello"


# ============================================================================
# Test Lease Constants
# ============================================================================

class TestLeaseConstants:
    """测试租约常量"""

    def test_lease_seconds(self):
        """租约秒数"""
        assert SindrisWorkerManager.LEASE_SECONDS == 20 * 60  # 20 minutes
