"""
Abstract base class for IDE AI agent adapters.

The AI Manager communicates ONLY through this interface.
All IDE-specific logic lives in concrete adapter implementations.

Adding a new IDE = implementing this class.
Zero changes needed in the AI Manager.
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
        - (future) KiroAdapter
    """

    @abstractmethod
    async def start_task(self, request: TaskRequest) -> str:
        """
        Start a new task. Returns a task ID that can be used to
        track, query, and stop this task.

        The task runs asynchronously — this method returns once
        the agent process has been launched, not when it finishes.
        """

    @abstractmethod
    async def send_followup(self, task_id: str, message: str) -> None:
        """
        Send a follow-up message to an already-running task session.
        Used for multi-turn interactions like error fixing.
        """

    @abstractmethod
    async def get_status(self, task_id: str) -> TaskStatus:
        """Get the current status of a task."""

    @abstractmethod
    async def get_events(self, task_id: str) -> list[TaskEvent]:
        """Get all events emitted by the agent for this task so far."""

    @abstractmethod
    async def stream_events(self, task_id: str) -> AsyncIterator[TaskEvent]:
        """Stream events in real-time as the agent works."""

    @abstractmethod
    async def get_output(self, task_id: str) -> str:
        """Get the accumulated text output from the agent."""

    @abstractmethod
    async def get_changed_files(self, task_id: str) -> list[FileChange]:
        """
        Get list of files created, modified, or deleted during this task.
        Detected by comparing file system state before and after,
        plus any tool_use events from the agent.
        """

    @abstractmethod
    async def get_diagnostics(self, task_id: str) -> list[DiagnosticEntry]:
        """
        Get diagnostic messages (errors, warnings) from the IDE
        or from running build/test commands.
        """

    @abstractmethod
    async def wait_for_completion(
        self, task_id: str, timeout_seconds: Optional[int] = None
    ) -> TaskResult:
        """
        Block until the task completes or the timeout is reached.
        Returns the full TaskResult.
        """

    @abstractmethod
    async def stop_task(self, task_id: str) -> TaskResult:
        """
        Stop/abort a running task. Returns the partial result.
        Must not raise if the task already finished.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if this IDE agent is installed and accessible
        in the current environment.
        """

    @abstractmethod
    async def get_adapter_info(self) -> dict:
        """
        Return metadata about this adapter:
        name, version, capabilities, limitations, etc.
        """
