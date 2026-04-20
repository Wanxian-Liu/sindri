"""
sindris_executor.py - 织界统一协调系统执行引擎 (v4.1)

版本:v4.1

架构原则:
- 执行框架 ≠ 文档系统
- sindri = 规划(Plan) + 执行(Execute) + 验证(Verify) 的循环
- Mock/集成/路径检验 必须内置

新架构:
- PlanEngine: 任务规划 (from modules)
- VerifyEngine: 验证引擎 (from modules)

内置组件:
- OMXContract: 路径契约机制
- MockRegistry: Mock追踪
- PathValidator: 路径验证
"""

VERSION = "4.1"

import uuid
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import sys
import os

# 添加模块路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(SCRIPT_DIR, "modules")
sys.path.insert(0, MODULES_DIR)
sys.path.insert(0, SCRIPT_DIR)

# 导入新架构引擎 (from modules)
from modules.plan_engine import (
    PlanEngine,
    Plan,
    Subtask,
    FastPathCache,
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    create_plan_engine as _create_plan_engine,
)
from modules.fusion_planner import (
    FusionPlanner,
    FusionPlan,
)
from modules.verify_engine import (
    VerifyEngine,
    VerifyResult,
    VerifyPhase,
    MtimeTracker,
    MockInjector,
    IntegrationVerifier,
    create_verify_engine as _create_verify_engine,
)


class SubagentState:
    """子代理状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SindrisExecutor:
    """
    Sindris执行器 - 新架构 (v4.1)

    两大引擎:
    1. PlanEngine - 任务规划
    2. VerifyEngine - 验证引擎

    内置组件:
    - MtimeTracker - 文件修改时间追踪
    - MockInjector - Mock注入
    - IntegrationVerifier - 集成断言验证
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or str(Path.home() / ".openclaw" / "workspace")
        self.session_id = f"sindris_{uuid.uuid4().hex[:12]}"

        # 初始化两大引擎
        self._init_engines()

        # 内部状态
        self._subagent_states: Dict[str, str] = {}
        self._subagent_sessions: Dict[str, str] = {}

        # 初始化日志
        self._setup_jsonl_logger()

    def _init_engines(self):
        """初始化两大引擎"""
        # FusionPlanner - 融合规划引擎(新架构)
        # 整合RoleMatcher(4层fallback) + PlanEngine(FastPath/CircuitBreaker)
        cache_dir = os.path.join(SCRIPT_DIR, "cache")
        self.plan_engine = FusionPlanner(
            workspace_root=self.workspace_root,
            cache_dir=cache_dir,
        )

        # VerifyEngine - 验证引擎
        self.verify_engine = _create_verify_engine(
            workspace_root=self.workspace_root,
        )

    def _setup_jsonl_logger(self):
        """初始化JSONL日志记录器（直接写文件，不走Python logging避免冗余）"""
        self.jsonl_dir = Path(SCRIPT_DIR) / ".logs"
        self.jsonl_dir.mkdir(exist_ok=True)
        self.jsonl_file = self.jsonl_dir / f"sindris_{datetime.now().strftime('%Y%m%d')}.jsonl"
        # 保留logger用于其他用途，但不用于JSONL写入
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s',
        )
        self.logger = logging.getLogger("sindris")

    def _log_jsonl(self, event_type: str, data: Dict[str, Any]):
        """写入JSONL日志（直接写文件，避免Python logging格式冗余）"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            **data
        }
        try:
            with open(self.jsonl_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            # JSONL写入失败不影响主流程，只记录警告
            self.logger.warning(f"JSONL write failed: {e}")

    def _plan_to_dict(self, plan: Plan) -> Dict[str, Any]:
        """将Plan对象转换为字典格式"""
        return {
            "task_id": plan.task_id,
            "original_task": plan.original_task,
            "subtasks": [
                {
                    "phase": s.phase,
                    "role": s.role,
                    "title": s.title,
                    "verify": s.verify,
                    "timeout": s.timeout,
                    "metadata": s.metadata,
                }
                for s in plan.subtasks
            ],
            "matched_roles": plan.matched_roles,
            "cache_hit": plan.cache_hit,
            "circuit_broken": plan.circuit_broken,
            "metadata": plan.metadata,
        }

    # ========== 核心接口 ==========

    async def plan(self, task: str) -> Dict[str, Any]:
        """
        规划阶段:返回子任务列表

        使用PlanEngine进行任务分解和角色匹配。

        返回结构:
        {
            "success": True,
            "task_id": "xxx",
            "subtasks": [...],
            "plan_summary": "...",
            "phase": "planned|audit|evolution",
        }
        """
        self._log_jsonl("plan_start", {"task": task[:100]})

        try:
            # 使用PlanEngine规划
            plan = self.plan_engine.plan(task)

            # 转换为字典
            result = self._plan_to_dict(plan)
            result["from_cache"] = plan.cache_hit
            result["success"] = True

            # 决定phase
            if any("audit" in s.role.lower() for s in plan.subtasks):
                result["phase"] = "audit"
            elif any("evolution" in s.role.lower() or "improver" in s.role.lower() for s in plan.subtasks):
                result["phase"] = "evolution"
            else:
                result["phase"] = "planned"

            # 统计信息
            result["stats"] = self.plan_engine.get_stats()

            # 记录完成
            self._log_jsonl("plan_complete", {
                "task_id": plan.task_id,
                "subtasks_count": len(plan.subtasks),
                "phase": result["phase"],
                "from_cache": plan.cache_hit,
            })

            return result

        except CircuitBreakerOpenError as e:
            self._log_jsonl("plan_circuit_open", {"error": str(e)})
            return {
                "success": False,
                "error": "Circuit breaker is open, please retry later",
                "phase": "circuit_open",
            }
        except ValueError as e:
            # 输入验证错误
            return {
                "success": False,
                "error": str(e),
                "phase": "rejected",
            }
        except Exception as e:
            self._log_jsonl("plan_error", {"error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "phase": "error",
            }

    def execute_subtask(self, subtask: Dict[str, Any], session_key: str):
        """
        标记子任务开始执行

        Args:
            subtask: 子任务配置
            session_key: 子代理session key
        """
        task_id = subtask.get("task_id")
        if task_id:
            self._subagent_states[task_id] = SubagentState.RUNNING
            self._subagent_sessions[task_id] = session_key

        self._log_jsonl("subtask_start", {
            "task_id": task_id,
            "session_key": session_key,
            "role": subtask.get("role"),
        })

    def complete_subtask(self, task_id: str, result: Any = None):
        """标记子任务完成"""
        self._subagent_states[task_id] = SubagentState.COMPLETE
        
        # 联动熔断器：记录执行结果
        self.plan_engine.record_execution_result(task_id, success=True)
        
        self._log_jsonl("subtask_complete", {
            "task_id": task_id,
        })

    def fail_subtask(self, task_id: str, error: str):
        """标记子任务失败"""
        self._subagent_states[task_id] = SubagentState.FAILED
        
        # 联动熔断器：记录执行结果
        self.plan_engine.record_execution_result(task_id, success=False)
        
        self._log_jsonl("subtask_fail", {
            "task_id": task_id,
            "error": error,
        })

    def get_task_state(self, task_id: str) -> Optional[str]:
        """获取子任务状态"""
        return self._subagent_states.get(task_id)

    def is_task_terminal(self, task_id: str) -> bool:
        """判断任务是否处于终态"""
        state = self._subagent_states.get(task_id)
        return state in (SubagentState.COMPLETE, SubagentState.FAILED, SubagentState.TIMEOUT)

    def check_timeouts(self, timeout_seconds: int = 600) -> List[str]:
        """检查并处理超时任务"""
        # 简单实现:暂无超时追踪
        return []

    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        states = {}
        for task_id, state in self._subagent_states.items():
            states[task_id] = {
                "state": state,
                "session": self._subagent_sessions.get(task_id),
            }
        return {
            "total_tasks": len(self._subagent_states),
            "states": states,
        }

    # ========== 验证接口 ==========

    async def verify(self, task_type: str, files: List[str] = None,
                     target_role: str = None, improver_id: str = None) -> Dict[str, Any]:
        """
        验证执行结果

        Args:
            task_type: 任务类型(dev/audit/evolution)
            files: 涉及的文件列表
            target_role: 目标角色(用于evolution验证)
            improver_id: 改进者ID(用于evolution验证)

        Returns:
            验证结果
        """
        if files is None:
            files = []

        # Mtime追踪
        if files:
            self.verify_engine.take_snapshot(files)

        # 执行验证(使用full_verify异步方法)
        result = await self.verify_engine.full_verify(
            task_name=task_type,
            files=files or [],
            verify_items=[],
        )

        return {
            "passed": result.passed,
            "issues": result.issues,
            "details": result.details,
            "recommendation": result.recommendation,
        }

    async def verify_with_ralph(self, task_name: str, verify_items: List[Dict[str, Any]],
                                execute_fn=None) -> Dict[str, Any]:
        """
        使用Ralph进行3轮循环验证

        Args:
            task_name: 任务名称
            verify_items: 验证项 [{"name": ..., "check_fn": ...}]
            execute_fn: 可选的执行函数

        Returns:
            Ralph验证结果
        """
        vresult = await self.verify_engine.verify_with_ralph(
            task_name=task_name,
            verify_items=verify_items,
            execute_fn=execute_fn,
        )

        return {
            "passed": vresult.passed,
            "total_checks": vresult.total_checks,
            "passed_checks": vresult.passed_checks,
            "failed_checks": vresult.failed_checks,
            "issues": vresult.issues,
            "details": vresult.details,
            "recommendation": vresult.recommendation,
        }

    # ========== Mock注入接口 ==========

    def inject_mock(self, file_path: str, content: str) -> None:
        """注入Mock"""
        self.verify_engine.inject_mock(file_path, content)

    def inject_mocks(self, items: List[Dict[str, str]]) -> None:
        """批量注入Mock"""
        self.verify_engine.inject_mocks(items)

    def restore_mocks(self) -> List[str]:
        """恢复所有Mock"""
        return self.verify_engine.restore_mocks()

    # ========== Mtime追踪接口 ==========

    def take_snapshot(self, files: List[str]) -> None:
        """拍摄文件快照"""
        self.verify_engine.take_snapshot(files)

    def check_changes(self, files: List[str]) -> Dict[str, Any]:
        """检查文件变化"""
        return self.verify_engine.check_changes(files)

    # ========== 集成断言接口 ==========

    def add_file_assertion(self, file_path: str) -> None:
        """添加文件断言"""
        self.verify_engine.add_file_assertion(file_path)

    def add_import_assertion(self, module_path: str) -> None:
        """添加导入断言"""
        self.verify_engine.add_import_assertion(module_path)

    async def run_assertions(self) -> Dict[str, Any]:
        """运行断言"""
        return await self.verify_engine.run_assertions()

    # ========== 兼容性别名 ==========

    @property
    def SubagentState(self):
        """子代理状态枚举(兼容性)"""
        return SubagentState

    def update_subagent_state(self, task_id: str, session_key: str, state: str):
        """更新子代理状态(兼容性)"""
        if state == "running":
            self._subagent_states[task_id] = SubagentState.RUNNING
            self._subagent_sessions[task_id] = session_key
        elif state == "complete":
            self._subagent_states[task_id] = SubagentState.COMPLETE
        elif state == "failed":
            self._subagent_states[task_id] = SubagentState.FAILED
        elif state == "timeout":
            self._subagent_states[task_id] = SubagentState.TIMEOUT

    def get_subagent_state(self, task_id: str) -> Optional[str]:
        """获取子代理状态(兼容性)"""
        return self._subagent_states.get(task_id)

    def is_subagent_terminal(self, task_id: str) -> bool:
        """判断子代理是否终态(兼容性)"""
        return self.is_task_terminal(task_id)

    def get_all_subagent_states(self) -> Dict[str, Dict]:
        """获取所有子代理状态(兼容性)"""
        return {
            task_id: {
                "state": state,
                "session": self._subagent_sessions.get(task_id),
            }
            for task_id, state in self._subagent_states.items()
        }

    # ========== 日志和状态 ==========

    def log_execution(self, task_id: str, phase: str, status: str,
                      details: Dict[str, Any] = None):
        """记录执行日志"""
        self._log_jsonl("execution", {
            "task_id": task_id,
            "phase": phase,
            "status": status,
            "details": details or {},
        })

    def get_execution_log(self) -> List[Dict[str, Any]]:
        """获取执行日志"""
        # 简单实现:返回内存中的状态
        return list(self._subagent_states.items())

    def cleanup(self) -> Dict[str, Any]:
        """清理所有副作用"""
        return self.verify_engine.cleanup()

    def record_execution_result(self, task_id: str, success: bool) -> None:
        """
        记录执行结果到熔断器
        
        Args:
            task_id: 任务ID
            success: 是否成功
        """
        self.plan_engine.record_execution_result(task_id, success)


# 兼容性别名
Sindris = SindrisExecutor


async def plan_sindris(task: str) -> Dict[str, Any]:
    """便捷函数:规划sindris"""
    executor = SindrisExecutor()
    return await executor.plan(task)
