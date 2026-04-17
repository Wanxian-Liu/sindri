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

# 尝试导入核心模块
try:
    from modules import (
        ReportGenerator,  # 报告生成（保留）
        RoleManager,      # 角色管理（使用中）
        TaskDecomposer,   # 任务分解（使用中）
        # 注意：SindrisScheduler和RoundManager已移除（死代码）
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"[sindris] Warning: Modules not available ({e})")
    MODULES_AVAILABLE = False

# 导入执行器（用于真正执行任务）
try:
    from agent_executor import AgentExecutor
except ImportError:
    AgentExecutor = None


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
            # 注意：scheduler和round_manager已移除（死代码）
            self.report_generator = ReportGenerator(self.session_id)
            self.role_manager = RoleManager(self.workspace_root)
            self.task_decomposer = TaskDecomposer(self.workspace_root)
        else:
            self.report_generator = None
            self.role_manager = None
            self.task_decomposer = None
        
        # OMX集成（如果有）
        try:
            from omx_integrator import get_integrator
            self.omx = get_integrator(self.workspace_root)
        except Exception:
            self.omx = None
        
        # 执行器（用于真正执行任务）
        self._agent_executor = AgentExecutor(workspace_root=self.workspace_root) if AgentExecutor else None
    
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
        from modules.role_matcher import FIXED_TEAM, FIXED_TEAM_TRIGGERS
        
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
        执行完整Round1-4流程（自动执行版）
        
        真正使用AgentExecutor执行Round2任务，
        不再只返回计划。
        """
        import time
        start_time = time.time()
        
        # Round1: 规划
        plan_result = await self.plan(task)
        
        if not plan_result.get("success"):
            return plan_result
        
        subtasks = plan_result.get("subtasks", [])
        roles = plan_result.get("roles", [])
        
        # Round2: 真正执行任务
        round2_results = []
        for i, subtask in enumerate(subtasks):
            role_data = subtask.get("role", {})
            task_title = subtask.get("title", "subtask")
            
            # role可能是字符串，转换为Dict格式
            if isinstance(role_data, str):
                role_dict = {"name": role_data, "id": role_data, "description": ""}
            else:
                role_dict = role_data or {}
            
            if self._agent_executor:
                try:
                    result = await self._agent_executor.execute(task_title, role_dict)
                    round2_results.append({
                        "index": i,
                        "task_id": subtask.get("task_id"),
                        "title": task_title,
                        "role": role_dict.get("name", "unknown"),
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                        "backend": result.backend,
                        "duration_ms": result.execution_time_ms,
                    })
                except Exception as e:
                    round2_results.append({
                        "index": i,
                        "title": task_title,
                        "role": role_dict.get("name", "unknown"),
                        "success": False,
                        "error": str(e)[:200],
                    })
            else:
                # 没有执行器时，标记为跳过
                round2_results.append({
                    "index": i,
                    "title": task_title,
                    "role": role_dict.get("name", "unknown"),
                    "success": False,
                    "error": "AgentExecutor not available",
                    "skipped": True,
                })
        
        # Round3: GStackHook审查（如果有）
        try:
            from modules.gstack_hook import gstack_hook
            
            reviewed_results = []
            for r in round2_results:
                if r.get('success') and r.get('output'):
                    hook_result = await gstack_hook.on_worker_complete(
                        task_id=r.get('task_id', ''),
                        output=str(r.get('output', '')),
                        worker_role=r.get('role', '')
                    )
                    r['gstack_review'] = hook_result
                reviewed_results.append(r)
            round2_results = reviewed_results
        except ImportError:
            pass  # GStackHook不可用，跳过
        except Exception as e:
            pass  # Hook调用失败，不阻塞流程
        
        # Round3: 审查结果
        review_passed = all(r.get("success") for r in round2_results)
        failed_count = sum(1 for r in round2_results if not r.get("success"))
        
        # Round4: 生成报告
        elapsed = time.time() - start_time
        
        return {
            "success": True,
            "session_id": self.session_id,
            "task": task,
            "phase": "completed",
            "rounds_completed": [1, 2, 3, 4],
            "plan_summary": plan_result.get("plan_summary"),
            "roles": roles,
            "subtasks": subtasks,
            "round2_results": round2_results,
            "review_passed": review_passed,
            "failed_count": failed_count,
            "total_tasks": len(subtasks),
            "elapsed_seconds": round(elapsed, 2),
            "execution_info": {
                "executor": "AgentExecutor (三级降级)",
                "phase": "round2_executed",
            },
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
