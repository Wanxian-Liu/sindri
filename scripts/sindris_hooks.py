"""
sindris_hooks.py - sindris Hook 系统

参考 oh-my-codex Hook 设计，为 sindris 提供事件驱动的 Hook 能力。

Hook 事件：
- SessionStart     → 会话启动
- RoundStart       → Round开始
- PreToolUse       → 工具执行前（安全检查）
- PostToolUse      → 工具执行后（结果审查）
- WorkerSpawn      → Worker启动
- WorkerComplete   → Worker完成
- RoundComplete    → Round完成
- ReviewSubmit     → 审查提交
- Stop             → 会话停止

使用示例：
    from sindris_hooks import SindrisHookManager, SindrisHookEvent, HookContext
    
    hooks = SindrisHookManager()
    hooks.register(SindrisHookEvent.PRE_TOOL_USE, my_safety_check)
    await hooks.trigger(HookContext(event=SindrisHookEvent.PRE_TOOL_USE, ...))
"""

import asyncio
import os
import sys
import json
import time
import re
from enum import Enum
from typing import Callable, Dict, List, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from functools import wraps
from collections.abc import Coroutine

# ============================================================
# Hook 事件定义
# ============================================================

class SindrisHookEvent(Enum):
    """sindris Hook 事件类型"""
    # 会话事件
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    
    # Round 事件
    ROUND_START = "RoundStart"
    ROUND_COMPLETE = "RoundComplete"
    
    # 工具事件
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    
    # Worker 事件
    WORKER_SPAWN = "WorkerSpawn"
    WORKER_COMPLETE = "WorkerComplete"
    WORKER_FAIL = "WorkerFail"
    WORKER_TIMEOUT = "WorkerTimeout"
    
    # 任务事件
    TASK_QUEUED = "TaskQueued"
    TASK_START = "TaskStart"
    TASK_COMPLETE = "TaskComplete"
    TASK_FAIL = "TaskFail"
    
    # 审查事件
    REVIEW_SUBMIT = "ReviewSubmit"
    REVIEW_APPROVE = "ReviewApprove"
    REVIEW_REJECT = "ReviewReject"
    
    # 安全事件
    SAFETY_BLOCK = "SafetyBlock"
    CIRCUIT_OPEN = "CircuitOpen"
    
    # 停止事件
    STOP = "Stop"


# ============================================================
# Hook 上下文
# ============================================================

@dataclass
class HookContext:
    """Hook 执行上下文"""
    event: SindrisHookEvent
    session_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Round 信息
    round: int = 0
    round_phase: str = ""
    
    # Worker 信息
    worker_id: str = ""
    worker_role: str = ""
    
    # 工具信息
    tool_name: str = ""
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Any = None
    tool_duration_ms: int = 0
    
    # 任务信息
    task_id: str = ""
    task_title: str = ""
    
    # 审查信息
    review_id: str = ""
    review_note: str = ""
    
    # 安全信息
    block_reason: str = ""
    danger_level: str = "none"  # none/low/medium/high/critical
    
    # 熔断信息
    circuit_breaker_name: str = ""
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# Hook 处理器
# ============================================================

HookHandler = Callable[[HookContext], Any]


def is_async_handler(handler: HookHandler) -> bool:
    """检查是否为异步处理器"""
    return asyncio.iscoroutinefunction(handler)


# ============================================================
# 内置安全 Hook
# ============================================================

class SafetyHook:
    """工具执行前安全检查 Hook"""
    
    # 高危工具列表
    DANGEROUS_TOOLS: Set[str] = {
        "exec", "write", "edit", "delete", "move", "rename"
    }
    
    # 高危命令模式
    DANGEROUS_PATTERNS: List[tuple] = [
        # 递归删除根目录或系统目录
        (r"rm\s+-rf\s+/\s*$", "critical", "递归删除根目录"),
        (r"rm\s+-rf\s+/bin", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/etc", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/usr", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/lib", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/sys", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/proc", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/boot", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/var", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/srv", "critical", "递归删除系统目录"),
        (r"rm\s+-rf\s+/root", "critical", "递归删除root目录"),
        (r"rm\s+-rf\s+/\s", "high", "递归删除根目录(可能)"),
        
        # Fork bomb
        (r":\(:\{.*:\|:&.*\}", "critical", "Fork bomb 攻击"),
        (r";\s*:\(\)\{.*\}\s*;\s*:", "critical", "Fork bomb 攻击"),
        (r"forkbomb", "critical", "Fork bomb 攻击"),
        
        # 磁盘写入
        (r"dd\s+if=.*of=/dev/sd", "critical", "直接写入磁盘"),
        (r"dd\s+if=.*of=/dev/hd", "critical", "直接写入磁盘"),
        (r"dd\s+if=.*of=/dev/null", "high", "dd写入null(可能危险)"),
        
        # 格式化
        (r"mkfs\s+-", "high", "格式化操作"),
        (r"mkfs\.ext", "high", "格式化ext文件系统"),
        
        # 下载并执行
        (r"curl\s+.*\|\s*bash", "high", "下载并执行脚本"),
        (r"wget\s+.*\|\s*bash", "high", "下载并执行脚本"),
        (r"bash\s+<\s*\(curl", "high", "下载并执行脚本"),
        (r"python.*\|\s*bash", "high", "下载并执行脚本"),
        
        # 修改系统权限
        (r"chmod\s+-R\s+777\s+/etc", "medium", "修改系统目录权限"),
        (r"chown\s+-R\s+.*\s+/etc", "medium", "修改系统目录所有者"),
        (r"chmod\s+4777", "medium", "设置SUID权限"),
        (r"chmod\s+4755", "medium", "设置SUID权限"),
        
        # 网络相关
        (r"iptables\s+-F", "medium", "清除iptables规则"),
        (r"ufw\s+disable", "medium", "关闭防火墙"),
        (r"systemctl\s+stop\s+firewalld", "medium", "关闭防火墙"),
    ]
    
    def __init__(self, block_threshold: str = "medium"):
        """
        初始化安全 Hook
        
        Args:
            block_threshold: 拦截级别 (none/low/medium/high/critical)
        """
        self.block_threshold = block_threshold
        self._level_order = ["none", "low", "medium", "high", "critical"]
        self._block_log: List[HookContext] = []
    
    def should_block(self, danger_level: str) -> bool:
        """判断是否应该拦截"""
        if self.block_threshold == "none":
            return False
        return self._level_order.index(danger_level) >= self._level_order.index(self.block_threshold)
    
    def check_tool(self, ctx: HookContext) -> HookContext:
        """
        检查工具是否安全
        
        Args:
            ctx: Hook 上下文
            
        Returns:
            更新后的 ctx，如果被拦截则设置 block_reason
        """
        if ctx.tool_name not in self.DANGEROUS_TOOLS:
            ctx.danger_level = "none"
            return ctx
        
        # 获取要检查的字符串（exec命令的command字段）
        command_str = ""
        tool_input = ctx.tool_input or {}
        
        # 直接从 tool_input 中提取 command 字段
        if "command" in tool_input:
            command_str = str(tool_input["command"])
        elif isinstance(tool_input, str):
            command_str = tool_input
        else:
            # fallback: 序列化但只用于模式匹配（不使用$锚点）
            command_str = json.dumps(tool_input)
        
        # 检查命令模式
        for pattern, level, reason in self.DANGEROUS_PATTERNS:
            # 移除$锚点，因为在JSON中命令不在末尾
            clean_pattern = pattern.rstrip('$').rstrip('\s*')
            if re.search(clean_pattern, command_str, re.IGNORECASE):
                ctx.danger_level = level
                ctx.block_reason = reason
                
                if self.should_block(level):
                    ctx.metadata["blocked"] = True
                    ctx.metadata["original_input"] = ctx.tool_input
                    ctx.tool_input = {"_BLOCKED": True, "reason": reason}
                
                return ctx
        
        ctx.danger_level = "low"
        return ctx
    
    def check_exec_command(self, command: str) -> tuple[bool, str, str]:
        """
        检查 exec 命令是否安全
        
        Args:
            command: 要执行的命令
            
        Returns:
            (should_block, danger_level, reason)
        """
        for pattern, level, reason in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return self.should_block(level), level, reason
        
        return False, "none", ""


# ============================================================
# Telemetry Hook
# ============================================================

class TelemetryHook:
    """遥测数据收集 Hook"""
    
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
    
    async def on_event(self, ctx: HookContext):
        """记录事件到遥测日志"""
        log_file = os.path.join(self.log_dir, f"hooks_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
        
        with open(log_file, "a") as f:
            f.write(json.dumps(ctx.to_dict(), ensure_ascii=False) + "\n")


# ============================================================
# Hook 管理器
# ============================================================

class SindrisHookManager:
    """
    sindris Hook 管理器
    
    管理所有 Hook 的注册和触发。
    
    使用示例：
        manager = SindrisHookManager()
        
        # 注册处理器
        async def my_handler(ctx: HookContext):
            print(f"Event: {ctx.event.value}")
        
        manager.register(SindrisHookEvent.SESSION_START, my_handler)
        
        # 触发 Hook
        ctx = HookContext(event=SindrisHookEvent.SESSION_START, session_id="test")
        await manager.trigger(ctx)
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.path.expanduser("~/.openclaw/skills/sindris")
        self.log_dir = os.path.join(self.workspace_root, ".omx", "logs", "hooks")
        
        # 初始化内置 Hook
        self.safety = SafetyHook()
        self.telemetry = TelemetryHook(self.log_dir)
        
        # 处理器注册表
        self._handlers: Dict[SindrisHookEvent, List[tuple[HookHandler, bool]]] = {
            event: [] for event in SindrisHookEvent
        }
        
        # 全局启用/禁用
        self._enabled = True
        
        # 统计
        self._stats = {event.value: {"count": 0, "errors": 0} for event in SindrisHookEvent}
    
    def register(
        self, 
        event: SindrisHookEvent, 
        handler: HookHandler,
        async_handler: bool = False
    ) -> None:
        """
        注册 Hook 处理器
        
        Args:
            event: Hook 事件类型
            handler: 处理器函数
            async_handler: 是否为异步处理器
        """
        # 自动检测
        if asyncio.iscoroutinefunction(handler):
            async_handler = True
        
        self._handlers[event].append((handler, async_handler))
    
    def unregister(self, event: SindrisHookEvent, handler: HookHandler) -> bool:
        """
        注销 Hook 处理器
        
        Returns:
            是否成功注销
        """
        for i, (h, _) in enumerate(self._handlers[event]):
            if h == handler:
                self._handlers[event].pop(i)
                return True
        return False
    
    def clear(self, event: Optional[SindrisHookEvent] = None) -> None:
        """清除 Hook 处理器"""
        if event:
            self._handlers[event] = []
        else:
            for e in SindrisHookEvent:
                self._handlers[e] = []
    
    async def trigger(self, ctx: HookContext) -> HookContext:
        """
        触发 Hook
        
        Args:
            ctx: Hook 上下文
            
        Returns:
            更新后的 ctx
        """
        if not self._enabled:
            return ctx
        
        self._stats[ctx.event.value]["count"] += 1
        
        # 触发安全检查（内置 Hook）
        if ctx.event == SindrisHookEvent.PRE_TOOL_USE:
            ctx = self.safety.check_tool(ctx)
            
            # 如果被拦截，触发 SAFETY_BLOCK 事件
            if ctx.metadata.get("blocked"):
                ctx.event = SindrisHookEvent.SAFETY_BLOCK
                await self._execute_handlers(ctx)
                ctx.event = SindrisHookEvent.PRE_TOOL_USE
                return ctx
        
        return await self._execute_handlers(ctx)
    
    async def _execute_handlers(self, ctx: HookContext) -> HookContext:
        """执行所有处理器"""
        for handler, is_async in self._handlers[ctx.event]:
            try:
                if is_async:
                    await handler(ctx)
                else:
                    # 同步处理器在异步环境中运行
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: handler(ctx))
            except Exception as e:
                self._stats[ctx.event.value]["errors"] += 1
                ctx.metadata["error"] = str(e)
        
        # 触发遥测（内置 Hook）
        try:
            await self.telemetry.on_event(ctx)
        except Exception:
            pass
        
        return ctx
    
    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """获取 Hook 统计信息"""
        return self._stats
    
    def enable(self) -> None:
        """启用 Hook"""
        self._enabled = True
    
    def disable(self) -> None:
        """禁用 Hook"""
        self._enabled = False


# ============================================================
# Hook 预设
# ============================================================

SINDRIS_HOOK_PRESETS = {
    "safety": {
        "events": [SindrisHookEvent.PRE_TOOL_USE],
        "description": "工具执行前安全检查",
    },
    "telemetry": {
        "events": [
            SindrisHookEvent.SESSION_START,
            SindrisHookEvent.ROUND_START,
            SindrisHookEvent.ROUND_COMPLETE,
            SindrisHookEvent.WORKER_COMPLETE,
            SindrisHookEvent.TASK_COMPLETE,
        ],
        "description": "运行时遥测数据收集",
    },
    "review": {
        "events": [
            SindrisHookEvent.REVIEW_SUBMIT,
            SindrisHookEvent.REVIEW_APPROVE,
            SindrisHookEvent.REVIEW_REJECT,
        ],
        "description": "审查流程记录",
    },
    "all": {
        "events": list(SindrisHookEvent),
        "description": "所有事件",
    },
}


# ============================================================
# 便捷函数
# ============================================================

_default_manager: Optional[SindrisHookManager] = None


def get_default_manager() -> SindrisHookManager:
    """获取默认的 Hook 管理器（单例）"""
    global _default_manager
    if _default_manager is None:
        _default_manager = SindrisHookManager()
    return _default_manager


async def trigger_hook(event: SindrisHookEvent, **kwargs) -> HookContext:
    """
    触发 Hook 的便捷函数
    
    使用示例：
        ctx = await trigger_hook(SindrisHookEvent.SESSION_START, session_id="abc")
    """
    manager = get_default_manager()
    ctx = HookContext(event=event, session_id=kwargs.get("session_id", "default"), **kwargs)
    return await manager.trigger(ctx)


# ============================================================
# CLI 工具
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="sindris Hook 管理工具")
    subparsers = parser.add_subparsers(dest="command")
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有 Hook 事件")
    
    # enable 命令
    enable_parser = subparsers.add_parser("enable", help="启用 Hook")
    enable_parser.add_argument("event", nargs="?", help="事件类型")
    
    # disable 命令
    disable_parser = subparsers.add_parser("disable", help="禁用 Hook")
    disable_parser.add_argument("event", nargs="?", help="事件类型")
    
    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="查看 Hook 统计")
    
    args = parser.parse_args()
    
    manager = get_default_manager()
    
    if args.command == "list":
        print("=== sindris Hook 事件 ===")
        for event in SindrisHookEvent:
            count = manager._stats[event.value]["count"]
            errors = manager._stats[event.value]["errors"]
            print(f"{event.value}: {count} 次触发, {errors} 次错误")
    
    elif args.command == "enable":
        manager.enable()
        print("Hook 已启用")
    
    elif args.command == "disable":
        manager.disable()
        print("Hook 已禁用")
    
    elif args.command == "stats":
        print("=== Hook 统计 ===")
        for event, stats in manager.get_stats().items():
            if stats["count"] > 0:
                print(f"{event}: {stats['count']} 触发, {stats['errors']} 错误")
    
    else:
        parser.print_help()
