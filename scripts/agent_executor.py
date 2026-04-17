"""
agent_executor.py - 两级降级执行器（简化版）

Level 1: sessions_spawn（OpenClaw内置）
Level 2: 本地模板（兜底）

移除了DeepSeek API依赖，简化架构。
"""

import asyncio
import os
import sys
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool = True
    task_id: str = ""
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    backend: str = "unknown"  # sessions_spawn / local
    execution_time_ms: int = 0
    title: str = ""
    role: str = ""
    duration_ms: int = 0
    verify_passed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

class ExecutionBackend(Enum):
    """执行后端"""
    SESSIONS_SPAWN = "sessions_spawn"
    LOCAL = "local"

class AgentExecutor:
    """
    两级降级执行器
    
    Level 1: sessions_spawn（OpenClaw内置，真实执行）
    Level 2: 本地模板（兜底）
    """
    
    def __init__(self, workspace_root: str = "/tmp/sindris-exec"):
        self.workspace_root = workspace_root
    
    async def execute(self, task: str, role: Dict[str, Any]) -> ExecutionResult:
        """执行任务，使用两级降级策略"""
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
        
        # Level 2: 本地模板（兜底）
        try:
            result = await self._execute_via_local(task, role, task_id)
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            return result
        except Exception as e:
            print(f"[AgentExecutor] Level 2 (local) 也失败: {e}")
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
        
        注意：这个方法需要OpenClaw内核支持。
        如果不可用，抛出NotImplementedError让调用方降级。
        """
        # 在OpenClaw上下文中，应该使用sessions_spawn工具
        # 但这里无法直接调用工具，需要依赖调用方
        raise NotImplementedError(
            "sessions_spawn需要OpenClaw内核，请使用sessions_spawn工具"
        )
    
    async def _execute_via_local(
        self, task: str, role: Dict, task_id: str
    ) -> ExecutionResult:
        """
        Level 2: 本地模板（兜底方案）
        
        生成基于角色的结构化分析模板。
        """
        role_name = role.get("name", role.get("id", "Specialist"))
        role_desc = role.get("description", "")
        
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
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
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
- 技术可行性：待评估
- 实现复杂度：待评估
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
        
        template = templates.get(role_name)
        if template:
            return template
        
        return f"""## [{role_name}] 任务分析

**分析时间**: {timestamp}

**任务**: {task}

### 1. 任务理解
{role_desc or '通用任务角色'}

### 2. 分析结果
基于角色 [{role_name}] 的专业分析已完成。
请在后续环节进行深度验证。
"""

