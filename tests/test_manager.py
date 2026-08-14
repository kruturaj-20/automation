"""
Unit tests for AgentManager: Mode 1 vs Mode 2 workflows and orchestration loop.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.config import AgentConfig, SecurityConfig
from src.core.manager import AgentManager
from src.core.state import TaskMode, TaskPhase
from src.ide.base import IDEAgentAdapter
from src.ide.models import ChangeType, FileChange, TaskResult, TaskStatus
from src.llm.base import LLMProvider
from src.planner.models import Approach
from src.verifier.verifier import VerificationResult


@pytest.fixture
def temp_workspace():
    d = tempfile.mkdtemp(prefix="mgr_test_ws_")
    # Place it inside an allowed path for test
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_manager_mode2_new_project_flow(temp_workspace, monkeypatch):
    # Empty workspace -> Mode 2 (New Project)
    mock_ide = MagicMock(spec=IDEAgentAdapter)
    mock_ide.start_task = AsyncMock(return_value="task-001")
    mock_ide.wait_for_completion = AsyncMock(return_value=TaskResult(status=TaskStatus.COMPLETED, duration_seconds=1.5))
    mock_ide.get_changed_files = AsyncMock(return_value=[
        FileChange(path=str(temp_workspace / "index.html"), change_type=ChangeType.CREATED)
    ])

    mock_llm = MagicMock(spec=LLMProvider)
    mock_llm.plan_architecture = AsyncMock(return_value=Approach(
        architecture_overview="Vanilla HTML5 app",
        suggested_tech_stack=["HTML5"],
        implementation_guidelines=["Create index.html"],
    ))

    monkeypatch.setattr(
        "src.verifier.verifier.TaskVerifier.verify",
        AsyncMock(return_value=VerificationResult(passed=True, details="HTML valid"))
    )

    config = AgentConfig()
    config.security.allowed_dirs = [str(temp_workspace.parent)]

    manager = AgentManager(
        ide_agent=mock_ide,
        llm=mock_llm,
        config=config,
    )

    summary = await manager.execute_task(
        instruction="Create a simple HTML page",
        workspace_dir=temp_workspace,
    )

    assert summary.mode == TaskMode.NEW_PROJECT
    assert summary.phase == TaskPhase.COMPLETED
    assert summary.verification_passed is True
    assert len(summary.files_created) == 1
    # In Mode 2, external LLM was consulted for architecture
    assert mock_llm.plan_architecture.call_count == 1
    # IDE AI executed the implementation
    assert mock_ide.start_task.call_count == 1


@pytest.mark.asyncio
async def test_manager_mode1_existing_project_flow(temp_workspace, monkeypatch):
    # Create indicator file -> Mode 1 (Existing Project)
    (temp_workspace / "package.json").write_text('{"name": "existing-app", "dependencies": {"react": "^18.0.0"}}')
    src_dir = temp_workspace / "src"
    src_dir.mkdir()
    (src_dir / "App.tsx").write_text("export default function App() {}")

    mock_ide = MagicMock(spec=IDEAgentAdapter)
    mock_ide.start_task = AsyncMock(return_value="task-002")
    mock_ide.wait_for_completion = AsyncMock(return_value=TaskResult(status=TaskStatus.COMPLETED, duration_seconds=2.0))
    mock_ide.get_changed_files = AsyncMock(return_value=[
        FileChange(path=str(src_dir / "Button.tsx"), change_type=ChangeType.CREATED),
        FileChange(path=str(src_dir / "App.tsx"), change_type=ChangeType.MODIFIED),
    ])

    mock_llm = MagicMock(spec=LLMProvider)

    monkeypatch.setattr(
        "src.verifier.verifier.TaskVerifier.verify",
        AsyncMock(return_value=VerificationResult(passed=True, details="React build passes"))
    )

    config = AgentConfig()
    config.security.allowed_dirs = [str(temp_workspace.parent)]

    manager = AgentManager(
        ide_agent=mock_ide,
        llm=mock_llm,
        config=config,
    )

    summary = await manager.execute_task(
        instruction="Add a Button component to the React app",
        workspace_dir=temp_workspace,
    )

    assert summary.mode == TaskMode.EXISTING_PROJECT
    assert summary.phase == TaskPhase.COMPLETED
    assert summary.verification_passed is True
    assert len(summary.files_created) == 1
    assert len(summary.files_modified) == 1
    # In Mode 1, external LLM is NOT consulted for architecture (brief grounded in codebase)
    assert mock_llm.plan_architecture.call_count == 0
    # IDE AI executed the implementation
    assert mock_ide.start_task.call_count == 1


@pytest.mark.asyncio
async def test_manager_blocks_unauthorized_paths(temp_workspace):
    mock_ide = MagicMock(spec=IDEAgentAdapter)
    mock_llm = MagicMock(spec=LLMProvider)

    config = AgentConfig()
    config.security.allowed_dirs = ["e:/Work/OnlyThisDir"]

    manager = AgentManager(
        ide_agent=mock_ide,
        llm=mock_llm,
        config=config,
    )

    summary = await manager.execute_task(
        instruction="Task in illegal path",
        workspace_dir="c:/Windows/System32",
    )

    assert summary.phase == TaskPhase.FAILED
    assert "OUTSIDE approved workspace boundaries" in summary.error_message
    assert mock_ide.start_task.call_count == 0
