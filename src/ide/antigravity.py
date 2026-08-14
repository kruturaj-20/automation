"""
AntigravityAdapter — Concrete implementation of IDEAgentAdapter
for Google's Antigravity IDE / Gemini CLI.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional

from .base import IDEAgentAdapter
from .models import (
    ChangeType,
    DiagnosticEntry,
    EventType,
    FileChange,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
)

_SDK_AVAILABLE = False
try:
    from google.antigravity import Agent as SDKAgent
    from google.antigravity import LocalAgentConfig as SDKLocalAgentConfig
    _SDK_AVAILABLE = True
except Exception:
    _SDK_AVAILABLE = False


def _map_event_type(raw_type: str) -> EventType:
    mapping = {
        "init": EventType.INIT,
        "message": EventType.MESSAGE,
        "tool_use": EventType.TOOL_USE,
        "tool_result": EventType.TOOL_RESULT,
        "error": EventType.ERROR,
        "result": EventType.RESULT,
    }
    return mapping.get(raw_type.lower(), EventType.UNKNOWN)


def _load_env_file():
    for candidate in [Path(".env"), Path("../.env"), Path("e:/Work/automation/.env")]:
        if candidate.exists():
            try:
                with open(candidate, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip()
                            if k and v and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


class _TaskSession:
    def __init__(
        self,
        task_id: str,
        request: TaskRequest,
        process: Optional[asyncio.subprocess.Process] = None,
    ):
        self.task_id = task_id
        self.request = request
        self.process = process
        self.status = TaskStatus.PENDING
        self.events: list[TaskEvent] = []
        self.output_lines: list[str] = []
        self.file_snapshot_before: dict[str, float] = {}
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.exit_code: Optional[int] = None
        self.error: Optional[str] = None
        self._completion_event = asyncio.Event()

    def mark_started(self):
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self, exit_code: int):
        self.status = TaskStatus.COMPLETED
        self.exit_code = exit_code
        self.completed_at = datetime.now()
        self._completion_event.set()

    def mark_failed(self, error: str):
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()
        self._completion_event.set()

    def mark_stopped(self):
        self.status = TaskStatus.STOPPED
        self.completed_at = datetime.now()
        self._completion_event.set()

    @property
    def duration_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def to_result(self) -> TaskResult:
        return TaskResult(
            status=self.status,
            exit_code=self.exit_code,
            output="\n".join(self.output_lines),
            events=list(self.events),
            file_changes=self._detect_file_changes(),
            diagnostics=[],
            error=self.error,
            started_at=self.started_at,
            completed_at=self.completed_at,
            duration_seconds=self.duration_seconds,
        )

    def _detect_file_changes(self) -> list[FileChange]:
        changes: list[FileChange] = []
        work_dir = Path(self.request.working_dir)
        if not work_dir.exists():
            return changes

        current_files: dict[str, float] = {}
        for p in work_dir.rglob("*"):
            if p.is_file() and "node_modules" not in p.parts and ".git" not in p.parts:
                try:
                    current_files[str(p)] = p.stat().st_mtime
                except OSError:
                    pass

        for path, mtime in current_files.items():
            if path not in self.file_snapshot_before:
                changes.append(FileChange(path=path, change_type=ChangeType.CREATED))
            elif mtime != self.file_snapshot_before[path]:
                changes.append(FileChange(path=path, change_type=ChangeType.MODIFIED))

        for path in self.file_snapshot_before:
            if path not in current_files:
                changes.append(FileChange(path=path, change_type=ChangeType.DELETED))

        return changes

    def snapshot_files(self):
        work_dir = Path(self.request.working_dir)
        if not work_dir.exists():
            self.file_snapshot_before = {}
            return

        for p in work_dir.rglob("*"):
            if p.is_file() and "node_modules" not in p.parts and ".git" not in p.parts:
                try:
                    self.file_snapshot_before[str(p)] = p.stat().st_mtime
                except OSError:
                    pass


class AntigravityAdapter(IDEAgentAdapter):
    """
    IDE agent adapter for Google Antigravity / Gemini CLI.
    """

    def __init__(
        self,
        cli_path: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        default_timeout: int = 180,
    ):
        _load_env_file()
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self._cli_path = cli_path or self._find_cli_path()
        self._default_model = default_model
        self._default_timeout = default_timeout
        self._sessions: dict[str, _TaskSession] = {}
        self._background_tasks: dict[str, asyncio.Task] = {}

    @staticmethod
    def _find_cli_path() -> str:
        if sys.platform == "win32":
            npm_dir = Path(os.environ.get("APPDATA", "")) / "npm"
            cmd_path = npm_dir / "gemini.cmd"
            if cmd_path.exists():
                return str(cmd_path)
            ps1_path = npm_dir / "gemini.ps1"
            if ps1_path.exists():
                return str(ps1_path)
        return "gemini"

    async def start_task(self, request: TaskRequest) -> str:
        task_id = str(uuid.uuid4())[:8]
        session = _TaskSession(task_id=task_id, request=request)

        work_dir = Path(request.working_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        session.snapshot_files()
        self._sessions[task_id] = session

        if _SDK_AVAILABLE and self._api_key:
            bg_task = asyncio.create_task(self._run_sdk_task(session))
            self._background_tasks[task_id] = bg_task
            session.mark_started()
        else:
            cmd = self._build_cli_command(request)
            try:
                env = os.environ.copy()
                if self._api_key:
                    env["GEMINI_API_KEY"] = self._api_key

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(work_dir),
                    env=env,
                )
                session.process = process
                session.mark_started()

                bg_task = asyncio.create_task(self._read_cli_output(session))
                self._background_tasks[task_id] = bg_task

            except FileNotFoundError:
                session.mark_failed(f"Gemini CLI not found at '{self._cli_path}'")
            except Exception as e:
                session.mark_failed(f"Failed to start task process: {e}")

        return task_id

    async def send_followup(self, task_id: str, message: str) -> None:
        session = self._get_session(task_id)
        new_request = TaskRequest(
            instruction=message,
            working_dir=session.request.working_dir,
            timeout_seconds=session.request.timeout_seconds,
            auto_approve=session.request.auto_approve,
            model=session.request.model,
        )
        old_snapshot = session.file_snapshot_before
        new_id = await self.start_task(new_request)
        new_session = self._sessions.pop(new_id)
        new_session.task_id = task_id
        new_session.file_snapshot_before = old_snapshot
        self._sessions[task_id] = new_session

    async def get_status(self, task_id: str) -> TaskStatus:
        session = self._get_session(task_id)
        return session.status

    async def get_events(self, task_id: str) -> list[TaskEvent]:
        session = self._get_session(task_id)
        return list(session.events)

    async def stream_events(self, task_id: str) -> AsyncIterator[TaskEvent]:
        session = self._get_session(task_id)
        seen = 0
        while True:
            while seen < len(session.events):
                yield session.events[seen]
                seen += 1

            if session._completion_event.is_set():
                while seen < len(session.events):
                    yield session.events[seen]
                    seen += 1
                break

            await asyncio.sleep(0.05)

    async def get_output(self, task_id: str) -> str:
        session = self._get_session(task_id)
        return "\n".join(session.output_lines)

    async def get_changed_files(self, task_id: str) -> list[FileChange]:
        session = self._get_session(task_id)
        return session._detect_file_changes()

    async def get_diagnostics(self, task_id: str) -> list[DiagnosticEntry]:
        return []

    async def wait_for_completion(
        self, task_id: str, timeout_seconds: Optional[int] = None
    ) -> TaskResult:
        session = self._get_session(task_id)
        timeout = timeout_seconds or session.request.timeout_seconds

        try:
            await asyncio.wait_for(session._completion_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            session.mark_failed(f"Task timed out after {timeout} seconds")
            await self._kill_session(session)

        bg_task = self._background_tasks.get(task_id)
        if bg_task and not bg_task.done():
            try:
                await asyncio.wait_for(bg_task, timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                bg_task.cancel()

        return session.to_result()

    async def stop_task(self, task_id: str) -> TaskResult:
        session = self._get_session(task_id)
        if session.status in (TaskStatus.RUNNING, TaskStatus.STARTING, TaskStatus.PENDING):
            await self._kill_session(session)
            session.mark_stopped()

        bg_task = self._background_tasks.get(task_id)
        if bg_task and not bg_task.done():
            bg_task.cancel()

        return session.to_result()

    async def is_available(self) -> bool:
        if _SDK_AVAILABLE:
            return True
        try:
            proc = await asyncio.create_subprocess_exec(
                self._cli_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except Exception:
            return False

    async def get_adapter_info(self) -> dict:
        available = await self.is_available()
        return {
            "name": "AntigravityAdapter",
            "sdk_available": _SDK_AVAILABLE,
            "sdk_version": "0.1.12" if _SDK_AVAILABLE else "none",
            "cli_path": self._cli_path,
            "available": available,
            "has_api_key": bool(self._api_key),
            "primary_engine": "google.antigravity (Python SDK)" if (_SDK_AVAILABLE and self._api_key) else "gemini (CLI)",
            "capabilities": {
                "start_task": True,
                "send_task": True,
                "detect_start": True,
                "observe_progress": True,
                "detect_file_changes": True,
                "detect_completion": True,
                "detect_failure": True,
                "stop_task": True,
                "independent_verification": True,
            },
        }

    async def _run_sdk_task(self, session: _TaskSession):
        try:
            cfg = SDKLocalAgentConfig(
                workspaces=[session.request.working_dir],
                api_key=self._api_key,
                model=session.request.model or self._default_model,
            )
            async with SDKAgent(cfg) as agent:
                session.events.append(
                    TaskEvent(type=EventType.INIT, timestamp=datetime.now(), content="Agent initialized via SDK")
                )
                response = await agent.chat(session.request.instruction)
                async for chunk in response.chunks:
                    event = TaskEvent(
                        type=EventType.MESSAGE,
                        timestamp=datetime.now(),
                        content=str(chunk),
                    )
                    session.events.append(event)
                    session.output_lines.append(str(chunk))

                result_text = await response.text()
                session.output_lines.append(result_text)
                session.mark_completed(exit_code=0)

        except Exception as e:
            session.mark_failed(str(e))

    async def _read_cli_output(self, session: _TaskSession):
        process = session.process
        if not process or not process.stdout:
            return

        buffer = ""
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(process.stdout.read(2048), timeout=0.5)
                except asyncio.TimeoutError:
                    if process.returncode is not None:
                        break
                    continue

                if not chunk:
                    break

                text = chunk.decode("utf-8", errors="replace")
                buffer += text

                if "Opening authentication page in your browser" in buffer or "Do you want to continue?" in buffer:
                    session.events.append(
                        TaskEvent(
                            type=EventType.ERROR,
                            timestamp=datetime.now(),
                            content="Authentication required: Set GEMINI_API_KEY in .env or run 'gemini' in terminal once.",
                        )
                    )
                    session.mark_failed("Authentication required: GEMINI_API_KEY missing or OAuth token expired.")
                    await self._kill_session(session)
                    return

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        raw_event = json.loads(line_str)
                        event = self._parse_cli_event(raw_event)
                        session.events.append(event)
                        if event.content:
                            session.output_lines.append(event.content)
                    except json.JSONDecodeError:
                        session.output_lines.append(line_str)

        except Exception as e:
            if session.status == TaskStatus.RUNNING:
                session.error = f"Stream reading error: {e}"

        try:
            if process.returncode is None:
                await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

        exit_code = process.returncode if process.returncode is not None else 0
        if session.status == TaskStatus.RUNNING:
            session.mark_completed(exit_code)

    def _parse_cli_event(self, raw: dict) -> TaskEvent:
        raw_type = raw.get("type", "unknown")
        event_type = _map_event_type(raw_type)

        content = ""
        tool_name = ""
        tool_args = {}
        tool_result = ""

        if event_type == EventType.MESSAGE:
            c = raw.get("content", "")
            if isinstance(c, dict):
                content = c.get("text", str(c))
            elif isinstance(c, list):
                content = "\n".join(str(x.get("text", x) if isinstance(x, dict) else x) for x in c)
            else:
                content = str(c)
        elif event_type == EventType.TOOL_USE:
            tool_name = raw.get("name", raw.get("tool", ""))
            tool_args = raw.get("args", raw.get("arguments", {}))
            content = f"Tool: {tool_name}"
        elif event_type == EventType.TOOL_RESULT:
            tool_result = str(raw.get("result", raw.get("output", "")))
            content = tool_result
        elif event_type == EventType.ERROR:
            content = raw.get("message", raw.get("error", str(raw)))
        elif event_type == EventType.RESULT:
            content = str(raw.get("text", raw.get("content", "")))

        return TaskEvent(
            type=event_type,
            timestamp=datetime.now(),
            raw_type=raw_type,
            content=content,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            metadata=raw,
        )

    def _build_cli_command(self, request: TaskRequest) -> list[str]:
        cmd = [self._cli_path, "-p", request.instruction, "--output-format", "stream-json", "--skip-trust"]
        if request.auto_approve:
            cmd.append("--yolo")
        model = request.model or self._default_model
        if model:
            cmd.extend(["-m", model])
        return cmd

    def _get_session(self, task_id: str) -> _TaskSession:
        if task_id not in self._sessions:
            raise ValueError(f"Unknown task ID: {task_id}")
        return self._sessions[task_id]

    async def _kill_session(self, session: _TaskSession):
        if session.process and session.process.returncode is None:
            try:
                session.process.terminate()
                try:
                    await asyncio.wait_for(session.process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    session.process.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
