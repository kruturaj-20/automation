"""
Unit tests for strengthened TaskVerifier.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from src.planner.models import Goal
from src.security.security_guard import SecurityGuard
from src.verifier.verifier import TaskVerifier, VerificationResult


@pytest.fixture
def temp_ws():
    d = tempfile.mkdtemp(prefix="verifier_test_ws_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_verifier_runs_pytest_when_tests_exist(temp_ws):
    (temp_ws / "main.py").write_text("def add(a, b):\n    return a + b\n")
    (temp_ws / "test_main.py").write_text("from main import add\ndef test_add():\n    assert add(1, 2) == 3\n")

    goal = Goal(raw_instruction="Add add function", summary="Add function")
    guard = SecurityGuard()
    guard.allowed_roots.append(temp_ws)

    res = await TaskVerifier.verify(goal, temp_ws, security_guard=guard)
    assert res.passed is True
    assert res.verification_type == "test_suite"
    assert "pytest" in res.details.lower()


@pytest.mark.asyncio
async def test_verifier_detects_failing_pytest(temp_ws):
    (temp_ws / "main.py").write_text("def add(a, b):\n    return a - b\n")  # Intentional bug
    (temp_ws / "test_main.py").write_text("from main import add\ndef test_add():\n    assert add(1, 2) == 3\n")

    goal = Goal(raw_instruction="Add add function", summary="Add function")
    guard = SecurityGuard()
    guard.allowed_roots.append(temp_ws)

    res = await TaskVerifier.verify(goal, temp_ws, security_guard=guard)
    assert res.passed is False
    assert res.verification_type == "test_suite"
    assert len(res.errors) > 0


@pytest.mark.asyncio
async def test_verifier_runs_entrypoint_when_no_tests(temp_ws):
    (temp_ws / "main.py").write_text("print('Hello from entrypoint')\n")

    goal = Goal(raw_instruction="Print hello", summary="Print hello")
    guard = SecurityGuard()
    guard.allowed_roots.append(temp_ws)

    res = await TaskVerifier.verify(goal, temp_ws, security_guard=guard)
    assert res.passed is True
    assert res.verification_type == "entrypoint_execution"


@pytest.mark.asyncio
async def test_verifier_detects_syntax_errors(temp_ws):
    (temp_ws / "helper.py").write_text("def broken(\n")  # Syntax error

    goal = Goal(raw_instruction="Fix syntax", summary="Fix syntax")
    guard = SecurityGuard()
    guard.allowed_roots.append(temp_ws)

    res = await TaskVerifier.verify(goal, temp_ws, security_guard=guard)
    assert res.passed is False
    assert res.verification_type == "syntax_check"
