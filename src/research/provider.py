"""
Concrete implementations of ResearchProvider for Phase 1.
"""

from __future__ import annotations

from typing import Optional

from .base import ResearchProvider, ResearchResult


class NoOpResearchProvider(ResearchProvider):
    """Default non-blocking research provider when web search is disabled."""

    async def search_documentation(self, query: str, technology: Optional[str] = None) -> ResearchResult:
        return ResearchResult(
            query=query,
            summary="Web research skipped (standard library / familiar stack).",
            successful=False,
        )

    async def is_available(self) -> bool:
        return True


class WebResearchProvider(ResearchProvider):
    """
    Lightweight web research provider extensible for Google Search / DuckDuckGo.
    Phase 1 implementation provides clean extensibility.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search_documentation(self, query: str, technology: Optional[str] = None) -> ResearchResult:
        # Phase 1 stub for documentation lookup
        return ResearchResult(
            query=query,
            summary=f"Documentation reference query formulated for {technology or 'general'} stack: {query}",
            sources=["official-docs"],
            successful=True,
        )

    async def is_available(self) -> bool:
        return bool(self.api_key)
