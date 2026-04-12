#!/usr/bin/env python3
"""
test_circuit_breaker.py - CircuitBreaker熔断器完整测试

测试覆盖：
1. CircuitBreaker 初始化与状态
2. CLOSED -> OPEN 状态转换
3. OPEN -> HALF_OPEN 恢复转换
4. HALF_OPEN -> CLOSED 成功恢复
5. HALF_OPEN -> OPEN 失败恢复
6. 指数退避延迟计算
7. record_success / record_failure
8. can_execute 逻辑
9. call 方法（正常执行/超时/熔断）
10. 全局熔断器缓存
11. 装饰器 with_circuit_breaker
12. 状态查询函数
"""

import sys
import os
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from importlib import reload

# 设置路径
SCRIPT_DIR = Path("/home/rayliu/.openclaw/skills/sindris/scripts")
sys.path.insert(0, str(SCRIPT_DIR))

# ============================================================
# 测试工具
# ============================================================

class TestContext:
    """测试上下文"""
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cb_test_")
    
    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg}: expected {expected!r}, got {actual!r}")

def assert_true(condition, msg=""):
    if not condition:
        raise AssertionError(f"{msg}: expected truthy, got {condition!r}")

def assert_raises(exception_type, callable_):
    """断言抛出指定异常"""
    raised = False
    try:
        callable_()
    except exception_type:
        raised = True
    if not raised:
        raise AssertionError(f"Expected {exception_type.__name__} to be raised")


# ============================================================
# 测试类
# ============================================================

def test_circuit_state_enum():
    """测试1: CircuitState枚举值"""
    from circuit_breaker import CircuitState
    
    assert_eq(CircuitState.CLOSED.value, "closed")
    assert_eq(CircuitState.OPEN.value, "open")
    assert_eq(CircuitState.HALF_OPEN.value, "half_open")
    print("✓ test_circuit_state_enum passed")


def test_role_timeouts_config():
    """测试2: 角色超时配置"""
    from circuit_breaker import ROLE_TIMEOUTS
    
    assert ROLE_TIMEOUTS["researcher"] == 300
    assert ROLE_TIMEOUTS["developer"] == 600
    assert ROLE_TIMEOUTS["verifier"] == 180
    assert ROLE_TIMEOUTS["recorder"] == 60
    # 未知角色应有默认值
    assert ROLE_TIMEOUTS.get("unknown", 300) == 300
    print("✓ test_role_timeouts_config passed")


def test_breaker_initialization():
    """测试3: 熔断器初始化"""
    from circuit_breaker import CircuitBreaker, CircuitState, DEFAULT_FAILURE_THRESHOLD
    
    # 默认初始化
    cb = CircuitBreaker("developer")
    assert_eq(cb.role_type, "developer")
    assert_eq(cb.timeout, 600)
    assert_eq(cb.state, CircuitState.CLOSED)
    assert_eq(cb.failures, 0)
    assert_eq(cb.successes, 0)
    assert_eq(cb.failure_threshold, DEFAULT_FAILURE_THRESHOLD)
    assert cb.last_failure_time is None
    
    # 自定义配置
    cb2 = CircuitBreaker(
        role_type="researcher",
        failure_threshold=3,
        recovery_timeout=60,
        half_open_max_calls=5
    )
    assert_eq(cb2.role_type, "researcher")
    assert_eq(cb2.timeout, 300)
    assert_eq(cb2.failure_threshold, 3)
    assert_eq(cb2.recovery_timeout, 60)
    assert_eq(cb2.half_open_max_calls, 5)
    print("✓ test_breaker_initialization passed")


def test_record_success_closed_state():
    """测试4: CLOSED状态下record_success"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    
    # CLOSED状态成功调用，逐渐减少失败计数
    cb.failures = 2
    cb.record_success()
    assert_eq(cb.failures, 1)
    
    cb.record_success()
    assert_eq(cb.failures, 0)
    
    cb.record_success()
    assert_eq(cb.failures, 0)  # 不变，不会是负数
    
    assert_eq(cb.state, CircuitState.CLOSED)
    print("✓ test_record_success_closed_state passed")


def test_record_success_half_open_state():
    """测试5: HALF_OPEN状态下record_success"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer", half_open_max_calls=3)
    cb._transition_to_half_open()
    
    assert_eq(cb.half_open_calls, 0)
    
    # 第三次成功应该转换到CLOSED
    cb.record_success()
    assert_eq(cb.half_open_calls, 1)
    assert_eq(cb.state, CircuitState.HALF_OPEN)
    
    cb.record_success()
    assert_eq(cb.half_open_calls, 2)
    assert_eq(cb.state, CircuitState.HALF_OPEN)
    
    cb.record_success()  # 达到阈值
    assert_eq(cb.state, CircuitState.CLOSED)
    assert_eq(cb.failures, 0)  # 重置
    assert_eq(cb.half_open_calls, 0)  # 重置
    print("✓ test_record_success_half_open_state passed")


def test_record_failure_closed_state():
    """测试6: CLOSED状态下record_failure"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer", failure_threshold=3)
    
    # 未达到阈值，保持CLOSED
    cb.record_failure()
    assert_eq(cb.state, CircuitState.CLOSED)
    assert_eq(cb.failures, 1)
    
    cb.record_failure()
    assert_eq(cb.state, CircuitState.CLOSED)
    assert_eq(cb.failures, 2)
    
    # 达到阈值，转换到OPEN
    cb.record_failure()
    assert_eq(cb.state, CircuitState.OPEN)
    assert_eq(cb.failures, 3)
    assert cb.last_failure_time is not None
    print("✓ test_record_failure_closed_state passed")


def test_record_failure_half_open_state():
    """测试7: HALF_OPEN状态下record_failure"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb._transition_to_half_open()
    
    # 半开状态失败，立即打开
    cb.record_failure()
    assert_eq(cb.state, CircuitState.OPEN)
    assert_eq(cb.failures, 1)
    print("✓ test_record_failure_half_open_state passed")


def test_record_failure_open_state():
    """测试8: OPEN状态下record_failure"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb._transition_to_open()
    
    old_time = cb.last_failure_time
    time.sleep(0.01)
    
    # OPEN状态失败，保持OPEN
    cb.record_failure()
    assert_eq(cb.state, CircuitState.OPEN)
    assert cb.last_failure_time >= old_time
    print("✓ test_record_failure_open_state passed")


def test_can_execute_closed():
    """测试9: CLOSED状态下can_execute"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer")
    assert cb.can_execute() == True
    print("✓ test_can_execute_closed passed")


def test_can_execute_open_not_ready():
    """测试10: OPEN状态下can_execute（未到恢复时间）"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer", recovery_timeout=300)
    cb._transition_to_open()
    
    # 刚刚打开，不到恢复时间
    assert cb.can_execute() == False
    print("✓ test_can_execute_open_not_ready passed")


def test_can_execute_open_ready():
    """测试11: OPEN状态下can_execute（到达恢复时间）"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer", recovery_timeout=0)  # 立即恢复
    cb._transition_to_open()
    
    # 应该转换到HALF_OPEN
    assert cb.can_execute() == True
    print("✓ test_can_execute_open_ready passed")


def test_can_execute_half_open():
    """测试12: HALF_OPEN状态下can_execute"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer", half_open_max_calls=2)
    cb._transition_to_half_open()
    
    # 初始HALF_OPEN状态，half_open_calls=0
    assert cb.can_execute() == True
    assert_eq(cb.half_open_calls, 0)
    
    # 第一次成功，half_open_calls=1，仍为HALF_OPEN
    cb.record_success()
    assert cb.can_execute() == True
    assert_eq(cb.half_open_calls, 1)
    assert cb.state == CircuitState.HALF_OPEN
    
    # 第二次成功，达到上限，立即转换到CLOSED
    cb.record_success()  # 达到上限，转换到CLOSED
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() == True  # CLOSED状态总是返回True
    print("✓ test_can_execute_half_open passed")


def test_exponential_backoff_delay():
    """测试13: 指数退避延迟计算"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer")
    
    # 测试延迟在合理范围
    delays = []
    for attempt in range(5):
        delay = cb._calculate_delay(attempt)
        delays.append(delay)
        assert delay > 0
        assert delay <= cb.max_delay * 1.5  # 包含jitter
    
    # 延迟应该递增（指数）
    assert delays[1] >= delays[0] * cb.exponential_base * 0.5  # 近似递增
    print(f"  Delays: {[f'{d:.2f}' for d in delays]}")
    print("✓ test_exponential_backoff_delay passed")


def test_call_success():
    """测试14: call方法成功执行"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer")
    
    def add(a, b):
        return a + b
    
    result = cb.call(add, 2, 3)
    assert_eq(result, 5)
    assert_eq(cb.failures, 0)
    assert_eq(cb.state.value, "closed")
    print("✓ test_call_success passed")


def test_call_failure_then_success():
    """测试15: call方法失败后成功"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer", failure_threshold=3)
    
    call_count = [0]
    
    def flaky_func():
        call_count[0] += 1
        if call_count[0] < 2:
            raise ValueError("temporary error")
        return "success"
    
    # 第一次调用会失败，但不会打开熔断器
    try:
        cb.call(flaky_func)
    except ValueError:
        pass
    
    # 第二次调用成功
    result = cb.call(flaky_func)
    assert_eq(result, "success")
    print("✓ test_call_failure_then_success passed")


def test_call_circuit_opened():
    """测试16: call方法熔断打开"""
    from circuit_breaker import CircuitBreaker, CircuitOpenError
    
    cb = CircuitBreaker("developer", failure_threshold=2)
    
    def always_fail():
        raise RuntimeError("always fails")
    
    # 连续失败，达到阈值
    assert_raises(CircuitOpenError, lambda: cb.call(always_fail))
    assert_raises(CircuitOpenError, lambda: cb.call(always_fail))
    
    # 此时熔断器打开，抛出异常
    assert_raises(CircuitOpenError, lambda: cb.call(always_fail))
    print("✓ test_call_circuit_opened passed")


def test_transition_to_half_open():
    """测试17: 转换到HALF_OPEN状态"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb._transition_to_half_open()
    
    assert_eq(cb.state, CircuitState.HALF_OPEN)
    assert_eq(cb.half_open_calls, 0)
    print("✓ test_transition_to_half_open passed")


def test_transition_to_closed():
    """测试18: 转换到CLOSED状态（恢复成功）"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb.failures = 5
    cb.successes = 2
    cb.last_failure_time = time.time()
    cb._transition_to_closed()
    
    assert_eq(cb.state, CircuitState.CLOSED)
    assert_eq(cb.failures, 0)
    assert_eq(cb.successes, 0)
    assert cb.last_failure_time is None
    print("✓ test_transition_to_half_open passed")


def test_transition_to_open():
    """测试19: 转换到OPEN状态"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb._transition_to_open()
    
    assert_eq(cb.state, CircuitState.OPEN)
    assert cb.last_failure_time is not None
    print("✓ test_transition_to_open passed")


def test_should_attempt_recovery_immediate():
    """测试20: 立即尝试恢复"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer")
    cb.last_failure_time = None
    assert cb._should_attemptRecovery() == True
    print("✓ test_should_attempt_recovery_immediate passed")


def test_should_attempt_recovery_timeout():
    """测试21: 超时后尝试恢复"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer", recovery_timeout=0)
    cb.last_failure_time = time.time()
    
    # recovery_timeout=0 应该立即返回True
    assert cb._should_attemptRecovery() == True
    print("✓ test_should_attempt_recovery_timeout passed")


def test_with_circuit_breaker_decorator():
    """测试22: 装饰器with_circuit_breaker"""
    from circuit_breaker import with_circuit_breaker, CircuitOpenError
    
    @with_circuit_breaker("developer", failure_threshold=1)
    def failing_func():
        raise ValueError("fail")
    
    assert_raises(CircuitOpenError, failing_func)
    print("✓ test_with_circuit_breaker_decorator passed")


def test_global_circuit_breaker_cache():
    """测试23: 全局熔断器缓存"""
    from circuit_breaker import get_circuit_breaker, reset_circuit, _circuit_breakers
    
    # 获取熔断器
    cb1 = get_circuit_breaker("developer")
    cb2 = get_circuit_breaker("developer")
    assert cb1 is cb2  # 同一实例
    
    cb3 = get_circuit_breaker("researcher")
    assert cb3 is not cb1  # 不同角色不同实例
    
    # 重置
    result = reset_circuit("developer")
    assert result["status"] == "reset"
    assert "developer" not in _circuit_breakers
    print("✓ test_global_circuit_breaker_cache passed")


def test_get_circuit_status():
    """测试24: 获取熔断器状态"""
    from circuit_breaker import get_circuit_breaker, get_circuit_status, CircuitState
    
    cb = get_circuit_breaker("verifier")
    status = get_circuit_status("verifier")
    
    assert status["role_type"] == "verifier"
    assert status["state"] == "closed"
    assert "failures" in status
    assert "successes" in status
    assert "timeout" in status
    assert "last_failure_time" in status
    assert "failure_threshold" in status
    print("✓ test_get_circuit_status passed")


def test_get_all_circuits_status():
    """测试25: 获取所有熔断器状态"""
    from circuit_breaker import get_circuit_breaker, get_all_circuits_status
    
    get_circuit_breaker("developer")
    get_circuit_breaker("researcher")
    
    all_status = get_all_circuits_status()
    
    assert "developer" in all_status
    assert "researcher" in all_status
    assert isinstance(all_status["developer"], dict)
    print("✓ test_get_all_circuits_status passed")


def test_execute_with_circuit_breaker_success():
    """测试26: execute_with_circuit_breaker成功执行"""
    from circuit_breaker import execute_with_circuit_breaker, get_circuit_breaker
    
    reset_circuit = lambda rt: get_circuit_breaker(rt)  # just reference
    
    def mock_func():
        return "result"
    
    result = execute_with_circuit_breaker(
        session_key="test_session",
        role_type="developer",
        func=mock_func
    )
    assert_eq(result, "result")
    print("✓ test_execute_with_circuit_breaker_success passed")


def test_execute_with_circuit_breaker_circuit_open():
    """测试27: execute_with_circuit_breaker熔断打开"""
    from circuit_breaker import (
        execute_with_circuit_breaker,
        get_circuit_breaker,
        reset_circuit,
        CircuitOpenError
    )
    
    # 先让熔断器打开
    cb = get_circuit_breaker("developer")
    cb._transition_to_open()
    
    def mock_func():
        return "result"
    
    assert_raises(
        CircuitOpenError,
        lambda: execute_with_circuit_breaker(
            session_key="test_session",
            role_type="developer",
            func=mock_func
        )
    )
    
    # 清理
    reset_circuit("developer")
    print("✓ test_execute_with_circuit_breaker_circuit_open passed")


def test_circuit_open_error():
    """测试28: CircuitOpenError异常"""
    from circuit_breaker import CircuitOpenError
    
    err = CircuitOpenError("test error")
    assert "test error" in str(err)
    
    # CircuitOpenError是Exception子类
    assert isinstance(err, Exception)
    
    # 使用raise from语法可以链接异常
    try:
        raise CircuitOpenError("wrapped") from ValueError("cause")
    except CircuitOpenError as e:
        assert e.__cause__ is not None
    
    print("✓ test_circuit_open_error passed")


def test_circuit_breaker_unknown_role_type():
    """测试29: 未知角色类型使用默认值超时"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("unknown_role")
    assert_eq(cb.timeout, 300)  # 默认值
    print("✓ test_circuit_breaker_unknown_role_type passed")


def test_half_open_max_calls_boundary():
    """测试30: 半开状态最大调用次数边界"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer", half_open_max_calls=1)
    cb._transition_to_half_open()
    
    # HALF_OPEN状态下can_execute返回True
    assert cb.can_execute() == True
    # record_success达到阈值后立即转换到CLOSED
    cb.record_success()  # 达到阈值，转换到CLOSED
    # CLOSED状态下can_execute返回True
    assert cb.can_execute() == True
    print("✓ test_half_open_max_calls_boundary passed")


# ============================================================
# 主函数
# ============================================================

def run_all_tests():
    tests = [
        test_circuit_state_enum,
        test_role_timeouts_config,
        test_breaker_initialization,
        test_record_success_closed_state,
        test_record_success_half_open_state,
        test_record_failure_closed_state,
        test_record_failure_half_open_state,
        test_record_failure_open_state,
        test_can_execute_closed,
        test_can_execute_open_not_ready,
        test_can_execute_open_ready,
        test_can_execute_half_open,
        test_exponential_backoff_delay,
        test_call_success,
        test_call_failure_then_success,
        test_call_circuit_opened,
        test_transition_to_half_open,
        test_transition_to_closed,
        test_transition_to_open,
        test_should_attempt_recovery_immediate,
        test_should_attempt_recovery_timeout,
        test_with_circuit_breaker_decorator,
        test_global_circuit_breaker_cache,
        test_get_circuit_status,
        test_get_all_circuits_status,
        test_execute_with_circuit_breaker_success,
        test_execute_with_circuit_breaker_circuit_open,
        test_circuit_open_error,
        test_circuit_breaker_unknown_role_type,
        test_half_open_max_calls_boundary,
    ]

    print("=" * 60)
    print("CircuitBreaker 熔断器测试")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"结果: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
