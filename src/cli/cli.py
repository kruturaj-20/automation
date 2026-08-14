"""
Rich-styled Terminal CLI Interface for the Autonomous AI Agent.
Supports interactive project discovery & selection and direct instruction dispatch.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.cli.project_selector import ProjectSelector
from src.core.config import AgentConfig, load_config
from src.core.manager import AgentManager
from src.core.state import ExecutionSummary, TaskMode, TaskPhase
from src.ide.antigravity import AntigravityAdapter
from src.llm.router import create_llm_provider
from src.workspace.models import Project

console = Console()


def print_banner():
    banner_text = (
        "[bold cyan]Personal Autonomous AI Computer Agent[/bold cyan]\n"
        "[dim]Architecture: AI Manager (Orchestrator) ──► Antigravity AI (Primary Coder) ──► Verifier[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan"))


def display_summary(summary: ExecutionSummary):
    table = Table(title="Execution Summary", border_style="green" if summary.verification_passed else "red")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    table.add_row("Task ID", summary.task_id)
    table.add_row("Instruction", summary.instruction)
    table.add_row(
        "Mode",
        "[bold yellow]MODE 1 (Existing Project)[/bold yellow]"
        if summary.mode == TaskMode.EXISTING_PROJECT
        else "[bold blue]MODE 2 (New Project)[/bold blue]",
    )
    table.add_row("Final Phase", f"[{'green' if summary.phase == TaskPhase.COMPLETED else 'red'}]{summary.phase.value}[/]")
    table.add_row("Verification", "[bold green]PASSED[/bold green]" if summary.verification_passed else "[bold red]FAILED[/bold red]")
    table.add_row("Files Created", str(len(summary.files_created)))
    table.add_row("Files Modified", str(len(summary.files_modified)))
    table.add_row("Attempts / Escalations", f"IDE: {summary.ide_attempts}, LLM: {summary.llm_escalations}")
    table.add_row("Duration", f"{summary.duration_seconds:.2f}s")

    if summary.error_message:
        table.add_row("Error Details", f"[red]{summary.error_message}[/red]")
    elif summary.verification_output:
        table.add_row("Verification Detail", f"[green]{summary.verification_output}[/green]")

    console.print(table)


async def run_cli_async(args: argparse.Namespace):
    config = load_config(args.config)
    print_banner()

    target_workspace = args.workspace
    instruction = args.instruction

    # 1. Project Discovery & Selection Layer
    if not target_workspace or args.select:
        selector = ProjectSelector()
        selected_project: Optional[Project] = selector.run_interactive(initial_scan=True)
        if not selected_project:
            return None
        target_workspace = selected_project.path

        if not instruction:
            console.print(f"[bold green]Project:[/] [bold white]{selected_project.name}[/]")
            console.print(f"[bold green]Type:[/]    [magenta]{selected_project.display_type}[/]")
            console.print(f"[bold green]Path:[/]    [dim]{selected_project.path}[/]\n")
            instruction = Prompt.ask("[bold yellow]What do you want me to do?[/]").strip()
            if not instruction:
                console.print("[yellow]No task instruction provided. Exiting.[/yellow]")
                return None

    # 2. Dependency Injection: Construct IDE adapter and LLM provider
    ide_adapter = AntigravityAdapter(
        cli_path=config.ide.cli_path,
        api_key=config.llm.api_key,
        default_model=config.ide.model,
    )
    llm_provider = create_llm_provider(config.llm)

    # 3. Construct AI Manager
    manager = AgentManager(
        ide_agent=ide_adapter,
        llm=llm_provider,
        config=config,
    )

    console.print(f"[bold]Target Workspace:[/] [yellow]{target_workspace}[/]")
    console.print(f"[bold]Instruction:[/] [white]{instruction}[/]\n")

    with console.status("[bold green]Executing autonomous task...[/bold green]", spinner="dots"):
        summary = await manager.execute_task(
            instruction=instruction,
            workspace_dir=target_workspace,
        )

    console.print()
    display_summary(summary)
    return summary


def run_cli():
    parser = argparse.ArgumentParser(description="Personal Autonomous AI Computer Agent")
    parser.add_argument("instruction", nargs="?", type=str, default=None, help="Natural language task instruction")
    parser.add_argument("--workspace", "-w", type=str, default=None, help="Target workspace path")
    parser.add_argument("--select", "-s", action="store_true", help="Launch interactive project discovery & selector")
    parser.add_argument("--config", "-c", type=str, default="config.yaml", help="Path to config.yaml")

    args = parser.parse_args()
    summary = asyncio.run(run_cli_async(args))
    if summary is None:
        sys.exit(0)
    sys.exit(0 if summary.verification_passed else 1)
