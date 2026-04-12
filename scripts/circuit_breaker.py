"""
circuit_breaker.py - 熔断机制模块
用于 Sindri's 多Agent协作系统的可靠性保护

V1.0.0 - 基于织界中枢熔断规则 V2.0
"""

import time
import functools
import logging
from typing import Callable, Any, Optional, Dict
from enum import Enum

# 配置日志
logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 闭合状态 - 正常执行
    OPEN = "open"          # 打开状态 - 拒绝执行，快速失败
    HALF_OPEN = "half_open"  # 半开状态 - 尝试恢复


# 角色超时配置（来自织界中枢熔断规则）
ROLE_TIMEOUTS: Dict[str, int] = {
    "researcher": 300,   # 研究员 300s
    "developer": 600,     # 开发者 600s
    "verifier": 180,     # 验证者 180s
    "recorder": 60,      # 记录员 60s
}

# 熔断器配置
DEFAULT_FAILURE_THRESHOLD = 5      # 失败次数阈值
DEFAULT_RECOVERY_TIMEOUT = 30      # 恢复尝试间隔(秒)
DEFAULT_HALF_OPEN_MAX_CALLS = 3    # 半开状态最大尝试次数


class CircuitBreaker:
    """
    熔断器类
    
    特性：
    - 基于角色类型的超时配置
    - 三态转换：closed -> open -> half_open -> closed
    - 指数退避重试策略
    - 线程安全
    """
    
    def __init__(
        self,
        role_type: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: int = DEFAULT_RECOVERY_TIMEOUT,
        half_open_max_calls: int = DEFAULT_HALF_OPEN_MAX_CALLS
    ):
        self.role_type = role_type
        self.timeout = ROLE_TIMEOUTS.get(role_type, 300)
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.failures = 0
        self.successes = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        
        # 指数退避配置
        self.base_delay = 1
        self.max_delay = 60
        self.exponential_base = 2
    
    def _calculate_delay(self, attempt: int) -> float:
        """计算指数退避延迟"""
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        # 添加 jitter 避免惊群效应
        import random
        return delay * (0.5 + random.random())
    
    def _should_attemptRecovery(self) -> bool:
        """检查是否应该尝试恢复"""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _transition_to_half_open(self):
        """转换到半开状态"""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        logger.info(f"[CircuitBreaker:{self.role_type}] 转换到 HALF_OPEN 状态")
    
    def _transition_to_closed(self):
        """转换到闭合状态（恢复成功）"""
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        logger.info(f"[CircuitBreaker:{self.role_type}] 恢复 CLOSED 状态")
    
    def _transition_to_open(self):
        """转换到打开状态"""
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        logger.warning(f"[CircuitBreaker:{self.role_type}] 触发熔断 OPEN 状态 (failures={self.failures})")
    
    def record_success(self):
        """记录成功调用"""
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # 成功时逐渐减少失败计数
            self.failures = max(0, self.failures - 1)
    
    def record_failure(self):
        """记录失败调用"""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # 半开状态失败，立即打开
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            if self.failures >= self.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitState.OPEN:
            # 保持打开状态，重置恢复计时
            pass
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attemptRecovery():
                self._transition_to_half_open()
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        
        return False
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器执行函数
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            CircuitOpenError: 熔断器打开时抛出
            TimeoutError: 执行超时时抛出
        """
        if not self.can_execute():
            raise CircuitOpenError(
                f"CircuitBreaker [{self.role_type}] is OPEN. "
                f"Try again in {self.recovery_timeout}s."
            )
        
        start_time = time.time()
        attempt = 0
        last_error = None
        
        while True:
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                last_error = e
                self.record_failure()
                
                # 如果熔断器打开或达到最大重试次数，抛出异常
                if not self.can_execute():
                    raise CircuitOpenError(
                        f"CircuitBreaker [{self.role_type}] opened after failures"
                    ) from last_error
                
                # 计算延迟并等待
                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"[CircuitBreaker:{self.role_type}] 调用失败 (attempt={attempt}), "
                    f"{delay:.1f}s 后重试"
                )
                time.sleep(delay)
                attempt += 1


class CircuitOpenError(Exception):
    """熔断器打开异常"""
    pass


def with_circuit_breaker(
    role_type: str,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    recovery_timeout: int = DEFAULT_RECOVERY_TIMEOUT
):
    """
    装饰器：为函数添加熔断器保护
    
    Args:
        role_type: 角色类型（researcher/developer/verifier/recorder）
        failure_threshold: 失败次数阈值
        recovery_timeout: 恢复超时(秒)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cb = CircuitBreaker(
                role_type=role_type,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
            return cb.call(func, *args, **kwargs)
        return wrapper
    return decorator


# 全局熔断器实例缓存
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(role_type: str) -> CircuitBreaker:
    """获取或创建指定角色类型的熔断器实例"""
    if role_type not in _circuit_breakers:
        _circuit_breakers[role_type] = CircuitBreaker(role_type)
    return _circuit_breakers[role_type]


def execute_with_circuit_breaker(
    session_key: str,
    role_type: str,
    func: Callable,
    *args,
    **kwargs
) -> Any:
    """
    使用熔断器执行子代理任务的包装函数
    
    与 sessions_spawn 集成，用于监控子代理执行
    
    Args:
        session_key: 子代理会话键
        role_type: 角色类型
        func: 要执行的函数（通常是 sessions_spawn 创建的子代理）
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        函数执行结果
        
    Raises:
        CircuitOpenError: 熔断器打开时抛出
        TimeoutError: 执行超时时抛出
    """
    cb = get_circuit_breaker(role_type)
    
    if not cb.can_execute():
        logger.warning(
            f"[execute_with_circuit_breaker] session={session_key}, "
            f"role={role_type}, circuit=OPEN"
        )
        raise CircuitOpenError(
            f"Role [{role_type}] circuit is OPEN for session {session_key}"
        )
    
    logger.info(
        f"[execute_with_circuit_breaker] session={session_key}, "
        f"role={role_type}, timeout={cb.timeout}s"
    )
    
    start_time = time.time()
    attempt = 0
    last_error = None
    
    while True:
        try:
            # 这里假设 func 会启动子代理并等待完成
            # 超时控制由内部的 session 管理
            result = func(*args, **kwargs)
            
            elapsed = time.time() - start_time
            logger.info(
                f"[execute_with_circuit_breaker] session={session_key} 完成 "
                f"(elapsed={elapsed:.1f}s, attempt={attempt})"
            )
            
            cb.record_success()
            return result
            
        except CircuitOpenError:
            # 熔断器已打开，不再重试
            raise
            
        except Exception as e:
            last_error = e
            elapsed = time.time() - start_time
            
            logger.warning(
                f"[execute_with_circuit_breaker] session={session_key} 失败 "
                f"(elapsed={elapsed:.1f}s, attempt={attempt}, error={type(e).__name__})"
            )
            
            cb.record_failure()
            
            # 检查是否应该继续重试
            if not cb.can_execute():
                raise CircuitOpenError(
                    f"Session {session_key} failed after circuit opened"
                ) from last_error
            
            # 指数退避
            delay = cb._calculate_delay(attempt)
            logger.info(f"[execute_with_circuit_breaker] {delay:.1f}s 后重试...")
            time.sleep(delay)
            attempt += 1


# 熔断器状态查询函数
def get_circuit_status(role_type: str) -> Dict[str, Any]:
    """获取熔断器状态"""
    cb = get_circuit_breaker(role_type)
    return {
        "role_type": cb.role_type,
        "state": cb.state.value,
        "failures": cb.failures,
        "successes": cb.successes,
        "timeout": cb.timeout,
        "last_failure_time": cb.last_failure_time,
        "failure_threshold": cb.failure_threshold,
        "recovery_timeout": cb.recovery_timeout,
    }


def reset_circuit(role_type: str) -> Dict[str, Any]:
    """重置熔断器"""
    if role_type in _circuit_breakers:
        del _circuit_breakers[role_type]
    return {"role_type": role_type, "status": "reset"}


def get_all_circuits_status() -> Dict[str, Dict[str, Any]]:
    """获取所有熔断器状态"""
    return {role: get_circuit_status(role) for role in _circuit_breakers}


if __name__ == "__main__":
    # 简单测试
    print("=== CircuitBreaker 测试 ===")
    
    # 测试角色超时配置
    print("\n角色超时配置:")
    for role, timeout in ROLE_TIMEOUTS.items():
        print(f"  {role}: {timeout}s")
    
    # 测试熔断器创建
    cb = CircuitBreaker("developer")
    print(f"\n创建 developer 熔断器:")
    print(f"  state: {cb.state.value}")
    print(f"  timeout: {cb.timeout}s")
    print(f"  failures: {cb.failures}")
    
    # 测试熔断器状态转换
    print("\n测试状态转换:")
    for i in range(6):
        cb.record_failure()
        print(f"  failure #{i+1}: state={cb.state.value}, failures={cb.failures}")
    
    # 测试半开恢复
    print("\n测试半开恢复:")
    cb._transition_to_half_open()
    print(f"  转换到半开: state={cb.state.value}")
    for i in range(3):
        cb.record_success()
        print(f"  success #{i+1}: state={cb.state.value}")
    
    # 测试状态查询
    print("\n熔断器状态:")
    status = get_circuit_status("developer")
    for k, v in status.items():
        print(f"  {k}: {v}")
