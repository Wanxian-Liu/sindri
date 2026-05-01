#!/usr/bin/env python3
"""
test_review_logger.py - review_logger.py 完整测试

测试覆盖:
1. ReviewEntry dataclass (init, to_dict, from_dict, __post_init__)
2. ResultSignal enum
3. ResultExtractor.extract_from_exit_code()
4. ResultExtractor.extract_from_output() - 错误/警告/关键模式检测
5. ResultExtractor.summarize()
6. ReviewLogger 初始化
7. ReviewLogger.log()
8. ReviewLogger.log_success()
9. ReviewLogger.log_failure()
10. ReviewLogger.log_timeout()
11. ReviewLogger.log_circuit_break()
12. ReviewLogger._write_entry()
13. ReviewLogger.get_stats()
14. ReviewLogger.list_recent()
15. get_default_logger()
16. log_review()
"""

import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

# ============================================================
# 测试工具
# ============================================================

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


# ============================================================
# fixtures
# ============================================================

@pytest.fixture
def temp_reviews_dir():
    tmp = tempfile.mkdtemp(prefix="reviews_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# ResultSignal
# ============================================================

def test_result_signal_values():
    """测试 ResultSignal enum 值"""
    from review_logger import ResultSignal
    assert_eq(ResultSignal.SUCCESS.value, "success")
    assert_eq(ResultSignal.FAILURE.value, "failure")
    assert_eq(ResultSignal.TIMEOUT.value, "timeout")
    assert_eq(ResultSignal.CIRCUIT_BREAK.value, "circuit_break")
    assert_eq(ResultSignal.CONSENSUS_YES.value, "consensus_yes")
    assert_eq(ResultSignal.CONSENSUS_NO.value, "consensus_no")
    assert_eq(ResultSignal.PARTIAL.value, "partial")


# ============================================================
# ReviewEntry
# ============================================================

def test_review_entry_init():
    """测试 ReviewEntry 基本初始化"""
    from review_logger import ReviewEntry
    e = ReviewEntry(
        id="rev_001",
        task_id="task_001",
        signal="success",
        summary="Task completed",
    )
    assert_eq(e.id, "rev_001")
    assert_eq(e.signal, "success")
    assert_true(e.created_at is not None)
    assert_true(e.updated_at is not None)

def test_review_entry_to_dict():
    """测试 ReviewEntry.to_dict()"""
    from review_logger import ReviewEntry
    e = ReviewEntry(
        id="rev_002",
        task_id="task_002",
        signal="failure",
        summary="Task failed",
        details={"exit_code": 1},
        tags=["error", "important"],
    )
    d = e.to_dict()
    assert_eq(d["id"], "rev_002")
    assert_eq(d["signal"], "failure")
    assert_eq(d["details"]["exit_code"], 1)
    assert_in("error", d["tags"])

def test_review_entry_from_dict():
    """测试 ReviewEntry.from_dict()"""
    from review_logger import ReviewEntry
    d = {
        "id": "rev_003",
        "task_id": "task_003",
        "signal": "success",
        "summary": "OK",
        "details": {},
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
        "tags": [],
        "blocked": False,
        "blocked_reason": None,
    }
    e = ReviewEntry.from_dict(d)
    assert_eq(e.id, "rev_003")
    assert_eq(e.summary, "OK")

def test_review_entry_post_init_sets_timestamps():
    """测试 ReviewEntry.__post_init__() 自动设置时间戳"""
    from review_logger import ReviewEntry
    from datetime import datetime
    e = ReviewEntry(
        id="rev_ts",
        task_id="task_ts",
        signal="success",
        summary="TS test",
    )
    created = datetime.fromisoformat(e.created_at)
    now = datetime.now()
    delta = abs((now - created).total_seconds())
    assert_true(delta < 5)


# ============================================================
# ResultExtractor
# ============================================================

def test_extract_from_exit_code_zero():
    """测试 extract_from_exit_code() 退出码0"""
    from review_logger import ResultExtractor, ResultSignal
    s = ResultExtractor.extract_from_exit_code(0)
    assert_eq(s, ResultSignal.SUCCESS)

def test_extract_from_exit_code_timeout():
    """测试 extract_from_exit_code() 超时退出码124"""
    from review_logger import ResultExtractor, ResultSignal
    s = ResultExtractor.extract_from_exit_code(124)
    assert_eq(s, ResultSignal.TIMEOUT)

def test_extract_from_exit_code_other():
    """测试 extract_from_exit_code() 其他退出码"""
    from review_logger import ResultExtractor, ResultSignal
    s = ResultExtractor.extract_from_exit_code(1)
    assert_eq(s, ResultSignal.FAILURE)
    s2 = ResultExtractor.extract_from_exit_code(127)
    assert_eq(s2, ResultSignal.FAILURE)

def test_extract_from_output_with_error():
    """测试 extract_from_output() 检测错误"""
    from review_logger import ResultExtractor
    output = "INFO: starting process\nERROR: connection refused\nDEBUG: retry..."
    result = ResultExtractor.extract_from_output(output)
    assert_true(result["has_error"])
    assert_eq(result["error_count"], 1)
    assert_in("ERROR: connection refused", result["error_lines"])

def test_extract_from_output_with_warning():
    """测试 extract_from_output() 检测警告"""
    from review_logger import ResultExtractor
    output = "Running...\nWARNING: deprecated API\nDone"
    result = ResultExtractor.extract_from_output(output)
    assert_true(result["has_warning"])
    assert_eq(result["warning_count"], 1)
    assert_in("WARNING: deprecated API", result["warning_lines"])

def test_extract_from_output_with_consensus_yes():
    """测试 extract_from_output() 检测CONSENSUS YES"""
    from review_logger import ResultExtractor
    output = "Some output\n[CONSENSUS: YES]\nDone"
    result = ResultExtractor.extract_from_output(output)
    assert_in("CONSENSUS_YES", result["key_patterns"])

def test_extract_from_output_with_consensus_no():
    """测试 extract_from_output() 检测CONSENSUS NO"""
    from review_logger import ResultExtractor
    output = "Output here\n[CONSENSUS: NO]\nFinished"
    result = ResultExtractor.extract_from_output(output)
    assert_in("CONSENSUS_NO", result["key_patterns"])

def test_extract_from_output_empty():
    """测试 extract_from_output() 空输出"""
    from review_logger import ResultExtractor
    result = ResultExtractor.extract_from_output("")
    assert_false(result["has_error"])
    assert_false(result["has_warning"])
    assert_eq(result["error_count"], 0)

def test_extract_from_output_none():
    """测试 extract_from_output() None"""
    from review_logger import ResultExtractor
    result = ResultExtractor.extract_from_output(None)
    assert_false(result["has_error"])
    assert_eq(result["error_count"], 0)

def test_extract_from_output_multiple_errors():
    """测试 extract_from_output() 多错误"""
    from review_logger import ResultExtractor
    output = "ERROR: one\nERROR: two\nERROR: three"
    result = ResultExtractor.extract_from_output(output)
    assert_eq(result["error_count"], 3)

def test_summarize_with_errors():
    """测试 summarize() 错误摘要"""
    from review_logger import ResultExtractor
    data = {
        "has_error": True,
        "has_warning": False,
        "error_count": 2,
        "warning_count": 0,
        "key_patterns": [],
        "error_lines": ["ERROR: one", "ERROR: two"],
    }
    s = ResultExtractor.summarize(data)
    # summarize returns Chinese: "发现 2 个错误"
    assert_in("2", s)
    assert_in("错误", s)

def test_summarize_with_warnings():
    """测试 summarize() 警告摘要"""
    from review_logger import ResultExtractor
    data = {
        "has_error": False,
        "has_warning": True,
        "error_count": 0,
        "warning_count": 3,
        "key_patterns": [],
        "warning_lines": ["WARN: a", "WARN: b", "WARN: c"],
    }
    s = ResultExtractor.summarize(data)
    # summarize returns Chinese: "发现 3 个警告"
    assert_in("3", s)
    assert_in("警告", s)

def test_summarize_clean():
    """测试 summarize() 干净输出"""
    from review_logger import ResultExtractor
    data = {
        "has_error": False,
        "has_warning": False,
        "error_count": 0,
        "warning_count": 0,
        "key_patterns": [],
    }
    s = ResultExtractor.summarize(data)
    # summarize returns "执行正常" for clean output
    assert_true(len(s) > 0)


# ============================================================
# ReviewLogger
# ============================================================

def test_review_logger_init(temp_reviews_dir):
    """测试 ReviewLogger 初始化"""
    from review_logger import ReviewLogger
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    assert_true(logger.reviews_dir.exists())
    assert_eq(logger.log_count, 0)

def test_review_logger_init_creates_dir(temp_reviews_dir):
    """测试 ReviewLogger 自动创建目录"""
    from review_logger import ReviewLogger
    nested = os.path.join(temp_reviews_dir, "a", "b")
    logger = ReviewLogger(reviews_dir=nested)
    assert_true(os.path.exists(nested))

def test_log_creates_entry(temp_reviews_dir):
    """测试 log() 创建条目"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    entry = logger.log("task_log_001", ResultSignal.SUCCESS, "Task OK")
    assert_eq(entry.task_id, "task_log_001")
    assert_eq(entry.signal, "success")
    assert_eq(entry.summary, "Task OK")
    assert_eq(logger.log_count, 1)

def test_log_with_auto_extract(temp_reviews_dir):
    """测试 log() 自动从输出提取"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    output = "Running...\nERROR: failed\nDone"
    entry = logger.log("task_extract_001", ResultSignal.FAILURE,
                        output=output)
    assert_true(entry.summary)  # 应该自动生成摘要
    assert_true(entry.details.get("output_analysis") is not None)

def test_log_with_auto_extract_no_summary(temp_reviews_dir):
    """测试 log() 无summary时从output生成"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    output = "INFO: done"
    entry = logger.log("task_no_summary", ResultSignal.SUCCESS, output=output)
    assert_true(entry.summary)

def test_log_success(temp_reviews_dir):
    """测试 log_success()"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    entry = logger.log_success("task_ok_001", "All good")
    assert_eq(entry.signal, "success")
    assert_eq(entry.summary, "All good")

def test_log_success_no_summary(temp_reviews_dir):
    """测试 log_success() 无summary"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    entry = logger.log_success("task_ok_002")
    assert_eq(entry.signal, "success")

def test_log_failure(temp_reviews_dir):
    """测试 log_failure()"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    entry = logger.log_failure("task_fail_001", "Something broke")
    assert_eq(entry.signal, "failure")
    assert_eq(entry.summary, "Something broke")

def test_log_timeout(temp_reviews_dir):
    """测试 log_timeout()"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    entry = logger.log_timeout("task_timeout_001", "Execution exceeded limit")
    assert_eq(entry.signal, "timeout")

def test_log_circuit_break(temp_reviews_dir):
    """测试 log_circuit_break()"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    entry = logger.log_circuit_break("task_cb_001", "Too many retries")
    assert_eq(entry.signal, "circuit_break")
    assert_true(entry.blocked)

def test_log_updates_stats(temp_reviews_dir):
    """测试 log() 更新统计"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    logger.log_success("t1")
    logger.log_success("t2")
    logger.log_failure("t3")
    stats = logger.get_stats()
    assert_eq(stats["total_logs"], 3)
    assert_eq(stats["signal_stats"]["success"], 2)
    assert_eq(stats["signal_stats"]["failure"], 1)

def test_write_entry_creates_daily_file(temp_reviews_dir):
    """测试 _write_entry() 按日期创建文件"""
    from review_logger import ReviewLogger, ResultSignal
    from datetime import datetime
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    logger.log("task_file_001", ResultSignal.SUCCESS, "Test")
    date_str = datetime.now().strftime("%Y-%m-%d")
    expected_file = logger.reviews_dir / f"{date_str}.jsonl"
    assert_true(expected_file.exists())

def test_write_entry_json_format(temp_reviews_dir):
    """测试 _write_entry() JSONL格式"""
    from datetime import datetime
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    logger.log("task_jsonl_001", ResultSignal.SUCCESS, "JSON test")
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_path = logger.reviews_dir / f"{date_str}.jsonl"
    lines = file_path.read_text().strip().split("\n")
    assert_true(len(lines) >= 1)
    import json
    entry_data = json.loads(lines[0])
    assert_eq(entry_data["task_id"], "task_jsonl_001")

def test_list_recent_empty(temp_reviews_dir):
    """测试 list_recent() 空目录"""
    from review_logger import ReviewLogger
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    entries = logger.list_recent(limit=5)
    assert_eq(entries, [])

def test_list_recent_with_entries(temp_reviews_dir):
    """测试 list_recent() 返回条目"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    logger.log("t_recent_1", ResultSignal.SUCCESS, "First")
    logger.log("t_recent_2", ResultSignal.FAILURE, "Second")
    entries = logger.list_recent(limit=10)
    assert_true(len(entries) >= 2)

def test_list_recent_respects_limit(temp_reviews_dir):
    """测试 list_recent() 遵守limit"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    for i in range(5):
        logger.log(f"t_limit_{i}", ResultSignal.SUCCESS, f"Task {i}")
    entries = logger.list_recent(limit=2)
    assert_true(len(entries) <= 2)

def test_get_stats(temp_reviews_dir):
    """测试 get_stats()"""
    from review_logger import ReviewLogger, ResultSignal
    logger = ReviewLogger(reviews_dir=temp_reviews_dir)
    logger.log_success("t_stats_1")
    logger.log_failure("t_stats_2")
    stats = logger.get_stats()
    assert_eq(stats["total_logs"], 2)
    assert_true("signal_stats" in stats)
    assert_true("reviews_dir" in stats)


# ============================================================
# 便捷函数
# ============================================================

def test_get_default_logger_singleton():
    """测试 get_default_logger() 单例"""
    from review_logger import get_default_logger, _default_logger
    import review_logger
    review_logger._default_logger = None
    l1 = get_default_logger()
    l2 = get_default_logger()
    assert_true(l1 is l2)

def test_log_review_function(temp_reviews_dir):
    """测试 log_review() 便捷函数"""
    from review_logger import log_review, ResultSignal
    # 使用临时目录
    import review_logger as rl_module
    original = rl_module._default_logger
    rl_module._default_logger = None

    # 创建临时logger
    from review_logger import ReviewLogger
    rl_module._default_logger = ReviewLogger(reviews_dir=temp_reviews_dir)

    entry = log_review("task_quick_001", ResultSignal.SUCCESS, summary="Quick test")
    assert_eq(entry.task_id, "task_quick_001")

    rl_module._default_logger = original


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
