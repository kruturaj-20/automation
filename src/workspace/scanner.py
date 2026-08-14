"""
Project Scanner.

Inspects approved workspace roots recursively, identifies software projects
reusing ProjectDetector, avoids system/build/dependency directories, and constructs
structured Project models for the registry.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.state import TaskMode
from src.inspector.detector import ProjectDetector, ProjectInfo
from src.security.security_guard import SecurityGuard
from .models import Project, WorkspaceRoot
from .registry import ProjectRegistry, WorkspaceRegistry

# Directories to skip when scanning to ensure fast, deterministic traversal
IGNORED_DIRS = {
    "node_modules",
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    ".next",
    ".turbo",
    ".gradle",
    ".dart_tool",
    "Pods",
    "target",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "$RECYCLE.BIN",
    "System Volume Information",
    ".agent_meta",
    "_e2e_workspaces",
}


class ProjectScanner:
    """Discovers software projects in approved workspace locations."""

    def __init__(
        self,
        workspace_registry: Optional[WorkspaceRegistry] = None,
        project_registry: Optional[ProjectRegistry] = None,
        security_guard: Optional[SecurityGuard] = None,
    ):
        self.workspace_reg = workspace_registry or WorkspaceRegistry()
        self.project_reg = project_registry or ProjectRegistry()
        self.guard = security_guard or self.workspace_reg.guard

    def scan(self, max_depth: int = 3) -> list[Project]:
        """
        Scan all approved workspace roots and discover projects.
        Updates ProjectRegistry and returns the discovered projects.
        """
        discovered: list[Project] = []
        discovered_paths: set[str] = set()

        for ws in self.workspace_reg.list_workspaces():
            root_path = Path(ws.path)
            if not root_path.exists() or not root_path.is_dir():
                continue

            # First, check if the workspace root itself is a project
            if self._is_candidate_dir(root_path):
                proj = self._inspect_and_build_project(root_path)
                if proj:
                    discovered.append(proj)
                    discovered_paths.add(proj.path)
                    self.project_reg.add_or_update(proj)
                    # If root is already a project, we still search subprojects up to max_depth

            # Scan immediate and nested subdirectories
            self._scan_directory(root_path, depth=1, max_depth=max_depth, discovered=discovered, discovered_paths=discovered_paths)

        # Remove stale projects no longer on disk
        self.project_reg.remove_stale_projects(discovered_paths)
        return discovered

    def _scan_directory(
        self,
        current_dir: Path,
        depth: int,
        max_depth: int,
        discovered: list[Project],
        discovered_paths: set[str],
    ):
        if depth > max_depth:
            return

        try:
            entries = [
                e for e in current_dir.iterdir()
                if e.is_dir() and e.name not in IGNORED_DIRS and not e.name.startswith(".")
            ]
        except Exception:
            return

        for sub_dir in sorted(entries, key=lambda d: d.name.lower()):
            resolved_str = str(sub_dir.resolve())

            # Security boundary validation: must be within approved workspace
            if not self.guard.is_path_allowed(sub_dir):
                continue

            if resolved_str in discovered_paths:
                continue

            if self._is_candidate_dir(sub_dir):
                proj = self._inspect_and_build_project(sub_dir)
                if proj:
                    discovered.append(proj)
                    discovered_paths.add(proj.path)
                    self.project_reg.add_or_update(proj)
                    # Scan nested subprojects inside this project (e.g. monorepos or backend/frontend split)
                    self._scan_directory(sub_dir, depth + 1, max_depth, discovered, discovered_paths)
                    continue

            # If not a project, continue traversing deeper
            self._scan_directory(sub_dir, depth + 1, max_depth, discovered, discovered_paths)

    def _is_candidate_dir(self, dir_path: Path) -> bool:
        """Check if directory contains its own project manifest or codebase files directly."""
        info: ProjectInfo = ProjectDetector.detect(dir_path)
        # Direct project: mode is EXISTING_PROJECT, has indicators, and manifest is in this direct folder
        return info.mode == TaskMode.EXISTING_PROJECT and len(info.indicators_found) > 0 and not info.is_nested

    def _inspect_and_build_project(self, dir_path: Path) -> Optional[Project]:
        """Inspect directory using ProjectDetector and build a Project model."""
        info: ProjectInfo = ProjectDetector.detect(dir_path)
        if info.mode != TaskMode.EXISTING_PROJECT or not info.indicators_found:
            return None

        resolved_path = str(dir_path.resolve())
        proj_id = hashlib.md5(resolved_path.encode("utf-8")).hexdigest()[:8]

        # Determine project display name (from folder or manifests)
        proj_name = dir_path.name

        # Check git repository
        has_git = (dir_path / ".git").exists()

        return Project(
            id=proj_id,
            name=proj_name,
            path=resolved_path,
            project_type=info.project_type,
            sub_type=info.sub_type,
            detected_indicators=info.indicators_found,
            last_scanned=datetime.now().isoformat(),
            git_repository_present=has_git,
            is_nested=info.is_nested,
        )
