"""
Data models for the IDE Agent abstraction layer.

These models are IDE-agnostic. They represent the interface contract
between the AI Manager and any IDE AI coding agent.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ─── Enums ────────────────────────────────────────────────────────────


class TaskStatus(enum.Enum):
    """Lifecycle status of a task delegated to an IDE AI agent."""

    PENDING = "pending"  # Created but not yet started
    STARTING = "starting"  # Being sent to the agent
    RUNNING = "running"  # Agent is actively working
    COMPLETED = "completed"  # Agent finished (success or failure)
    FAILED = "failed"  # Agent process crashed or timed out
    STOPPED = "stopped"  # Manually stopped / aborted
    UNKNOWN = "unknown"  # Cannot determine status


class EventType(enum.Enum):
    """Types of events that can be emitted by an IDE AI agent."""

    INIT = "init"  # Session initialized
    MESSAGE = "message"  # Agent text output (thinking, explanation)
    TOOL_USE = "tool_use"  # Agent calling a tool (file edit, terminal, etc.)
    TOOL_RESULT = "tool_result"  # Result of a tool call
    ERROR = "error"  # Non-fatal error or warning
    RESULT = "result"  # Final result of the session
    UNKNOWN = "unknown"  # Unrecognized event type


class ChangeType(enum.Enum):
    """Type of file system change."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


class DiagnosticSeverity(enum.Enum):
    """Severity of a diagnostic message."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


# ─── Data Classes ─────────────────────────────────────────────────────


@dataclass
class TaskRequest:
    """A task to be sent to the IDE AI agent."""

    instruction: str  # Natural language instruction
    working_dir: str  # Directory the agent should work in
    timeout_seconds: int = 300  # Max time before we consider it stuck
    auto_approve: bool = True  # Whether to auto-approve agent actions
    model: Optional[str] = None  # Override the default model


@dataclass
class TaskEvent:
    """A single event emitted by the IDE AI agent during execution."""

    type: EventType
    timestamp: datetime
    raw_type: str = ""  # Original event type string from the IDE
    content: str = ""  # Text content of the event
    tool_name: str = ""  # Name of tool being called (for TOOL_USE)
    tool_args: dict = field(default_factory=dict)  # Tool arguments
    tool_result: str = ""  # Tool execution result
    metadata: dict = field(default_factory=dict)  # Any extra data


@dataclass
class FileChange:
    """A file that was created, modified, or deleted during the task."""

    path: str  # Absolute path to the file
    change_type: ChangeType
    detected_at: datetime = field(default_factory=datetime.now)


@dataclass
class DiagnosticEntry:
    """A diagnostic message (error, warning, etc.) from the IDE."""

    file: str
    line: int
    column: int
    severity: DiagnosticSeverity
    message: str
    source: str = ""  # e.g., "typescript", "eslint"


@dataclass
class TaskResult:
    """Complete result of a task execution."""

    status: TaskStatus
    exit_code: Optional[int] = None
    output: str = ""  # Final text output from the agent
    events: list[TaskEvent] = field(default_factory=list)
    file_changes: list[FileChange] = field(default_factory=list)
    diagnostics: list[DiagnosticEntry] = field(default_factory=list)
    error: Optional[str] = None  # Error message if failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    @property
    def succeeded(self) -> bool:
        return self.status == TaskStatus.COMPLETED and self.exit_code == 0

    @property
    def was_stopped(self) -> bool:
        return self.status == TaskStatus.STOPPED
