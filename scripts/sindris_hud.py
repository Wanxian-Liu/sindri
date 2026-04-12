"""
sindris_hud.py - sindris 实时状态显示模块

功能:
  1. 实时任务状态显示
  2. 熔断状态监控
  3. 团队运行时状态
  4. 进度条和统计

基于 oh-my-codex HUD 设计
"""

import sys
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

# ============================================================
# 类型定义
# ============================================================

class HUDStyle(Enum):
    """HUD样式"""
    COMPACT = "compact"      # 紧凑模式
    EXPANDED = "expanded"    # 展开模式
    MINIMAL = "minimal"     # 最小模式

@dataclass
class TaskDisplay:
    """任务显示信息"""
    task_id: str
    title: str
    role: str
    status: str
    progress: int  # 0-100
    duration_ms: Optional[int] = None
    error: Optional[str] = None

@dataclass
class HUDData:
    """HUD数据"""
    session_id: str
    current_round: str
    tasks: List[TaskDisplay]
    queue_size: int
    blocked_count: int
    circuit_breaks: int
    success_rate: float
    total_duration_ms: int
    stats: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# HUD 渲染器
# ============================================================

class HUDRenderer:
    """
    HUD渲染器
    
    使用方法:
        renderer = HUDRenderer()
        output = renderer.render(data)
        print(output)
    """

    def __init__(self, style: HUDStyle = HUDStyle.COMPACT):
        self.style = style
        self.width = 80

    def render(self, data: HUDData) -> str:
        """渲染HUD"""
        if self.style == HUDStyle.MINIMAL:
            return self._render_minimal(data)
        elif self.style == HUDStyle.EXPANDED:
            return self._render_expanded(data)
        else:
            return self._render_compact(data)

    def _render_minimal(self, data: HUDData) -> str:
        """最小模式"""
        lines = []
        lines.append(f"【sindris】 Round:{data.current_round} Tasks:{len(data.tasks)} Q:{data.queue_size} Blocked:{data.blocked_count}")
        
        for task in data.tasks:
            status_icon = self._get_status_icon(task.status)
            progress_bar = self._make_progress_bar(task.progress)
            lines.append(f"  {status_icon} {task.role}: {task.title[:30]} {progress_bar}")
        
        return "\n".join(lines)

    def _render_compact(self, data: HUDData) -> str:
        """紧凑模式"""
        lines = []
        lines.append(self._header(f"sindris HUD"))
        lines.append(self._separator())
        
        # 汇总信息
        lines.append(f"  Session: {data.session_id[:12]}")
        lines.append(f"  Round: {data.current_round}")
        lines.append(f"  Queue: {data.queue_size} | Blocked: {data.blocked_count} | Circuit Breaks: {data.circuit_breaks}")
        lines.append(f"  Success Rate: {data.success_rate:.1%}")
        
        if data.stats:
            lines.append(f"  Total Tasks: {data.stats.get('total_tasks', 0)} | Completed: {data.stats.get('successful_tasks', 0)} | Failed: {data.stats.get('failed_tasks', 0)}")
        
        lines.append(self._separator())
        
        # 任务列表
        lines.append("  Tasks:")
        for task in data.tasks:
            status_icon = self._get_status_icon(task.status)
            progress_bar = self._make_progress_bar(task.progress)
            
            task_line = f"  {status_icon} [{task.role}] {task.title[:35]} {progress_bar}"
            if task.error:
                task_line += f" ⚠️ {task.error[:20]}"
            lines.append(task_line)
        
        lines.append(self._separator())
        lines.append(f"  Updated: {datetime.now().strftime('%H:%M:%S')}")
        
        return "\n".join(lines)

    def _render_expanded(self, data: HUDData) -> str:
        """展开模式"""
        lines = []
        lines.append(self._header(f"sindris HUD (Expanded)"))
        lines.append(self._separator())
        
        # Session信息
        lines.append(f"  Session: {data.session_id}")
        lines.append(f"  Current Round: {data.current_round}")
        lines.append(f"  Timestamp: {datetime.now().isoformat()}")
        lines.append(self._separator())
        
        # 统计
        lines.append("  Statistics:")
        lines.append(f"    Total Tasks: {data.stats.get('total_tasks', 0)}")
        lines.append(f"    Completed: {data.stats.get('successful_tasks', 0)}")
        lines.append(f"    Failed: {data.stats.get('failed_tasks', 0)}")
        lines.append(f"    Blocked: {data.blocked_count}")
        lines.append(f"    Circuit Breaks: {data.circuit_breaks}")
        lines.append(f"    Success Rate: {data.success_rate:.1%}")
        lines.append(f"    Total Duration: {data.total_duration_ms}ms")
        lines.append(self._separator())
        
        # 任务详情
        lines.append("  Task Details:")
        for i, task in enumerate(data.tasks, 1):
            lines.append(f"    {i}. [{task.task_id}]")
            lines.append(f"       Title: {task.title}")
            lines.append(f"       Role: {task.role}")
            lines.append(f"       Status: {task.status} {self._get_status_icon(task.status)}")
            lines.append(f"       Progress: {task.progress}% {self._make_progress_bar(task.progress)}")
            if task.duration_ms:
                lines.append(f"       Duration: {task.duration_ms}ms")
            if task.error:
                lines.append(f"       Error: {task.error}")
            lines.append("")
        
        lines.append(self._separator())
        
        return "\n".join(lines)

    def _header(self, title: str) -> str:
        """渲染标题"""
        padding = (self.width - len(title) - 2) // 2
        return f"╔{'═' * padding} {title} {'═' * padding}╗"

    def _separator(self) -> str:
        """渲染分隔线"""
        return f"╠{'─' * (self.width - 2)}╣"

    def _get_status_icon(self, status: str) -> str:
        """获取状态图标"""
        icons = {
            "pending": "⏳",
            "queued": "📋",
            "in_progress": "🔄",
            "review": "👀",
            "completed": "✅",
            "failed": "❌",
            "blocked": "🚫",
        }
        return icons.get(status, "❓")

    def _make_progress_bar(self, progress: int, width: int = 10) -> str:
        """生成进度条"""
        filled = int(width * progress / 100)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"


# ============================================================
# HUD 主类
# ============================================================

class SindrisHUD:
    """
    sindris HUD控制器
    
    使用方法:
        hud = SindrisHUD()
        hud.update(data)
        hud.refresh()
    """

    def __init__(
        self,
        style: HUDStyle = HUDStyle.COMPACT,
        output: Optional[Callable[[str], None]] = None,
    ):
        """
        初始化HUD
        
        Args:
            style: 显示样式
            output: 输出函数，默认print
        """
        self.style = style
        self.output = output or print
        self.renderer = HUDRenderer(style)
        self.last_render: Optional[str] = None
        self.enabled = True

    def update(self, data: HUDData):
        """
        更新HUD数据
        
        Args:
            data: HUD数据
        """
        if not self.enabled:
            return
        
        # 渲染新内容
        new_render = self.renderer.render(data)
        
        # 如果内容没变，不刷新
        if new_render == self.last_render:
            return
        
        # 清除旧内容并输出新内容
        self._clear_and_write(new_render)
        self.last_render = new_render

    def clear(self):
        """清除HUD"""
        if self.last_render:
            lines = len(self.last_render.split('\n'))
            # 发送清屏和光标上移
            self.output("\033[2J\033[H")  # 终端清屏
            self.last_render = None

    def disable(self):
        """禁用HUD"""
        self.enabled = False
        self.last_render = None

    def enable(self):
        """启用HUD"""
        self.enabled = True

    def _clear_and_write(self, content: str):
        """清除并写入新内容"""
        if self.last_render is None:
            # 首次输出，不需要清除
            self.output(content)
        else:
            # 清除旧内容
            lines = len(self.last_render.split('\n'))
            # 光标上移并清除
            for _ in range(lines):
                self.output("\033[2K\033[A")  # 清除行并上移
            self.output("\033[2K")  # 清除最后一行
            self.output(content)

    @staticmethod
    def create_from_executor(executor) -> 'SindrisHUD':
        """
        从executor创建HUD
        
        Args:
            executor: SindrisExecutor实例
            
        Returns:
            SindrisHUD实例
        """
        from telemetry_collector import TelemetryCollector
        from task_queue import TaskQueue
        
        # 收集数据
        telemetry = executor.telemetry if hasattr(executor, 'telemetry') else None
        queue = executor.task_queue if hasattr(executor, 'task_queue') else None
        
        # 构建HUD数据
        tasks = []
        if hasattr(executor, 'tasks'):
            for task in executor.tasks:
                tasks.append(TaskDisplay(
                    task_id=task.id,
                    title=task.title,
                    role=task.metadata.get('role', {}).get('name', 'unknown'),
                    status='pending',  # 需要从实际状态获取
                    progress=0,
                ))
        
        # 获取统计
        stats = {}
        if telemetry:
            stats = telemetry.get_stats()
        
        queue_size = 0
        blocked_count = 0
        if queue:
            queue_size = queue.get_queue_size()
            blocked_count = len(queue.get_blocked_tasks())
        
        success_rate = 0.0
        if stats.get('total_tasks', 0) > 0:
            success_rate = stats.get('successful_tasks', 0) / stats.get('total_tasks', 1)
        
        data = HUDData(
            session_id=executor.session_id,
            current_round=executor.current_round.phase.value if executor.current_round else "unknown",
            tasks=tasks,
            queue_size=queue_size,
            blocked_count=blocked_count,
            circuit_breaks=stats.get('circuit_breaks', 0),
            success_rate=success_rate,
            total_duration_ms=stats.get('total_duration_ms', 0),
            stats=stats,
        )
        
        return SindrisHUD(data=data)


# ============================================================
# CLI工具
# ============================================================

def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='sindris HUD')
    parser.add_argument('--style', choices=['minimal', 'compact', 'expanded'], default='compact')
    parser.add_argument('--watch', action='store_true', help='实时监控')
    args = parser.parse_args()
    
    style = HUDStyle[args.style.upper()]
    hud = SindrisHUD(style=style)
    
    # 模拟数据
    data = HUDData(
        session_id="sess_abc123",
        current_round="Round2",
        tasks=[
            TaskDisplay("task_001", "开发用户认证", "developer", "in_progress", 60),
            TaskDisplay("task_002", "编写测试用例", "tester", "pending", 0),
            TaskDisplay("task_003", "部署到服务器", "devops", "completed", 100),
        ],
        queue_size=2,
        blocked_count=1,
        circuit_breaks=0,
        success_rate=0.75,
        total_duration_ms=5000,
        stats={"total_tasks": 4, "successful_tasks": 3, "failed_tasks": 1},
    )
    
    print("sindris HUD Demo")
    print("=" * 80)
    print(hud.renderer.render(data))


if __name__ == "__main__":
    main()
