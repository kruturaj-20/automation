"""
Unit tests for ErrorHandler strict 3-tier escalation logic.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.state import TaskMode
from src.errors.handler import ErrorHandler, ErrorResolution
from src.ide.base import IDEAgentAdapter
from src.ide.models import TaskResult, TaskStatus
from src.llm.base import ErrorAnalysis, LLMProvider
from src.planner.models import Goal, ProjectContext
from src.verifier.verifier import VerificationResult


@pytest.mark.asyncio
async def test_ide_ai_fixes_error_on_first_attempt(monkeypatch):
    mock_ide = MagicMock(spec=IDEAgentAdapter)
    mock_ide.start_task = AsyncMock(return_value="task-123")
    mock_ide.wait_for_completion = AsyncMock(return_value=TaskResult(status=TaskStatus.COMPLETED, exit_code=0))

    mock_llm = MagicMock(spec=LLMProvider)

    # Mock TaskVerifier.verify to succeed on the first fix attempt
    monkeypatch.setattr(
        "src.verifier.verifier.TaskVerifier.verify",
        AsyncMock(return_value=VerificationResult(passed=True, details="Fixed!"))
    )

    goal = Goal(raw_instruction="Fix button", summary="Fix button")
    context = ProjectContext(mode=TaskMode.EXISTING_PROJECT, root_dir=".", project_type="python")

    resolution = await ErrorHandler.handle_errors(
        initial_errors=["SyntaxError: invalid syntax"],
        goal=goal,
        context=context,
        ide_agent=mock_ide,
        llm=mock_llm,
    )

    assert resolution.resolved is True
    assert resolution.resolved_by == "ide_ai_attempt_1"
    assert resolution.total_attempts == 1
    # External LLM should NOT have been called because IDE AI fixed it immediately
    assert mock_llm.analyze_error.call_count == 0


@pytest.mark.asyncio
async def test_escalation_to_external_llm_when_ide_ai_fails(monkeypatch):
    mock_ide = MagicMock(spec=IDEAgentAdapter)
    mock_ide.start_task = AsyncMock(return_value="task-123")
    mock_ide.wait_for_completion = AsyncMock(return_value=TaskResult(status=TaskStatus.COMPLETED, exit_code=0))

    mock_llm = MagicMock(spec=LLMProvider)
    mock_llm.analyze_error = AsyncMock(
        return_value=ErrorAnalysis(
            root_cause="Missing package export",
            recommended_fix="Export function in index.ts",
            code_modifications_summary="export { Button }",
        )
    )

    # Fail first 2 attempts (IDE AI tier 1 & 2), pass on 3rd attempt (LLM guided)
    verify_mock = AsyncMock(side_effect=[
        VerificationResult(passed=False, errors=["Fail 1"]),
        VerificationResult(passed=False, errors=["Fail 2"]),
        VerificationResult(passed=True, details="Passed after LLM guidance"),
    ])
    monkeypatch.setattr("src.verifier.verifier.TaskVerifier.verify", verify_mock)

    goal = Goal(raw_instruction="Build module", summary="Build module")
    context = ProjectContext(mode=TaskMode.EXISTING_PROJECT, root_dir=".", project_type="nodejs")

    resolution = await ErrorHandler.handle_errors(
        initial_errors=["Build failure"],
        goal=goal,
        context=context,
        ide_agent=mock_ide,
        llm=mock_llm,
    )

    assert resolution.resolved is True
    assert resolution.resolved_by == "llm_guided_ide_ai"
    assert resolution.total_attempts == 3
    # External LLM was called after IDE AI attempts failed
    assert mock_llm.analyze_error.call_count == 1
    # IDE AI executed all 3 implementation attempts
    assert mock_ide.start_task.call_count == 3
