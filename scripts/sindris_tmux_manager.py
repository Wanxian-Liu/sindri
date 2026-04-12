#!/usr/bin/env python3
"""
sindris_tmux_manager.py - tmux Worker Runtime for Sindris

Design philosophy (自研, inspired by oh-my-codex team.ts + claw-code worker_boot.rs):
- TmuxManager: low-level tmux session/window lifecycle
- SindrisWorkerManager: worker state machine + command dispatch
- Event sourcing for observability (append-only event log)
- Graceful degradation: mock runtime when tmux unavailable

Worker lifecycle:
  SPAWNING -> TRUST_REQUIRED -> READY -> RUNNING -> COMPLETED/FAILED
                         ^                      |
                         +-------- restart -----+

Inspired by:
  - oh-my-codex: team.ts - session/window per worker, task claiming, lease heartbeat
  - claw-code: worker_boot.rs - trust gate detection, prompt delivery, ready signal
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Worker Status
# ---------------------------------------------------------------------------

class WorkerStatus(Enum):
    """Worker lifecycle states, inspired by claw-code worker_boot.rs"""
    SPAWNING      = auto()   # process started, not yet ready
    TRUST_REQUIRED = auto()   # waiting for trust gate approval
    READY         = auto()   # ready for prompt delivery
    RUNNING       = auto()   # prompt delivered, agent working
    COMPLETED     = auto()   # task finished successfully
    FAILED        = auto()   # task failed or terminal error


# ---------------------------------------------------------------------------
# Event sourcing
# ---------------------------------------------------------------------------

class WorkerEventKind(Enum):
    SPAWNED          = auto()
    TRUST_REQUIRED   = auto()
    TRUST_RESOLVED   = auto()
    READY            = auto()
    PROMPT_SENT      = auto()
    PROMPT_MISDELIVERED = auto()
    RUNNING          = auto()
    HEARTBEAT        = auto()
    COMPLETED        = auto()
    FAILED           = auto()
    RESTARTED        = auto()
    TERMINATED       = auto()


@dataclass
class WorkerEvent:
    seq: int
    kind: WorkerEventKind
    status: WorkerStatus
    detail: str
    timestamp: str  # ISO8601

    def to_line(self) -> str:
        return f"[{self.timestamp}] [{self.kind.name}] {self.detail}"


# ---------------------------------------------------------------------------
# Worker model
# ---------------------------------------------------------------------------

@dataclass
class Worker:
    id: str
    role: str
    agent_id: str
    status: WorkerStatus
    command: Optional[str]
    log_file: str
    window_name: Optional[str] = None
    session_name: Optional[str] = None
    lease_expires_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    assigned_task_ids: list[str] = field(default_factory=list)
    events: list[WorkerEvent] = field(default_factory=list)
    last_error: Optional[str] = None

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def push_event(self, kind: WorkerEventKind, detail: str, new_status: Optional[WorkerStatus] = None):
        self.events.append(WorkerEvent(
            seq=len(self.events) + 1,
            kind=kind,
            status=new_status or self.status,
            detail=detail,
            timestamp=self.now_iso(),
        ))

    def is_stale(self) -> bool:
        if self.lease_expires_at and self.status == WorkerStatus.RUNNING:
            exp = datetime.fromisoformat(self.lease_expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        return False

    def mark_heartbeat(self):
        self.last_heartbeat_at = self.now_iso()
        if self.status == WorkerStatus.FAILED:
            self.status = WorkerStatus.READY

    def append_log(self, line: str):
        ts = self.now_iso()
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")

    def summary(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "status": self.status.name,
            "window": self.window_name,
            "last_heartbeat": self.last_heartbeat_at,
            "stale": self.is_stale(),
            "events_count": len(self.events),
        }


# ---------------------------------------------------------------------------
# Low-level tmux operations (TmuxManager)
# ---------------------------------------------------------------------------

class TmuxManager:
    """
    Low-level tmux session/window manager.
    Provides: availability check, session create/ensure, window create,
    send-keys, pane capture.
    """

    def __init__(self, session_name: str, log_dir: str = "/tmp/sindris-workers"):
        self.session_name = session_name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._available: Optional[bool] = None

    # -- tmux availability ----------------------------------------------------

    def is_available(self) -> bool:
        if self._available is None:
            try:
                subprocess.run(
                    ["tmux", "list-sessions"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
                self._available = True
            except Exception:
                self._available = False
        return self._available

    # -- session management ---------------------------------------------------

    def ensure_session(self) -> bool:
        """Create session if it doesn't exist. Returns True if session ready."""
        if not self.is_available():
            return False
        try:
            r = subprocess.run(
                ["tmux", "has-session", "-t", self.session_name],
                capture_output=True, timeout=5, check=False,
            )
            if r.returncode == 0:
                return True
            # create detached session with a placeholder window
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", self.session_name, "-n", "manager"],
                capture_output=True, timeout=10, check=False,
            )
            return True
        except Exception:
            return False

    def kill_session(self) -> bool:
        """Kill the entire tmux session."""
        if not self.is_available():
            return False
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", self.session_name],
                capture_output=True, timeout=5, check=False,
            )
            return True
        except Exception:
            return False

    # -- window management ---------------------------------------------------

    def create_window(self, window_name: str, command: str) -> bool:
        """Create a named window in the session with the given command."""
        if not self.is_available():
            return False
        try:
            r = subprocess.run(
                ["tmux", "new-window", "-t", self.session_name, "-n", window_name, command],
                capture_output=True, timeout=10, check=False,
            )
            return r.returncode == 0
        except Exception:
            return False

    def kill_window(self, window_name: str) -> bool:
        if not self.is_available():
            return False
        try:
            subprocess.run(
                ["tmux", "kill-window", "-t", f"{self.session_name}:{window_name}"],
                capture_output=True, timeout=5, check=False,
            )
            return True
        except Exception:
            return False

    # -- command dispatch -----------------------------------------------------

    def send_keys(self, window_name: str, text: str, enter: bool = True) -> bool:
        """Send text (and Enter) to a tmux window pane."""
        if not self.is_available():
            return False
        try:
            cmd = ["tmux", "send-keys", "-t", f"{self.session_name}:{window_name}"]
            if enter:
                cmd += ["-l", text, "Enter"]
            else:
                cmd += ["-l", text]
            subprocess.run(cmd, capture_output=True, timeout=5, check=False)
            return True
        except Exception:
            return False

    def capture_pane(self, window_name: str, lines: int = 200) -> str:
        """Capture visible pane output for observation."""
        if not self.is_available():
            return ""
        try:
            r = subprocess.run(
                ["tmux", "capture-pane", "-t", f"{self.session_name}:{window_name}",
                 "-p", "-S", f"-{lines}"],
                capture_output=True, timeout=5, text=True, check=False,
            )
            return r.stdout
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Trust / ready detection (inspired by claw-code worker_boot.rs)
# ---------------------------------------------------------------------------

_TRUST_PATTERNS = [
    re.compile(r"do you trust the files in this folder", re.I),
    re.compile(r"trust the files in this folder", re.I),
    re.compile(r"trust this folder", re.I),
    re.compile(r"allow and continue", re.I),
    re.compile(r"yes, proceed", re.I),
]

_READY_PATTERNS = [
    re.compile(r"ready for (your )?input", re.I),
    re.compile(r"ready for prompt", re.I),
    re.compile(r"send a message", re.I),
]

_SHELL_PROMPT_RE = re.compile(r"^[\$\#\%]|\$ |\# |% |› |\❯ ")


def detect_trust_prompt(screen: str) -> bool:
    for p in _TRUST_PATTERNS:
        if p.search(screen):
            return True
    return False


def detect_ready_for_prompt(screen: str) -> bool:
    for p in _READY_PATTERNS:
        if p.search(screen):
            return True
    lines = screen.strip().splitlines()
    if not lines:
        return False
    last = lines[-1].strip()
    if _SHELL_PROMPT_RE.search(last):
        return False
    # Vi-like indicators
    if any(x in last for x in ["│ >", "│ ›", "│ ❯", "❯", "›", "> "]):
        return True
    return False


def detect_running_cue(screen: str) -> bool:
    cues = ["thinking", "working", "running tests", "inspecting", "analyzing"]
    low = screen.lower()
    return any(c in low for c in cues)


# ---------------------------------------------------------------------------
# SindrisWorkerManager
# ---------------------------------------------------------------------------

class SindrisWorkerManager:
    """
    Worker lifecycle manager with event sourcing and graceful mock fallback.

    Responsibilities:
    - Worker registry (create/spawn/restart/terminate)
    - Command dispatch via tmux send-keys
    - State observation (screen capture → status inference)
    - Lease/heartbeat tracking
    - Trust gate resolution
    - Mock fallback when tmux unavailable
    """

    LEASE_SECONDS = 20 * 60  # 20-minute task lease (from team.ts)

    def __init__(
        self,
        session_name: str,
        workspace_root: str,
        log_dir: str = "/tmp/sindris-workers",
    ):
        self.workspace_root = workspace_root
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._tmux = TmuxManager(session_name, str(self.log_dir))
        self._workers: dict[str, Worker] = {}
        self._lock = threading.RLock()

    # -- backend query -------------------------------------------------------

    @property
    def backend_kind(self) -> str:
        return "tmux" if self._tmux.is_available() else "mock"

    @property
    def backend_available(self) -> bool:
        return self._tmux.is_available()

    # -- worker registry -----------------------------------------------------

    def list_workers(self) -> list[dict]:
        with self._lock:
            return [w.summary() for w in self._workers.values()]

    def get_worker(self, worker_id: str) -> Optional[Worker]:
        with self._lock:
            return self._workers.get(worker_id)

    # -- worker creation -----------------------------------------------------

    def create_worker(
        self,
        role: str,
        agent_id: Optional[str] = None,
    ) -> Worker:
        """Register a worker record without spawning it."""
        wid = f"w_{uuid.uuid4().hex[:10]}"
        log_file = str(self.log_dir / f"{wid}.log")
        Path(log_file).touch()
        w = Worker(
            id=wid,
            role=role,
            agent_id=agent_id or wid,
            status=WorkerStatus.SPAWNING,
            command=None,
            log_file=log_file,
            session_name=self._tmux.session_name if self._tmux.is_available() else None,
        )
        w.append_log(f"worker created, role={role}")
        w.push_event(WorkerEventKind.SPAWNED, f"worker {wid} created for role {role}")
        with self._lock:
            self._workers[wid] = w
        return w

    def spawn_worker(self, worker_id: str, command: Optional[str] = None) -> bool:
        """
        Spawn a real tmux window or mock process for the worker.
        Returns True on success.
        """
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return False

        cmd = command or f"printf 'Sindris worker {worker_id} ready\\n'; while true; do sleep 3600; done"
        w.command = cmd

        if self._tmux.is_available():
            self._tmux.ensure_session()
            w.window_name = worker_id
            ok = self._tmux.create_window(worker_id, cmd)
            if ok:
                w.status = WorkerStatus.SPAWNING
                w.append_log(f"spawn tmux:{self._tmux.session_name}:{worker_id} -> {cmd}")
                w.push_event(WorkerEventKind.SPAWNED,
                             f"tmux window spawned: {cmd[:60]}")
            else:
                w.status = WorkerStatus.FAILED
                w.last_error = "tmux window creation failed"
                w.push_event(WorkerEventKind.FAILED, "tmux window creation failed")
                w.append_log("ERROR: tmux window creation failed")
                return False
        else:
            # mock mode: mark as ready immediately
            w.window_name = None
            w.status = WorkerStatus.READY
            w.append_log(f"mock spawn -> {cmd}")
            w.push_event(WorkerEventKind.SPAWNED, f"mock worker spawned: {cmd[:60]}")
            w.push_event(WorkerEventKind.READY, "mock worker ready")

        return True

    # -- command dispatch ----------------------------------------------------

    def send_command(self, worker_id: str, command: str, wait_ready: bool = False,
                     timeout: float = 30.0) -> tuple[bool, str]:
        """
        Send a command to a worker pane and optionally wait for ready state.
        Returns (success, message).
        """
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return False, f"worker {worker_id} not found"

        if w.status not in (WorkerStatus.SPAWNING, WorkerStatus.READY,
                            WorkerStatus.RUNNING, WorkerStatus.TRUST_REQUIRED):
            return False, f"worker {worker_id} not ready (status={w.status.name})"

        if self._tmux.is_available() and w.window_name:
            self._tmux.send_keys(w.window_name, command, enter=True)
        else:
            w.append_log(f"[mock send] {command}")

        w.status = WorkerStatus.RUNNING
        w.lease_expires_at = datetime.now(timezone.utc).isoformat()
        w.lease_expires_at = (datetime.now(timezone.utc).timestamp()
                             + self.LEASE_SECONDS)
        from datetime import timedelta
        w.lease_expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=self.LEASE_SECONDS)
        ).isoformat()
        w.append_log(f"command sent: {command[:80]}")
        w.push_event(WorkerEventKind.PROMPT_SENT, f"dispatched: {command[:60]}")
        w.push_event(WorkerEventKind.RUNNING, "agent working")

        if wait_ready:
            return self._wait_for_ready(worker_id, timeout)
        return True, "command dispatched"

    def _wait_for_ready(self, worker_id: str, timeout: float) -> tuple[bool, str]:
        """Poll worker until READY or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.5)
            st = self.observe(worker_id)
            if st == WorkerStatus.READY:
                return True, "worker ready"
            if st == WorkerStatus.FAILED:
                return False, "worker failed during command"
        return False, "timeout waiting for ready"

    # -- observation (screen parsing) ----------------------------------------

    def observe(self, worker_id: str) -> WorkerStatus:
        """
        Observe worker pane, update status based on screen content.
        Returns the updated status.
        """
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return WorkerStatus.FAILED

        screen = ""
        if self._tmux.is_available() and w.window_name:
            screen = self._tmux.capture_pane(w.window_name)

        # Mock mode: no screen to parse
        if not screen:
            return w.status

        prev = w.status

        # Trust gate detection
        if w.status != WorkerStatus.TRUST_REQUIRED:
            if detect_trust_prompt(screen):
                w.status = WorkerStatus.TRUST_REQUIRED
                w.last_error = "trust gate: user approval required"
                w.push_event(WorkerEventKind.TRUST_REQUIRED, "trust prompt detected")
                w.append_log("BLOCKED: trust prompt detected")
                return w.status

        # Ready detection
        if w.status in (WorkerStatus.SPAWNING, WorkerStatus.RUNNING):
            if detect_ready_for_prompt(screen):
                w.status = WorkerStatus.READY
                w.lease_expires_at = None
                if w.last_error and "trust" in w.last_error.lower():
                    w.last_error = None
                w.push_event(WorkerEventKind.READY, "ready for next prompt")
                w.append_log("READY: worker ready for prompt")
                return w.status

        # Running cue (prompt delivered, agent working)
        if w.status == WorkerStatus.RUNNING and detect_running_cue(screen):
            w.last_error = None

        return w.status

    def resolve_trust(self, worker_id: str) -> tuple[bool, str]:
        """Manually resolve trust gate and resume worker."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return False, f"worker {worker_id} not found"
            if w.status != WorkerStatus.TRUST_REQUIRED:
                return False, f"worker not waiting on trust (status={w.status.name})"

        w.status = WorkerStatus.SPAWNING
        w.last_error = None
        w.append_log("TRUST: manually resolved")
        w.push_event(WorkerEventKind.TRUST_RESOLVED, "trust gate resolved manually")

        if self._tmux.is_available() and w.window_name:
            self._tmux.send_keys(w.window_name, "y", enter=True)
        return True, "trust resolved"

    # -- heartbeat -----------------------------------------------------------

    def heartbeat(self, worker_id: str, note: str = "") -> bool:
        """Record worker heartbeat, clear stale flag."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return False
        w.mark_heartbeat()
        w.append_log(f"heartbeat{': ' + note if note else ''}")
        w.push_event(WorkerEventKind.HEARTBEAT, f"heartbeat{': ' + note if note else ''}")
        return True

    def reconcile(self) -> list[str]:
        """
        Check all workers for stale leases. Mark stale workers.
        Returns list of stale worker IDs.
        """
        stale = []
        with self._lock:
            for wid, w in self._workers.items():
                if w.is_stale():
                    w.status = WorkerStatus.FAILED
                    w.last_error = "lease expired, worker considered stale"
                    w.push_event(WorkerEventKind.FAILED, "lease expired, marked stale")
                    stale.append(wid)
        return stale

    # -- lifecycle -----------------------------------------------------------

    def complete(self, worker_id: str, result: str = "") -> bool:
        """Mark worker task as completed."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return False
        w.status = WorkerStatus.COMPLETED
        w.lease_expires_at = None
        w.append_log(f"COMPLETED: {result[:200]}")
        w.push_event(WorkerEventKind.COMPLETED, result[:120] or "task completed")
        return True

    def fail(self, worker_id: str, reason: str = "") -> bool:
        """Mark worker as failed."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return False
        w.status = WorkerStatus.FAILED
        w.last_error = reason
        w.append_log(f"FAILED: {reason}")
        w.push_event(WorkerEventKind.FAILED, reason[:120] or "worker failed")
        return True

    def restart_worker(self, worker_id: str) -> bool:
        """Restart a worker (kill window + respawn)."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return False

        if self._tmux.is_available() and w.window_name:
            self._tmux.kill_window(w.window_name)

        w.status = WorkerStatus.SPAWNING
        w.window_name = None
        w.lease_expires_at = None
        w.last_error = None
        w.append_log("RESTART: worker restarting")
        w.push_event(WorkerEventKind.RESTARTED, "worker restarted")
        return self.spawn_worker(worker_id, w.command)

    def terminate(self, worker_id: str) -> bool:
        """Permanently terminate a worker."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return False

        if self._tmux.is_available() and w.window_name:
            self._tmux.kill_window(w.window_name)

        w.status = WorkerStatus.FAILED
        w.append_log("TERMINATED")
        w.push_event(WorkerEventKind.TERMINATED, "worker terminated by control plane")
        return True

    # -- shutdown ------------------------------------------------------------

    def shutdown(self) -> int:
        """Kill all tmux windows and session. Returns count of workers terminated."""
        count = 0
        with self._lock:
            for wid in list(self._workers.keys()):
                self.terminate(wid)
                count += 1
        if self._tmux.is_available():
            self._tmux.kill_session()
        return count

    # -- log access ----------------------------------------------------------

    def read_logs(self, worker_id: str, limit: int = 50) -> list[str]:
        """Read last N lines from worker log file."""
        with self._lock:
            w = self._workers.get(worker_id)
            if not w:
                return []
        try:
            with open(w.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [l.strip() for l in lines[-limit:] if l.strip()]
        except Exception:
            return []

    # -- factory -------------------------------------------------------------

    @classmethod
    def create_team(
        cls,
        team_name: str,
        workspace_root: str,
        worker_specs: list[dict],
    ) -> tuple["SindrisWorkerManager", list[Worker]]:
        """
        Factory: create a worker manager + spawn all workers.
        worker_specs: list of {role, agent_id?}
        """
        slug = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")[:32]
        session_name = f"sindris-{slug}"
        mgr = cls(session_name, workspace_root)

        workers = []
        for spec in worker_specs:
            w = mgr.create_worker(
                role=spec["role"],
                agent_id=spec.get("agent_id"),
            )
            mgr.spawn_worker(w.id, spec.get("command"))
            workers.append(w)

        return mgr, workers
