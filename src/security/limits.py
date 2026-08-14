"""
Execution limits and emergency stop manager.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from src.core.config import LimitsConfig


class ExecutionLimiter:
    """Tracks loop iterations, runtime durations, and enforces thresholds."""

    def __init__(self, config: LimitsConfig):
        self.config = config
        self._iteration_count = 0
        self._start_time: Optional[float] = None
        self._stopped = False

    def start(self):
        self._iteration_count = 0
        self._start_time = time.time()
        self._stopped = False

    def step(self) -> tuple[bool, str]:
        """
        Record one iteration step and check limits.
        Returns (is_ok: bool, reason: str).
        """
        if self._stopped:
            return False, "Emergency stop has been triggered."

        self._iteration_count += 1
        if self._iteration_count > self.config.max_iterations:
            return False, f"Iteration limit exceeded ({self._iteration_count} > {self.config.max_iterations})."

        if self._start_time:
            elapsed_minutes = (time.time() - self._start_time) / 60.0
            if elapsed_minutes > self.config.task_timeout_minutes:
                return False, f"Task execution timeout exceeded ({elapsed_minutes:.1f}m > {self.config.task_timeout_minutes}m)."

        return True, "OK"

    def emergency_stop(self):
        self._stopped = True

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    @property
    def elapsed_seconds(self) -> float:
        if not self._start_time:
            return 0.0
        return time.time() - self._start_time
