"""
omx_contract.py - OMX状态层路径定义

基于 oh-my-codex contract.ts 移植
负责: .omx/ 目录结构、路径定义、布局初始化
"""

import os
import json
import fcntl
import time
from pathlib import Path
from typing import Any, Optional
from typing import Optional, List

# OMX布局目录（与OMX一致）
OMX_LAYOUT_DIRS = [
    "state",
    "sessions", 
    "plans",
    "research",
    "team",
    "logs",
    "memory",
]

def omx_dir(root: str) -> str:
    """返回 .omx/ 目录路径"""
    return os.path.join(root, ".omx")

def omx_path(root: str, *segments: str) -> str:
    """返回 .omx/ 下的子路径"""
    return os.path.join(omx_dir(root), *segments)

def state_file(root: str, mode: str) -> str:
    """状态文件路径: .omx/state/{mode}-state.json"""
    return omx_path(root, "state", f"{mode}-state.json")

def tasks_file(root: str) -> str:
    """任务图文件: .omx/state/tasks.json"""
    return omx_path(root, "state", "tasks.json")

def notes_file(root: str) -> str:
    """笔记文件: .omx/state/notepad.json"""
    return omx_path(root, "state", "notepad.json")

def session_file(root: str) -> str:
    """会话文件: .omx/sessions/current.json"""
    return omx_path(root, "sessions", "current.json")

def memory_file(root: str, namespace: str = "project") -> str:
    """记忆文件: .omx/memory/{namespace}.json"""
    return omx_path(root, "memory", f"{namespace}.json")

def team_file(root: str) -> str:
    """团队文件: .omx/team/team.json"""
    return omx_path(root, "team", "team.json")

def team_log_dir(root: str) -> str:
    """团队日志目录: .omx/team/logs/"""
    return omx_path(root, "team", "logs")

def team_log_file(root: str, worker_id: str) -> str:
    """团队日志文件: .omx/team/logs/{worker_id}.log"""
    return omx_path(root, "team", "logs", f"{worker_id}.log")

def reviews_file(root: str) -> str:
    """审查队列: .omx/state/reviews.json"""
    return omx_path(root, "state", "reviews.json")

def inbox_file(root: str) -> str:
    """消息箱: .omx/state/inbox.json"""
    return omx_path(root, "state", "inbox.json")

def ledger_file(root: str) -> str:
    """执行日志: .omx/logs/ledger.json"""
    return omx_path(root, "logs", "ledger.json")

def hooks_state_file(root: str) -> str:
    """Hook状态: .omx/state/hooks.json"""
    return omx_path(root, "state", "hooks.json")

def plugins_state_file(root: str) -> str:
    """插件状态: .omx/state/plugins.json"""
    return omx_path(root, "state", "plugins.json")

def autoresearch_log_file(root: str) -> str:
    """研究日志: .omx/logs/autoresearch.log"""
    return omx_path(root, "logs", "autoresearch.log")

def hook_events_log_file(root: str) -> str:
    """Hook事件日志: .omx/logs/hooks.log"""
    return omx_path(root, "logs", "hooks.log")

def hud_config_file(root: str) -> str:
    """HUD配置: .omx/hud-config.json"""
    return omx_path(root, "hud-config.json")

def ensure_dir(path: str) -> None:
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)

def ensure_omx_layout(root: str) -> str:
    """
    初始化 .omx/ 目录结构
    
    创建所有必需的目录和默认配置文件
    
    Returns:
        .omx/ 目录路径
    """
    base = omx_dir(root)
    ensure_dir(base)
    
    # 创建所有子目录
    for entry in OMX_LAYOUT_DIRS:
        ensure_dir(omx_path(root, entry))
    
    # 创建team/logs目录
    ensure_dir(team_log_dir(root))
    
    # 创建默认HUD配置（如果不存在）
    hud_path = hud_config_file(root)
    if not os.path.exists(hud_path):
        with open(hud_path, 'w', encoding='utf-8') as f:
            json.dump({
                "preset": "focused",
                "refreshMs": 1000,
                "showInbox": True,
                "showReviews": True,
            }, f, indent=2)
    
    return base

def read_json(path: str, default=None, retries: int = 3) -> Any:
    """读取JSON文件（带文件锁和重试），失败时返回默认值"""
    for attempt in range(retries):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (FileNotFoundError, json.JSONDecodeError):
            if attempt < retries - 1:
                time.sleep(0.01 * (attempt + 1))
            else:
                return default
    return default

def write_json(path: str, data, retries: int = 3) -> None:
    """写入JSON文件（带文件锁和重试）"""
    ensure_dir(os.path.dirname(path))
    for attempt in range(retries):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return
        except (IOError, OSError):
            if attempt < retries - 1:
                time.sleep(0.01 * (attempt + 1))
            else:
                raise
    raise IOError(f"Failed to write {path} after {retries} attempts")

def list_omx_dirs(root: str) -> List[str]:
    """列出所有OMX目录"""
    return OMX_LAYOUT_DIRS

# ============================================================
# 工作区根目录（动态获取或设置）
# ============================================================

_workspace_root: Optional[str] = None

def get_workspace_root() -> str:
    """获取当前工作区根目录"""
    global _workspace_root
    if _workspace_root is None:
        # 默认为~/.openclaw/workspace
        _workspace_root = os.path.expanduser("~/.openclaw/workspace")
    return _workspace_root

def set_workspace_root(root: str) -> None:
    """设置工作区根目录"""
    global _workspace_root
    _workspace_root = root

def get_default_omx_paths():
    """获取当前工作区的默认OMX路径集合"""
    root = get_workspace_root()
    return {
        "root": root,
        "omx_dir": omx_dir(root),
        "tasks": tasks_file(root),
        "reviews": reviews_file(root),
        "inbox": inbox_file(root),
        "ledger": ledger_file(root),
        "team": team_file(root),
        "hud_config": hud_config_file(root),
    }
