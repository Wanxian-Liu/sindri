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
from .task_decomposer import TaskDecomposer

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
]
