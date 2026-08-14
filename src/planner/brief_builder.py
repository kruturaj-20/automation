"""
Task Brief Builder.

Transforms user instructions, project inspection context, and architecture advice
into comprehensive, developer-ready task briefs for the IDE AI (Antigravity AI).
"""

from __future__ import annotations

import uuid
from typing import Optional

from src.core.state import TaskMode
from .models import Approach, Goal, ProjectContext, TaskBrief


class TaskBriefBuilder:
    """Constructs structured task briefs tailored to Mode 1 or Mode 2."""

    @classmethod
    def build_mode1_brief(
        cls,
        goal: Goal,
        context: ProjectContext,
    ) -> TaskBrief:
        """
        Build a brief for MODE 1: EXISTING PROJECT.
        Grounded in the current codebase architecture.
        """
        task_id = str(uuid.uuid4())[:8]

        context_summary_lines = [
            f"Existing {context.project_type.upper()} project detected.",
            f"Root directory: {context.root_dir}",
        ]
        if context.entry_points:
            context_summary_lines.append(f"Entry points: {', '.join(context.entry_points)}")
        if context.dependencies:
            dep_names = list(context.dependencies.keys())[:10]
            context_summary_lines.append(f"Key dependencies: {', '.join(dep_names)}")
        if context.structure_summary:
            context_summary_lines.append(f"\nProject Tree:\n{context.structure_summary}")

        requirements = [
            f"Implement the requested feature: {goal.raw_instruction}",
            "Preserve existing architecture, conventions, and design patterns.",
            "Update or create relevant files to integrate cleanly with existing entry points.",
        ]

        verification_hints = [
            "Ensure modified code compiles / runs without syntax errors.",
            "Ensure no breaking changes to existing imports or exports.",
        ]
        if context.scripts.get("build"):
            verification_hints.append(f"Build command: `npm run build` or `{context.scripts['build']}`")
        if context.scripts.get("test"):
            verification_hints.append(f"Test command: `npm test` or `{context.scripts['test']}`")

        constraints = [
            "Do NOT delete unrelated existing files.",
            "Follow existing formatting and file naming standards.",
            "Install any newly required packages if necessary.",
        ]

        return TaskBrief(
            task_id=task_id,
            mode=TaskMode.EXISTING_PROJECT,
            instruction=goal.raw_instruction,
            working_dir=context.root_dir,
            context_summary="\n".join(context_summary_lines),
            requirements=requirements,
            architecture_notes=["Work strictly within the existing project architecture."],
            verification_hints=verification_hints,
            constraints=constraints,
        )

    @classmethod
    def build_mode2_brief(
        cls,
        goal: Goal,
        target_dir: str,
        approach: Approach,
    ) -> TaskBrief:
        """
        Build a brief for MODE 2: NEW PROJECT.
        Grounded in external LLM architecture recommendations.
        """
        task_id = str(uuid.uuid4())[:8]

        context_summary_lines = [
            "New project creation from scratch.",
            f"Target workspace: {target_dir}",
            f"Architecture: {approach.architecture_overview}",
        ]

        requirements = [
            f"Create a complete, functional project for: {goal.raw_instruction}",
            "Initialize all required configuration files, package manifests, and source files.",
            "Implement modern, rich aesthetics, clean styling, and responsive layout.",
            "Ensure all key features are fully implemented and functional (no placeholders).",
        ]

        architecture_notes = []
        if approach.suggested_tech_stack:
            architecture_notes.append(f"Recommended Tech Stack: {', '.join(approach.suggested_tech_stack)}")
        if approach.suggested_dependencies:
            architecture_notes.append(f"Required Packages / Dependencies: {', '.join(approach.suggested_dependencies)}")
        for guideline in approach.implementation_guidelines:
            architecture_notes.append(guideline)

        verification_hints = [
            "Create all necessary entry files (e.g. index.html, main.ts, or main.py).",
            "Verify all files are written and the application can build/run cleanly.",
        ]

        constraints = [
            "Keep all project files strictly inside the target workspace directory.",
            "Write production-quality code with proper structure and comments.",
        ]

        return TaskBrief(
            task_id=task_id,
            mode=TaskMode.NEW_PROJECT,
            instruction=goal.raw_instruction,
            working_dir=target_dir,
            context_summary="\n".join(context_summary_lines),
            requirements=requirements,
            architecture_notes=architecture_notes,
            verification_hints=verification_hints,
            constraints=constraints,
        )
