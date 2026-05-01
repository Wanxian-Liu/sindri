#!/usr/bin/env python3
"""
trace_report.py - Trace continuity report for Sindris execution flows.

Usage:
  python scripts/trace_report.py trace_xxx
  python scripts/trace_report.py trace_xxx --workspace-root /path/to/sindris
  python scripts/trace_report.py trace_xxx --jsonl /tmp/sindris_20260501.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _default_workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _collect_jsonl_files(workspace_root: Path, explicit_jsonl: str | None) -> List[Path]:
    if explicit_jsonl:
        p = Path(explicit_jsonl)
        return [p] if p.exists() else []
    logs_dir = workspace_root / ".logs"
    if not logs_dir.exists():
        return []
    return sorted(logs_dir.glob("sindris_*.jsonl"))


def _load_trace_events(trace_id: str, jsonl_files: List[Path]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for file in jsonl_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("trace_id") == trace_id:
                        events.append(obj)
        except OSError:
            continue
    return events


def _load_trace_actions(trace_id: str, workspace_root: Path) -> List[Dict[str, Any]]:
    actions_file = workspace_root / ".omx" / "state" / "sindris_actions.json"
    if not actions_file.exists():
        return []
    try:
        with open(actions_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [a for a in data if isinstance(a, dict) and a.get("trace_id") == trace_id]


def build_trace_report(trace_id: str, workspace_root: Path, explicit_jsonl: str | None = None) -> Dict[str, Any]:
    jsonl_files = _collect_jsonl_files(workspace_root, explicit_jsonl)
    events = _load_trace_events(trace_id, jsonl_files)
    actions = _load_trace_actions(trace_id, workspace_root)

    event_types = [e.get("event_type") for e in events]
    spawn_events = [e for e in events if e.get("event_type") == "spawn_registered"]
    yield_events = [e for e in events if e.get("event_type") == "yield_boundary"]
    complete_events = [e for e in events if e.get("event_type") in ("subtask_complete", "subtask_fail")]

    has_trace_created = "execution_trace_created" in event_types
    has_before_yield = any(e.get("phase") == "before_yield" for e in yield_events)
    has_after_yield = any(e.get("phase") == "after_yield" for e in yield_events)
    spawn_fields_ok = all(e.get("run_id") and e.get("child_session_key") for e in spawn_events)
    action_terminal_count = sum(1 for a in actions if a.get("status") in ("completed", "failed"))

    checks = {
        "trace_created": has_trace_created,
        "spawn_recorded": len(spawn_events) > 0,
        "spawn_fields_complete": spawn_fields_ok,
        "yield_before_recorded": has_before_yield,
        "yield_after_recorded": has_after_yield,
        "subtask_terminal_recorded": len(complete_events) > 0,
        "omx_actions_present": len(actions) > 0,
    }
    score = sum(1 for ok in checks.values() if ok)
    total = len(checks)
    complete = score == total

    return {
        "trace_id": trace_id,
        "workspace_root": str(workspace_root),
        "jsonl_files": [str(p) for p in jsonl_files],
        "counts": {
            "events": len(events),
            "spawns": len(spawn_events),
            "yields": len(yield_events),
            "subtask_terminal_events": len(complete_events),
            "omx_actions": len(actions),
            "omx_actions_terminal": action_terminal_count,
        },
        "checks": checks,
        "summary": {
            "score": f"{score}/{total}",
            "complete": complete,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Sindris trace continuity across JSONL and OMX.")
    parser.add_argument("trace_id", help="Trace id like trace_xxxxx")
    parser.add_argument(
        "--workspace-root",
        default=str(_default_workspace_root()),
        help="Sindris workspace root (default: repo root inferred from script path)",
    )
    parser.add_argument(
        "--jsonl",
        default=None,
        help="Optional explicit JSONL file path. If omitted, scan .logs/sindris_*.jsonl",
    )
    args = parser.parse_args()

    report = build_trace_report(
        trace_id=args.trace_id,
        workspace_root=Path(args.workspace_root),
        explicit_jsonl=args.jsonl,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
