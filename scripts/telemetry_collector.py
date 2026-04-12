"""
telemetry_collector.py - 运行时遥测数据收集模块

基于 oh-my-codex telemetry hook 概念设计
功能: 收集执行时间、成功率、熔断次数等遥测数据

数据收集项:
  - 执行时间: task_duration_ms
  - 成功率: success/failure/total
  - 熔断次数: circuit_breaks
  - 危险拦截: safety_blocks
  - 角色分布: role_distribution
  - 并行度: parallel_tasks
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum
import threading

# ============================================================
# 类型定义
# ============================================================

class TelemetryEvent(Enum):
    """遥测事件类型"""
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAILURE = "task_failure"
    CIRCUIT_BREAK = "circuit_break"
    SAFETY_BLOCK = "safety_block"
    CONSENSUS_YES = "consensus_yes"
    CONSENSUS_NO = "consensus_no"
    ROUND_CHANGE = "round_change"

@dataclass
class TelemetryEntry:
    """遥测条目"""
    event: str
    timestamp: str
    task_id: Optional[str] = None
    worker_id: Optional[str] = None
    role: Optional[str] = None
    duration_ms: Optional[int] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

# ============================================================
# TelemetryCollector 主类
# ============================================================

class TelemetryCollector:
    """
    运行时遥测收集器
    
    使用方法:
        collector = TelemetryCollector()
        collector.record(TelemetryEvent.TASK_COMPLETE, task_id="task_001")
        stats = collector.get_stats()
    """

    def __init__(self, telemetry_dir: Optional[str] = None):
        """
        初始化TelemetryCollector
        
        Args:
            telemetry_dir: 遥测目录，默认使用.omx/logs/
        """
        if telemetry_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sindris_root = os.path.dirname(script_dir)
            omx_dir = os.path.join(sindris_root, ".omx")
            telemetry_dir = os.path.join(omx_dir, "logs")
        
        self.telemetry_dir = Path(telemetry_dir)
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前任务追踪
        self._current_task_start: Dict[str, float] = {}
        
        # 统计
        self._stats_lock = threading.Lock()
        self._stats = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "circuit_breaks": 0,
            "safety_blocks": 0,
            "total_duration_ms": 0,
            "role_stats": {},  # role -> count
        }
        
        # 事件日志
        self._events: List[TelemetryEntry] = []

    def record(
        self,
        event: TelemetryEvent,
        task_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        role: Optional[str] = None,
        success: Optional[bool] = None,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> TelemetryEntry:
        """
        记录遥测事件
        
        Args:
            event: 事件类型
            task_id: 任务ID
            worker_id: Worker ID
            role: 角色名称
            success: 是否成功
            error: 错误信息
            details: 额外详情
            
        Returns:
            TelemetryEntry: 创建的条目
        """
        entry = TelemetryEntry(
            event=event.value,
            timestamp=datetime.now().isoformat(),
            task_id=task_id,
            worker_id=worker_id,
            role=role,
            success=success,
            error=error,
            details=details or {}
        )
        
        # 写入日志文件
        self._write_entry(entry)
        
        # 更新统计
        self._update_stats(entry)
        
        # 记录到内存
        self._events.append(entry)
        
        return entry

    def task_start(self, task_id: str, role: Optional[str] = None) -> None:
        """记录任务开始"""
        self._current_task_start[task_id] = time.time()
        self.record(
            event=TelemetryEvent.TASK_START,
            task_id=task_id,
            role=role,
        )

    def task_complete(
        self,
        task_id: str,
        role: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """记录任务完成"""
        duration_ms = None
        if task_id in self._current_task_start:
            duration_ms = int((time.time() - self._current_task_start[task_id]) * 1000)
            del self._current_task_start[task_id]
        
        self.record(
            event=TelemetryEvent.TASK_COMPLETE if success else TelemetryEvent.TASK_FAILURE,
            task_id=task_id,
            role=role,
            success=success,
            error=error,
            details={"duration_ms": duration_ms} if duration_ms else {},
        )

    def circuit_break(
        self,
        task_id: str,
        role: str,
        reason: str,
    ) -> None:
        """记录熔断"""
        self.record(
            event=TelemetryEvent.CIRCUIT_BREAK,
            task_id=task_id,
            role=role,
            success=False,
            error=f"Circuit break: {reason}",
            details={"reason": reason},
        )

    def safety_block(
        self,
        task_id: str,
        command: str,
        danger_level: str,
    ) -> None:
        """记录安全拦截"""
        self.record(
            event=TelemetryEvent.SAFETY_BLOCK,
            task_id=task_id,
            success=False,
            error=f"Safety blocked: {command}",
            details={"command": command, "danger_level": danger_level},
        )

    def consensus(self, task_id: str, approved: bool) -> None:
        """记录共识投票"""
        self.record(
            event=TelemetryEvent.CONSENSUS_YES if approved else TelemetryEvent.CONSENSUS_NO,
            task_id=task_id,
            success=approved,
        )

    def round_change(self, from_round: str, to_round: str, task_id: Optional[str] = None) -> None:
        """记录Round切换"""
        self.record(
            event=TelemetryEvent.ROUND_CHANGE,
            task_id=task_id,
            details={"from_round": from_round, "to_round": to_round},
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._stats_lock:
            stats = self._stats.copy()
        
        # 计算派生指标
        if stats["total_tasks"] > 0:
            stats["success_rate"] = stats["successful_tasks"] / stats["total_tasks"]
            stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["total_tasks"]
        else:
            stats["success_rate"] = 0.0
            stats["avg_duration_ms"] = 0
        
        return stats

    def get_role_stats(self) -> Dict[str, Dict[str, int]]:
        """获取角色统计"""
        with self._stats_lock:
            return self._stats.get("role_stats", {}).copy()

    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近事件"""
        return [e.to_dict() for e in self._events[-limit:]]

    def _write_entry(self, entry: TelemetryEntry):
        """写入遥测日志文件"""
        # 按日期组织: telemetry_YYYY-MM-DD.jsonl
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.telemetry_dir / f"telemetry_{date_str}.jsonl"
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def _update_stats(self, entry: TelemetryEntry):
        """更新统计信息"""
        with self._stats_lock:
            if entry.event in [TelemetryEvent.TASK_COMPLETE.value, TelemetryEvent.TASK_FAILURE.value]:
                self._stats["total_tasks"] += 1
                
                if entry.success:
                    self._stats["successful_tasks"] += 1
                else:
                    self._stats["failed_tasks"] += 1
                
                if entry.duration_ms:
                    self._stats["total_duration_ms"] += entry.duration_ms
                
                if entry.role:
                    role_stats = self._stats.setdefault("role_stats", {})
                    role_stats[entry.role] = role_stats.get(entry.role, 0) + 1
            
            elif entry.event == TelemetryEvent.CIRCUIT_BREAK.value:
                self._stats["circuit_breaks"] += 1
            
            elif entry.event == TelemetryEvent.SAFETY_BLOCK.value:
                self._stats["safety_blocks"] += 1


# ============================================================
# 便捷函数
# ============================================================

_default_collector: Optional[TelemetryCollector] = None

def get_default_collector() -> TelemetryCollector:
    """获取默认TelemetryCollector实例"""
    global _default_collector
    if _default_collector is None:
        _default_collector = TelemetryCollector()
    return _default_collector


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("TelemetryCollector 单元测试")
    print("=" * 60)
    
    collector = TelemetryCollector()
    
    # 模拟任务流程
    collector.task_start("task_001", role="developer")
    collector.task_complete("task_001", role="developer", success=True)
    print("✅ 任务1完成")
    
    collector.task_start("task_002", role="researcher")
    collector.task_complete("task_002", role="researcher", success=False, error="超时")
    print("✅ 任务2失败")
    
    collector.circuit_break("task_003", role="developer", reason="连续失败3次")
    print("✅ 熔断记录")
    
    collector.safety_block("task_004", command="rm -rf /", danger_level="critical")
    print("✅ 安全拦截记录")
    
    collector.consensus("task_005", approved=True)
    print("✅ 共识记录")
    
    collector.round_change("Round1", "Round2")
    print("✅ Round切换")
    
    print("=" * 60)
    print(f"统计: {collector.get_stats()}")
    print(f"角色统计: {collector.get_role_stats()}")
