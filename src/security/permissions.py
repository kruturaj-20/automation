"""
Workspace boundary and permissions guard.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.core.config import SecurityConfig


class PermissionGuard:
    """Validates operations and directory access against security rules."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.allowed_roots = [
            Path(p).resolve() for p in config.allowed_dirs
        ]

    def is_path_allowed(self, target_path: str | Path) -> bool:
        """Check if target_path is within allowed workspace boundaries."""
        try:
            resolved = Path(target_path).resolve()
            for allowed in self.allowed_roots:
                try:
                    resolved.relative_to(allowed)
                    return True
                except ValueError:
                    pass
            return False
        except Exception:
            return False

    def validate_action(self, action_type: str, path: Optional[str | Path] = None) -> tuple[bool, str]:
        """
        Check if action is permitted.
        Returns (allowed: bool, reason: str).
        """
        # Check explicit deny
        for denied in self.config.deny:
            if action_type == denied:
                return False, f"Action '{action_type}' is explicitly DENIED by policy."

        # Check path boundary if path is provided
        if path and not self.is_path_allowed(path):
            return False, f"Path '{path}' is OUTSIDE approved workspace boundaries: {self.config.allowed_dirs}"

        return True, "Approved"
