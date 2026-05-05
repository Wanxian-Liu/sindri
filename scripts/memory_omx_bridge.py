"""
memory_omx_bridge.py — 任务记忆（MemoryManager）与 OMX `.omx/memory/{namespace}.json` 的桥接。

见仓库内 docs/MEMORY_OMX_CONTRACT.md 字段约定。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from memory_manager import MemoryManager

from omx_contract import ensure_omx_layout, memory_file, write_json


SCHEMA_VERSION = 1


def _load_memories_from_index(index_path: Path, max_lines: int = 50_000) -> List[Dict[str, Any]]:
    """从 index.jsonl 读取最多 max_lines 条 TaskMemory 字典（顺序保持文件顺序）。"""
    if not index_path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    with open(index_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def build_omx_memory_document(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成写入 `.omx/memory/{namespace}.json` 的文档体。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "sindris.memory_manager",
        "updated_at": datetime.now().isoformat(),
        "entries": entries,
    }


def sync_memory_index_to_omx(
    memory_manager: "MemoryManager",
    omx_root: str,
    namespace: str = "sindris_tasks",
    max_index_lines: int = 50_000,
) -> str:
    """
    将 MemoryManager 的 index.jsonl 导出为 OMX 记忆文件。

    Returns:
        写入的绝对路径（字符串）
    """
    ensure_omx_layout(omx_root)
    index_path = Path(memory_manager.index_file)
    entries = _load_memories_from_index(index_path, max_lines=max_index_lines)
    payload = build_omx_memory_document(entries)
    out_path = memory_file(omx_root, namespace)
    write_json(out_path, payload)
    return out_path


def read_omx_memory_namespace(omx_root: str, namespace: str = "sindris_tasks") -> Dict[str, Any] | None:
    """只读加载 OMX 记忆 JSON（不存在或损坏则返回 None）。"""
    from omx_contract import read_json

    path = memory_file(omx_root, namespace)
    data = read_json(path, default=None)
    return data if isinstance(data, dict) else None
