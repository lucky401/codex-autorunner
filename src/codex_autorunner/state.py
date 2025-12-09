import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .utils import atomic_write, read_json


@dataclasses.dataclass
class RunnerState:
    last_run_id: Optional[int]
    status: str
    last_exit_code: Optional[int]
    last_run_started_at: Optional[str]
    last_run_finished_at: Optional[str]

    def to_json(self) -> str:
        payload = {
            "last_run_id": self.last_run_id,
            "status": self.status,
            "last_exit_code": self.last_exit_code,
            "last_run_started_at": self.last_run_started_at,
            "last_run_finished_at": self.last_run_finished_at,
        }
        return json.dumps(payload, indent=2) + "\n"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state(state_path: Path) -> RunnerState:
    data = read_json(state_path)
    if not data:
        return RunnerState(None, "idle", None, None, None)
    return RunnerState(
        last_run_id=data.get("last_run_id"),
        status=data.get("status", "idle"),
        last_exit_code=data.get("last_exit_code"),
        last_run_started_at=data.get("last_run_started_at"),
        last_run_finished_at=data.get("last_run_finished_at"),
    )


def save_state(state_path: Path, state: RunnerState) -> None:
    atomic_write(state_path, state.to_json())
