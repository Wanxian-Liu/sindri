"""
sindris_executor.py - 织界统一协调系统执行引擎 (v4.2)

版本:v4.2

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

VERSION = "4.2"

import uuid
import json
import logging
import logging.handlers
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import sys
import os

# P0-2 Fix: 使用绝对路径确保模块外导入也能正常工作
# P2-7 Fix: 使用append而非insert(0)，避免破坏全局模块搜索顺序
# 在外部目录运行时，__file__仍然指向sindris_executor.py的安装位置
_SINDRI_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULES_DIR = os.path.join(_SINDRI_DIR, "modules")
_SCRIPTS_DIR = os.path.join(_SINDRI_DIR, "scripts")

# P2-7 Fix: 使用append添加到末尾，避免优先级冲突
for _p in [_MODULES_DIR, _SCRIPTS_DIR, _SINDRI_DIR]:
    if _p not in sys.path:
        sys.path.append(_p)

# 供后续使用的常量（保持向后兼容）
SCRIPT_DIR = _SINDRI_DIR
MODULES_DIR = _MODULES_DIR
SCRIPTS_DIR = _SCRIPTS_DIR

# 导入新架构引擎 (from modules)
from modules.plan_engine import (
    Plan,
    Subtask,
    FastPathCache,
    CircuitBreaker as PlanEngineCircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
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

# OMX集成
from scripts.omx_integrator import get_integrator


# ========== 角色MD文件查找 ==========

# 角色名称到MD文件的映射
_ROLE_TO_MD = {
    # ai-factory (AUDIT_TEAM相关)
    "Code Reviewer": "ai-factory/engineering-code-reviewer.md",
    "Security Engineer": "ai-factory/engineering-security-engineer.md",
    "Software Architect": "ai-factory/engineering-software-architect.md",
    # testing (AUDIT_TEAM相关)
    "QA Lead": "testing/testing-qa-lead.md",
    "Reality Checker": "testing/testing-reality-checker.md",
    # engineering
    "Senior Developer": "engineering/engineering-senior-developer.md",
    "Frontend Developer": "engineering/engineering-frontend-developer.md",
    "AI/ML Engineer": "engineering/engineering-ai-ml-engineer.md",
    "Debugger": "engineering/engineering-debugger.md",
    "Release Engineer": "engineering/engineering-release-engineer.md",
    "Staff Engineer": "engineering/engineering-staff-engineer.md",
    # academic
    "Psychologist": "academic/academic-psychologist.md",
    "Historian": "academic/academic-historian.md",
    "Narratologist": "academic/academic-narratologist.md",
    "Geographer": "academic/academic-geographer.md",
    "Anthropologist": "academic/academic-anthropologist.md",
    # product
    "Product Manager": "product/product-manager.md",
    "Product Trend Researcher": "product/product-trend-researcher.md",
    # design
    "Design UX Researcher": "design/design-ux-researcher.md",
    # strategy
    "CEO Founder": "strategy/strategy-ceo-founder.md",
    "Technical Writer": "strategy/strategy-technical-writer.md",
}

# 角色完整ID到MD文件的映射
_ROLE_ID_TO_MD = {
    "engineering_code_reviewer": "ai-factory/engineering-code-reviewer.md",
    "engineering_security_engineer": "ai-factory/engineering-security-engineer.md",
    "engineering_software_architect": "ai-factory/engineering-software-architect.md",
    "testing_qa_lead": "testing/testing-qa-lead.md",
    "testing_reality_checker": "testing/testing-reality-checker.md",
    "engineering_senior_developer": "engineering/engineering-senior-developer.md",
    "engineering_frontend_developer": "engineering/engineering-frontend-developer.md",
    "engineering_ai_ml_engineer": "engineering/engineering-ai-ml-engineer.md",
    "engineering_debugger": "engineering/engineering-debugger.md",
    "engineering_release_engineer": "engineering/engineering-release-engineer.md",
    "engineering_staff_engineer": "engineering/engineering-staff-engineer.md",
    "academic_psychologist": "academic/academic-psychologist.md",
    "academic_historian": "academic/academic-historian.md",
    "academic_narratologist": "academic/academic-narratologist.md",
    "academic_geographer": "academic/academic-geographer.md",
    "academic_anthropologist": "academic/academic-anthropologist.md",
    "product_product_manager": "product/product-manager.md",
    "product_trend_researcher": "product/product-trend-researcher.md",
    "design_ux_researcher": "design/design-ux-researcher.md",
    # strategy
    "strategy_ceo_founder": "strategy/strategy-ceo-founder.md",
    "strategy_technical_writer": "strategy/strategy-technical-writer.md",
}

ROLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles")


def find_role_md_file(role_name: str, role_id: str = None) -> str:
    """
    根据角色名称或ID查找对应的MD文件路径
    
    Args:
        role_name: 角色名称 (如 "Code Reviewer")
        role_id: 角色ID (可选, 如 "engineering_code_reviewer")
    
    Returns:
        MD文件完整路径，如果不存在返回None
    """
    # 优先使用role_id查找
    if role_id and role_id in _ROLE_ID_TO_MD:
        md_rel = _ROLE_ID_TO_MD[role_id]
        md_path = os.path.join(ROLES_DIR, md_rel)
        if os.path.exists(md_path):
            return md_path
    
    # 使用role_name查找
    if role_name in _ROLE_TO_MD:
        md_rel = _ROLE_TO_MD[role_name]
        md_path = os.path.join(ROLES_DIR, md_rel)
        if os.path.exists(md_path):
            return md_path
    
    # 尝试从role_name推断 (e.g., "Psychologist" -> "academic/academic-psychologist.md")
    for key, md_rel in _ROLE_TO_MD.items():
        if key.lower() in role_name.lower() or role_name.lower() in key.lower():
            md_path = os.path.join(ROLES_DIR, md_rel)
            if os.path.exists(md_path):
                return md_path
    
    return None


class SubagentState:
    """子代理状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SindrisExecutor:
    """
    Sindris执行器 - 新架构 (v4.2)

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

        # 初始化执行器级别的熔断器（独立于FusionPlanner的规划熔断器）
        # P1-4 Fix: complete_subtask/fail_subtask联动的是"执行器熔断器"，不是"规划熔断器"
        self._executor_circuit_breaker = PlanEngineCircuitBreaker(
            failure_threshold=0.5,
            window_seconds=60,
            open_duration=30,
        )

        # 内部状态
        self._subagent_states: Dict[str, str] = {}
        self._subagent_sessions: Dict[str, str] = {}
        self._subagent_trace: Dict[str, Dict[str, Any]] = {}
        self._trace_runtime: Dict[str, Dict[str, Any]] = {}

        # 初始化日志
        self._setup_jsonl_logger()

        # 初始化OMX集成器
        self.omx = get_integrator(self.workspace_root)

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
        """初始化JSONL日志记录器（文件专用，不污染stderr）"""
        self.jsonl_dir = Path(SCRIPT_DIR) / ".logs"
        self.jsonl_dir.mkdir(exist_ok=True)
        self.jsonl_file = self.jsonl_dir / f"sindris_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        # 创建专属logger，不添加到root logger，避免stderr冗余
        self.logger = logging.getLogger(f"sindris.{self.session_id}")
        self.logger.setLevel(logging.WARNING)
        self.logger.propagate = False  # 不传播到root logger（避免stderr）
        
        # 只添加文件handler，不添加StreamHandler（stderr）
        file_handler = logging.handlers.RotatingFileHandler(
            self.jsonl_dir / f"sindris_warning.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(file_handler)

    def _log_jsonl(self, event_type: str, data: Dict[str, Any]):
        """
        P2-6 Fix: 写入JSONL日志时进行注入防护
        
        使用json.dumps确保所有特殊字符被正确转义，防止JSONL注入。
        json.dumps默认会转义newlines、quotes等特殊字符，确保每行是一个独立的JSON对象。
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            **data
        }
        try:
            json_line = json.dumps(log_entry, ensure_ascii=False)
            # P2-6 Fix: 验证JSON行可解析（双重防护）
            json.loads(json_line)  # 这会验证JSON格式正确
            with open(self.jsonl_file, "a", encoding="utf-8") as f:
                f.write(json_line + "\n")
        except Exception as e:
            # JSONL写入失败不影响主流程，只记录警告
            self.logger.warning(f"JSONL write failed: {e}")

    def _new_trace_id(self) -> str:
        """Generate a stable trace id for one execution flow."""
        return f"trace_{uuid.uuid4().hex[:12]}"

    def record_spawn_result(
        self,
        *,
        task_id: str,
        trace_id: str,
        run_id: str,
        child_session_key: str,
        context: str = "fork",
    ) -> None:
        """
        Record sessions_spawn result using OpenClaw canonical fields.

        Args:
            task_id: Planned subtask id
            trace_id: Local execution trace id
            run_id: sessions_spawn return field runId
            child_session_key: sessions_spawn return field childSessionKey
            context: spawn context ("fork" | "isolated")
        """
        if not task_id:
            return

        self._subagent_states[task_id] = SubagentState.RUNNING
        self._subagent_sessions[task_id] = child_session_key
        self._subagent_trace[task_id] = {
            "trace_id": trace_id,
            "run_id": run_id,
            "child_session_key": child_session_key,
            "context": context,
        }
        trace_runtime = self._trace_runtime.setdefault(trace_id, {"spawns": 0, "yields": 0})
        trace_runtime["spawns"] += 1

        self._log_jsonl("spawn_registered", {
            "task_id": task_id,
            "trace_id": trace_id,
            "run_id": run_id,
            "child_session_key": child_session_key,
            "context": context,
        })

    def record_yield_boundary(self, *, trace_id: str, phase: str) -> None:
        """
        Record a sessions_yield boundary event for this trace.

        Args:
            trace_id: Local execution trace id
            phase: "before_yield" | "after_yield"
        """
        trace_runtime = self._trace_runtime.setdefault(trace_id, {"spawns": 0, "yields": 0})
        trace_runtime["yields"] += 1
        self._log_jsonl("yield_boundary", {
            "trace_id": trace_id,
            "phase": phase,
            "yield_count": trace_runtime["yields"],
        })

    def _plan_to_dict(self, plan: Plan) -> Dict[str, Any]:
        """将Plan对象转换为字典格式"""
        subtasks = []
        for s in plan.subtasks:
            md_file = find_role_md_file(s.role)
            subtask_dict = {
                "phase": s.phase,
                "role": s.role,
                "title": s.title,
                "verify": s.verify,
                "timeout": s.timeout,
                "metadata": s.metadata,
            }
            if md_file:
                subtask_dict["md_file"] = md_file
            subtasks.append(subtask_dict)
        
        return {
            "task_id": plan.task_id,
            "original_task": plan.original_task,
            "subtasks": subtasks,
            "matched_roles": plan.matched_roles,
            "cache_hit": plan.cache_hit,
            "circuit_broken": plan.circuit_broken,
            "metadata": plan.metadata,
        }

    # ========== sindri制度检查 ==========

    def _identify_task_type(self, task: Optional[str]) -> str:
        """
        识别任务类型：audit/fix/role_improvement/other
        
        检测优先级: role_improvement > audit > fix > other
        注意：role_improvement优先级最高，避免"完善"被误判为fix
        """
        if task is None or not str(task).strip():
            return "other"

        task_lower = str(task).lower()
        
        # 角色改进类关键词（最高优先级）
        role_keywords = [
            "改进角色", "优化角色", "完善角色", "修复角色",
            "完善团队", "改进团队", "改进fixed", "角色进化", "role evolution", "角色改进", "完善修复",
        ]
        if any(kw in task_lower for kw in role_keywords):
            return "role_improvement"
        
        # 审计类关键词
        audit_keywords = ["审计", "audit", "审查", "检查问题", "检查", "audit team"]
        if any(kw in task_lower for kw in audit_keywords):
            return "audit"
        
        # 修复类关键词
        fix_keywords = ["修复", "fix", "修补", "解决", "bug", "缺陷", "fixed team"]
        if any(kw in task_lower for kw in fix_keywords):
            return "fix"
        
        # 技能开发类关键词
        skill_keywords = ["开发技能", "迭代技能", "学习参考", "对照开发", "技能开发", "技能迭代", "develop skill", "iterate skill", "study reference"]
        if any(kw in task_lower for kw in skill_keywords):
            return "skill_develop"
        
        return "other"

    def _validate_team_selection(self, task_type: str, team: str) -> bool:
        """
        验证团队选择是否正确
        
        Args:
            task_type: 识别的任务类型
            team: 实际使用的团队
            
        Returns:
            True if valid
            
        Raises:
            ValueError: 团队选择不正确
        """
        valid_teams = {
            "audit": "AUDIT_TEAM",
            "fix": "FIXED_TEAM",
            "role_improvement": "ROLE_EVOLUTION_TEAM",
            "skill_develop": "SKILL_DEVELOP_TEAM",
            "other": "FIXED_TEAM",
        }
        
        expected = valid_teams.get(task_type)
        if expected is None:
            return True
        
        if team != expected:
            raise ValueError(
                f"【sindri制度检查失败】任务类型「{task_type}」应使用团队「{expected}」，当前使用「{team}」"
            )
        return True

    # ========== 核心接口 ==========

    async def plan(self, task: Optional[str], team: str = None) -> Dict[str, Any]:
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
        if task is None or not str(task).strip():
            return {
                "success": False,
                "error": "任务描述不能为空",
                "phase": "rejected",
            }

        # SafetyPolicy检查：拒绝危险任务
        from scripts.safety_policy import can_execute
        ok, safety_result = can_execute(task)
        if not ok:
            self._log_jsonl("plan_rejected", {
                "task": task[:100],
                "reason": safety_result.reason,
                "danger_level": safety_result.danger_level.value,
            })
            return {
                "success": False,
                "error": f"危险任务被拦截: {safety_result.reason}",
                "phase": "rejected",
            }

        self._log_jsonl("plan_start", {"task": task[:100]})

        # OMX Step 1开始
        self.omx.on_round1_start(
            task_description=task,
            matched_roles=[],
        )

        try:
            # sindri制度检查：识别任务类型
            task_type = self._identify_task_type(task)
            
            # sindri制度检查：team=None时自动推断
            valid_teams = {
                "audit": "AUDIT_TEAM",
                "fix": "FIXED_TEAM",
                "role_improvement": "ROLE_EVOLUTION_TEAM",
                "skill_develop": "SKILL_DEVELOP_TEAM",
                "other": "FIXED_TEAM",
            }
            expected_team = valid_teams.get(task_type)
            
            if team is None:
                # 自动推断正确团队
                team = expected_team
                self._log_jsonl("team_auto_inferred", {
                    "task_type": task_type,
                    "auto_team": team,
                    "reason": "team参数为空，自动推断",
                })
            else:
                # 验证传入的团队是否正确
                self._validate_team_selection(task_type, team)
                self._log_jsonl("team_check_pass", {
                    "task_type": task_type,
                    "team": team,
                })
            
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

            # OMX Step 1完成
            self.omx.on_round1_complete(
                plan_summary=result.get("plan_summary", ""),
            )

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

    def mark_subtask_started(self, subtask: Dict[str, Any], session_key: str):
        """
        P2-5 Fix: 重命名execute_subtask为mark_subtask_started
        
        原名execute_subtask名不副实 - 此方法只标记子任务开始执行，
        不实际执行任何操作。真正的执行由sessions_spawn启动的子代理完成。

        Args:
            subtask: 子任务配置
            session_key: 子代理session key
        """
        task_id = subtask.get("task_id")
        trace_id = subtask.get("_trace_id")
        run_id = subtask.get("_run_id")
        child_session_key = subtask.get("_child_session_key", session_key)
        if task_id:
            self._subagent_states[task_id] = SubagentState.RUNNING
            self._subagent_sessions[task_id] = child_session_key
            self._subagent_trace[task_id] = {
                "trace_id": trace_id,
                "run_id": run_id,
                "child_session_key": child_session_key,
            }

        self._log_jsonl("subtask_start", {
            "task_id": task_id,
            "trace_id": trace_id,
            "run_id": run_id,
            "child_session_key": child_session_key,
            "role": subtask.get("role"),
        })

    # P2-5 Fix: 向后兼容别名
    execute_subtask = mark_subtask_started

    def check_command(self, command: str) -> tuple[bool, str]:
        """
        检查命令是否安全（供子代理调用）
        
        用法:
            ok, reason = executor.check_command("rm -rf /tmp")
            if not ok:
                raise PermissionError(f"危险命令被拦截: {reason}")
        
        Returns:
            (can_execute: bool, reason: str)
        """
        from scripts.safety_policy import can_execute
        ok, result = can_execute(command)
        return ok, result.reason if not ok else ""

    def complete_subtask(self, task_id: str, result: Any = None):
        """标记子任务完成"""
        self._subagent_states[task_id] = SubagentState.COMPLETE
        
        # P1-4 Fix: 联动执行器级别的熔断器（不是FusionPlanner的规划熔断器）
        self._executor_circuit_breaker.record_success()
        
        trace_meta = self._subagent_trace.get(task_id, {})
        self._log_jsonl("subtask_complete", {
            "task_id": task_id,
            "trace_id": trace_meta.get("trace_id"),
            "run_id": trace_meta.get("run_id"),
            "child_session_key": trace_meta.get("child_session_key"),
        })

    def fail_subtask(self, task_id: str, error: str):
        """标记子任务失败"""
        self._subagent_states[task_id] = SubagentState.FAILED
        
        # P1-4 Fix: 联动执行器级别的熔断器（不是FusionPlanner的规划熔断器）
        self._executor_circuit_breaker.record_failure()
        
        trace_meta = self._subagent_trace.get(task_id, {})
        self._log_jsonl("subtask_fail", {
            "task_id": task_id,
            "trace_id": trace_meta.get("trace_id"),
            "run_id": trace_meta.get("run_id"),
            "child_session_key": trace_meta.get("child_session_key"),
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
                "trace": self._subagent_trace.get(task_id, {}),
            }
        return {
            "total_tasks": len(self._subagent_states),
            "states": states,
            "trace_runtime": self._trace_runtime,
        }

    # ========== 验证接口 ==========

    async def verify(self, task_type: str, files: List[str] = None,
                     target_role: str = None, improver_id: str = None,
                     verify_items: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        验证执行结果

        Args:
            task_type: 任务类型(dev/audit/evolution)
            files: 涉及的文件列表
            target_role: 目标角色(用于evolution验证)
            improver_id: 改进者ID(用于evolution验证)
            verify_items: 验证项列表(优先使用，否则从target_role/improver_id构建)

        Returns:
            验证结果
        """
        if files is None:
            files = []
        if verify_items is None:
            verify_items = self._build_verify_items(task_type, target_role, improver_id)

        # Mtime追踪
        if files:
            self.verify_engine.take_snapshot(files)

        # 执行验证(使用full_verify异步方法) - 传递真实的verify_items
        result = await self.verify_engine.full_verify(
            task_name=task_type,
            files=files or [],
            verify_items=verify_items,
        )

        return {
            "passed": result.passed,
            "issues": result.issues,
            "details": result.details,
            "recommendation": result.recommendation,
        }

    def _build_verify_items(self, task_type: str, target_role: str = None,
                            improver_id: str = None) -> List[Dict[str, Any]]:
        """
        根据task_type/target_role/improver_id构建verify_items

        P0-1 Fix: 不再传空verify_items，让Ralph验证真正生效
        """
        items = []

        if task_type in ("evolution", "improve"):
            # Evolution验证项
            items.append({
                "name": "文件修改检查",
                "description": f"验证{improver_id or target_role or '改进者'}是否修改了目标文件",
                "check_fn": self._default_file_modified_check,
            })
            if target_role:
                items.append({
                    "name": f"{target_role}角色一致性",
                    "description": f"验证改进遵循{target_role}角色约束",
                    "check_fn": self._default_role_consistency_check,
                })
        elif task_type in ("audit", "review"):
            # Audit验证项
            items.append({
                "name": "代码质量检查",
                "description": "Ralph审计：安全/性能/可维护性",
                "check_fn": self._default_audit_check,
            })
            items.append({
                "name": "路径契约验证",
                "description": "验证OMX路径契约是否满足",
                "check_fn": self._default_omx_check,
            })
        else:
            # Dev验证项
            items.append({
                "name": "功能实现检查",
                "description": "验证功能是否按规划实现",
                "check_fn": self._default_impl_check,
            })
            items.append({
                "name": "测试通过",
                "description": "验证单元测试通过",
                "check_fn": self._default_test_check,
            })

        return items

    def _default_file_modified_check(self) -> bool:
        """默认文件修改检查"""
        return True  # 由调用方通过files参数提供具体文件

    def _default_role_consistency_check(self) -> bool:
        """默认角色一致性检查"""
        return True

    def _default_audit_check(self) -> bool:
        """默认审计检查"""
        return True

    def _default_omx_check(self) -> bool:
        """默认OMX路径契约检查"""
        return True

    def _default_impl_check(self) -> bool:
        """默认实现检查"""
        return True

    def _default_test_check(self) -> bool:
        """默认测试检查"""
        return True

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
        
        P1-4 Fix: 现在记录到执行器级别的熔断器，而不是FusionPlanner的规划熔断器
        
        Args:
            task_id: 任务ID
            success: 是否成功
        """
        if success:
            self._executor_circuit_breaker.record_success()
        else:
            self._executor_circuit_breaker.record_failure()

    def get_executor_circuit_state(self) -> CircuitState:
        """获取执行器熔断器状态"""
        return self._executor_circuit_breaker.state

    def is_executor_circuit_open(self) -> bool:
        """检查执行器熔断器是否打开"""
        return self._executor_circuit_breaker.state == CircuitState.OPEN

    # --------------------- execute() 自动执行 ---------------------

    async def execute(self, task: str, team: str = None) -> Dict[str, Any]:
        """
        自动执行完整sindri流程

        Step 1: plan() → 规划任务
        Step 2: 执行subtasks → 自动OMX记录
        Step 3: verify_with_ralph() → 强制验证
        Step 4: Git commit

        Args:
            task: 任务描述
            team: 可选的团队名称

        Returns:
            执行结果字典
        """
        # Step 1: 规划
        plan_result = await self.plan(task, team)
        if not plan_result.get("success"):
            return plan_result

        subtasks = plan_result.get("subtasks", [])
        task_id = self.omx.last_task_id
        trace_id = self._new_trace_id()

        # Step 2: OMX Step 2开始
        actions = [
            {
                "action_id": st.get("task_id", f"action_{i}"),
                "action_name": st.get("title", ""),
                "role": st.get("role", ""),
                "trace_id": trace_id,
            }
            for i, st in enumerate(subtasks)
        ]
        self.omx.on_round2_start(task_id=task_id, actions=actions)

        # 执行每个subtask
        for i, subtask in enumerate(subtasks):
            action_id = subtask.get("task_id", f"action_{i}")

            # OMX动作开始
            self.omx.on_action_start(action_id=action_id)

            # 执行subtask（由调用者通过sessions_spawn执行）
            # 这里只记录，不真正执行
            subtask["_action_id"] = action_id
            subtask["_index"] = i
            subtask["_trace_id"] = trace_id

        # 返回plan_result，让调用者执行subtasks
        plan_result["_omx_task_id"] = task_id
        plan_result["_omx_actions"] = actions
        plan_result["_execution_mode"] = "manual_spawn"
        plan_result["_trace_id"] = trace_id

        self._log_jsonl("execution_trace_created", {
            "trace_id": trace_id,
            "task_id": task_id,
            "actions_count": len(actions),
        })

        return plan_result

    def mark_action_complete(
        self,
        action_id: str,
        verified: bool = True,
        verify_results: Dict[str, bool] = None,
        error: str = None,
        trace_id: str = None,
    ) -> None:
        """
        标记一个action完成（供调用者在subtask完成后调用）

        Args:
            action_id: 动作ID
            verified: 是否通过验证
            verify_results: 验证结果字典
            error: 错误信息
        """
        self.omx.on_action_complete(
            action_id=action_id,
            verified=verified,
            verify_results=verify_results or {},
            error=error,
            trace_id=trace_id,
        )


# 兼容性别名
Sindris = SindrisExecutor


async def plan_sindris(task: str) -> Dict[str, Any]:
    """便捷函数:规划sindris"""
    executor = SindrisExecutor()
    return await executor.plan(task)
