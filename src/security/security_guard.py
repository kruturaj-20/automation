"""
SecurityGuard — Workspace sandboxing, command filtering, and credential isolation.

INVARIANTS:
1. Denies file access outside configured workspace allowlist.
2. Never exposes credentials, API keys, passwords, or tokens to external LLMs or logs.
3. Validates all verification commands against dangerous shell patterns.
4. Strictly isolates .env and sensitive credential stores.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

from src.core.config import SecurityConfig

# Sensitive file patterns that must never be leaked to external LLMs
SENSITIVE_PATTERNS = [
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"id_rsa|id_ed25519|\.pem$|\.key$", re.IGNORECASE),
    re.compile(r"credentials\.json|service_account.*\.json", re.IGNORECASE),
    re.compile(r"\.aws|\.gnupg|\.ssh", re.IGNORECASE),
]

# Sensitive regex patterns for value sanitization
SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z-_]{30,})"),                      # Google API Key
    re.compile(r"(sk-[a-zA-Z0-9_-]{20,})"),                      # OpenAI / Anthropic Key
    re.compile(r"(ghp_[a-zA-Z0-9]{30,})"),                        # GitHub Token
    re.compile(r"(bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.I),       # Bearer Token
    re.compile(r"(api[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?)", re.I),
    re.compile(r"(password\s*[:=]\s*['\"]?[^'\"]+['\"]?)", re.I),
]

# Blocked dangerous shell commands
DANGEROUS_COMMANDS = [
    re.compile(r"\brm\s+-rf\s+[/~]", re.I),
    re.compile(r"\bdel\b.*[c-z]:\\", re.I),
    re.compile(r"\bformat\s+[c-z]:", re.I),
    re.compile(r"\bdiskpart\b", re.I),
    re.compile(r"\bshutdown\b", re.I),
    re.compile(r"\bcurl\b.*\|\s*(?:ba|z|t?c|k)?sh", re.I),
    re.compile(r"\bwget\b.*\|\s*(?:ba|z|t?c|k)?sh", re.I),
]


class SecurityGuard:
    """Security governance layer controlling paths, commands, and secrets."""

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.allowed_roots = [
            Path(p).resolve() for p in self.config.allowed_dirs
        ]

    def is_path_allowed(self, target_path: str | Path) -> bool:
        """Check if target_path is strictly inside an approved workspace."""
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

    def is_sensitive_file(self, file_path: str | Path) -> bool:
        """Check if a file contains credentials or sensitive system secrets."""
        name = Path(file_path).name
        return any(pattern.search(name) for pattern in SENSITIVE_PATTERNS)

    def validate_command(self, command: str, cwd: Optional[str | Path] = None) -> tuple[bool, str]:
        """
        Validate that a command is safe to run.
        Returns (is_safe: bool, reason: str).
        """
        if cwd and not self.is_path_allowed(cwd):
            return False, f"Command execution denied: Working directory '{cwd}' is outside allowed workspaces."

        for pattern in DANGEROUS_COMMANDS:
            if pattern.search(command):
                return False, f"Command blocked by SecurityGuard: Detected prohibited destructive pattern."

        return True, "Command approved"

    def validate_action(self, action_type: str, path: Optional[str | Path] = None) -> tuple[bool, str]:
        """Validate general action against security policies."""
        for denied in self.config.deny:
            if action_type == denied:
                return False, f"Action '{action_type}' is explicitly DENIED by security policy."

        if path and not self.is_path_allowed(path):
            return False, f"Path '{path}' is OUTSIDE approved workspace boundaries: {self.config.allowed_dirs}"

        return True, "Action approved"

    def sanitize_secrets(self, text: str) -> str:
        """Redact known API keys, tokens, and passwords from logs or prompts."""
        if not text:
            return ""
        sanitized = text
        for pattern in SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized
