"""
agent_executor.py - 三级降级执行器

为sindris提供可靠的任务执行能力：
Level 1: sessions_spawn（OpenClaw内置）
Level 2: DeepSeek API直接调用
Level 3: 本地代码执行（兜底）

使用示例：
    executor = AgentExecutor()
    result = await executor.execute(task, role)
"""

import asyncio
import os
import sys
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# DeepSeek客户端路径
DEEPSEEK_CLIENT_PATH = os.path.expanduser("~/.openclaw/projects/Mimir-Core/utils/deepseek_client.py")

@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    task_id: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    backend: str = "unknown"  # sessions_spawn / deepseek / local / mock
    execution_time_ms: int = 0

class ExecutionBackend(Enum):
    """执行后端"""
    SESSIONS_SPAWN = "sessions_spawn"
    DEEPSEEK = "deepseek"
    LOCAL = "local"
    MOCK = "mock"

class AgentExecutor:
    """
    三级降级执行器
    
    按优先级尝试：
    1. sessions_spawn - OpenClaw内置子Agent
    2. DeepSeek API - 直接LLM调用
    3. Local exec - 本地代码执行（最后兜底）
    """
    
    def __init__(self, workspace_root: str = "/tmp/sindris-exec"):
        self.workspace_root = workspace_root
        self._deepseek_client = None
        self._init_deepseek_client()
    
    def _init_deepseek_client(self):
        """初始化DeepSeek客户端"""
        try:
            if os.path.exists(DEEPSEEK_CLIENT_PATH):
                import importlib.util
                # 确保DEEPSEEK_API_KEY环境变量已设置
                if not os.environ.get('DEEPSEEK_API_KEY'):
                    os.environ['DEEPSEEK_API_KEY'] = 'sk-478c1dd983e44adb974876e438776898'
                
                spec = importlib.util.spec_from_file_location(
                    "deepseek_client", DEEPSEEK_CLIENT_PATH
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                # 直接创建实例，避免单例问题
                self._deepseek_client = module.DeepSeekClient()
        except Exception as e:
            print(f"[AgentExecutor] DeepSeek客户端初始化失败: {e}")
            self._deepseek_client = None
    
    async def execute(self, task: str, role: Dict[str, Any]) -> ExecutionResult:
        """
        执行任务，使用三级降级策略
        
        Args:
            task: 任务描述
            role: 角色信息（包含id, name, description等）
            
        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        task_id = f"exec_{int(start_time * 1000)}"
        
        # Level 1: 尝试sessions_spawn
        try:
            result = await self._execute_via_sessions_spawn(task, role, task_id)
            if result.success:
                result.execution_time_ms = int((time.time() - start_time) * 1000)
                return result
        except Exception as e:
            print(f"[AgentExecutor] Level 1 (sessions_spawn) 失败: {e}")
        
        # Level 2: 尝试DeepSeek API
        try:
            result = await self._execute_via_deepseek(task, role, task_id)
            if result.success:
                result.execution_time_ms = int((time.time() - start_time) * 1000)
                return result
        except Exception as e:
            print(f"[AgentExecutor] Level 2 (DeepSeek) 失败: {e}")
        
        # Level 3: 本地代码执行（兜底）
        try:
            result = await self._execute_via_local(task, role, task_id)
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            return result
        except Exception as e:
            print(f"[AgentExecutor] Level 3 (local) 也失败: {e}")
            return ExecutionResult(
                success=False,
                task_id=task_id,
                error=str(e),
                backend="none"
            )
    
    async def _execute_via_sessions_spawn(
        self, task: str, role: Dict, task_id: str
    ) -> ExecutionResult:
        """
        Level 1: 通过sessions_spawn执行
        
        注意：这个方法在AgentExecutor中不可用（需要OpenClaw内核）
        直接抛出异常让调用方知道需要降级
        """
        raise NotImplementedError(
            "sessions_spawn requires OpenClaw kernel - use DeepSeek instead"
        )
    
    async def _execute_via_deepseek(
        self, task: str, role: Dict, task_id: str
    ) -> ExecutionResult:
        """
        Level 2: 通过DeepSeek API直接执行
        
        DeepSeek可以处理任何类型的任务，包括分析、设计、规划等
        """
        if not self._deepseek_client:
            raise RuntimeError("DeepSeek client not initialized")
        
        # 构造角色提示词
        role_prompt = self._build_role_prompt(role)
        
        # 构造消息
        messages = [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": task}
        ]
        
        # 调用DeepSeek
        response = self._deepseek_client.chat(
            messages=messages,
            model="deepseek-chat"
        )
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        return ExecutionResult(
            success=True,
            task_id=task_id,
            output={"content": content, "model": "deepseek-chat"},
            backend=ExecutionBackend.DEEPSEEK.value
        )
    
    async def _execute_via_local(
        self, task: str, role: Dict, task_id: str
    ) -> ExecutionResult:
        """
        Level 3: 本地代码执行（兜底方案）
        
        AgentExecutor主要依赖DeepSeek，本地执行只是理论上的兜底
        """
        raise NotImplementedError(
            "Local execution not implemented - DeepSeek handles all task types"
        )
    
    def _build_role_prompt(self, role: Dict) -> str:
        """构建角色提示词"""
        role_name = role.get("name", role.get("id", "Specialist"))
        role_desc = role.get("description", "")
        capabilities = role.get("capabilities", [])
        
        prompt = f"""You are a {role_name}.

Role Description:
{role_desc}

Your Capabilities:
{', '.join(capabilities) if isinstance(capabilities, list) else capabilities}

Instructions:
1. Analyze the task carefully
2. Provide a clear, structured response
3. If code is requested, write clean, working code
4. Include explanations where helpful

Task:"""
        return prompt


# 全局实例
_global_executor: Optional[AgentExecutor] = None

def get_global_executor(workspace_root: str = "/tmp/sindris-exec") -> AgentExecutor:
    """获取全局AgentExecutor实例"""
    global _global_executor
    if _global_executor is None:
        _global_executor = AgentExecutor(workspace_root)
    return _global_executor
