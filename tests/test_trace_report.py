#!/usr/bin/env python3
"""Trace report script tests."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from trace_report import build_trace_report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_actions(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)


def test_build_trace_report_complete_chain(tmp_path):
    trace_id = "trace_ok"
    jsonl = tmp_path / ".logs" / "sindris_20260501.jsonl"
    _write_jsonl(
        jsonl,
        [
            {"event_type": "execution_trace_created", "trace_id": trace_id},
            {"event_type": "spawn_registered", "trace_id": trace_id, "run_id": "run1", "child_session_key": "child1"},
            {"event_type": "yield_boundary", "trace_id": trace_id, "phase": "before_yield"},
            {"event_type": "yield_boundary", "trace_id": trace_id, "phase": "after_yield"},
            {"event_type": "subtask_complete", "trace_id": trace_id, "task_id": "a1"},
        ],
    )
    _write_actions(
        tmp_path / ".omx" / "state" / "sindris_actions.json",
        [{"action_id": "a1", "trace_id": trace_id, "status": "completed"}],
    )

    report = build_trace_report(trace_id, tmp_path)
    assert report["summary"]["complete"] is True
    assert report["counts"]["spawns"] == 1
    assert report["counts"]["omx_actions_terminal"] == 1


def test_build_trace_report_incomplete_chain(tmp_path):
    trace_id = "trace_bad"
    jsonl = tmp_path / ".logs" / "sindris_20260501.jsonl"
    _write_jsonl(
        jsonl,
        [
            {"event_type": "spawn_registered", "trace_id": trace_id, "run_id": "", "child_session_key": ""},
            {"event_type": "yield_boundary", "trace_id": trace_id, "phase": "before_yield"},
        ],
    )

    report = build_trace_report(trace_id, tmp_path)
    assert report["summary"]["complete"] is False
    assert report["checks"]["spawn_fields_complete"] is False
    assert report["checks"]["yield_after_recorded"] is False
