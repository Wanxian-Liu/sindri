"""
scheduler.py - 任务调度模块

职责：
- 子代理启动和管理
- 熔断器管理
- 超时控制
"""

import asyncio
import uuid
import concurrent.futures
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

# 熔断器
try:
    from circuit_breaker import CircuitBreaker
except ImportError:
    CircuitBreaker = None


class AgentEvent(Enum):
    """子代理事件类型"""
    SPAWNED = "spawned"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class AgentEventData:
    """事件数据"""
    event: AgentEvent
    session_key: str
    worker_id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: float = 0.0


@dataclass
class SchedulerConfig:
    """调度配置"""
    max_retries: int = 3
    default_timeout: int = 600  # 10分钟
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: int = 60
    max_thread_pool_workers: int = 4


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
        
        # 事件回调
        self._event_handlers: Dict[AgentEvent, List[Callable[[AgentEventData], None]]] = {
            event: [] for event in AgentEvent
        }
        
        # 线程池：用于同步OMX操作
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.max_thread_pool_workers,
            thread_name_prefix="omx_worker_"
        )
    
    def register_event_handler(self, event: AgentEvent, handler: Callable[[AgentEventData], None]) -> None:
        """注册事件处理器"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    def _emit_event(self, event_data: AgentEventData) -> None:
        """触发事件"""
        import time
        event_data.timestamp = time.time()
        
        handlers = self._event_handlers.get(event_data.event, [])
        for handler in handlers:
            try:
                # 如果是协程函数，使用ensure_future调度
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event_data))
                else:
                    handler(event_data)
            except Exception as e:
                print(f"[Scheduler] Event handler error: {e}")
    
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
            
            event_data = AgentEventData(
                event=AgentEvent.SPAWNED,
                session_key=result.get("sessionKey", session_id),
                worker_id=role_type,
                result={"backend": "openclaw"}
            )
            self._emit_event(event_data)
            
            return {
                "session_key": result.get("sessionKey", session_id),
                "status": "spawned",
                "backend": "openclaw",
                "worker_id": role_type,
            }
        except Exception as e:
            # 降级到mock模式
            event_data = AgentEventData(
                event=AgentEvent.FAILED,
                session_key=f"mock_{session_id}",
                worker_id=role_type,
                error=str(e)[:100]
            )
            self._emit_event(event_data)
            
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
        event_callback: Optional[Callable[[AgentEventData], None]] = None,
    ) -> Dict[str, Any]:
        """
        等待子代理完成（async + 事件回调）
        
        Args:
            session_key: 会话密钥
            timeout: 超时时间（秒）
            backend: 后端类型
            event_callback: 可选的事件回调函数
        
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
            result = {
                "success": True,
                "output": "mock result",
                "error": None,
                "duration_ms": 0,
            }
            
            if event_callback:
                event_data = AgentEventData(
                    event=AgentEvent.COMPLETED,
                    session_key=session_key,
                    worker_id="mock",
                    result=result
                )
                if asyncio.iscoroutinefunction(event_callback):
                    await event_callback(event_data)
                else:
                    event_callback(event_data)
            
            return result
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 使用sessions_yield等待结果
            from sessions_send import sessions_send
            
            result = await sessions_send(
                sessionKey=session_key,
                message="完成了吗？",
                timeoutSeconds=timeout,
            )
            
            elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            final_result = {
                "success": True,
                "output": str(result)[:500],
                "error": None,
                "duration_ms": elapsed_ms,
            }
            
            # 触发完成事件
            event_data = AgentEventData(
                event=AgentEvent.COMPLETED,
                session_key=session_key,
                worker_id="unknown",
                result=final_result
            )
            self._emit_event(event_data)
            
            if event_callback:
                if asyncio.iscoroutinefunction(event_callback):
                    await event_callback(event_data)
                else:
                    event_callback(event_data)
            
            return final_result
            
        except asyncio.TimeoutError:
            elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            event_data = AgentEventData(
                event=AgentEvent.TIMEOUT,
                session_key=session_key,
                worker_id="unknown",
                error=f"Timeout after {timeout}s"
            )
            self._emit_event(event_data)
            
            return {
                "success": False,
                "output": None,
                "error": f"Timeout after {timeout}s",
                "duration_ms": elapsed_ms,
            }
            
        except Exception as e:
            elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            event_data = AgentEventData(
                event=AgentEvent.FAILED,
                session_key=session_key,
                worker_id="unknown",
                error=str(e)[:200]
            )
            self._emit_event(event_data)
            
            return {
                "success": False,
                "output": None,
                "error": str(e)[:200],
                "duration_ms": elapsed_ms,
            }
    
    async def wait_for_agent_with_callback(
        self,
        session_key: str,
        timeout: int,
        backend: str = "openclaw",
        on_complete: Optional[Callable[[AgentEventData], None]] = None,
        on_timeout: Optional[Callable[[AgentEventData], None]] = None,
        on_error: Optional[Callable[[AgentEventData], None]] = None,
    ) -> Dict[str, Any]:
        """
        等待子代理完成（带多个事件回调）
        
        Args:
            session_key: 会话密钥
            timeout: 超时时间（秒）
            backend: 后端类型
            on_complete: 完成回调
            on_timeout: 超时回调
            on_error: 错误回调
        
        Returns:
            {
                "success": bool,
                "output": "...",
                "error": "...",
                "duration_ms": int
            }
        """
        async def event_callback(event_data: AgentEventData):
            if event_data.event == AgentEvent.COMPLETED and on_complete:
                on_complete(event_data)
            elif event_data.event == AgentEvent.TIMEOUT and on_timeout:
                on_timeout(event_data)
            elif event_data.event == AgentEvent.FAILED and on_error:
                on_error(event_data)
        
        return await self.wait_for_agent(
            session_key=session_key,
            timeout=timeout,
            backend=backend,
            event_callback=event_callback
        )
    
    def run_in_executor(self, func: Callable, *args, **kwargs) -> asyncio.Future:
        """
        在线程池中运行同步操作（用于OMX等同步操作）
        
        Returns:
            asyncio.Future wrapping the executor result
        """
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            self._executor,
            lambda: func(*args, **kwargs)
        )
    
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
    
    def cancel_task(self, session_key: str) -> bool:
        """取消活跃任务"""
        if session_key in self._active_tasks:
            task = self._active_tasks[session_key]
            task.cancel()
            del self._active_tasks[session_key]
            
            event_data = AgentEventData(
                event=AgentEvent.CANCELLED,
                session_key=session_key,
                worker_id="unknown"
            )
            self._emit_event(event_data)
            return True
        return False
    
    def shutdown(self, wait: bool = True) -> None:
        """关闭调度器"""
        # 取消所有活跃任务
        for session_key in list(self._active_tasks.keys()):
            self.cancel_task(session_key)
        
        # 关闭线程池
        self._executor.shutdown(wait=wait)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
