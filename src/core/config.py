"""
Configuration loader for the AI Manager.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


def _load_env():
    """Load .env files from workspace if present."""
    for candidate in [Path(".env"), Path("../.env"), Path("e:/Work/automation/.env")]:
        if candidate.exists():
            try:
                with open(candidate, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip()
                            if k and v and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


@dataclass
class IDEConfig:
    type: str = "antigravity"
    cli_path: str = "gemini"
    prefer_sdk: bool = True
    model: str = "gemini-2.5-pro"
    approval_mode: str = "yolo"
    sandbox: bool = False
    timeout_seconds: int = 300


@dataclass
class LLMConfig:
    default_provider: str = "gemini"
    api_key: Optional[str] = None
    model: str = "gemini-2.5-pro"
    temperature: float = 0.2


@dataclass
class SecurityConfig:
    allowed_dirs: list[str] = field(default_factory=lambda: ["e:\\Work", "e:/Work"])
    auto_approve: list[str] = field(default_factory=lambda: [
        "file.read", "file.create", "file.modify", "terminal.run_in_project"
    ])
    ask_user: list[str] = field(default_factory=lambda: [
        "file.delete", "terminal.run_system", "git.push"
    ])
    deny: list[str] = field(default_factory=lambda: [
        "access.personal_files", "access.credentials"
    ])


@dataclass
class LimitsConfig:
    max_iterations: int = 10
    max_error_retries_ide: int = 2
    max_error_retries_llm: int = 2
    task_timeout_minutes: int = 30


@dataclass
class ProjectsConfig:
    default_dir: str = "e:\\Work\\Projects"
    allowed_dirs: list[str] = field(default_factory=lambda: ["e:\\Work", "e:/Work"])


@dataclass
class AgentConfig:
    ide: IDEConfig = field(default_factory=IDEConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    projects: ProjectsConfig = field(default_factory=ProjectsConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    default_workspace: str = "e:\\Work\\automation"


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """Load configuration from YAML and environment variables."""
    _load_env()

    path = Path(config_path or "config.yaml")
    data: dict[str, Any] = {}

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

    ide_data = data.get("ide", {})
    ag_data = ide_data.get("antigravity", {})
    ide_cfg = IDEConfig(
        type=ide_data.get("type", "antigravity"),
        cli_path=ag_data.get("cli_path", "gemini"),
        prefer_sdk=ag_data.get("prefer_sdk", True),
        model=ag_data.get("model", "gemini-2.5-pro"),
        approval_mode=ag_data.get("approval_mode", "yolo"),
        sandbox=ag_data.get("sandbox", False),
        timeout_seconds=ag_data.get("timeout_seconds", 300),
    )

    llm_data = data.get("llm", {})
    gemini_data = llm_data.get("gemini", {})
    api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or gemini_data.get("api_key")
    )
    # Handle placeholder strings like "${GEMINI_API_KEY}"
    if api_key and api_key.startswith("${") and api_key.endswith("}"):
        var_name = api_key[2:-1]
        api_key = os.environ.get(var_name)

    llm_cfg = LLMConfig(
        default_provider=llm_data.get("default_provider", "gemini"),
        api_key=api_key,
        model=gemini_data.get("model", "gemini-2.5-pro"),
        temperature=float(gemini_data.get("temperature", 0.2)),
    )

    sec_data = data.get("security", {})
    projects_data = data.get("projects", {})
    allowed_dirs = projects_data.get("allowed_dirs", ["e:\\Work", "e:/Work"])
    sec_cfg = SecurityConfig(
        allowed_dirs=allowed_dirs,
        auto_approve=sec_data.get("auto_approve", ["file.read", "file.create", "file.modify", "terminal.run_in_project"]),
        ask_user=sec_data.get("ask_user", ["file.delete", "terminal.run_system", "git.push"]),
        deny=sec_data.get("deny", ["access.personal_files", "access.credentials"]),
    )

    projects_cfg = ProjectsConfig(
        default_dir=projects_data.get("default_dir", "e:\\Work\\automation"),
        allowed_dirs=allowed_dirs,
    )

    agent_data = data.get("agent", {})
    limits_cfg = LimitsConfig(
        max_iterations=int(agent_data.get("max_iterations", 10)),
        max_error_retries_ide=int(agent_data.get("max_error_retries_ide", 2)),
        max_error_retries_llm=int(agent_data.get("max_error_retries_llm", 2)),
        task_timeout_minutes=int(agent_data.get("task_timeout_minutes", 30)),
    )

    return AgentConfig(
        ide=ide_cfg,
        llm=llm_cfg,
        security=sec_cfg,
        projects=projects_cfg,
        limits=limits_cfg,
        default_workspace=projects_cfg.default_dir,
    )
