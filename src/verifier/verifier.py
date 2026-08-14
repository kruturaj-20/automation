"""
Independent Task Verifier.

Executes build/test/syntax checks independently of the IDE AI agent to confirm
the code actually works and fulfills the user's requirements.

INVARIANT:
py_compile alone is NOT sufficient verification. The verifier must execute actual
project-appropriate tests/build commands where available.
Commands are passed through SecurityGuard for safety validation.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.planner.models import Goal, ProjectContext
from src.security.security_guard import SecurityGuard


@dataclass
class VerificationResult:
    """Outcome of an independent verification check."""

    passed: bool
    command_run: str = ""
    exit_code: Optional[int] = None
    output: str = ""
    errors: list[str] = field(default_factory=list)
    details: str = ""
    verification_type: str = "unknown"  # "test_suite", "build_command", "entrypoint_execution", "syntax_check", "static_dom"


class TaskVerifier:
    """Runs independent, project-aware verification commands against the workspace."""

    @classmethod
    async def verify(
        cls,
        goal: Goal,
        working_dir: str | Path,
        context: Optional[ProjectContext] = None,
        security_guard: Optional[SecurityGuard] = None,
    ) -> VerificationResult:
        work_path = Path(working_dir)

        if not work_path.exists():
            return VerificationResult(
                passed=False,
                errors=[f"Working directory does not exist: {work_path}"],
                verification_type="none",
            )

        guard = security_guard or SecurityGuard(None)

        # 1. Node.js project verification
        if (work_path / "package.json").exists():
            return await cls._verify_nodejs(work_path, guard)

        # 2. Python project verification
        elif (work_path / "requirements.txt").exists() or (work_path / "pyproject.toml").exists() or any(work_path.glob("*.py")):
            return await cls._verify_python(work_path, guard)

        # 3. Rust project verification
        elif (work_path / "Cargo.toml").exists():
            return await cls._verify_rust(work_path, guard)

        # 4. Flutter / Dart verification
        elif (work_path / "pubspec.yaml").exists():
            return await cls._verify_flutter(work_path, guard)

        # 5. Java / Kotlin verification
        elif (work_path / "pom.xml").exists() or (work_path / "build.gradle").exists() or (work_path / "build.gradle.kts").exists():
            return await cls._verify_java(work_path, guard)

        # 6. Static HTML / Frontend verification
        return await cls._verify_static_html(work_path, goal)

    @classmethod
    async def _verify_nodejs(cls, work_path: Path, guard: SecurityGuard) -> VerificationResult:
        """Run npm test or npm run build if configured in package.json."""
        pkg_json = work_path / "package.json"
        scripts: dict[str, str] = {}
        try:
            pkg_data = json.loads(pkg_json.read_text(encoding="utf-8"))
            scripts = pkg_data.get("scripts", {})
        except Exception:
            pass

        # If test script is defined, run npm test
        if "test" in scripts and (work_path / "node_modules").exists():
            cmd = "npm test"
            res = await cls._run_subprocess(cmd, work_path, guard)
            res.verification_type = "test_suite"
            return res

        # If build script is defined, run npm run build
        if "build" in scripts and (work_path / "node_modules").exists():
            cmd = "npm run build"
            res = await cls._run_subprocess(cmd, work_path, guard)
            res.verification_type = "build_command"
            return res

        # Check for entry points
        has_entry = (
            (work_path / "index.html").exists()
            or (work_path / "src" / "App.tsx").exists()
            or (work_path / "src" / "index.ts").exists()
            or (work_path / "index.js").exists()
        )
        if not has_entry:
            return VerificationResult(
                passed=False,
                errors=["No entry point (index.html, src/App.tsx, index.js) found in Node project."],
                verification_type="structure_check",
            )

        return VerificationResult(
            passed=True,
            details="Node.js project structure, manifests, and entry points verified.",
            verification_type="structure_check",
        )

    @classmethod
    async def _verify_python(cls, work_path: Path, guard: SecurityGuard) -> VerificationResult:
        """
        Verify Python project:
        - If test files exist (test_*.py, *_test.py, tests/): run `pytest`
        - Else if main.py exists: run `python main.py` execution test
        - Else: run `py_compile` syntax compilation
        """
        test_files = [
            f for f in work_path.rglob("*.py")
            if (f.name.startswith("test_") or f.name.endswith("_test.py") or "tests" in f.parts)
            and not any(part in ("venv", ".venv", "__pycache__") for part in f.parts)
        ]

        # 1. Run actual unit tests if test files exist
        if test_files:
            cmd = f'"{sys.executable}" -m pytest "{work_path}" -v'
            res = await cls._run_subprocess(cmd, work_path, guard)
            res.verification_type = "test_suite"
            if res.passed:
                res.details = f"Unit test suite passed cleanly with pytest ({len(test_files)} test file(s))."
            return res

        # 2. If main.py or app.py exists, test execution
        entrypoints = [f for f in [work_path / "main.py", work_path / "app.py"] if f.exists()]
        if entrypoints:
            target_entry = entrypoints[0]
            cmd = f'"{sys.executable}" "{target_entry.name}"'
            res = await cls._run_subprocess(cmd, work_path, guard, timeout=10)
            res.verification_type = "entrypoint_execution"
            if res.passed:
                res.details = f"Entrypoint '{target_entry.name}' executed successfully without errors."
            return res

        # 3. Syntax compilation check
        py_files = [
            f for f in work_path.rglob("*.py")
            if not any(part in ("venv", ".venv", "__pycache__") for part in f.parts)
        ]
        if not py_files:
            return VerificationResult(
                passed=False,
                errors=["No Python source files found in workspace."],
                verification_type="none",
            )

        errors = []
        for py_file in py_files:
            cmd = f'"{sys.executable}" -m py_compile "{py_file}"'
            res = await cls._run_subprocess(cmd, work_path, guard)
            if not res.passed:
                errors.append(f"Syntax error in {py_file.name}: {res.output}")

        if errors:
            return VerificationResult(
                passed=False,
                errors=errors,
                verification_type="syntax_check",
            )

        return VerificationResult(
            passed=True,
            details=f"Python syntax compilation verified across {len(py_files)} file(s).",
            verification_type="syntax_check",
        )

    @classmethod
    async def _verify_rust(cls, work_path: Path, guard: SecurityGuard) -> VerificationResult:
        res = await cls._run_subprocess("cargo check", work_path, guard)
        res.verification_type = "build_command"
        return res

    @classmethod
    async def _verify_flutter(cls, work_path: Path, guard: SecurityGuard) -> VerificationResult:
        res = await cls._run_subprocess("flutter analyze", work_path, guard)
        res.verification_type = "build_command"
        return res

    @classmethod
    async def _verify_java(cls, work_path: Path, guard: SecurityGuard) -> VerificationResult:
        if (work_path / "pom.xml").exists():
            res = await cls._run_subprocess("mvn test-compile", work_path, guard)
            res.verification_type = "build_command"
            return res
        elif (work_path / "build.gradle").exists() or (work_path / "build.gradle.kts").exists():
            res = await cls._run_subprocess("gradle testClasses", work_path, guard)
            res.verification_type = "build_command"
            return res
        return VerificationResult(passed=True, details="Java manifests detected and verified.", verification_type="structure_check")

    @classmethod
    async def _verify_static_html(cls, work_path: Path, goal: Goal) -> VerificationResult:
        """Verify HTML/web project files and markup."""
        html_files = list(work_path.glob("*.html"))
        if not html_files:
            all_files = [f for f in work_path.iterdir() if f.is_file()]
            if all_files:
                return VerificationResult(
                    passed=True,
                    details=f"Workspace populated with {len(all_files)} file(s).",
                    verification_type="structure_check",
                )
            return VerificationResult(
                passed=False,
                errors=["No files generated in workspace."],
                verification_type="none",
            )

        first_html = html_files[0]
        content = first_html.read_text(encoding="utf-8", errors="replace").lower()
        if not ("<html" in content or "<!doctype" in content or "<body" in content):
            return VerificationResult(
                passed=False,
                errors=[f"{first_html.name} does not contain valid HTML markup."],
                verification_type="static_dom",
            )

        return VerificationResult(
            passed=True,
            details=f"HTML structure in '{first_html.name}' confirmed.",
            verification_type="static_dom",
        )

    @classmethod
    async def _run_subprocess(
        cls,
        command: str,
        cwd: Path,
        guard: Optional[SecurityGuard] = None,
        timeout: int = 60,
    ) -> VerificationResult:
        if guard:
            safe, reason = guard.validate_command(command, cwd=cwd)
            if not safe:
                return VerificationResult(
                    passed=False,
                    command_run=command,
                    errors=[f"SecurityGuard blocked command: {reason}"],
                    verification_type="security_blocked",
                )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out_str = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
            passed = (proc.returncode == 0)
            errors = [out_str.strip()] if not passed else []
            return VerificationResult(
                passed=passed,
                command_run=command,
                exit_code=proc.returncode,
                output=out_str.strip(),
                errors=errors,
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                command_run=command,
                errors=[str(e)],
            )
