"""
Data models for planning and task brief generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.core.state import TaskMode


@dataclass
class Goal:
    """Parsed intent and requirements from user instruction."""

    raw_instruction: str
    summary: str
    target_technology: Optional[str] = None
    key_features: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass
class ProjectContext:
    """Current state and architecture of the workspace."""

    mode: TaskMode
    root_dir: str
    project_type: str  # e.g., "react", "python", "flutter", "empty"
    indicator_files: list[str] = field(default_factory=list)
    structure_summary: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
    existing_files: list[str] = field(default_factory=list)


@dataclass
class Approach:
    """Architecture / approach recommendation from external LLMs."""

    architecture_overview: str
    suggested_tech_stack: list[str] = field(default_factory=list)
    suggested_dependencies: list[str] = field(default_factory=list)
    implementation_guidelines: list[str] = field(default_factory=list)
    recommended_structure: list[str] = field(default_factory=list)


@dataclass
class TaskBrief:
    """
    Structured brief delivered to the IDE AI (Antigravity AI) for execution.
    The IDE AI uses this brief to perform 100% of the implementation.
    """

    task_id: str
    mode: TaskMode
    instruction: str
    working_dir: str
    context_summary: str
    requirements: list[str] = field(default_factory=list)
    architecture_notes: list[str] = field(default_factory=list)
    verification_hints: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    def to_developer_prompt(self) -> str:
        """Format the brief into a comprehensive instruction for the IDE AI."""
        lines = [
            f"# TASK BRIEF: {self.instruction}",
            "",
            f"**Execution Mode:** {'Existing Codebase Modification' if self.mode == TaskMode.EXISTING_PROJECT else 'New Project Creation'}",
            f"**Working Directory:** `{self.working_dir}`",
            "",
            "## Context & Current Architecture",
            self.context_summary or "No existing project detected. Creating project from scratch.",
            "",
            "## Implementation Requirements",
        ]
        for req in self.requirements:
            lines.append(f"- {req}")

        if self.architecture_notes:
            lines.append("\n## Architecture & Technology Guidelines")
            for note in self.architecture_notes:
                lines.append(f"- {note}")

        if self.constraints:
            lines.append("\n## Constraints & Guardrails")
            for c in self.constraints:
                lines.append(f"- {c}")

        if self.verification_hints:
            lines.append("\n## Verification & Acceptance Criteria")
            for v in self.verification_hints:
                lines.append(f"- {v}")

        lines.append("\n**Action:** Please implement all necessary files, dependencies, and code directly in the project.")
        return "\n".join(lines)
