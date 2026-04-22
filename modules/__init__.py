"""
Sindri+GStackPro混合框架 - 主入口

整合Sindri Round1-4流程与GStackPro质量关卡

流程:
Round0: CEO审视 (GStackPro) - 值不值得做？
Round1: 规划 (Sindri) - 178角色匹配
Round2: 执行 (Sindri) + Paranoid Review (GStackPro)
Round3: 集成 + Health Score (GStackPro)
Round4: 完成 (Sindri)
"""

from .gstack_integration import (
    GStackRole,
    GStackResult,
    call_gstack_role,
)
from .health_score import (
    HealthScoreConfig,
    HealthScoreResult,
    calculate_health_score,
    format_health_report,
)

# Sindris核心组件
from .scheduler import SindrisScheduler
from .round_manager import RoundManager
from .report_generator import ReportGenerator
from .role_manager import RoleManager
from .role_matcher import RoleMatcher, FIXED_TEAM, FIXED_TEAM_TRIGGERS
from .role_hierarchical_matcher import (
    RoleHierarchicalMatcher,
    classify_domain,
    classify_skills,
    match_roles,
)
from .task_decomposer import TaskDecomposer
from .plan_engine import (
    Plan,
    Subtask,
    FastPathCache,
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
)
from .fusion_planner import (
    FusionPlanner,
    FusionPlan,
)
from .verify_engine import (
    VerifyEngine,
    VerifyResult,
    VerifyPhase,
    MtimeTracker,
    MockInjector,
    IntegrationVerifier,
    create_verify_engine,
)

# OMX集成器
from scripts.omx_integrator import OMXIntegrator, get_integrator, reset_integrator

__all__ = [
    # GStackPro
    "GStackRole",
    "GStackResult",
    "call_gstack_role",
    "HealthScoreConfig",
    "HealthScoreResult",
    "calculate_health_score",
    "format_health_report",
    # Sindris核心
    "SindrisScheduler",
    "RoundManager",
    "ReportGenerator",
    "RoleManager",
    "RoleMatcher",
    "FIXED_TEAM",
    "FIXED_TEAM_TRIGGERS",
    # 分层角色匹配
    "RoleHierarchicalMatcher",
    "classify_domain",
    "classify_skills",
    "match_roles",
    # 任务规划引擎
    "Plan",
    "Subtask",
    "FastPathCache",
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerOpenError",
    # 融合规划引擎（新架构）
    "FusionPlanner",
    "FusionPlan",
    # 验证引擎
    "VerifyEngine",
    "VerifyResult",
    "VerifyPhase",
    "MtimeTracker",
    "MockInjector",
    "IntegrationVerifier",
    "create_verify_engine",
    # 进化任务
    "EVOLUTION_TASK_CONFIG",
    "HERMES_CORE_COMPONENTS",
    "MIMIR_AETHER_COMPONENTS",
    "EVOLUTION_REPORT_TEMPLATE",
    # OMX集成器
    "OMXIntegrator",
    "get_integrator",
    "reset_integrator",
]
