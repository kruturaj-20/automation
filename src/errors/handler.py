"""
Strict 3-Tier Error Escalation Handler.

Hierarchy:
  Tier 1 (Attempt 1): Antigravity AI gets first chance to fix error.
  Tier 2 (Attempt 2): Antigravity AI gets second chance with accumulated context.
  Tier 3 (Escalation): External LLM analyzes error + previous attempts, formulates
                       a solution, and passes it to Antigravity AI to implement.

INVARIANT:
External LLMs NEVER modify project files directly.
Antigravity AI remains the sole coder throughout all tiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.ide.base import IDEAgentAdapter
from src.ide.models import TaskRequest, TaskResult
from src.llm.base import ErrorAnalysis, LLMProvider
from src.planner.models import Goal, ProjectContext
from src.verifier.verifier import TaskVerifier, VerificationResult


@dataclass
class ErrorResolution:
    """Outcome of error resolution process."""

    resolved: bool
    resolved_by: str  # "ide_ai_attempt_1", "ide_ai_attempt_2", "llm_guided_ide_ai", "unresolved"
    total_attempts: int = 0
    final_verification: Optional[VerificationResult] = None
    error_summary: str = ""
    history: list[str] = field(default_factory=list)


class ErrorHandler:
    """Orchestrates the error fixing loop according to the architectural rules."""

    IDE_AI_MAX_ATTEMPTS = 2
    LLM_ESCALATION_MAX_ATTEMPTS = 2

    @classmethod
    async def handle_errors(
        cls,
        initial_errors: list[str],
        goal: Goal,
        context: ProjectContext,
        ide_agent: IDEAgentAdapter,
        llm: LLMProvider,
        security_guard: Optional[Any] = None,
    ) -> ErrorResolution:
        current_errors = list(initial_errors)
        attempt_history: list[str] = []
        total_attempts = 0

        # ── TIER 1 & 2: Antigravity AI gets initial chances to fix ────
        for attempt_idx in range(1, cls.IDE_AI_MAX_ATTEMPTS + 1):
            total_attempts += 1
            error_str = "\n".join(current_errors)
            attempt_label = f"IDE AI Fix Attempt {attempt_idx}"
            attempt_history.append(f"{attempt_label}: Error: {error_str[:150]}")

            fix_instruction = (
                f"The build / verification failed with the following error:\n\n"
                f"{error_str}\n\n"
                f"Please inspect the project files, fix the root cause, and ensure the project builds cleanly."
            )

            # Delegate fix to IDE AI
            fix_req = TaskRequest(
                instruction=fix_instruction,
                working_dir=context.root_dir,
                timeout_seconds=180,
            )
            fix_task_id = await ide_agent.start_task(fix_req)
            await ide_agent.wait_for_completion(fix_task_id, timeout_seconds=180)

            # Independently verify the result
            verification = await TaskVerifier.verify(
                goal, context.root_dir, context, security_guard=security_guard
            )
            if verification.passed:
                return ErrorResolution(
                    resolved=True,
                    resolved_by=f"ide_ai_attempt_{attempt_idx}",
                    total_attempts=total_attempts,
                    final_verification=verification,
                    history=attempt_history,
                )

            current_errors = verification.errors or ["Build still failing."]

        # ── TIER 3: Escalate to External LLM ──────────────────────────
        for llm_attempt in range(1, cls.LLM_ESCALATION_MAX_ATTEMPTS + 1):
            total_attempts += 1
            error_str = "\n".join(current_errors)

            # 1. External LLM analyzes error (Reasoning only, no file edits)
            analysis: ErrorAnalysis = await llm.analyze_error(
                error=error_str,
                context=context,
                previous_attempts=attempt_history,
            )
            attempt_history.append(f"External LLM Analysis {llm_attempt}: Root Cause={analysis.root_cause[:100]}")

            # 2. Hand external LLM solution BACK to Antigravity AI to implement
            guided_instruction = (
                f"An external architecture analysis has diagnosed the persistent error:\n\n"
                f"**Root Cause:** {analysis.root_cause}\n"
                f"**Recommended Fix:** {analysis.recommended_fix}\n"
                f"**Modifications Needed:** {analysis.code_modifications_summary}\n\n"
                f"Please implement this solution directly in the codebase now."
            )

            guided_req = TaskRequest(
                instruction=guided_instruction,
                working_dir=context.root_dir,
                timeout_seconds=180,
            )
            guided_task_id = await ide_agent.start_task(guided_req)
            await ide_agent.wait_for_completion(guided_task_id, timeout_seconds=180)

            # 3. Independently verify
            verification = await TaskVerifier.verify(
                goal, context.root_dir, context, security_guard=security_guard
            )
            if verification.passed:
                return ErrorResolution(
                    resolved=True,
                    resolved_by="llm_guided_ide_ai",
                    total_attempts=total_attempts,
                    final_verification=verification,
                    history=attempt_history,
                )

            current_errors = verification.errors or ["Error persisted after LLM guidance."]

        # Retries exhausted
        return ErrorResolution(
            resolved=False,
            resolved_by="unresolved",
            total_attempts=total_attempts,
            error_summary="\n".join(current_errors),
            history=attempt_history,
        )
