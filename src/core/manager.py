"""
AI Manager — Autonomous Computer Agent Orchestrator.

Decoupled core orchestrator implementing:
- MODE 1: EXISTING PROJECT (Inspect codebase → grounded brief → Antigravity AI coders → Verify → Error hierarchy)
- MODE 2: NEW PROJECT (Understand idea → External LLM architecture → scaffold root → Antigravity AI coders → Verify → Error hierarchy)

CRITICAL INVARIANTS:
1. Antigravity AI (IDE AI) performs 100% of the actual code editing and creation.
2. External LLMs act strictly as advisors, architects, researchers, and debuggers.
3. The AI Manager itself NEVER directly creates application source files or business logic.
4. AI Manager orchestrates the loop through the abstract IDEAgentAdapter interface.
5. All research operations go through the extensible ResearchProvider interface.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.config import AgentConfig
from src.core.state import ExecutionSummary, TaskMode, TaskPhase, TaskState
from src.errors.handler import ErrorHandler, ErrorResolution
from src.ide.base import IDEAgentAdapter
from src.ide.models import ChangeType, TaskRequest, TaskResult
from src.inspector.detector import ProjectDetector
from src.inspector.inspector import CodebaseInspector
from src.llm.base import LLMProvider
from src.planner.brief_builder import TaskBriefBuilder
from src.planner.models import Approach, Goal, ProjectContext, TaskBrief
from src.research.base import ResearchProvider
from src.research.provider import NoOpResearchProvider
from src.security.action_log import ActionLog
from src.security.limits import ExecutionLimiter
from src.security.security_guard import SecurityGuard
from src.verifier.verifier import TaskVerifier, VerificationResult


class AgentManager:
    """Core AI Manager orchestrating autonomous coding workflows."""

    def __init__(
        self,
        ide_agent: IDEAgentAdapter,
        llm: LLMProvider,
        config: AgentConfig,
        research_provider: Optional[ResearchProvider] = None,
        action_log: Optional[ActionLog] = None,
    ):
        self.ide_agent = ide_agent
        self.llm = llm
        self.config = config
        self.research = research_provider or NoOpResearchProvider()
        self.action_log = action_log or ActionLog()
        self.permissions = SecurityGuard(config.security)
        self.limiter = ExecutionLimiter(config.limits)

    async def execute_task(
        self,
        instruction: str,
        workspace_dir: Optional[str | Path] = None,
    ) -> ExecutionSummary:
        """Execute a user instruction autonomously."""
        task_id = str(uuid.uuid4())[:8]
        target_dir = Path(workspace_dir or self.config.default_workspace).resolve()

        state = TaskState(
            task_id=task_id,
            instruction=instruction,
            working_dir=str(target_dir),
            project_type="unknown",
        )
        self.limiter.start()

        summary = ExecutionSummary(
            task_id=task_id,
            instruction=instruction,
            mode=TaskMode.NEW_PROJECT,
            phase=TaskPhase.INITIALIZING,
        )

        # ── 0. Security Boundary Validation ───────────────────────────
        allowed, reason = self.permissions.validate_action("file.create", target_dir)
        if not allowed:
            state.transition_to(TaskPhase.FAILED, note=reason)
            summary.phase = TaskPhase.FAILED
            summary.error_message = reason
            self.action_log.log(task_id, "security_violation", {"reason": reason}, status="failed")
            return summary

        # Manager creates only the workspace root and metadata directory (no application files)
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / ".agent_meta").mkdir(exist_ok=True)

        # ── 1. Understand Goal ─────────────────────────────────────────
        state.transition_to(TaskPhase.INSPECTING, note="Inspecting workspace & understanding goal")
        self.action_log.log(task_id, "task_start", {"instruction": instruction, "target_dir": str(target_dir)})

        goal = Goal(
            raw_instruction=instruction,
            summary=instruction[:100],
        )

        # ── 2. Project Detection & Codebase Inspection ────────────────
        project_info, context = CodebaseInspector.inspect(target_dir)
        state.mode = project_info.mode
        summary.mode = project_info.mode

        # ── 3. Workflow Routing: Mode 1 vs Mode 2 ─────────────────────
        brief: TaskBrief

        if project_info.mode == TaskMode.EXISTING_PROJECT:
            # ──────────────────────────────────────────────────────────
            # MODE 1: EXISTING PROJECT
            # ──────────────────────────────────────────────────────────
            state.project_type = project_info.project_type
            state.indicators_found = project_info.indicators_found
            state.transition_to(TaskPhase.PREPARING_BRIEF, note="Building Mode 1 existing codebase brief")
            self.action_log.log(
                task_id,
                "mode1_existing_project_detected",
                {
                    "project_type": project_info.project_type,
                    "indicators": project_info.indicators_found,
                    "entry_points": project_info.entry_points,
                },
            )
            brief = TaskBriefBuilder.build_mode1_brief(goal, context)

        else:
            # ──────────────────────────────────────────────────────────
            # MODE 2: NEW PROJECT
            # ──────────────────────────────────────────────────────────
            # Initial state is unknown project_type
            state.project_type = "unknown"
            state.transition_to(TaskPhase.CONSULTING_LLM, note="Consulting external LLM for architecture/tech stack")
            self.action_log.log(task_id, "mode2_new_project_detected", {"target_dir": str(target_dir)})

            # Ask external LLM for architecture/approach (Reasoning ONLY, zero file writes)
            approach: Approach = await self.llm.plan_architecture(goal, context)

            # Assign project type based on architecture recommendation
            if approach.suggested_tech_stack:
                first_tech = approach.suggested_tech_stack[0].lower()
                if "python" in first_tech:
                    state.project_type = "python"
                elif "react" in first_tech or "node" in first_tech or "next" in first_tech:
                    state.project_type = "nodejs"
                elif "flutter" in first_tech:
                    state.project_type = "flutter"
                elif "rust" in first_tech:
                    state.project_type = "rust"
                else:
                    state.project_type = first_tech
            else:
                state.project_type = "generic"

            self.action_log.log(
                task_id,
                "llm_architecture_formulated",
                {
                    "architecture": approach.architecture_overview,
                    "tech_stack": approach.suggested_tech_stack,
                    "dependencies": approach.suggested_dependencies,
                    "selected_project_type": state.project_type,
                },
            )

            state.transition_to(TaskPhase.PREPARING_BRIEF, note="Building Mode 2 new project brief")
            brief = TaskBriefBuilder.build_mode2_brief(goal, str(target_dir), approach)

        # ── 4. Delegate Coding to IDE AI (Antigravity AI) ─────────────
        state.transition_to(TaskPhase.DELEGATING_TO_IDE, note="Antigravity AI performing implementation")
        self.action_log.log(task_id, "ide_dispatch", {"brief_instruction": brief.instruction})

        developer_prompt = brief.to_developer_prompt()
        task_req = TaskRequest(
            instruction=developer_prompt,
            working_dir=str(target_dir),
            timeout_seconds=self.config.ide.timeout_seconds,
            auto_approve=(self.config.ide.approval_mode == "yolo"),
            model=self.config.ide.model,
        )

        ide_task_id = await self.ide_agent.start_task(task_req)
        ide_result: TaskResult = await self.ide_agent.wait_for_completion(ide_task_id)

        # Record file changes
        changes = await self.ide_agent.get_changed_files(ide_task_id)
        summary.files_created = [c.path for c in changes if c.change_type == ChangeType.CREATED]
        summary.files_modified = [c.path for c in changes if c.change_type == ChangeType.MODIFIED]
        summary.files_deleted = [c.path for c in changes if c.change_type == ChangeType.DELETED]

        self.action_log.log(
            task_id,
            "ide_completed",
            {
                "status": ide_result.status.value,
                "files_created": len(summary.files_created),
                "files_modified": len(summary.files_modified),
                "duration_seconds": ide_result.duration_seconds,
            },
        )

        # ── 5. Independent Build/Test Verification ────────────────────
        state.transition_to(TaskPhase.VERIFYING, note="Running independent verification checks")
        verification: VerificationResult = await TaskVerifier.verify(
            goal, target_dir, context, security_guard=self.permissions
        )

        if verification.passed:
            state.transition_to(TaskPhase.COMPLETED, note="Verification passed on initial run")
            summary.phase = TaskPhase.COMPLETED
            summary.verification_passed = True
            summary.verification_output = verification.details
            summary.duration_seconds = self.limiter.elapsed_seconds
            self.action_log.log(
                task_id,
                "verification_passed",
                {"details": verification.details, "type": verification.verification_type},
            )
            return summary

        # ── 6. Error Escalation Hierarchy ──────────────────────────────
        state.transition_to(TaskPhase.ERROR_HANDLING, note="Verification failed, initiating 3-tier error hierarchy")
        self.action_log.log(task_id, "verification_failed", {"errors": verification.errors})

        # Re-inspect to get updated project context for error handling
        _, updated_context = CodebaseInspector.inspect(target_dir)

        resolution: ErrorResolution = await ErrorHandler.handle_errors(
            initial_errors=verification.errors,
            goal=goal,
            context=updated_context,
            ide_agent=self.ide_agent,
            llm=self.llm,
            security_guard=self.permissions,
        )

        summary.ide_attempts = resolution.total_attempts
        summary.verification_passed = resolution.resolved

        if resolution.resolved:
            state.transition_to(TaskPhase.COMPLETED, note=f"Resolved by {resolution.resolved_by}")
            summary.phase = TaskPhase.COMPLETED
            summary.verification_output = resolution.final_verification.details if resolution.final_verification else "Resolved"
            self.action_log.log(
                task_id,
                "error_resolved",
                {"resolved_by": resolution.resolved_by, "attempts": resolution.total_attempts},
            )
        else:
            state.transition_to(TaskPhase.FAILED, note="Error retries exhausted")
            summary.phase = TaskPhase.FAILED
            summary.error_message = resolution.error_summary
            self.action_log.log(
                task_id,
                "error_unresolved",
                {"error": resolution.error_summary, "attempts": resolution.total_attempts},
                status="failed",
            )

        summary.duration_seconds = self.limiter.elapsed_seconds
        return summary
