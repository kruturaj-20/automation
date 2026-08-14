"""
Unit tests for WorkspaceRegistry.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from src.core.config import AgentConfig, SecurityConfig
from src.security.security_guard import SecurityGuard
from src.workspace.registry import WorkspaceRegistry


@pytest.fixture
def temp_env():
    root1 = tempfile.mkdtemp(prefix="ws_reg_root1_")
    root2 = tempfile.mkdtemp(prefix="ws_reg_root2_")
    cfg = AgentConfig()
    cfg.projects.allowed_dirs = [root1]
    cfg.security.allowed_dirs = [root1]
    guard = SecurityGuard(cfg.security)

    registry = WorkspaceRegistry(config=cfg, security_guard=guard)
    yield Path(root1), Path(root2), registry
    shutil.rmtree(root1, ignore_errors=True)
    shutil.rmtree(root2, ignore_errors=True)


def test_workspace_registry_initial_workspaces(temp_env):
    root1, _, registry = temp_env
    workspaces = registry.list_workspaces()
    assert len(workspaces) >= 1
    assert str(root1.resolve()) in [ws.path for ws in workspaces]


def test_workspace_registry_add_valid_workspace(temp_env):
    _, root2, registry = temp_env
    ok, msg = registry.add_workspace(root2, name="Projects Root")
    assert ok is True
    assert "Added workspace" in msg
    assert str(root2.resolve()) in [ws.path for ws in registry.list_workspaces()]
    assert registry.is_path_approved(root2 / "subproject") is True


def test_workspace_registry_rejects_nonexistent_directory(temp_env):
    _, _, registry = temp_env
    non_existent = "e:/NonExistentPath_12345/FooBar"
    ok, msg = registry.add_workspace(non_existent)
    assert ok is False
    assert "does not exist" in msg


def test_workspace_registry_rejects_system_directory(temp_env):
    _, _, registry = temp_env
    system_dir = "C:/Windows/System32"
    ok, msg = registry.add_workspace(system_dir)
    assert ok is False
    assert "System directories cannot be added" in msg or "does not exist" in msg


def test_workspace_registry_remove_workspace(temp_env):
    root1, root2, registry = temp_env
    registry.add_workspace(root2, name="SecondRoot")
    assert len(registry.list_workspaces()) == 2

    # Remove by name
    removed = registry.remove_workspace("SecondRoot")
    assert removed is True
    assert len(registry.list_workspaces()) == 1
    assert str(root2.resolve()) not in [ws.path for ws in registry.list_workspaces()]
