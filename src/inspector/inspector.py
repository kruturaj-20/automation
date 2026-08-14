"""
Codebase Inspector.

Performs read-only inspection of an existing codebase to generate a grounded
ProjectContext without modifying any files.
Explicitly excludes sensitive files (.env, credentials, keys) from context.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from src.core.state import TaskMode
from src.planner.models import ProjectContext
from .detector import ProjectDetector, ProjectInfo

# Patterns for sensitive files that must NEVER be read into context or briefs
SENSITIVE_PATTERNS = [
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"id_rsa|id_ed25519|\.pem$|\.key$", re.IGNORECASE),
    re.compile(r"credentials\.json|service_account.*\.json", re.IGNORECASE),
    re.compile(r"\.aws|\.gnupg|\.ssh", re.IGNORECASE),
]


class CodebaseInspector:
    """Read-only inspector for project codebases with sensitive file isolation."""

    @classmethod
    def inspect(cls, directory: str | Path, max_depth: int = 4) -> tuple[ProjectInfo, ProjectContext]:
        path = Path(directory)
        info = ProjectDetector.detect(path)

        if info.mode == TaskMode.NEW_PROJECT:
            context = ProjectContext(
                mode=TaskMode.NEW_PROJECT,
                root_dir=str(path),
                project_type="unknown",
                indicator_files=[],
                structure_summary="No existing codebase detected. Workspace is empty or uninitialized.",
            )
            return info, context

        # Generate structure summary
        structure_lines: list[str] = [
            f"Project Root: {path.name}/ (Type: {info.project_type}{f', {info.sub_type}' if info.sub_type else ''})"
        ]
        existing_files: list[str] = []

        def is_sensitive(name: str) -> bool:
            return any(p.search(name) for p in SENSITIVE_PATTERNS)

        def build_tree(current_dir: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return

            try:
                entries = sorted(list(current_dir.iterdir()), key=lambda e: (not e.is_dir(), e.name))
            except Exception:
                return

            # Filter noisy and sensitive directories/files
            ignored_dirs = {
                ".git", "node_modules", "venv", ".venv", "__pycache__",
                "dist", "build", ".next", ".turbo", "coverage", ".dart_tool",
                ".aws", ".ssh"
            }
            entries = [
                e for e in entries
                if e.name not in ignored_dirs
                and not e.name.startswith(".")
                and not is_sensitive(e.name)
            ]

            for idx, entry in enumerate(entries):
                is_last = (idx == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                rel_path = str(entry.relative_to(path)).replace("\\", "/")

                if entry.is_dir():
                    structure_lines.append(f"{prefix}{connector}{entry.name}/")
                    extension = "    " if is_last else "│   "
                    build_tree(entry, prefix + extension, depth + 1)
                else:
                    structure_lines.append(f"{prefix}{connector}{entry.name}")
                    existing_files.append(rel_path)

        build_tree(path)

        context = ProjectContext(
            mode=TaskMode.EXISTING_PROJECT,
            root_dir=str(path),
            project_type=info.project_type,
            indicator_files=info.indicators_found,
            structure_summary="\n".join(structure_lines[:80]),
            dependencies={**info.dependencies, **info.dev_dependencies},
            scripts=info.scripts,
            entry_points=info.entry_points,
            existing_files=existing_files[:100],
        )

        return info, context
