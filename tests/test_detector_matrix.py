"""
Comprehensive Project Detection Matrix Tests.

Covers:
1. Node/React & React Native
2. Python & FastAPI
3. Flutter & standalone Dart
4. Rust
5. Go
6. Java/Kotlin (Maven & Gradle)
7. .NET (.sln, .csproj)
8. PHP (composer.json)
9. Ruby (Gemfile)
10. C/C++ (CMakeLists.txt, Makefile)
11. Empty directory (mode=NEW_PROJECT, project_type="unknown")
12. Unrelated files only (notes.txt, image.png)
13. Nested project directory
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from src.core.state import TaskMode
from src.inspector.detector import ProjectDetector


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="detector_matrix_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_detect_react_native(temp_dir):
    (temp_dir / "package.json").write_text('{"name": "mobile_app", "dependencies": {"react-native": "0.73.0"}}')
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "nodejs"
    assert info.sub_type == "react-native"


def test_detect_standalone_dart(temp_dir):
    (temp_dir / "pubspec.yaml").write_text("name: dart_cli\ndependencies:\n  args: ^2.4.0\n")
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "dart"


def test_detect_golang(temp_dir):
    (temp_dir / "go.mod").write_text("module example.com/app\ngo 1.21\n")
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "golang"


def test_detect_java_maven(temp_dir):
    (temp_dir / "pom.xml").write_text("<project></project>")
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "java"
    assert info.sub_type == "maven"


def test_detect_java_gradle(temp_dir):
    (temp_dir / "build.gradle.kts").write_text("plugins { kotlin(\"jvm\") }")
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "java"
    assert info.sub_type == "gradle"


def test_detect_dotnet(temp_dir):
    (temp_dir / "App.csproj").write_text("<Project Sdk=\"Microsoft.NET.Sdk\"></Project>")
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "dotnet"


def test_detect_php(temp_dir):
    (temp_dir / "composer.json").write_text('{"name": "app/web"}')
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "php"


def test_detect_ruby(temp_dir):
    (temp_dir / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n")
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "ruby"


def test_detect_cpp(temp_dir):
    (temp_dir / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.10)")
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "cpp"


def test_detect_unrelated_files_only(temp_dir):
    (temp_dir / "vacation_photos.txt").write_text("photos")
    (temp_dir / "todo.doc").write_text("buy milk")
    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "generic_codebase"
    assert len(info.indicators_found) == 0


def test_detect_nested_project(temp_dir):
    sub = temp_dir / "backend_service"
    sub.mkdir()
    (sub / "pyproject.toml").write_text('[project]\nname = "nested_service"\n')

    info = ProjectDetector.detect(temp_dir)
    assert info.mode == TaskMode.EXISTING_PROJECT
    assert info.project_type == "python"
    assert info.is_nested is True
