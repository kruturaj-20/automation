"""
Project Detection Engine.

Inspects workspaces for project indicator files to reliably classify whether
a workspace contains an existing codebase (Mode 1) or is a new project (Mode 2).
Supports nested subprojects, multi-ecosystem analysis, and deep framework detection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.core.state import TaskMode


@dataclass
class ProjectInfo:
    """Detailed metadata about detected workspace project."""

    mode: TaskMode
    project_type: str             # e.g. "nodejs", "python", "flutter", "dart", "rust", "golang", "java", "dotnet", "php", "ruby", "cpp", "unknown"
    sub_type: Optional[str] = None # e.g. "react", "react-native", "vite", "fastapi", "django"
    root_dir: str = ""
    indicators_found: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)
    dev_dependencies: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    has_git: bool = False
    total_files: int = 0
    is_nested: bool = False


# Matrix of ecosystem indicator files
PROJECT_INDICATORS: dict[str, list[str]] = {
    "nodejs": [
        "package.json", "tsconfig.json", "jsconfig.json", "package-lock.json",
        "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "metro.config.js"
    ],
    "python": [
        "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg",
        "Pipfile", "poetry.lock", "environment.yml", "manage.py"
    ],
    "flutter": [
        "pubspec.yaml", "pubspec.lock"
    ],
    "rust": [
        "Cargo.toml", "Cargo.lock"
    ],
    "golang": [
        "go.mod", "go.sum"
    ],
    "java": [
        "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"
    ],
    "dotnet": [
        "*.sln", "*.csproj", "*.fsproj"
    ],
    "php": [
        "composer.json", "composer.lock"
    ],
    "ruby": [
        "Gemfile", "Gemfile.lock"
    ],
    "cpp": [
        "CMakeLists.txt", "Makefile", "meson.build"
    ],
}


class ProjectDetector:
    """Inspects a directory and determines if an existing project exists."""

    @classmethod
    def detect(cls, directory: str | Path) -> ProjectInfo:
        path = Path(directory)

        if not path.exists() or not path.is_dir():
            return ProjectInfo(
                mode=TaskMode.NEW_PROJECT,
                project_type="unknown",
                root_dir=str(path),
            )

        indicators_found: list[str] = []
        detected_types: set[str] = set()

        # Check primary indicators in root directory
        for ecosystem, indicator_list in PROJECT_INDICATORS.items():
            for indicator in indicator_list:
                if "*" in indicator:
                    matches = list(path.glob(indicator))
                    if matches:
                        indicators_found.extend([m.name for m in matches])
                        detected_types.add(ecosystem)
                else:
                    if (path / indicator).exists():
                        indicators_found.append(indicator)
                        detected_types.add(ecosystem)

        has_git = (path / ".git").exists()

        # Count non-ignored files
        all_files = [
            f for f in path.rglob("*")
            if f.is_file() and not any(
                part.startswith(".") or part in ("node_modules", "venv", ".venv", "__pycache__", "target", "build")
                for part in f.parts
            )
        ]

        # Nested project detection (if no indicator in root, inspect immediate subdirectories)
        if not indicators_found and len(all_files) > 0:
            for sub_dir in [d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")]:
                sub_info = cls.detect(sub_dir)
                if sub_info.mode == TaskMode.EXISTING_PROJECT and sub_info.indicators_found:
                    sub_info.is_nested = True
                    return sub_info

        if not indicators_found and len(all_files) == 0:
            return ProjectInfo(
                mode=TaskMode.NEW_PROJECT,
                project_type="unknown",
                root_dir=str(path),
                has_git=has_git,
                total_files=0,
            )

        if not indicators_found and len(all_files) > 0:
            # Folder has files but no standard build/project manifest
            return ProjectInfo(
                mode=TaskMode.EXISTING_PROJECT,
                project_type="generic_codebase",
                root_dir=str(path),
                indicators_found=[],
                has_git=has_git,
                total_files=len(all_files),
            )

        # Primary ecosystem determination
        primary_type = "generic_codebase"
        for candidate in ["nodejs", "python", "flutter", "rust", "golang", "java", "dotnet", "php", "ruby", "cpp"]:
            if candidate in detected_types:
                primary_type = candidate
                break

        # Subtype and dependency analysis
        sub_type = None
        deps: dict[str, str] = {}
        dev_deps: dict[str, str] = {}
        scripts: dict[str, str] = {}
        entry_points: list[str] = []

        if primary_type == "nodejs" and (path / "package.json").exists():
            try:
                pkg_data = json.loads((path / "package.json").read_text(encoding="utf-8"))
                deps = pkg_data.get("dependencies", {})
                dev_deps = pkg_data.get("devDependencies", {})
                scripts = pkg_data.get("scripts", {})

                all_deps = {**deps, **dev_deps}
                if "react-native" in all_deps:
                    sub_type = "react-native"
                elif "react" in all_deps:
                    sub_type = "react"
                elif "next" in all_deps:
                    sub_type = "nextjs"
                elif "vue" in all_deps:
                    sub_type = "vue"
                elif "express" in all_deps:
                    sub_type = "express"

                for ep in [
                    "src/main.tsx", "src/main.ts", "src/index.tsx", "src/index.ts",
                    "src/App.tsx", "App.tsx", "App.js", "index.js", "server.js", "src/index.js"
                ]:
                    if (path / ep).exists():
                        entry_points.append(ep)

            except Exception:
                pass

        elif primary_type == "python":
            if (path / "requirements.txt").exists():
                try:
                    req_text = (path / "requirements.txt").read_text(encoding="utf-8").lower()
                    if "fastapi" in req_text:
                        sub_type = "fastapi"
                    elif "django" in req_text:
                        sub_type = "django"
                    elif "flask" in req_text:
                        sub_type = "flask"
                except Exception:
                    pass

            for ep in ["main.py", "app.py", "src/main.py", "server.py", "manage.py"]:
                if (path / ep).exists():
                    entry_points.append(ep)

        elif primary_type == "flutter":
            # Check if standalone Dart or Flutter
            pubspec_txt = (path / "pubspec.yaml").read_text(encoding="utf-8", errors="replace").lower()
            if "sdk: flutter" not in pubspec_txt and "flutter:" not in pubspec_txt:
                primary_type = "dart"

            for ep in ["lib/main.dart", "bin/main.dart"]:
                if (path / ep).exists():
                    entry_points.append(ep)

        elif primary_type == "java":
            if (path / "pom.xml").exists():
                sub_type = "maven"
            elif (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
                sub_type = "gradle"

        return ProjectInfo(
            mode=TaskMode.EXISTING_PROJECT,
            project_type=primary_type,
            sub_type=sub_type,
            root_dir=str(path),
            indicators_found=indicators_found,
            entry_points=entry_points,
            dependencies=deps,
            dev_dependencies=dev_deps,
            scripts=scripts,
            has_git=has_git,
            total_files=len(all_files),
        )
