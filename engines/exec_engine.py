"""
exec_engine.py - 执行编排引擎

职责：
1. 子代理状态管理
2. 执行流程控制
3. 超时处理
4. 错误恢复
5. 与sessions_spawn集成
"""

import uuid
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class SubagentState(Enum):
    """子代理状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class SubagentContext:
    """子代理执行上下文"""
    task_id: str
    session_key: Optional[str] = None
    state: SubagentState = SubagentState.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    state_history: List[Dict] = field(default_factory=list)


class ExecEngine:
    """
    执行编排引擎
    
    职责：
    1. 管理子代理生命周期
    2. 状态流转跟踪
    3. 超时控制
    4. 执行日志
    """
    
    def __init__(self, workspace_root: str, script_dir: str):
        self.workspace_root = workspace_root
        self.script_dir = script_dir
        self._subagent_states: Dict[str, SubagentContext] = {}
        self._execution_log: List[Dict[str, Any]] = []
    
    def create_subagent(self, task_id: str) -> SubagentContext:
        """
        创建子代理上下文
        
        Args:
            task_id: 子任务ID
        
        Returns:
            SubagentContext
        """
        ctx = SubagentContext(task_id=task_id)
        self._subagent_states[task_id] = ctx
        return ctx
    
    def start_subagent(self, task_id: str, session_key: str):
        """
        标记子代理开始执行
        
        Args:
            task_id: 子任务ID
            session_key: session key
        """
        if task_id not in self._subagent_states:
            self.create_subagent(task_id)
        
        ctx = self._subagent_states[task_id]
        ctx.session_key = session_key
        ctx.state = SubagentState.RUNNING
        ctx.started_at = datetime.now().isoformat()
        
        self._log("subagent_start", {
            "task_id": task_id,
            "session_key": session_key,
        })
    
    def complete_subagent(self, task_id: str, result: Any = None):
        """
        标记子代理完成
        
        Args:
            task_id: 子任务ID
            result: 执行结果
        """
        if task_id not in self._subagent_states:
            logger.warning(f"complete_subagent: unknown task_id {task_id}")
            return
        
        ctx = self._subagent_states[task_id]
        ctx.state = SubagentState.COMPLETE
        ctx.completed_at = datetime.now().isoformat()
        ctx.result = result
        
        self._log("subagent_complete", {
            "task_id": task_id,
            "duration": self._get_duration(ctx),
        })
    
    def fail_subagent(self, task_id: str, error: str):
        """
        标记子代理失败
        
        Args:
            task_id: 子任务ID
            error: 错误信息
        """
        if task_id not in self._subagent_states:
            logger.warning(f"fail_subagent: unknown task_id {task_id}")
            return
        
        ctx = self._subagent_states[task_id]
        ctx.state = SubagentState.FAILED
        ctx.completed_at = datetime.now().isoformat()
        ctx.error = error
        
        self._log("subagent_fail", {
            "task_id": task_id,
            "error": error,
            "duration": self._get_duration(ctx),
        })
    
    def timeout_subagent(self, task_id: str):
        """标记子代理超时"""
        if task_id not in self._subagent_states:
            return
        
        ctx = self._subagent_states[task_id]
        ctx.state = SubagentState.TIMEOUT
        ctx.completed_at = datetime.now().isoformat()
        ctx.error = "Execution timeout"
        
        self._log("subagent_timeout", {
            "task_id": task_id,
            "duration": self._get_duration(ctx),
        })
    
    def cancel_subagent(self, task_id: str):
        """取消子代理"""
        if task_id not in self._subagent_states:
            return
        
        ctx = self._subagent_states[task_id]
        ctx.state = SubagentState.CANCELLED
        ctx.completed_at = datetime.now().isoformat()
        
        self._log("subagent_cancel", {"task_id": task_id})
    
    def get_state(self, task_id: str) -> Optional[SubagentState]:
        """获取子代理状态"""
        ctx = self._subagent_states.get(task_id)
        return ctx.state if ctx else None
    
    def get_context(self, task_id: str) -> Optional[SubagentContext]:
        """获取子代理上下文"""
        return self._subagent_states.get(task_id)
    
    def is_terminal(self, task_id: str) -> bool:
        """判断是否处于终态"""
        state = self.get_state(task_id)
        if state is None:
            return False
        return state in (SubagentState.COMPLETE, SubagentState.FAILED,
                        SubagentState.CANCELLED, SubagentState.TIMEOUT)
    
    def is_running(self, task_id: str) -> bool:
        """判断是否正在运行"""
        return self.get_state(task_id) == SubagentState.RUNNING
    
    def get_all_states(self) -> Dict[str, str]:
        """获取所有子代理状态"""
        return {
            task_id: ctx.state.value
            for task_id, ctx in self._subagent_states.items()
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        states = [ctx.state for ctx in self._subagent_states.values()]
        return {
            "total": len(self._subagent_states),
            "pending": states.count(SubagentState.PENDING),
            "running": states.count(SubagentState.RUNNING),
            "complete": states.count(SubagentState.COMPLETE),
            "failed": states.count(SubagentState.FAILED),
            "timeout": states.count(SubagentState.TIMEOUT),
            "cancelled": states.count(SubagentState.CANCELLED),
        }
    
    def check_timeout(self, timeout_seconds: int) -> List[str]:
        """
        检查超时的子代理
        
        Args:
            timeout_seconds: 超时阈值
        
        Returns:
            超时的task_id列表
        """
        timed_out = []
        now = datetime.now()
        
        for task_id, ctx in self._subagent_states.items():
            if ctx.state != SubagentState.RUNNING:
                continue
            
            if ctx.started_at:
                started = datetime.fromisoformat(ctx.started_at)
                elapsed = (now - started).total_seconds()
                if elapsed > timeout_seconds:
                    timed_out.append(task_id)
                    self.timeout_subagent(task_id)
        
        return timed_out
    
    def _get_duration(self, ctx: SubagentContext) -> Optional[float]:
        """计算执行时长（秒）"""
        if not ctx.started_at:
            return None
        
        end_time = ctx.completed_at or datetime.now().isoformat()
        start = datetime.fromisoformat(ctx.started_at)
        end = datetime.fromisoformat(end_time)
        return (end - start).total_seconds()
    
    def _log(self, event_type: str, data: Dict[str, Any]):
        """记录执行日志"""
        self._execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            **data
        })
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """获取执行日志"""
        return self._execution_log
    
    def clear_log(self):
        """清空日志"""
        self._execution_log.clear()
    
    # ========== 便捷方法：构建spawn消息 ==========
    
    def build_spawn_message(self, subtask: Dict[str, Any]) -> str:
        """
        构建发送给子代理的消息
        
        Args:
            subtask: 子任务配置
        
        Returns:
            格式化消息字符串
        """
        role = subtask.get("role", "Specialist")
        title = subtask.get("title", "")
        role_prompt = subtask.get("role_prompt", "")
        
        # 构建消息
        parts = [
            f"## {title}",
            "",
            f"**角色**: {role}",
            "",
            "**任务描述**:",
            f"{role_prompt}",
        ]
        
        tools = subtask.get("tools", [])
        if tools:
            parts.extend([
                "",
                f"**可用工具**: {', '.join(tools)}",
            ])
        
        verify = subtask.get("verify", [])
        if verify:
            parts.extend([
                "",
                "**验证条件**:",
                *[f"- {v}" for v in verify],
            ])
        
        return "\n".join(parts)
