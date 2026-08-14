"""
Workspace Registry and Project Registry.

Maintains approved development workspace roots and discovered projects.
All operations are validated through SecurityGuard to enforce workspace sandboxing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.core.config import AgentConfig, SecurityConfig, load_config
from src.security.security_guard import SecurityGuard
from .models import Project, WorkspaceRoot


class WorkspaceRegistry:
    """Stores and validates approved workspace root directories."""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        security_guard: Optional[SecurityGuard] = None,
    ):
        self.config = config or load_config()
        self.guard = security_guard or SecurityGuard(self.config.security)
        self._workspaces: dict[str, WorkspaceRoot] = {}
        self._init_from_config()

    def _init_from_config(self):
        for raw_path in self.config.projects.allowed_dirs:
            try:
                resolved = str(Path(raw_path).resolve())
                name = Path(resolved).name or resolved
                self._workspaces[resolved] = WorkspaceRoot(path=resolved, name=name)
            except Exception:
                pass

    def add_workspace(self, path: str | Path, name: Optional[str] = None) -> tuple[bool, str]:
        """
        Add a new approved workspace root.
        Validates path exists and is a directory.
        """
        try:
            target_path = Path(path).resolve()
        except Exception as e:
            return False, f"Invalid path: {e}"

        if not target_path.exists():
            return False, f"Directory does not exist: {target_path}"
        if not target_path.is_dir():
            return False, f"Path is not a directory: {target_path}"

        resolved_str = str(target_path)

        # Check against dangerous/system directories
        if target_path.drive and target_path == Path(target_path.drive + "\\"):
            return False, "Cannot add whole drive root as a workspace."
        
        low_res = resolved_str.lower().replace("/", "\\")
        if (
            "\\windows\\system32" in low_res
            or low_res.endswith("\\windows")
            or "\\program files" in low_res
        ):
            return False, "System directories cannot be added as workspaces."

        ws_name = name or target_path.name or resolved_str
        self._workspaces[resolved_str] = WorkspaceRoot(path=resolved_str, name=ws_name)

        # Update guard's allowed roots dynamically
        if resolved_str not in [str(p) for p in self.guard.allowed_roots]:
            self.guard.allowed_roots.append(target_path)
            self.config.projects.allowed_dirs.append(resolved_str)
            self.config.security.allowed_dirs.append(resolved_str)

        return True, f"Added workspace root: {resolved_str}"

    def remove_workspace(self, path_or_name: str) -> bool:
        """Remove a workspace root by path or name."""
        target_key = None
        for path_str, ws in self._workspaces.items():
            if path_str.lower() == path_or_name.lower() or ws.name.lower() == path_or_name.lower():
                target_key = path_str
                break

        if target_key:
            del self._workspaces[target_key]
            self.guard.allowed_roots = [
                p for p in self.guard.allowed_roots if str(p) != target_key
            ]
            return True
        return False

    def list_workspaces(self) -> list[WorkspaceRoot]:
        """List all active approved workspace roots."""
        return [ws for ws in self._workspaces.values() if ws.is_active]

    def is_path_approved(self, path: str | Path) -> bool:
        """Validate whether a path is within any approved workspace root."""
        return self.guard.is_path_allowed(path)


class ProjectRegistry:
    """Manages the catalog of discovered projects."""

    def __init__(self):
        self._projects: dict[str, Project] = {}

    def add_or_update(self, project: Project):
        """Add or update a project record."""
        self._projects[project.id] = project

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """Retrieve a project by its unique ID (or numeric string)."""
        if project_id in self._projects:
            return self._projects[project_id]

        # Also support 1-based indexing lookup
        try:
            idx = int(project_id) - 1
            all_projs = list(self._projects.values())
            if 0 <= idx < len(all_projs):
                return all_projs[idx]
        except (ValueError, IndexError):
            pass

        return None

    def get_by_path(self, path: str | Path) -> Optional[Project]:
        """Retrieve a project by its filesystem path."""
        try:
            resolved = str(Path(path).resolve())
            for proj in self._projects.values():
                if str(Path(proj.path).resolve()) == resolved:
                    return proj
        except Exception:
            pass
        return None

    def list_projects(self) -> list[Project]:
        """Return all discovered projects sorted by name."""
        return sorted(self._projects.values(), key=lambda p: p.name.lower())

    def remove_stale_projects(self, existing_paths: set[str]):
        """Remove projects that are not in the current discovered set or no longer exist on disk."""
        normalized_existing = {str(Path(p).resolve()).lower() for p in existing_paths}
        to_remove = []
        for pid, proj in self._projects.items():
            try:
                proj_norm = str(Path(proj.path).resolve()).lower()
                if proj_norm not in normalized_existing and not Path(proj.path).exists():
                    to_remove.append(pid)
                elif proj_norm not in normalized_existing:
                    to_remove.append(pid)
            except Exception:
                to_remove.append(pid)
        for pid in to_remove:
            del self._projects[pid]

    def clear(self):
        """Clear all registered projects."""
        self._projects.clear()
