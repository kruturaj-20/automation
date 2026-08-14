"""
Unit tests for AntigravityAdapter and IDEAgentAdapter interface contract.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest
from src.ide.antigravity import AntigravityAdapter
from src.ide.base import IDEAgentAdapter
from src.ide.models import ChangeType, FileChange, TaskEvent, TaskRequest, TaskStatus


@pytest.fixture
def adapter():
    return AntigravityAdapter()


@pytest.mark.asyncio
async def test_adapter_interface_compliance(adapter):
    assert isinstance(adapter, IDEAgentAdapter)
    info = await adapter.get_adapter_info()
    assert info["name"] == "AntigravityAdapter"
    assert "capabilities" in info
    assert info["capabilities"]["start_task"] is True
    assert info["capabilities"]["stop_task"] is True


@pytest.mark.asyncio
async def test_file_change_detection():
    tmpdir = tempfile.mkdtemp(prefix="test_changes_")
    try:
        adapter = AntigravityAdapter()
        req = TaskRequest(
            instruction="Test file changes",
            working_dir=tmpdir,
            timeout_seconds=5,
        )
        task_id = await adapter.start_task(req)

        # Create a file in the workspace
        f1 = Path(tmpdir) / "test.txt"
        f1.write_text("hello world")

        changes = await adapter.get_changed_files(task_id)
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.CREATED
        assert Path(changes[0].path).name == "test.txt"

        await adapter.stop_task(task_id)
        await asyncio.sleep(0.2)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_stop_task_lifecycle():
    tmpdir = tempfile.mkdtemp(prefix="test_stop_")
    try:
        adapter = AntigravityAdapter()
        req = TaskRequest(
            instruction="Task to abort",
            working_dir=tmpdir,
            timeout_seconds=60,
        )
        task_id = await adapter.start_task(req)
        await asyncio.sleep(0.1)

        result = await adapter.stop_task(task_id)
        assert result.status in (TaskStatus.STOPPED, TaskStatus.FAILED, TaskStatus.COMPLETED)
        assert result.was_stopped is True or result.status == TaskStatus.STOPPED
        await asyncio.sleep(0.3)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
