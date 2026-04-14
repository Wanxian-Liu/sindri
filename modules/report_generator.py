"""
report_generator.py - 报告生成模块

职责：
- RoundContext数据结构
- ExecutionResult数据结构
- 各类报告生成
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class ExecutionStatus(str):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class RoundPhase(str):
    """Round阶段"""
    PLANNING = "planning"
    EXECUTION = "execution"
    REVIEW = "review"
    COMPLETION = "completion"


@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: str
    title: str
    role: str
    status: ExecutionStatus
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    verify_passed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RoundContext:
    """Round上下文"""
    round: int
    phase: RoundPhase
    task: str
    matched_roles: List[Dict]
    tasks: List[Any] = field(default_factory=list)
    plan_summary: str = ""
    session_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round": self.round,
            "phase": self.phase,
            "task": self.task,
            "matched_roles": self.matched_roles,
            "tasks": [t.to_dict() if hasattr(t, 'to_dict') else str(t) for t in self.tasks],
            "plan_summary": self.plan_summary,
            "session_id": self.session_id,
        }


class ReportGenerator:
    """
    报告生成器
    
    职责：
    1. 生成各阶段报告
    2. 汇总执行结果
    3. 生成最终交付物
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._reports: List[Dict[str, Any]] = []
        self._start_time = datetime.now()
    
    def generate_round1_report(self, ctx: RoundContext) -> Dict[str, Any]:
        """生成Round1规划报告"""
        report = {
            "session_id": self.session_id,
            "round": 1,
            "phase": "planning",
            "timestamp": datetime.now().isoformat(),
            "task": ctx.task,
            "matched_roles": [r.get('name', r.get('id', 'unknown')) for r in ctx.matched_roles],
            "task_count": len(ctx.tasks),
            "plan_summary": ctx.plan_summary,
        }
        self._reports.append(report)
        return report
    
    def generate_round2_report(self, results: List[ExecutionResult]) -> Dict[str, Any]:
        """生成Round2执行报告"""
        success_count = sum(1 for r in results if r.status == ExecutionStatus.SUCCESS)
        failed_count = len(results) - success_count
        
        report = {
            "session_id": self.session_id,
            "round": 2,
            "phase": "execution",
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(results),
            "successful": success_count,
            "failed": failed_count,
            "success_rate": f"{success_count/len(results)*100:.1f}%" if results else "0%",
            "results": [r.to_dict() for r in results],
        }
        self._reports.append(report)
        return report
    
    def generate_round3_report(self, results: List[ExecutionResult], review_passed: bool) -> Dict[str, Any]:
        """生成Round3审查报告"""
        report = {
            "session_id": self.session_id,
            "round": 3,
            "phase": "review",
            "timestamp": datetime.now().isoformat(),
            "reviewed_tasks": len(results),
            "review_passed": review_passed,
            "summary": "通过" if review_passed else "需要修改",
        }
        self._reports.append(report)
        return report
    
    def generate_final_report(self, all_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成最终报告"""
        total_duration = (datetime.now() - self._start_time).total_seconds()
        
        final_report = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "total_duration_seconds": total_duration,
            "rounds_completed": len(all_reports),
            "reports": all_reports,
        }
        return final_report
    
    def format_markdown(self, report: Dict[str, Any]) -> str:
        """格式化报告为Markdown"""
        lines = [
            f"# Sindris 执行报告",
            f"",
            f"**Session ID**: {report.get('session_id', 'unknown')}",
            f"**Timestamp**: {report.get('timestamp', 'unknown')}",
            "",
        ]
        
        if 'round' in report:
            lines.append(f"## Round {report['round']} - {report.get('phase', 'unknown').title()}")
            lines.append("")
            
            for key, value in report.items():
                if key in ('session_id', 'timestamp', 'round', 'phase'):
                    continue
                if isinstance(value, dict):
                    lines.append(f"### {key.title()}")
                    for k, v in value.items():
                        lines.append(f"- **{k}**: {v}")
                    lines.append("")
                elif isinstance(value, list):
                    lines.append(f"### {key.title()}")
                    for item in value[:10]:  # 限制显示10条
                        lines.append(f"- {item}")
                    if len(value) > 10:
                        lines.append(f"- ... 还有 {len(value) - 10} 条")
                    lines.append("")
                else:
                    lines.append(f"- **{key}**: {value}")
        
        return "\n".join(lines)
    
    def save_report(self, report: Dict[str, Any], path: str) -> None:
        """保存报告到文件"""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
