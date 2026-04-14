"""
sindris_executor.py - 织界统一协调系统执行引擎 (模块化重构版)

版本历史：
- v2.21: 初始版本
- v3.0: 模块化重构，按职责拆分为独立模块
"""

VERSION = "3.1"

import asyncio
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

import sys
import os

# 添加模块路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(SCRIPT_DIR, "scripts")
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, SCRIPTS)

# 尝试导入新模块
try:
    from modules import (
        SindrisScheduler,
        RoundManager,
        ReportGenerator,
        RoleManager,
        TaskDecomposer,
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"[sindris] Warning: New modules not available ({e}), using legacy mode")
    MODULES_AVAILABLE = False

# sindris自有模块（独立运行，不依赖织界中枢）
from consensus_officer import ConsensusOfficer
from circuit_breaker import CircuitBreaker
from safety_policy import SafetyPolicy, DangerLevel
from review_logger import ReviewLogger, ResultSignal
from telemetry_collector import TelemetryCollector, TelemetryEvent
from memory_manager import MemoryManager
from task_queue import TaskQueue, BlockReason
from sindris_hud import SindrisHUD, HUDStyle, HUDData, TaskDisplay


class TaskStatus:
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkerStatus:
    """Worker状态枚举"""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class SindrisExecutor:
    """
    Sindris执行器 - 主入口
    
    使用模块化架构：
    - TaskDecomposer: 任务分解 + 固定小组
    - RoundManager: Round1-4流程
    - SindrisScheduler: 子代理调度
    - ReportGenerator: 报告生成
    - RoleManager: 角色管理
    """
    
    def __init__(
        self,
        workspace_root: Optional[str] = None,
    ):
        self.workspace_root = workspace_root or str(Path.home() / ".openclaw" / "workspace")
        self.session_id = f"sindris_{uuid.uuid4().hex[:12]}"
        
        # 初始化模块（如果可用）
        if MODULES_AVAILABLE:
            self.scheduler = SindrisScheduler()
            self.round_manager = RoundManager(
                workspace_root=self.workspace_root,
                session_id=self.session_id,
            )
            self.report_generator = ReportGenerator(self.session_id)
            self.role_manager = RoleManager(self.workspace_root)
            self.task_decomposer = TaskDecomposer(self.workspace_root)
        else:
            self.scheduler = None
            self.round_manager = None
            self.report_generator = None
            self.role_manager = None
            self.task_decomposer = None
        
        # OMX集成（如果有）
        try:
            from omx_integrator import get_integrator
            self.omx = get_integrator(self.workspace_root)
        except Exception:
            self.omx = None
        
        # 熔断器
        self._circuit_breakers: Dict[str, Any] = {}
    
    def _get_circuit_breaker(self, role_type: str):
        """获取熔断器"""
        if role_type not in self._circuit_breakers:
            self._circuit_breakers[role_type] = CircuitBreaker(
                task_id=f"{self.session_id}_{role_type}",
                role=role_type,
            )
        return self._circuit_breakers[role_type]
    
    async def plan(self, task: str) -> Dict[str, Any]:
        """
        规划阶段：返回子任务列表
        
        使用新模块进行任务分解
        """
        if not self.task_decomposer:
            return await self._plan_legacy(task)
        
        # 使用模块化分解
        roles = self.task_decomposer.get_roles(task, [])
        decomposed = self.task_decomposer.decompose_by_round(task, roles)
        
        # 合并所有任务
        all_tasks = []
        all_tasks.extend(decomposed.get("round1", []))
        all_tasks.extend(decomposed.get("round2", []))
        all_tasks.extend(decomposed.get("round3", []))
        
        # 构建subtasks
        subtasks = []
        for t in all_tasks:
            role = t.metadata.get("role", {})
            subtasks.append({
                "task_id": t.id,
                "role": role.get("name", role.get("id", "unknown")),
                "role_type": self.role_manager.infer_role_type(role) if self.role_manager else "general",
                "title": t.title,
                "timeout": self.role_manager.get_timeout(role.get("name", "")) if self.role_manager else 600,
                "allowed_tools": self.role_manager.get_allowed_tools(role.get("name", "")) if self.role_manager else ["read", "exec"],
                "phase": t.phase,
            })
        
        return {
            "success": True,
            "task_id": self.session_id,
            "subtasks": subtasks,
            "plan_summary": f"分解为{len(subtasks)}个子任务，角色: {[r.get('name', r.get('id', '?')) for r in roles]}",
            "phase": "planned",
            "roles": roles,
        }
    
    async def _plan_legacy(self, task: str) -> Dict[str, Any]:
        """遗留模式规划"""
        # 简化版，使用固定小组
        from modules.task_decomposer import FIXED_TEAM, FIXED_TEAM_TRIGGERS
        
        task_lower = task.lower()
        if any(trigger in task_lower for trigger in FIXED_TEAM_TRIGGERS):
            matched_roles = FIXED_TEAM
        else:
            matched_roles = []
        
        return {
            "success": True,
            "task_id": self.session_id,
            "subtasks": [],
            "plan_summary": f"使用固定小组: {[r['name'] for r in matched_roles]}",
            "phase": "planned",
            "roles": matched_roles,
        }
    
    async def run(self, task: str, verify: bool = False) -> Dict[str, Any]:
        """
        执行完整Round1-4流程
        
        注意：这个方法返回执行计划，不是自动执行。
        真正的执行需要主Agent调用 sessions_spawn 工具。
        """
        # Round1: 规划
        plan_result = await self.plan(task)
        
        if not plan_result.get("success"):
            return plan_result
        
        # 返回执行计划
        return {
            "success": True,
            "session_id": self.session_id,
            "plan_summary": plan_result.get("plan_summary"),
            "subtasks": plan_result.get("subtasks", []),
            "total_tasks": len(plan_result.get("subtasks", [])),
            "phase": "planned",
            "instructions": [
                "【Round1】sindris.plan() 返回此计划",
                "【Round2】对每个subtask调用 sessions_spawn",
                "【Round3】使用 round3_prompt 进行审查",
                "【Round4】使用 round4_prompt 完成",
            ],
        }
    
    def get_role_allowed_tools(self, role_name: str) -> List[str]:
        """获取角色允许的工具"""
        if self.role_manager:
            return self.role_manager.get_allowed_tools(role_name)
        
        # 默认工具
        return ["read", "exec", "edit", "write"]


# 兼容性别名
Sindris = SindrisExecutor


async def run_sindris(task: str) -> Dict[str, Any]:
    """便捷函数：执行sindris"""
    executor = SindrisExecutor()
    return await executor.run(task)


async def plan_sindris(task: str) -> Dict[str, Any]:
    """便捷函数：规划sindris"""
    executor = SindrisExecutor()
    return await executor.plan(task)
