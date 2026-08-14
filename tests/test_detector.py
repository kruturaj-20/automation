"""
Unit tests for ProjectDetector and CodebaseInspector.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from src.core.state import TaskMode
from src.inspector.detector import ProjectDetector
from src.inspector.inspector import CodebaseInspector


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="agent_detector_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_detect_empty_directory_is_new_project(temp_dir):
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.NEW_PROJECT
    assert info.project_type == "unknown"
    assert len(info.indicators_found) == 0


def test_detect_nodejs_react_project(temp_dir):
    pkg_json = temp_dir / "package.json"
    pkg_json.write_text('{"name": "test-app", "dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}, "scripts": {"build": "vite build"}}')
    tsconfig = temp_dir / "tsconfig.json"
    tsconfig.write_text("{}")
    src = temp_dir / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export default function App() {}")

    info, context = CodebaseInspector.inspect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "nodejs"
    assert info.sub_type == "react"
    assert "package.json" in info.indicators_found
    assert "tsconfig.json" in info.indicators_found
    assert "react" in context.dependencies
    assert context.scripts.get("build") == "vite build"


def test_detect_python_fastapi_project(temp_dir):
    req_txt = temp_dir / "requirements.txt"
    req_txt.write_text("fastapi>=0.100.0\nuvicorn>=0.23.0\npydantic>=2.0\n")
    main_py = temp_dir / "main.py"
    main_py.write_text("from fastapi import FastAPI\napp = FastAPI()\n")

    info, context = CodebaseInspector.inspect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "python"
    assert info.sub_type == "fastapi"
    assert "requirements.txt" in info.indicators_found
    assert "main.py" in context.entry_points


def test_detect_flutter_project(temp_dir):
    pubspec = temp_dir / "pubspec.yaml"
    pubspec.write_text("name: flutter_app\ndependencies:\n  flutter:\n    sdk: flutter\n")
    lib = temp_dir / "lib"
    lib.mkdir()
    (lib / "main.dart").write_text("void main() {}")

    info, context = CodebaseInspector.inspect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "flutter"
    assert "pubspec.yaml" in info.indicators_found
    assert "lib/main.dart" in context.entry_points


def test_detect_rust_project(temp_dir):
    cargo = temp_dir / "Cargo.toml"
    cargo.write_text('[package]\nname = "rust_app"\nversion = "0.1.0"\n')

    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "rust"
    assert "Cargo.toml" in info.indicators_found


def test_detect_generic_codebase(temp_dir):
    # Has files but no known manifest
    (temp_dir / "script.sh").write_text("echo hello")
    (temp_dir / "notes.txt").write_text("some notes")

    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "generic_codebase"
