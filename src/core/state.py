"""
State machine and tracking models for the AI Manager.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


class TaskMode(str, enum.Enum):
    """Execution mode determined by workspace inspection."""

    EXISTING_PROJECT = "existing_project"  # Operating inside an existing codebase
    NEW_PROJECT = "new_project"            # Creating a project from scratch


class TaskPhase(str, enum.Enum):
    """Lifecycle phases of the AI Manager orchestration loop."""

    INITIALIZING = "initializing"
    INSPECTING = "inspecting"
    CONSULTING_LLM = "consulting_llm"      # External LLM architecture/approach
    PREPARING_BRIEF = "preparing_brief"
    DELEGATING_TO_IDE = "delegating_to_ide" # IDE AI (Antigravity AI) coding
    VERIFYING = "verifying"                # Independent build/test checks
    ERROR_HANDLING = "error_handling"      # 3-tier escalation
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class ExecutionSummary:
    """Summary of actions taken during a task."""

    task_id: str
    instruction: str
    mode: TaskMode
    phase: TaskPhase
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    ide_attempts: int = 0
    llm_escalations: int = 0
    verification_passed: bool = False
    verification_output: str = ""
    error_message: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0


@dataclass
class TaskState:
    """Current state of a running task in the AI Manager."""

    task_id: str
    instruction: str
    mode: TaskMode = TaskMode.NEW_PROJECT
    phase: TaskPhase = TaskPhase.INITIALIZING
    working_dir: str = ""
    project_type: str = "unknown"
    indicators_found: list[str] = field(default_factory=list)
    current_attempt: int = 0
    ide_retry_count: int = 0
    llm_escalation_count: int = 0
    last_error: Optional[str] = None
    history: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def transition_to(self, phase: TaskPhase, note: str = ""):
        """Record phase transition."""
        self.phase = phase
        self.updated_at = datetime.now()
        self.history.append({
            "phase": phase.value,
            "timestamp": self.updated_at.isoformat(),
            "note": note,
        })
