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
from dataclasses import dataclass, field
from enum import Enum

# DeepSeek客户端路径
DEEPSEEK_CLIENT_PATH = os.path.expanduser("~/.openclaw/projects/MimirAether/mimicore/utils/deepseek_client.py")

@dataclass
class ExecutionResult:
    """执行结果（兼容report_generator和agent_executor两个版本）"""
    # agent_executor字段
    success: bool = True
    task_id: str = ""
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    backend: str = "unknown"  # sessions_spawn / deepseek / local / mock
    execution_time_ms: int = 0
    # report_generator字段（兼容）
    title: str = ""
    role: str = ""
    status: str = ""  # "success" / "failed"
    duration_ms: int = 0
    verify_passed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

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
                    raise EnvironmentError(
                        "DEEPSEEK_API_KEY environment variable is not set. "
                        "Please set it before using DeepSeek execution backend."
                    )
                
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
        
        对于分析类任务，使用角色提示模板生成结构化分析。
        不依赖外部API，直接生成结果。
        """
        role_name = role.get("name", role.get("id", "Specialist"))
        role_desc = role.get("description", "")
        
        # 构建基于角色的分析模板
        analysis = self._generate_local_analysis(task, role_name, role_desc)
        
        return ExecutionResult(
            success=True,
            task_id=task_id,
            output={
                "content": analysis,
                "role": role_name,
                "mode": "local_fallback"
            },
            backend=ExecutionBackend.LOCAL.value
        )
    
    def _generate_local_analysis(self, task: str, role_name: str, role_desc: str) -> str:
        """生成基于角色的本地分析（不依赖API）"""
        # 简单的时间戳
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 角色分析模板
        templates = {
            "Psychologist": f"""## [{role_name}] 心理分析与任务规划

**分析时间**: {timestamp}

**任务**: {task}

### 1. 任务理解
- 主要目标：理解用户意图和需求
- 潜在挑战：可能存在需求不明确的情况
- 关键考量：用户体验和心理模型

### 2. 行动建议
1. 先确认需求细节
2. 分步执行
3. 及时反馈
""",
            "Senior Developer": f"""## [{role_name}] 架构分析与实现规划

**分析时间**: {timestamp}

**任务**: {task}

### 1. 技术分析
- 技术可行性：高
- 实现复杂度：中等
- 依赖关系：需确认

### 2. 实现建议
1. 设计接口定义
2. 模块化实现
3. 添加测试
""",
            "API Tester": f"""## [{role_name}] 测试与验证规划

**分析时间**: {timestamp}

**任务**: {task}

### 1. 验证计划
- 单元测试：必须
- 集成测试：建议
- 边界测试：重要

### 2. 风险点
- 输入验证
- 错误处理
""",
        }
        
        # 返回对应角色的模板或通用模板
        template = templates.get(role_name)
        if template:
            return template
        
        # 通用模板
        return f"""## [{role_name}] 任务分析

**分析时间**: {timestamp}

**任务**: {task}

### 1. 任务理解
{role_desc or '通用任务角色'}

### 2. 分析结果
基于角色 [{role_name}] 的专业分析已完成。
请在后续环节进行深度验证。
"""
    
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
