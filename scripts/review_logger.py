"""
review_logger.py - 结果review记录模块

基于 oh-my-codex review hook 概念设计
功能: 捕获执行结果，提取关键信号，写入.omx/reviews/

结果信号类型:
  - success: 任务成功完成
  - failure: 任务失败
  - timeout: 任务超时
  - circuit_break: 熔断触发
  - consensus_yes: 共识投票通过
  - consensus_no: 共识投票拒绝
"""

import json
import uuid
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path

# ============================================================
# 类型定义
# ============================================================

class ResultSignal(Enum):
    """结果信号"""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CIRCUIT_BREAK = "circuit_break"
    CONSENSUS_YES = "consensus_yes"
    CONSENSUS_NO = "consensus_no"
    PARTIAL = "partial"  # 部分成功

@dataclass
class ReviewEntry:
    """Review条目"""
    id: str
    task_id: str
    signal: str
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = field(default_factory=list)
    blocked: bool = False
    blocked_reason: Optional[str] = None

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'ReviewEntry':
        return ReviewEntry(**d)

# ============================================================
# 结果提取器
# ============================================================

class ResultExtractor:
    """
    从执行结果中提取关键信号
    """

    @staticmethod
    def extract_from_exit_code(exit_code: int) -> ResultSignal:
        """从退出码提取信号"""
        if exit_code == 0:
            return ResultSignal.SUCCESS
        elif exit_code == 124:  # timeout
            return ResultSignal.TIMEOUT
        else:
            return ResultSignal.FAILURE

    @staticmethod
    def extract_from_output(output: str) -> Dict[str, Any]:
        """
        从输出中提取关键信息
        
        Returns:
            包含以下键的字典:
            - has_error: bool
            - has_warning: bool
            - error_count: int
            - warning_count: int
            - key_patterns: list (发现的关键模式)
        """
        result = {
            "has_error": False,
            "has_warning": False,
            "error_count": 0,
            "warning_count": 0,
            "key_patterns": [],
            "error_lines": [],
            "warning_lines": []
        }
        
        if not output:
            return result
        
        lines = output.split('\n')
        
        for line in lines:
            line_lower = line.lower()
            
            # 错误检测
            if any(p in line_lower for p in ['error', 'fail', 'exception', 'traceback']):
                result['has_error'] = True
                result['error_count'] += 1
                result['error_lines'].append(line.strip())
            
            # 警告检测
            if any(p in line_lower for p in ['warning', 'warn', 'deprecated']):
                result['has_warning'] = True
                result['warning_count'] += 1
                result['warning_lines'].append(line.strip())
            
            # 关键模式检测
            if 'consensus: yes' in line_lower or '[consensus: yes]' in line_lower:
                result['key_patterns'].append('CONSENSUS_YES')
            if 'consensus: no' in line_lower or '[consensus: no]' in line_lower:
                result['key_patterns'].append('CONSENSUS_NO')
            if 'circuit break' in line_lower:
                result['key_patterns'].append('CIRCUIT_BREAK')
        
        return result

    @staticmethod
    def summarize(result: Dict[str, Any]) -> str:
        """生成摘要文本"""
        if result['has_error']:
            return f"发现 {result['error_count']} 个错误"
        elif result['has_warning']:
            return f"发现 {result['warning_count']} 个警告"
        else:
            return "执行正常"


# ============================================================
# ReviewLogger 主类
# ============================================================

class ReviewLogger:
    """
    结果review记录器
    
    使用方法:
        logger = ReviewLogger()
        logger.log(task_id="task_001", signal=ResultSignal.SUCCESS, details={...})
    """

    def __init__(self, reviews_dir: Optional[str] = None):
        """
        初始化ReviewLogger
        
        Args:
            reviews_dir: reviews目录路径，默认使用.omx/reviews/
        """
        if reviews_dir is None:
            # 查找.omx目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # sindris skills/scripts/ -> sindris/.omx/
            sindris_root = os.path.dirname(script_dir)
            omx_dir = os.path.join(sindris_root, ".omx")
            reviews_dir = os.path.join(omx_dir, "reviews")
        
        self.reviews_dir = Path(reviews_dir)
        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计
        self.log_count = 0
        self.signal_stats: Dict[str, int] = {}

    def log(
        self,
        task_id: str,
        signal: ResultSignal,
        summary: str = "",
        details: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        output: Optional[str] = None
    ) -> ReviewEntry:
        """
        记录执行结果
        
        Args:
            task_id: 任务ID
            signal: 结果信号
            summary: 摘要描述
            details: 详细信息
            tags: 标签列表
            output: 原始输出（可选，用于提取）
            
        Returns:
            ReviewEntry: 创建的条目
        """
        # 如果没有摘要但有输出，自动提取
        if not summary and output:
            extracted = ResultExtractor.extract_from_output(output)
            summary = ResultExtractor.summarize(extracted)
            details = details or {}
            details['output_analysis'] = extracted
        elif not summary:
            summary = f"任务 {task_id} {signal.value}"
        
        # 创建条目
        entry = ReviewEntry(
            id=f"review_{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            signal=signal.value,
            summary=summary,
            details=details or {},
            tags=tags or []
        )
        
        # 写入文件
        self._write_entry(entry)
        
        # 更新统计
        self.log_count += 1
        self.signal_stats[signal.value] = self.signal_stats.get(signal.value, 0) + 1
        
        return entry

    def log_success(
        self,
        task_id: str,
        summary: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> ReviewEntry:
        """快捷方法: 记录成功"""
        return self.log(task_id, ResultSignal.SUCCESS, summary, details)

    def log_failure(
        self,
        task_id: str,
        summary: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> ReviewEntry:
        """快捷方法: 记录失败"""
        return self.log(task_id, ResultSignal.FAILURE, summary, details)

    def log_timeout(
        self,
        task_id: str,
        summary: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> ReviewEntry:
        """快捷方法: 记录超时"""
        return self.log(task_id, ResultSignal.TIMEOUT, summary, details)

    def log_circuit_break(
        self,
        task_id: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ) -> ReviewEntry:
        """快捷方法: 记录熔断"""
        entry = self.log(
            task_id,
            ResultSignal.CIRCUIT_BREAK,
            f"熔断触发: {reason}",
            details=details,
            tags=["circuit_break"]
        )
        entry.blocked = True
        entry.blocked_reason = reason
        return entry

    def _write_entry(self, entry: ReviewEntry):
        """写入条目到文件"""
        # 按日期组织文件: reviews/YYYY-MM-DD.jsonl
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.reviews_dir / f"{date_str}.jsonl"
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_logs": self.log_count,
            "signal_stats": self.signal_stats,
            "reviews_dir": str(self.reviews_dir)
        }

    def list_recent(self, limit: int = 10) -> List[ReviewEntry]:
        """列出最近的review条目"""
        entries = []
        
        # 读取今天的文件
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.reviews_dir / f"{date_str}.jsonl"
        
        if not file_path.exists():
            return entries
        
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line in lines[-limit:]:
            try:
                data = json.loads(line.strip())
                entries.append(ReviewEntry.from_dict(data))
            except json.JSONDecodeError:
                continue
        
        return list(reversed(entries))


# ============================================================
# 便捷函数
# ============================================================

_default_logger: Optional[ReviewLogger] = None

def get_default_logger() -> ReviewLogger:
    """获取默认ReviewLogger实例"""
    global _default_logger
    if _default_logger is None:
        _default_logger = ReviewLogger()
    return _default_logger

def log_review(task_id: str, signal: ResultSignal, **kwargs) -> ReviewEntry:
    """快速记录review"""
    return get_default_logger().log(task_id, signal, **kwargs)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("ReviewLogger 单元测试")
    print("=" * 60)
    
    logger = ReviewLogger()
    
    # 测试日志
    entry1 = logger.log_success("task_001", "任务执行成功")
    print(f"✅ 记录成功: {entry1.id}")
    
    entry2 = logger.log_failure("task_002", "任务执行失败")
    print(f"❌ 记录失败: {entry2.id}")
    
    entry3 = logger.log_timeout("task_003", "任务超时")
    print(f"⏱️ 记录超时: {entry3.id}")
    
    entry4 = logger.log_circuit_break("task_004", "连续失败3次")
    print(f"⚡ 记录熔断: {entry4.id}")
    
    # 测试输出分析
    test_output = """
    2024-01-01 10:00:00 Starting task
    [CONSENSUS: YES] 任务通过
    2024-01-01 10:00:01 Completed
    """
    extracted = ResultExtractor.extract_from_output(test_output)
    print(f"\n输出分析: {extracted}")
    
    print("=" * 60)
    print(f"统计: {logger.get_stats()}")
