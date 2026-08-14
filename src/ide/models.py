"""
IDE-agnostic data models for the IDE Agent abstraction layer.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class EventType(str, enum.Enum):
    INIT = "init"
    MESSAGE = "message"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    RESULT = "result"
    UNKNOWN = "unknown"


class ChangeType(str, enum.Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


class DiagnosticSeverity(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


class AgentStatus(str, enum.Enum):
    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"
    STOPPED = "stopped"
    UNAVAILABLE = "unavailable"


@dataclass
class TaskRequest:
    """A task request dispatched to an IDE AI agent."""

    instruction: str
    working_dir: str
    timeout_seconds: int = 300
    auto_approve: bool = True
    model: Optional[str] = None


@dataclass
class TaskEvent:
    """A structured event emitted during execution."""

    type: EventType
    timestamp: datetime
    raw_type: str = ""
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class FileChange:
    """A detected file change in the workspace."""

    path: str
    change_type: ChangeType
    detected_at: datetime = field(default_factory=datetime.now)


@dataclass
class DiagnosticEntry:
    """Diagnostic message from the IDE or build tools."""

    file: str
    line: int
    column: int
    severity: DiagnosticSeverity
    message: str
    source: str = ""


@dataclass
class TaskResult:
    """Execution outcome from an IDE AI agent."""

    status: TaskStatus
    exit_code: Optional[int] = None
    output: str = ""
    events: list[TaskEvent] = field(default_factory=list)
    file_changes: list[FileChange] = field(default_factory=list)
    diagnostics: list[DiagnosticEntry] = field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    @property
    def succeeded(self) -> bool:
        return self.status == TaskStatus.COMPLETED and (self.exit_code == 0 or self.exit_code is None)

    @property
    def was_stopped(self) -> bool:
        return self.status == TaskStatus.STOPPED
