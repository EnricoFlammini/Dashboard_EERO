"""
Maintenance state for startup and SQLite housekeeping (Issue #117).

While a stage is active the API answers 503 (except /api/health) and the web UI
shows a maintenance overlay instead of looking offline, then reloads itself once
the stage ends. Stages nest: a database repair started during startup reports
"db_repair" and falls back to "starting" when it finishes.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

STAGE_STARTING = "starting"
STAGE_DB_REPAIR = "db_repair"
STAGE_STARTUP_FAILED = "startup_failed"


class MaintenanceState:
    def __init__(self) -> None:
        self._stages: List[str] = []
        self._since: Optional[datetime] = None

    @property
    def active(self) -> bool:
        return bool(self._stages)

    @property
    def stage(self) -> Optional[str]:
        return self._stages[-1] if self._stages else None

    @property
    def failed(self) -> bool:
        return STAGE_STARTUP_FAILED in self._stages

    def begin(self, stage: str) -> None:
        if not self._stages:
            self._since = datetime.now(timezone.utc)
        self._stages.append(stage)

    def end(self, stage: str) -> None:
        for i in range(len(self._stages) - 1, -1, -1):
            if self._stages[i] == stage:
                del self._stages[i]
                break
        if not self._stages:
            self._since = None

    @contextmanager
    def stage_scope(self, stage: str) -> Iterator[None]:
        self.begin(stage)
        try:
            yield
        finally:
            self.end(stage)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "since": self._since.isoformat() if self._since else None,
        }


maintenance_state = MaintenanceState()
