"""
Abstract base class for IDE AI agent adapters.

The AI Manager communicates ONLY through this interface.
All IDE-specific logic lives in concrete adapter implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from .models import (
    DiagnosticEntry,
    FileChange,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
)


class IDEAgentAdapter(ABC):
    """
    Abstract interface for any IDE AI coding agent.

    Implementations:
        - AntigravityAdapter (Antigravity IDE / Gemini CLI)
        - (future) ClineAdapter
        - (future) CursorAdapter
        - (future) VSCodeAdapter
    """

    @abstractmethod
    async def start_task(self, request: TaskRequest) -> str:
        """Start a new task. Returns a unique task ID."""

    @abstractmethod
    async def send_followup(self, task_id: str, message: str) -> None:
        """Send a follow-up instruction to an existing session."""

    @abstractmethod
    async def get_status(self, task_id: str) -> TaskStatus:
        """Get the current status of a task."""

    @abstractmethod
    async def get_events(self, task_id: str) -> list[TaskEvent]:
        """Get all events emitted by the agent for this task."""

    @abstractmethod
    async def stream_events(self, task_id: str) -> AsyncIterator[TaskEvent]:
        """Stream events in real time."""

    @abstractmethod
    async def get_output(self, task_id: str) -> str:
        """Get accumulated text output from the agent."""

    @abstractmethod
    async def get_changed_files(self, task_id: str) -> list[FileChange]:
        """Get list of files created, modified, or deleted."""

    @abstractmethod
    async def get_diagnostics(self, task_id: str) -> list[DiagnosticEntry]:
        """Get diagnostic messages."""

    @abstractmethod
    async def wait_for_completion(
        self, task_id: str, timeout_seconds: Optional[int] = None
    ) -> TaskResult:
        """Block until the task completes or times out."""

    @abstractmethod
    async def stop_task(self, task_id: str) -> TaskResult:
        """Stop/abort a running task."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this IDE agent is installed and accessible."""

    @abstractmethod
    async def get_adapter_info(self) -> dict:
        """Return adapter metadata."""
