"""
Google Gemini external reasoning provider.

Provides architectural guidance for new projects (Mode 2) and deep
debugging analysis when IDE AI error retries fail.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from src.planner.models import Approach, Goal, ProjectContext
from .base import ErrorAnalysis, LLMProvider


class GeminiProvider(LLMProvider):
    """External LLM reasoning provider using Google Gemini."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-pro",
        temperature: float = 0.2,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model = model
        self.temperature = temperature
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                pass

    async def plan_architecture(self, goal: Goal, context: Optional[ProjectContext] = None) -> Approach:
        """Formulate architecture and technology advice."""
        if self._client:
            prompt = f"""You are a principal software architect. Formulate an architecture and tech stack recommendation for the following project:

Goal: {goal.raw_instruction}
Key Features: {', '.join(goal.key_features) if goal.key_features else 'Standard implementation'}
Target Tech: {goal.target_technology or 'Best suitable modern stack'}

Provide your response in JSON format with keys:
- "architecture_overview": string
- "suggested_tech_stack": list of strings
- "suggested_dependencies": list of strings
- "implementation_guidelines": list of strings
- "recommended_structure": list of file/directory path strings
"""
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                text = response.text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                data = json.loads(text)
                return Approach(
                    architecture_overview=data.get("architecture_overview", "Standard modern architecture"),
                    suggested_tech_stack=data.get("suggested_tech_stack", []),
                    suggested_dependencies=data.get("suggested_dependencies", []),
                    implementation_guidelines=data.get("implementation_guidelines", []),
                    recommended_structure=data.get("recommended_structure", []),
                )
            except Exception:
                pass

        # Heuristic fallback if API key is not connected yet
        raw = goal.raw_instruction.lower()
        if "react" in raw or "next" in raw:
            return Approach(
                architecture_overview="React component-based frontend architecture with responsive design.",
                suggested_tech_stack=["React 18+", "Vite or Next.js", "Vanilla CSS / CSS Modules"],
                suggested_dependencies=["react", "react-dom", "lucide-react"],
                implementation_guidelines=[
                    "Use modular component structure in src/components/",
                    "Implement clean state management with React hooks",
                    "Add responsive styling with modern CSS variables",
                ],
                recommended_structure=["package.json", "index.html", "src/App.tsx", "src/components/", "src/index.css"],
            )
        elif "python" in raw or "fastapi" in raw:
            return Approach(
                architecture_overview="Python modular application architecture.",
                suggested_tech_stack=["Python 3.11+", "FastAPI / Uvicorn", "Pydantic"],
                suggested_dependencies=["fastapi", "uvicorn", "pydantic"],
                implementation_guidelines=[
                    "Implement modular routes and dependency injection",
                    "Use Pydantic schemas for data validation",
                ],
                recommended_structure=["requirements.txt", "main.py", "app/routers/", "app/models/"],
            )

        return Approach(
            architecture_overview="Clean, decoupled architecture tailored to user goal.",
            suggested_tech_stack=["HTML5", "CSS3", "JavaScript"],
            suggested_dependencies=[],
            implementation_guidelines=["Create clean entrypoint and modular structure"],
            recommended_structure=["index.html", "style.css", "app.js"],
        )

    async def analyze_error(
        self,
        error: str,
        context: ProjectContext,
        previous_attempts: list[str],
    ) -> ErrorAnalysis:
        """Analyze persistent build/test errors."""
        if self._client:
            prompt = f"""You are an expert software debugger. The IDE AI failed to fix an error after previous attempts.

Project Type: {context.project_type}
Working Directory: {context.root_dir}
Current Error:
{error}

Previous Fix Attempts:
{json.dumps(previous_attempts, indent=2)}

Provide a root-cause diagnosis and explicit fix instructions for the IDE AI to apply in JSON format with keys:
- "root_cause": string
- "recommended_fix": string
- "code_modifications_summary": string
- "suggested_commands": list of strings
"""
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                text = response.text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                data = json.loads(text)
                return ErrorAnalysis(
                    root_cause=data.get("root_cause", "Build/Runtime execution failure"),
                    recommended_fix=data.get("recommended_fix", "Resolve syntax or dependency mismatch"),
                    code_modifications_summary=data.get("code_modifications_summary", ""),
                    suggested_commands=data.get("suggested_commands", []),
                )
            except Exception:
                pass

        return ErrorAnalysis(
            root_cause="Persistent build or runtime error detected by independent verifier.",
            recommended_fix=f"Inspect error trace and ensure all required modules and exports match: {error[:200]}",
            code_modifications_summary="Correct syntax, imports, or missing files reported in error.",
            suggested_commands=[],
        )

    async def is_available(self) -> bool:
        return bool(self.api_key)
