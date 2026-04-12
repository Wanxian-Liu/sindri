"""
circuit_breaker 补充测试 - 覆盖 retry 逻辑
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from unittest.mock import patch, MagicMock
from circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    execute_with_circuit_breaker,
    get_circuit_breaker,
)


def test_execute_with_circuit_breaker_retry_then_success():
    """测试retry逻辑: 失败后重试最终成功"""
    # 清理全局缓存
    from circuit_breaker import _circuit_breakers
    _circuit_breakers.clear()
    
    cb = get_circuit_breaker("developer")
    # 设置高阈值，这样几次失败不会打开熔断器
    cb.failure_threshold = 10
    cb.failures = 0
    cb._transition_to_closed()
    
    call_count = [0]  # 使用list以便在嵌套函数中修改
    
    def mock_func(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] < 3:  # 前两次失败
            raise RuntimeError("Temporary failure")
        return "success"
    
    # Mock sleep以加速测试
    with patch('circuit_breaker.time.sleep', return_value=None):
        result = execute_with_circuit_breaker(
            session_key="test-session",
            role_type="developer",
            func=mock_func
        )
    
    assert result == "success"
    assert call_count[0] == 3  # 被调用3次


def test_execute_with_circuit_breaker_circuit_open_error():
    """测试熔断器打开时抛出CircuitOpenError"""
    from circuit_breaker import _circuit_breakers
    _circuit_breakers.clear()
    
    cb = get_circuit_breaker("developer")
    # 设置低阈值，少量失败就打开
    cb.failure_threshold = 1
    cb.failures = 0
    cb._transition_to_closed()
    
    def mock_func(*args, **kwargs):
        raise RuntimeError("Permanent failure")
    
    with patch('circuit_breaker.time.sleep', return_value=None):
        try:
            execute_with_circuit_breaker(
                session_key="test-session",
                role_type="developer",
                func=mock_func
            )
            assert False, "Should have raised CircuitOpenError"
        except CircuitOpenError as e:
            assert "failed after circuit opened" in str(e)


def test_can_execute_half_open_at_limit():
    """测试HALF_OPEN状态下达到调用上限时返回False"""
    cb = CircuitBreaker("developer", half_open_max_calls=2)
    cb._transition_to_half_open()
    
    # 此时 half_open_calls=0, can_execute应该返回True
    assert cb.can_execute() == True
    
    # 模拟已经调用过1次(但还在HALF_OPEN状态)
    # 通过直接操作内部状态来测试边界
    cb.half_open_calls = 1
    assert cb.can_execute() == True  # 1 < 2
    
    cb.half_open_calls = 2
    assert cb.can_execute() == False  # 2 >= 2


def test_record_failure_in_closed_state_below_threshold():
    """测试CLOSED状态下失败但未达到阈值"""
    cb = CircuitBreaker("developer", failure_threshold=5)
    cb._transition_to_closed()
    
    assert cb.state == CircuitState.CLOSED
    
    # 几次失败但不达到阈值
    for i in range(4):
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failures == i + 1


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v"],
        capture_output=False
    )
    sys.exit(result.returncode)
