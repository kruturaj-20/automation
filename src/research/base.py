"""
Abstract base class for research and documentation providers.

Allows web/documentation search to be plugged in without altering the core manager.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ResearchResult:
    """Findings from a research or documentation lookup."""

    query: str
    summary: str
    code_examples: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    successful: bool = True


class ResearchProvider(ABC):
    """
    Abstract interface for documentation/web research.
    """

    @abstractmethod
    async def search_documentation(self, query: str, technology: Optional[str] = None) -> ResearchResult:
        """Search documentation or best practices for a specific tech stack."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if research provider is online and configured."""
