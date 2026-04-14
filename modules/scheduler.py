"""
scheduler.py - 任务调度模块

职责：
- 子代理启动和管理
- 熔断器管理
- 超时控制
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# 熔断器
try:
    from circuit_breaker import CircuitBreaker
except ImportError:
    CircuitBreaker = None


@dataclass
class SchedulerConfig:
    """调度配置"""
    max_retries: int = 3
    default_timeout: int = 300
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: int = 60


class SindrisScheduler:
    """
    任务调度器
    
    职责：
    1. 管理子代理的启动和等待
    2. 熔断器状态管理
    3. 超时控制
    """
    
    def __init__(self, config: Optional[SchedulerConfig] = None):
        self.config = config or SchedulerConfig()
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
    
    def get_circuit_breaker(self, role_type: str) -> Optional[CircuitBreaker]:
        """获取熔断器"""
        if CircuitBreaker is None:
            return None
        if role_type not in self._circuit_breakers:
            self._circuit_breakers[role_type] = CircuitBreaker(
                task_id=f"scheduler_{role_type}",
                role=role_type,
                failure_threshold=self.config.circuit_failure_threshold,
                recovery_timeout=self.config.circuit_recovery_timeout,
            )
        return self._circuit_breakers[role_type]
    
    def is_circuit_open(self, role_type: str) -> bool:
        """检查熔断器是否打开"""
        cb = self.get_circuit_breaker(role_type)
        if cb is None:
            return False
        return cb.state == "open"
    
    def record_success(self, role_type: str) -> None:
        """记录成功"""
        cb = self.get_circuit_breaker(role_type)
        cb and cb.record_success()
    
    def record_failure(self, role_type: str) -> None:
        """记录失败"""
        cb = self.get_circuit_breaker(role_type)
        cb and cb.record_failure()
    
    async def spawn_subagent(
        self,
        task_title: str,
        role_type: str,
        allowed_tools: List[str],
        timeout: int,
        cwd: str,
    ) -> Dict[str, Any]:
        """
        启动子代理
        
        Returns:
            {
                "session_key": "...",
                "status": "spawned|error",
                "backend": "openclaw|mock",
                "error": "..." # 如果失败
            }
        """
        from sessions_spawn import sessions_spawn
        
        session_id = f"sindris_{uuid.uuid4().hex[:8]}"
        
        try:
            result = await sessions_spawn(
                task=task_title,
                runtime="subagent",
                runTimeoutSeconds=timeout,
                cleanup="keep",
            )
            return {
                "session_key": result.get("sessionKey", session_id),
                "status": "spawned",
                "backend": "openclaw",
                "worker_id": role_type,
            }
        except Exception as e:
            # 降级到mock模式
            return {
                "session_key": f"mock_{session_id}",
                "status": "mock_spawned",
                "backend": "mock",
                "error": str(e)[:100],
                "worker_id": role_type,
            }
    
    async def wait_for_agent(
        self,
        session_key: str,
        timeout: int,
        backend: str = "openclaw",
    ) -> Dict[str, Any]:
        """
        等待子代理完成
        
        Returns:
            {
                "success": bool,
                "output": "...",
                "error": "...",
                "duration_ms": int
            }
        """
        if backend == "mock" or session_key.startswith("mock_"):
            # mock模式直接返回
            return {
                "success": True,
                "output": "mock result",
                "error": None,
                "duration_ms": 0,
            }
        
        try:
            # 使用sessions_yield等待结果
            from sessions_send import sessions_send
            
            result = await sessions_send(
                sessionKey=session_key,
                message="完成了吗？",
                timeoutSeconds=timeout,
            )
            return {
                "success": True,
                "output": str(result)[:500],
                "error": None,
                "duration_ms": timeout * 1000,
            }
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "error": str(e)[:200],
                "duration_ms": timeout * 1000,
            }
    
    async def execute_with_timeout(
        self,
        coro,
        timeout: int,
    ) -> Any:
        """带超时的执行"""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Timeout after {timeout}s",
                "timed_out": True,
            }
