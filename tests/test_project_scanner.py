"""
Unit tests for ProjectScanner.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from src.core.config import AgentConfig
from src.security.security_guard import SecurityGuard
from src.workspace.registry import ProjectRegistry, WorkspaceRegistry
from src.workspace.scanner import ProjectScanner


@pytest.fixture
def scanner_env():
    root = tempfile.mkdtemp(prefix="scanner_root_")
    root_path = Path(root)

    # 1. Seed Python project
    py_dir = root_path / "PythonTool"
    py_dir.mkdir()
    (py_dir / "pyproject.toml").write_text('[project]\nname = "python-tool"\nversion = "0.1.0"\n')
    (py_dir / "main.py").write_text("print('Hello Python')\n")
    (py_dir / ".git").mkdir()  # Git repository present

    # 2. Seed Node / React Native project
    rn_dir = root_path / "FinanceFlow"
    rn_dir.mkdir()
    (rn_dir / "package.json").write_text('{"name": "finance-flow", "dependencies": {"react-native": "^0.73.0"}}')
    (rn_dir / "App.tsx").write_text("export default function App() {}")
    (rn_dir / "node_modules").mkdir()
    (rn_dir / "node_modules" / "fake_dep").mkdir()
    (rn_dir / "node_modules" / "fake_dep" / "package.json").write_text('{"name": "fake"}')

    # 3. Seed Flutter project
    fl_dir = root_path / "MobileApp"
    fl_dir.mkdir()
    (fl_dir / "pubspec.yaml").write_text("name: mobile_app\ndependencies:\n  flutter:\n    sdk: flutter\n")
    (fl_dir / "lib").mkdir()
    (fl_dir / "lib" / "main.dart").write_text("void main() {}")

    # 4. Seed Java project
    java_dir = root_path / "JavaBackend"
    java_dir.mkdir()
    (java_dir / "pom.xml").write_text("<project></project>")

    # 5. Seed nested monorepo subprojects
    mono_dir = root_path / "Monorepo"
    mono_dir.mkdir()
    (mono_dir / "services").mkdir()
    sub_svc = mono_dir / "services" / "auth-service"
    sub_svc.mkdir()
    (sub_svc / "requirements.txt").write_text("fastapi>=0.100.0\n")

    # 6. Seed unrelated directory with non-code files
    random_dir = root_path / "RandomDocs"
    random_dir.mkdir()
    (random_dir / "notes.txt").write_text("meeting notes")
    (random_dir / "budget.xlsx").write_text("dummy binary content")

    # 7. Seed sensitive credentials file in root
    (root_path / ".env").write_text("SECRET_KEY=12345\n")

    cfg = AgentConfig()
    cfg.projects.allowed_dirs = [str(root_path)]
    cfg.security.allowed_dirs = [str(root_path)]
    guard = SecurityGuard(cfg.security)

    ws_reg = WorkspaceRegistry(config=cfg, security_guard=guard)
    proj_reg = ProjectRegistry()
    scanner = ProjectScanner(workspace_registry=ws_reg, project_registry=proj_reg, security_guard=guard)

    yield root_path, scanner, proj_reg

    shutil.rmtree(root, ignore_errors=True)


def test_project_scanner_discovers_all_projects(scanner_env):
    root_path, scanner, proj_reg = scanner_env
    projects = scanner.scan()

    names = {p.name: p for p in projects}

    # Verify discovered projects
    assert "PythonTool" in names
    assert names["PythonTool"].project_type == "python"
    assert names["PythonTool"].git_repository_present is True

    assert "FinanceFlow" in names
    assert names["FinanceFlow"].project_type == "nodejs"
    assert names["FinanceFlow"].sub_type == "react-native"

    assert "MobileApp" in names
    assert names["MobileApp"].project_type == "flutter"

    assert "JavaBackend" in names
    assert names["JavaBackend"].project_type == "java"

    # Verify nested project discovery
    assert "auth-service" in names
    assert names["auth-service"].project_type == "python"

    # Verify unrelated folders and node_modules are NOT classified as top-level projects
    assert "RandomDocs" not in names
    assert "fake_dep" not in names


def test_project_scanner_populates_registry(scanner_env):
    _, scanner, proj_reg = scanner_env
    scanner.scan()

    all_projs = proj_reg.list_projects()
    assert len(all_projs) == 5

    # Lookups
    p1 = proj_reg.get_by_id("1")
    assert p1 is not None
    assert p1.name in ["PythonTool", "FinanceFlow", "MobileApp", "JavaBackend", "auth-service"]
