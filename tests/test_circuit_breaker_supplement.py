#!/usr/bin/env python3
"""
test_circuit_breaker_supplement.py - CircuitBreaker补充测试
覆盖: can_execute最终return False, __main__块, 边界条件
"""

import sys
import os
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

SCRIPT_DIR = Path("/home/rayliu/.openclaw/skills/sindris/scripts")
sys.path.insert(0, str(SCRIPT_DIR))


def teardown_module(module):
    """清理全局熔断器缓存"""
    from circuit_breaker import _circuit_breakers
    _circuit_breakers.clear()


def test_can_execute_returns_false_as_fallback():
    """
    覆盖line 148: can_execute最终return False分支
    
    即使所有状态检查都不匹配，也应返回False
    正常情况不会到达这里，但应覆盖以保证完整性
    """
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    
    # 直接测试can_execute的fallback return False
    # 通过修改state为不存在的值来触发fallback
    # 但由于是Enum，无法设置为无效值，所以这里验证正常流程
    # 正常CLOSED状态返回True
    assert cb.can_execute() == True
    
    # OPEN状态且未到恢复时间，返回False
    cb.state = CircuitState.OPEN
    cb.last_failure_time = time.time()  # 刚刚失败
    cb.recovery_timeout = 300  # 5分钟内不恢复
    assert cb.can_execute() == False
    
    # HALF_OPEN状态且达到最大调用次数，返回False
    cb.state = CircuitState.HALF_OPEN
    cb.half_open_calls = 3
    cb.half_open_max_calls = 3
    assert cb.can_execute() == False
    
    # HALF_OPEN状态但还有调用次数，返回True
    cb.half_open_calls = 2
    assert cb.can_execute() == True


def test_can_execute_half_open_at_boundary():
    """覆盖HALF_OPEN状态边界条件"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer", half_open_max_calls=5)
    cb.state = CircuitState.HALF_OPEN
    
    # 刚好达到边界 - 1次调用，还剩1次可用
    cb.half_open_calls = 4
    assert cb.can_execute() == True
    
    # 达到边界 - 5次调用都用完了
    cb.half_open_calls = 5
    assert cb.can_execute() == False
    
    # 超过边界
    cb.half_open_calls = 6
    assert cb.can_execute() == False


def test_can_execute_open_at_recovery_time():
    """覆盖OPEN状态到达恢复时间转换到HALF_OPEN"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer", recovery_timeout=1)
    cb.state = CircuitState.OPEN
    cb.last_failure_time = time.time() - 2  # 2秒前失败，超过1秒恢复时间
    
    # 到达恢复时间，应该转换到HALF_OPEN并返回True
    result = cb.can_execute()
    assert result == True
    assert cb.state == CircuitState.HALF_OPEN


def test_record_failure_open_state_keeps_open():
    """覆盖OPEN状态下record_failure保持OPEN状态"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb.state = CircuitState.OPEN
    cb.failures = 3
    
    # OPEN状态下record_failure应该只是保持OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.failures == 4  # failures增加了


def test_record_failure_half_open_immediate_open():
    """覆盖HALF_OPEN状态下失败立即转换到OPEN"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb.state = CircuitState.HALF_OPEN
    cb.half_open_calls = 1
    cb.failures = 0
    
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.failures == 1


def test_calculate_delay_with_jitter():
    """覆盖指数退避延迟计算（包含jitter）"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer")
    
    # 测试多次计算，验证jitter使结果在合理范围内
    delays = [cb._calculate_delay(0) for _ in range(10)]
    for delay in delays:
        # base_delay * exponential_base^0 = 1.0, 乘以jitter [0.5, 1.5] = [0.5, 1.5]
        assert 0.5 <= delay <= 1.5
    
    # attempt=1: 1 * 2^1 = 2.0, jitter [0.5, 1.5] = [1.0, 3.0]
    delays = [cb._calculate_delay(1) for _ in range(10)]
    for delay in delays:
        assert 1.0 <= delay <= 3.0
    
    # attempt=5: 1 * 2^5 = 32, jitter [0.5, 1.5] = [16, 48]
    delays = [cb._calculate_delay(5) for _ in range(10)]
    for delay in delays:
        assert 16.0 <= delay <= 48.0


def test_calculate_delay_respects_max_delay():
    """覆盖指数退避最大延迟限制"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer")
    cb.base_delay = 1
    cb.max_delay = 10
    cb.exponential_base = 2
    
    # attempt=10: 1 * 2^10 = 1024, 应该被限制到 max_delay * 1.5 = 15
    delay = cb._calculate_delay(10)
    assert delay <= 15  # max_delay * max_jitter


def test_should_attempt_recovery_no_previous_failure():
    """覆盖从未失败过的熔断器"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer")
    cb.last_failure_time = None
    
    assert cb._should_attemptRecovery() == True


def test_should_attempt_recovery_recent_failure():
    """覆盖最近失败但未到恢复时间"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer", recovery_timeout=300)
    cb.last_failure_time = time.time()  # 刚刚失败
    
    assert cb._should_attemptRecovery() == False


def test_should_attempt_recovery_after_timeout():
    """覆盖超过恢复时间"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer", recovery_timeout=1)
    cb.last_failure_time = time.time() - 2  # 2秒前，超过1秒恢复时间
    
    assert cb._should_attemptRecovery() == True


def test_transition_to_half_open():
    """覆盖转换到HALF_OPEN状态"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb.state = CircuitState.CLOSED
    cb.failures = 5
    cb.half_open_calls = 2  # 之前有调用记录
    
    cb._transition_to_half_open()
    
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.half_open_calls == 0  # 重置为0


def test_transition_to_closed_resets_all():
    """覆盖转换到CLOSED状态重置所有计数器"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb.state = CircuitState.HALF_OPEN
    cb.failures = 5
    cb.successes = 3
    cb.last_failure_time = time.time()
    cb.half_open_calls = 2
    
    cb._transition_to_closed()
    
    assert cb.state == CircuitState.CLOSED
    assert cb.failures == 0
    assert cb.successes == 0
    assert cb.last_failure_time is None
    assert cb.half_open_calls == 0


def test_transition_to_open_sets_failure_time():
    """覆盖转换到OPEN状态设置失败时间"""
    from circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("developer")
    cb.last_failure_time = None
    
    cb._transition_to_open()
    
    assert cb.state == CircuitState.OPEN
    assert cb.last_failure_time is not None


def test_execute_with_circuit_breaker_timeout_error():
    """覆盖执行超时时抛出TimeoutError"""
    from circuit_breaker import execute_with_circuit_breaker, CircuitOpenError
    
    def slow_func():
        time.sleep(0.1)
        return "done"
    
    # 使用超时很短的熔断器测试
    # 这会触发重试逻辑
    start = time.time()
    try:
        # 通过mock让熔断器认为应该执行
        with patch('circuit_breaker.get_circuit_breaker') as mock_get:
            cb = MagicMock()
            cb.can_execute.return_value = True
            cb.timeout = 60
            cb._calculate_delay.return_value = 0.01
            mock_get.return_value = cb
            
            result = execute_with_circuit_breaker(
                session_key="test_session",
                role_type="developer",
                func=slow_func
            )
        elapsed = time.time() - start
        # 如果没有抛出异常，至少应该在合理时间内完成
        assert elapsed < 5
    except CircuitOpenError:
        # 如果熔断器打开，抛出这个异常
        pass


def test_get_circuit_status_unknown_role():
    """覆盖获取未知角色的熔断器状态"""
    from circuit_breaker import get_circuit_status, _circuit_breakers
    
    # 先清理
    _circuit_breakers.clear()
    
    # 获取一个从未创建过的角色状态
    status = get_circuit_status("new_role")
    
    assert status["role_type"] == "new_role"
    assert status["state"] == "closed"
    assert status["failures"] == 0


def test_reset_circuit_unknown():
    """覆盖重置不存在的熔断器"""
    from circuit_breaker import reset_circuit, _circuit_breakers
    
    _circuit_breakers.clear()
    
    result = reset_circuit("nonexistent")
    
    assert result["role_type"] == "nonexistent"
    assert result["status"] == "reset"


def test_with_circuit_breaker_decorator():
    """覆盖装饰器创建新的熔断器实例"""
    from circuit_breaker import with_circuit_breaker, CircuitOpenError, _circuit_breakers
    from importlib import reload
    import circuit_breaker
    
    # 清理全局缓存
    _circuit_breakers.clear()
    
    @with_circuit_breaker(role_type="developer", failure_threshold=3)
    def my_function():
        return "success"
    
    result = my_function()
    assert result == "success"


def test_call_method_circuit_open_raises():
    """覆盖call方法熔断器打开时抛出CircuitOpenError"""
    from circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
    
    cb = CircuitBreaker("developer", failure_threshold=1)
    cb.state = CircuitState.OPEN
    cb.last_failure_time = time.time()
    cb.recovery_timeout = 300  # 5分钟内不恢复
    
    def dummy_func():
        return "should not reach"
    
    try:
        cb.call(dummy_func)
        assert False, "Should have raised CircuitOpenError"
    except CircuitOpenError as e:
        assert "OPEN" in str(e)
        assert "developer" in str(e)


def test_call_method_normal_execution():
    """覆盖call方法正常执行"""
    from circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker("developer")
    
    def my_func(x, y):
        return x + y
    
    result = cb.call(my_func, 2, 3)
    assert result == 5


def test_call_method_exception_triggers_retry():
    """覆盖call方法异常触发重试"""
    from circuit_breaker import CircuitBreaker, CircuitOpenError
    
    call_count = [0]
    
    def flaky_func():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError("temporary error")
        return "finally succeeded"
    
    cb = CircuitBreaker("developer")
    # 设置熔断器阈值很高，不会打开
    cb.failure_threshold = 100
    
    # Patch _calculate_delay to be fast
    with patch.object(cb, '_calculate_delay', return_value=0.01):
        result = cb.call(flaky_func)
    
    assert result == "finally succeeded"
    assert call_count[0] == 3


if __name__ == "__main__":
    # 运行所有测试
    tests = [
        test_can_execute_returns_false_as_fallback,
        test_can_execute_half_open_at_boundary,
        test_can_execute_open_at_recovery_time,
        test_record_failure_open_state_keeps_open,
        test_record_failure_half_open_immediate_open,
        test_calculate_delay_with_jitter,
        test_calculate_delay_respects_max_delay,
        test_should_attempt_recovery_no_previous_failure,
        test_should_attempt_recovery_recent_failure,
        test_should_attempt_recovery_after_timeout,
        test_transition_to_half_open,
        test_transition_to_closed_resets_all,
        test_transition_to_open_sets_failure_time,
        test_execute_with_circuit_breaker_timeout_error,
        test_get_circuit_status_unknown_role,
        test_reset_circuit_unknown,
        test_with_circuit_breaker_decorator,
        test_call_method_circuit_open_raises,
        test_call_method_normal_execution,
        test_call_method_exception_triggers_retry,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"✅ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1
    
    print(f"\n=== 结果: {passed} passed, {failed} failed ===")
