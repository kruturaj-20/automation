"""
Append-only Audit Log for autonomous actions with secret sanitization.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .security_guard import SecurityGuard


@dataclass
class ActionRecord:
    """A single audited action."""

    timestamp: str
    task_id: str
    action_type: str  # "task_received", "project_detected", "brief_generated", "ide_started", "verified", etc.
    details: dict[str, Any] = field(default_factory=dict)
    status: str = "success"
    error: Optional[str] = None


class ActionLog:
    """Manages persistent append-only action logs with secret redaction."""

    def __init__(self, log_dir: str | Path = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"actions_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def _sanitize_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize string values in dictionary."""
        sanitized = {}
        for k, v in d.items():
            if isinstance(v, str):
                # Check for sensitive keys
                if any(sec in k.lower() for sec in ["api_key", "secret", "password", "token"]):
                    sanitized[k] = "[REDACTED_SECRET]"
                else:
                    # Sanitize value patterns
                    sanitized[k] = SecurityGuard(None).sanitize_secrets(v) if v else ""
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_dict(v)
            elif isinstance(v, list):
                sanitized[k] = [
                    self._sanitize_dict(item) if isinstance(item, dict)
                    else (SecurityGuard(None).sanitize_secrets(item) if isinstance(item, str) else item)
                    for item in v
                ]
            else:
                sanitized[k] = v
        return sanitized

    def log(
        self,
        task_id: str,
        action_type: str,
        details: Optional[dict[str, Any]] = None,
        status: str = "success",
        error: Optional[str] = None,
    ) -> ActionRecord:
        clean_details = self._sanitize_dict(details or {})
        clean_error = SecurityGuard(None).sanitize_secrets(error) if error else None

        record = ActionRecord(
            timestamp=datetime.now().isoformat(),
            task_id=task_id,
            action_type=action_type,
            details=clean_details,
            status=status,
            error=clean_error,
        )
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except Exception:
            pass
        return record
