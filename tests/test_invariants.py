"""
Architectural Invariant Tests.

PROVES:
1. AI Manager NEVER creates, modifies, or writes application source files (.py, .ts, package.json, etc.).
2. External LLM Provider has ZERO filesystem mutation methods or write capabilities.
3. IDE Abstraction: AI Manager communicates strictly via IDEAgentAdapter, enabling pluggable IDEs without changing manager code.
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
from src.ide.models import TaskRequest, TaskResult, TaskStatus
from src.llm.base import ErrorAnalysis, LLMProvider
from src.planner.models import Approach, Goal, ProjectContext


@pytest.fixture
def temp_ws():
    d = tempfile.mkdtemp(prefix="invariant_test_ws_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


class CustomTestIDEAdapter(IDEAgentAdapter):
    """A mock IDE adapter representing future IDEs (e.g. VS Code, Cursor, Kiro)."""

    def __init__(self):
        self.started_tasks = []

    async def start_task(self, request: TaskRequest) -> str:
        self.started_tasks.append(request)
        return "custom-ide-task-001"

    async def send_followup(self, task_id: str, message: str) -> None:
        pass

    async def get_status(self, task_id: str) -> TaskStatus:
        return TaskStatus.COMPLETED

    async def get_events(self, task_id: str):
        return []

    async def stream_events(self, task_id: str):
        if False:
            yield

    async def get_output(self, task_id: str) -> str:
        return "Custom IDE completed task."

    async def get_changed_files(self, task_id: str):
        return []

    async def get_diagnostics(self, task_id: str):
        return []

    async def wait_for_completion(self, task_id: str, timeout_seconds=None) -> TaskResult:
        return TaskResult(status=TaskStatus.COMPLETED, exit_code=0, output="Custom IDE success")

    async def stop_task(self, task_id: str) -> TaskResult:
        return TaskResult(status=TaskStatus.STOPPED)

    async def is_available(self) -> bool:
        return True

    async def get_adapter_info(self) -> dict:
        return {"name": "CustomTestIDEAdapter", "version": "1.0.0"}


@pytest.mark.asyncio
async def test_invariant_manager_never_creates_application_files(temp_ws, monkeypatch):
    """
    PROVES: AI Manager creates ONLY workspace root and .agent_meta metadata dir.
    Manager MUST NOT create application files (.py, .ts, package.json, etc.).
    """
    custom_ide = CustomTestIDEAdapter()
    mock_llm = MagicMock(spec=LLMProvider)
    mock_llm.plan_architecture = AsyncMock(return_value=Approach(
        architecture_overview="Python app architecture",
        suggested_tech_stack=["Python"],
    ))

    # Mock TaskVerifier to succeed
    monkeypatch.setattr(
        "src.verifier.verifier.TaskVerifier.verify",
        AsyncMock(return_value=MagicMock(passed=True, details="OK", verification_type="mock"))
    )

    config = AgentConfig()
    config.security.allowed_dirs = [str(temp_ws.parent)]

    manager = AgentManager(
        ide_agent=custom_ide,
        llm=mock_llm,
        config=config,
    )

    summary = await manager.execute_task(
        instruction="Create a python app",
        workspace_dir=temp_ws,
    )

    # Inspect all files created in the workspace
    created_items = list(temp_ws.rglob("*"))
    app_extensions = [".py", ".js", ".ts", ".tsx", ".jsx", ".dart", ".java", ".go", ".rs", ".cs", ".html"]
    app_manifests = ["package.json", "pubspec.yaml", "requirements.txt", "pom.xml", "Cargo.toml"]

    for item in created_items:
        if item.is_file():
            # Assert no application code or manifests were created by Manager
            assert item.suffix.lower() not in app_extensions, f"Manager directly created application file: {item}"
            assert item.name not in app_manifests, f"Manager directly created manifest: {item}"

    # Only .agent_meta directory or internal logs may exist
    for item in created_items:
        if item.is_dir():
            assert item.name == ".agent_meta" or item.name == temp_ws.name


@pytest.mark.asyncio
async def test_invariant_external_llm_zero_filesystem_access(temp_ws):
    """
    PROVES: LLMProvider implementations have zero filesystem write APIs.
    Calling plan_architecture or analyze_error modifies zero workspace files.
    """
    from src.llm.gemini_provider import GeminiProvider

    # Count files before
    files_before = set(temp_ws.rglob("*"))

    llm = GeminiProvider(api_key="fake-key-for-isolation-test")
    # Verify class has no write methods
    forbidden_methods = ["write_file", "create_file", "modify_file", "delete_file", "save", "execute_command"]
    for m in forbidden_methods:
        assert not hasattr(llm, m), f"LLMProvider unexpectedly has filesystem write method: {m}"

    goal = Goal(raw_instruction="Architecture idea", summary="idea")
    context = ProjectContext(mode=TaskMode.NEW_PROJECT, root_dir=str(temp_ws), project_type="unknown")

    # Run planning
    approach = await llm.plan_architecture(goal, context)
    assert isinstance(approach, Approach)

    # Verify zero files modified or created by LLM
    files_after = set(temp_ws.rglob("*"))
    assert files_before == files_after, "External LLM unexpectedly mutated workspace filesystem!"


@pytest.mark.asyncio
async def test_invariant_ide_abstraction_allows_pluggable_ides(temp_ws, monkeypatch):
    """
    PROVES: AI Manager communicates strictly via IDEAgentAdapter.
    Any new IDE (VS Code, Cursor, Kiro, etc.) can be plugged in without changing Manager code.
    """
    custom_ide = CustomTestIDEAdapter()
    mock_llm = MagicMock(spec=LLMProvider)
    mock_llm.plan_architecture = AsyncMock(return_value=Approach(
        architecture_overview="Pluggable architecture",
        suggested_tech_stack=["Rust"],
    ))

    monkeypatch.setattr(
        "src.verifier.verifier.TaskVerifier.verify",
        AsyncMock(return_value=MagicMock(passed=True, details="Verified", verification_type="mock"))
    )

    config = AgentConfig()
    config.security.allowed_dirs = [str(temp_ws.parent)]

    manager = AgentManager(
        ide_agent=custom_ide,
        llm=mock_llm,
        config=config,
    )

    summary = await manager.execute_task(
        instruction="Build high performance Rust service",
        workspace_dir=temp_ws,
    )

    assert summary.phase == TaskPhase.COMPLETED
    assert len(custom_ide.started_tasks) == 1
    assert "Rust" in custom_ide.started_tasks[0].instruction
