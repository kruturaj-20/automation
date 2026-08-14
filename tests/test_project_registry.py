"""
Unit tests for ProjectRegistry.
"""

from src.workspace.models import Project
from src.workspace.registry import ProjectRegistry


def test_project_registry_operations():
    reg = ProjectRegistry()

    p1 = Project(
        id="proj-001",
        name="FinanceFlow",
        path="E:/Work/FinanceFlow",
        project_type="nodejs",
        sub_type="react-native",
        detected_indicators=["package.json"],
    )
    p2 = Project(
        id="proj-002",
        name="NeuroStack",
        path="E:/Work/NeuroStack",
        project_type="python",
        detected_indicators=["pyproject.toml"],
    )

    reg.add_or_update(p1)
    reg.add_or_update(p2)

    assert len(reg.list_projects()) == 2

    # Lookup by ID
    assert reg.get_by_id("proj-001") == p1
    # Lookup by 1-based numeric index
    assert reg.get_by_id("1") in [p1, p2]

    # Lookup by path
    found = reg.get_by_path("E:\\Work\\FinanceFlow")
    assert found is not None
    assert found.name == "FinanceFlow"

    # Stale removal
    reg.remove_stale_projects(existing_paths={"E:/Work/FinanceFlow"})
    # p2 does not exist on disk, so it should be pruned
    assert reg.get_by_id("proj-002") is None
    assert len(reg.list_projects()) == 1
