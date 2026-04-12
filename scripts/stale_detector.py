"""
stale_detector.py - Worker超时检测

简化版：基于任务超时的stale检测，不引入心跳机制
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path

@dataclass
class WorkerLease:
    worker_id: str
    task_id: str
    started_at: str
    timeout_seconds: int
    status: str = "busy"

class StaleDetector:
    def __init__(self, state_file: str = None):
        if state_file is None:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sindris_root = os.path.dirname(script_dir)
            state_file = os.path.join(sindris_root, ".omx", "state", "leases.jsonl")
        
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._leases: Dict[str, WorkerLease] = {}
        self._load()

    def mark_busy(self, worker_id: str, task_id: str, timeout_seconds: int = 300):
        self._leases[worker_id] = WorkerLease(
            worker_id=worker_id,
            task_id=task_id,
            started_at=datetime.now().isoformat(),
            timeout_seconds=timeout_seconds,
            status="busy"
        )
        self._save()

    def mark_completed(self, worker_id: str):
        self._leases.pop(worker_id, None)
        self._save()

    def check_stale(self) -> List[WorkerLease]:
        stale = []
        now = datetime.now()
        for worker_id, lease in list(self._leases.items()):
            elapsed = (now - datetime.fromisoformat(lease.started_at)).total_seconds()
            if elapsed > lease.timeout_seconds:
                lease.status = "stale"
                stale.append(lease)
        if stale:
            self._save()
        return stale

    def recover(self, worker_id: str):
        self._leases.pop(worker_id, None)
        self._save()

    def get_stats(self) -> dict:
        return {
            "total_leases": len(self._leases),
            "stale_count": sum(1 for l in self._leases.values() if l.status == "stale"),
            "busy_count": sum(1 for l in self._leases.values() if l.status == "busy"),
        }

    def _load(self):
        if not self.state_file.exists():
            return
        self._leases = {}
        with open(self.state_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    lease = WorkerLease(**data)
                    self._leases[lease.worker_id] = lease
                except Exception:
                    continue

    def _save(self):
        with open(self.state_file, "w") as f:
            for lease in self._leases.values():
                f.write(json.dumps(asdict(lease)) + "\n")

if __name__ == "__main__":
    # 测试
    detector = StaleDetector(state_file="/tmp/leases_test.jsonl")
    
    detector.mark_busy("worker_a", "task_001", timeout_seconds=5)
    print(f"✅ 标记busy，当前状态: {detector.get_stats()}")
    
    import time
    time.sleep(6)
    stale = detector.check_stale()
    print(f"✅ 检查stale: {len(stale)} 个")
    
    detector.recover("worker_a")
    print(f"✅ 恢复后: {detector.get_stats()}")
