"""
Sindri+GStackPro混合框架 - Health Score计算

P0修复3: 硬编码阈值改为可配置
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import json


@dataclass
class HealthScoreConfig:
    """Health Score配置"""
    functional_weight: float = 30.0      # 功能测试权重
    edge_cases_weight: float = 25.0       # 边界测试权重
    console_errors_weight: float = 25.0   # 控制台错误权重
    design_regressions_weight: float = 20.0  # 设计退化权重
    excellent_threshold: float = 90.0      # 🟢 Excellent门槛
    good_threshold: float = 70.0          # 🟡 Good门槛
    needs_work_threshold: float = 50.0    # 🟠 Needs Work门槛


@dataclass
class HealthScoreResult:
    """Health Score结果"""
    score: int
    status: str
    breakdown: Dict[str, Any]
    ship_recommendation: str
    issues: List[str]


def calculate_health_score(
    test_results: Dict[str, Any],
    config: Optional[HealthScoreConfig] = None
) -> HealthScoreResult:
    """
    计算Health Score
    
    公式:
    Health Score = round(
        functional_tests_passed / total_tests × 30 +
        edge_cases_covered / total_edge_cases × 25 +
        no_console_errors × 25 +
        no_design_regressions × 20
    )
    
    Args:
        test_results: 测试结果，包含:
            - functional: {"passed": int, "total": int}
            - edge_cases: {"covered": int, "total": int}
            - console_errors: bool (True表示无错误)
            - design_regressions: bool (True表示无退化)
        config: 可选的配置
        
    Returns:
        HealthScoreResult: 包含分数、状态、建议
    """
    if config is None:
        config = HealthScoreConfig()
    
    # 计算各项得分
    functional_score = 0.0
    if test_results.get("functional"):
        t = test_results["functional"]
        if t.get("total", 0) > 0:
            functional_score = (t["passed"] / t["total"]) * config.functional_weight
    
    edge_cases_score = 0.0
    if test_results.get("edge_cases"):
        e = test_results["edge_cases"]
        if e.get("total", 0) > 0:
            edge_cases_score = (e["covered"] / e["total"]) * config.edge_cases_weight
    
    console_errors_score = config.console_errors_weight if test_results.get("console_errors", True) else 0.0
    
    design_regressions_score = config.design_regressions_weight if test_results.get("design_regressions", True) else 0.0
    
    # 计算总分
    total_score = round(functional_score + edge_cases_score + console_errors_score + design_regressions_score)
    
    # 判断状态
    if total_score >= config.excellent_threshold:
        status = "🟢 Excellent"
        recommendation = "Ready to ship immediately"
    elif total_score >= config.good_threshold:
        status = "🟡 Good"
        recommendation = "2-3 minor issues, fix before ship"
    elif total_score >= config.needs_work_threshold:
        status = "🟠 Needs Work"
        recommendation = "Significant bugs, fix before next sprint"
    else:
        status = "🔴 Do Not Ship"
        recommendation = "Core functionality broken, must fix"
    
    # 收集问题
    issues = []
    if test_results.get("functional", {}).get("failed_details"):
        issues.extend(test_results["functional"]["failed_details"])
    
    return HealthScoreResult(
        score=total_score,
        status=status,
        breakdown={
            "functional": {
                "passed": test_results.get("functional", {}).get("passed", 0),
                "total": test_results.get("functional", {}).get("total", 0),
                "score": functional_score
            },
            "edge_cases": {
                "covered": test_results.get("edge_cases", {}).get("covered", 0),
                "total": test_results.get("edge_cases", {}).get("total", 0),
                "score": edge_cases_score
            },
            "console_errors": {
                "passed": test_results.get("console_errors", True),
                "score": console_errors_score
            },
            "design_regressions": {
                "passed": test_results.get("design_regressions", True),
                "score": design_regressions_score
            }
        },
        ship_recommendation=recommendation,
        issues=issues
    )


def format_health_report(result: HealthScoreResult) -> str:
    """格式化Health Score报告"""
    lines = [
        f"# Health Score: {result.score}/100 {result.status}",
        "",
        "## Breakdown",
    ]
    
    for category, data in result.breakdown.items():
        if isinstance(data, dict):
            score = data.get("score", 0)
            lines.append(f"- {category}: {score:.1f}")
    
    lines.extend([
        "",
        f"## Recommendation",
        f"{result.ship_recommendation}",
        ""
    ])
    
    if result.issues:
        lines.append("## Issues Found")
        for issue in result.issues:
            lines.append(f"- {issue}")
    
    return "\n".join(lines)
