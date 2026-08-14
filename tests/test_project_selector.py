"""
Unit tests for CLI ProjectSelector.
"""

from unittest.mock import MagicMock, patch

import pytest
from src.cli.project_selector import ProjectSelector
from src.workspace.models import Project, WorkspaceRoot
from src.workspace.registry import ProjectRegistry, WorkspaceRegistry
from src.workspace.scanner import ProjectScanner


@pytest.fixture
def selector_fixture():
    ws_reg = MagicMock(spec=WorkspaceRegistry)
    ws_reg.list_workspaces.return_value = [
        WorkspaceRoot(path="E:/Work", name="Work"),
        WorkspaceRoot(path="E:/Projects", name="Projects"),
    ]

    p1 = Project(
        id="p1",
        name="FinanceFlow",
        path="E:/Work/FinanceFlow",
        project_type="nodejs",
        sub_type="react-native",
        git_repository_present=True,
    )
    p2 = Project(
        id="p2",
        name="PythonTool",
        path="E:/Work/PythonTool",
        project_type="python",
        git_repository_present=False,
    )

    proj_reg = ProjectRegistry()
    proj_reg.add_or_update(p1)
    proj_reg.add_or_update(p2)

    scanner = MagicMock(spec=ProjectScanner)
    scanner.scan.return_value = [p1, p2]

    selector = ProjectSelector(
        workspace_registry=ws_reg,
        project_registry=proj_reg,
        scanner=scanner,
    )
    return selector, p1, p2


def test_project_selector_renders_menu(selector_fixture):
    selector, p1, p2 = selector_fixture
    # Verify render_menu executes cleanly with rich console
    selector.render_menu([p1, p2])


def test_project_selector_select_valid_project(selector_fixture):
    selector, p1, p2 = selector_fixture
    # Simulate user entering "1"
    with patch("rich.prompt.Prompt.ask", side_effect=["1"]):
        chosen = selector.run_interactive(initial_scan=False)
        assert chosen is not None
        assert chosen.name in ["FinanceFlow", "PythonTool"]


def test_project_selector_user_quits(selector_fixture):
    selector, _, _ = selector_fixture
    # Simulate user entering "Q"
    with patch("rich.prompt.Prompt.ask", side_effect=["Q"]):
        chosen = selector.run_interactive(initial_scan=False)
        assert chosen is None
