"""
Workspace and Project data models for Project Discovery & Selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class WorkspaceRoot:
    """An approved root directory where projects may reside."""

    path: str
    name: str
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True


@dataclass
class Project:
    """Structured representation of a discovered software project."""

    id: str
    name: str
    path: str
    project_type: str
    sub_type: Optional[str] = None
    detected_indicators: list[str] = field(default_factory=list)
    last_scanned: str = field(default_factory=lambda: datetime.now().isoformat())
    git_repository_present: bool = False
    is_nested: bool = False

    @property
    def display_type(self) -> str:
        """Formatted project type for UI display."""
        if self.sub_type:
            # e.g. "React Native", "FastAPI", "React"
            clean_sub = self.sub_type.replace("-", " ").title()
            return clean_sub
        return self.project_type.capitalize()
