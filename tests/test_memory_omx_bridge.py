#!/usr/bin/env python3
"""Tests for memory_omx_bridge (B1 OMX snapshot + read back)."""

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def test_sync_memory_index_to_omx_roundtrip(tmp_path):
    from memory_manager import MemoryManager
    from memory_omx_bridge import read_omx_memory_namespace, sync_memory_index_to_omx

    mem_root = tmp_path / "sindris_mem"
    mgr = MemoryManager(str(mem_root))
    mgr.save_task_memory(
        task_id="t_bridge_1",
        task_title="OMX bridge smoke test",
        success=True,
        role="tester",
    )

    ws = tmp_path / "workspace_root"
    out = sync_memory_index_to_omx(mgr, str(ws), namespace="sindris_tasks")
    assert Path(out).is_file()

    data = read_omx_memory_namespace(str(ws), "sindris_tasks")
    assert data is not None
    assert data.get("schema_version") == 1
    assert data.get("source") == "sindris.memory_manager"
    assert isinstance(data.get("entries"), list)
    assert len(data["entries"]) >= 1
    assert any(e.get("task_id") == "t_bridge_1" for e in data["entries"])


def test_search_keyword_matches_content(tmp_path):
    from memory_manager import MemoryManager

    mgr = MemoryManager(str(tmp_path / "mem"))
    mgr.save_task_memory(
        task_id="sk_1",
        task_title="unique-keyword-xyz-123",
        success=True,
    )
    hits = mgr.search_keyword("unique-keyword-xyz", limit=5)
    assert len(hits) >= 1
    assert any("unique-keyword-xyz" in h.content for h in hits)
