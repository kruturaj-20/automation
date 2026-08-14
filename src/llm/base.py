"""
Abstract base class for External LLM reasoning/advisory providers.

CRITICAL INVARIANT:
External LLMs are advisors, architects, researchers, and debuggers.
They NEVER directly create, edit, or delete project files.
Their recommendations are returned to the AI Manager and handed
to the IDE AI (Antigravity AI) for actual coding.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from src.planner.models import Approach, Goal, ProjectContext


@dataclass
class ErrorAnalysis:
    """Diagnostic analysis returned by external LLM."""

    root_cause: str
    recommended_fix: str
    code_modifications_summary: str = ""
    additional_context: str = ""
    suggested_commands: list[str] = field(default_factory=list)


class LLMProvider(ABC):
    """
    Abstract interface for external reasoning LLMs.
    """

    @abstractmethod
    async def plan_architecture(self, goal: Goal, context: Optional[ProjectContext] = None) -> Approach:
        """
        Produce architecture, tech stack, and structure advice for a project.
        Used primarily in Mode 2 (New Project).
        """

    @abstractmethod
    async def analyze_error(
        self,
        error: str,
        context: ProjectContext,
        previous_attempts: list[str],
    ) -> ErrorAnalysis:
        """
        Deep error analysis when IDE AI attempts fail.
        Formulates a solution for IDE AI to implement.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider API key and endpoint are valid."""
