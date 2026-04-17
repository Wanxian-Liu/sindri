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

__all__ = [
    "GStackRole",
    "GStackResult", 
    "call_gstack_role",
    "HealthScoreConfig",
    "HealthScoreResult",
    "calculate_health_score",
    "format_health_report",
]
