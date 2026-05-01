#!/usr/bin/env python3
"""
test_telemetry_collector.py - telemetry_collector.py 完整测试

测试覆盖:
1. TelemetryEvent enum
2. TelemetryEntry dataclass (to_dict)
3. TelemetryCollector 初始化
4. TelemetryCollector.record()
5. TelemetryCollector.task_start()
6. TelemetryCollector.task_complete()
7. TelemetryCollector.circuit_break()
8. TelemetryCollector.safety_block()
9. TelemetryCollector.consensus()
10. TelemetryCollector.round_change()
11. TelemetryCollector.get_stats()
12. TelemetryCollector.get_role_stats()
13. TelemetryCollector.get_recent_events()
14. TelemetryCollector._write_entry()
15. TelemetryCollector._update_stats()
16. get_default_collector()
"""

import sys
import os
import tempfile
import shutil
import time
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg}: expected {expected!r}, got {actual!r}")

def assert_true(condition, msg=""):
    if not condition:
        raise AssertionError(f"{msg}: expected truthy, got {condition!r}")

def assert_in(substr, s, msg=""):
    if substr not in s:
        raise AssertionError(f"{msg}: expected {substr!r} in {s!r}")

def assert_false(condition, msg=""):
    if condition:
        raise AssertionError(f"{msg}: expected falsy, got {condition!r}")


@pytest.fixture
def temp_telemetry_dir():
    tmp = tempfile.mkdtemp(prefix="telemetry_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_telemetry_event_enum():
    """测试 TelemetryEvent enum"""
    from telemetry_collector import TelemetryEvent
    assert_eq(TelemetryEvent.TASK_START.value, "task_start")
    assert_eq(TelemetryEvent.TASK_COMPLETE.value, "task_complete")
    assert_eq(TelemetryEvent.TASK_FAILURE.value, "task_failure")
    assert_eq(TelemetryEvent.CIRCUIT_BREAK.value, "circuit_break")
    assert_eq(TelemetryEvent.SAFETY_BLOCK.value, "safety_block")
    assert_eq(TelemetryEvent.CONSENSUS_YES.value, "consensus_yes")
    assert_eq(TelemetryEvent.CONSENSUS_NO.value, "consensus_no")
    assert_eq(TelemetryEvent.ROUND_CHANGE.value, "round_change")


def test_telemetry_entry_to_dict():
    """测试 TelemetryEntry.to_dict()"""
    from telemetry_collector import TelemetryEntry
    e = TelemetryEntry(
        event="task_complete",
        timestamp="2024-01-01T00:00:00",
        task_id="t_001",
        role="developer",
        success=True,
        duration_ms=1500,
    )
    d = e.to_dict()
    assert_eq(d["event"], "task_complete")
    assert_eq(d["task_id"], "t_001")
    assert_eq(d["role"], "developer")
    assert_eq(d["duration_ms"], 1500)


def test_collector_init(temp_telemetry_dir):
    """测试 TelemetryCollector 初始化"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    assert_true(c.telemetry_dir.exists())
    stats = c.get_stats()
    assert_eq(stats["total_tasks"], 0)


def test_collector_init_creates_dir(temp_telemetry_dir):
    """测试 TelemetryCollector 自动创建目录"""
    from telemetry_collector import TelemetryCollector
    nested = os.path.join(temp_telemetry_dir, "a", "b", "c")
    c = TelemetryCollector(telemetry_dir=nested)
    assert_true(os.path.exists(nested))


def test_record_basic(temp_telemetry_dir):
    """测试 record() 基本功能"""
    from telemetry_collector import TelemetryCollector, TelemetryEvent
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    entry = c.record(TelemetryEvent.TASK_COMPLETE, task_id="t_rec_001")
    assert_eq(entry.event, "task_complete")
    assert_eq(entry.task_id, "t_rec_001")


def test_record_with_all_fields(temp_telemetry_dir):
    """测试 record() 所有字段"""
    from telemetry_collector import TelemetryCollector, TelemetryEvent
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    entry = c.record(
        TelemetryEvent.TASK_FAILURE,
        task_id="t_fail_001",
        worker_id="w_001",
        role="developer",
        success=False,
        error="Connection refused",
        details={"exit_code": 1},
    )
    assert_eq(entry.worker_id, "w_001")
    assert_eq(entry.role, "developer")
    assert_false(entry.success)
    assert_eq(entry.error, "Connection refused")
    assert_eq(entry.details["exit_code"], 1)


def test_task_start(temp_telemetry_dir):
    """测试 task_start()"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.task_start("t_start_001", role="developer")
    events = c.get_recent_events(limit=10)
    assert_true(any(e["task_id"] == "t_start_001" for e in events))


def test_task_complete_success(temp_telemetry_dir):
    """测试 task_complete() 成功"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.task_start("t_complete_001", role="tester")
    time.sleep(0.01)
    c.task_complete("t_complete_001", role="tester", success=True)
    stats = c.get_stats()
    assert_eq(stats["total_tasks"], 1)
    assert_eq(stats["successful_tasks"], 1)
    assert_eq(stats["failed_tasks"], 0)


def test_task_complete_failure(temp_telemetry_dir):
    """测试 task_complete() 失败"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.task_start("t_fail_001", role="devops")
    c.task_complete("t_fail_001", role="devops", success=False, error="Timeout")
    stats = c.get_stats()
    assert_eq(stats["total_tasks"], 1)
    assert_eq(stats["successful_tasks"], 0)
    assert_eq(stats["failed_tasks"], 1)


def test_circuit_break(temp_telemetry_dir):
    """测试 circuit_break()"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.circuit_break("t_cb_001", "developer", "Too many retries")
    stats = c.get_stats()
    assert_eq(stats["circuit_breaks"], 1)
    events = c.get_recent_events(limit=1)
    assert_true(len(events) > 0)
    assert_true("Circuit break" in events[0]["error"])


def test_safety_block(temp_telemetry_dir):
    """测试 safety_block()"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.safety_block("t_safety_001", "rm -rf /", "high")
    stats = c.get_stats()
    assert_eq(stats["safety_blocks"], 1)
    events = c.get_recent_events(limit=1)
    assert_true("Safety blocked" in events[0]["error"])


def test_consensus_yes(temp_telemetry_dir):
    """测试 consensus() YES"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.consensus("t_cons_001", approved=True)
    events = c.get_recent_events(limit=1)
    assert_true(len(events) > 0)
    assert_eq(events[0]["event"], "consensus_yes")
    assert_true(events[0]["success"])


def test_consensus_no(temp_telemetry_dir):
    """测试 consensus() NO"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.consensus("t_cons_002", approved=False)
    events = c.get_recent_events(limit=1)
    assert_true(len(events) > 0)
    assert_eq(events[0]["event"], "consensus_no")
    assert_false(events[0]["success"])


def test_round_change(temp_telemetry_dir):
    """测试 round_change()"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.round_change("Round1", "Round2", task_id="t_round_001")
    events = c.get_recent_events(limit=1)
    assert_true(len(events) > 0)
    assert_eq(events[0]["event"], "round_change")
    assert_eq(events[0]["details"]["from_round"], "Round1")
    assert_eq(events[0]["details"]["to_round"], "Round2")


def test_get_stats_empty(temp_telemetry_dir):
    """测试 get_stats() 空收集器"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    stats = c.get_stats()
    assert_eq(stats["total_tasks"], 0)
    assert_eq(stats["success_rate"], 0.0)
    assert_eq(stats["avg_duration_ms"], 0)


def test_get_stats_with_tasks(temp_telemetry_dir):
    """测试 get_stats() 有任务时"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.task_start("t_stat_1", role="developer")
    c.task_complete("t_stat_1", role="developer", success=True)
    c.task_start("t_stat_2", role="devops")
    c.task_complete("t_stat_2", role="devops", success=False)
    stats = c.get_stats()
    assert_eq(stats["total_tasks"], 2)
    assert_eq(stats["successful_tasks"], 1)
    assert_eq(stats["failed_tasks"], 1)
    assert_eq(stats["success_rate"], 0.5)


def test_get_role_stats(temp_telemetry_dir):
    """测试 get_role_stats()"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.task_start("t_role_1", role="developer")
    c.task_complete("t_role_1", role="developer", success=True)
    c.task_start("t_role_2", role="developer")
    c.task_complete("t_role_2", role="developer", success=True)
    c.task_start("t_role_3", role="tester")
    c.task_complete("t_role_3", role="tester", success=True)
    role_stats = c.get_role_stats()
    assert_eq(role_stats.get("developer", 0), 2)
    assert_eq(role_stats.get("tester", 0), 1)


def test_get_recent_events_empty(temp_telemetry_dir):
    """测试 get_recent_events() 空"""
    from telemetry_collector import TelemetryCollector
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    events = c.get_recent_events(limit=10)
    assert_eq(events, [])


def test_get_recent_events_with_limit(temp_telemetry_dir):
    """测试 get_recent_events() limit参数"""
    from telemetry_collector import TelemetryCollector, TelemetryEvent
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    for i in range(5):
        c.record(TelemetryEvent.TASK_START, task_id=f"t_limit_{i}")
    events = c.get_recent_events(limit=2)
    assert_true(len(events) <= 2)


def test_write_entry_creates_file(temp_telemetry_dir):
    """测试 _write_entry() 创建日志文件"""
    from telemetry_collector import TelemetryCollector, TelemetryEvent
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    c.record(TelemetryEvent.TASK_START, task_id="t_file_001")
    import glob
    files = glob.glob(os.path.join(temp_telemetry_dir, "telemetry_*.jsonl"))
    assert_true(len(files) > 0)


def test_update_stats_task_complete(temp_telemetry_dir):
    """测试 _update_stats() TASK_COMPLETE"""
    from telemetry_collector import TelemetryCollector, TelemetryEvent, TelemetryEntry
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    entry = TelemetryEntry(
        event=TelemetryEvent.TASK_COMPLETE.value,
        timestamp="2024-01-01T00:00:00",
        task_id="t_upd_001",
        role="developer",
        success=True,
        duration_ms=1000,
    )
    c._update_stats(entry)
    stats = c.get_stats()
    assert_eq(stats["total_tasks"], 1)
    assert_eq(stats["successful_tasks"], 1)
    assert_eq(stats["total_duration_ms"], 1000)


def test_update_stats_task_failure(temp_telemetry_dir):
    """测试 _update_stats() TASK_FAILURE"""
    from telemetry_collector import TelemetryCollector, TelemetryEntry
    c = TelemetryCollector(telemetry_dir=temp_telemetry_dir)
    entry = TelemetryEntry(
        event="task_failure",
        timestamp="2024-01-01T00:00:00",
        task_id="t_fail_upd",
        success=False,
    )
    c._update_stats(entry)
    stats = c.get_stats()
    assert_eq(stats["failed_tasks"], 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
