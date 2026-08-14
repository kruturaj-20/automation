"""
CLI Project Selector & Workspace Management Interface.

Provides an interactive terminal menu using Rich to scan approved workspaces,
browse discovered software projects, add/remove workspace roots, and select
a target project before initiating the AI Manager workflow.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.workspace.models import Project, WorkspaceRoot
from src.workspace.registry import ProjectRegistry, WorkspaceRegistry
from src.workspace.scanner import ProjectScanner

console = Console()


class ProjectSelector:
    """Interactive Project Selector and Workspace Manager."""

    def __init__(
        self,
        workspace_registry: Optional[WorkspaceRegistry] = None,
        project_registry: Optional[ProjectRegistry] = None,
        scanner: Optional[ProjectScanner] = None,
    ):
        self.workspace_reg = workspace_registry or WorkspaceRegistry()
        self.project_reg = project_registry or ProjectRegistry()
        self.scanner = scanner or ProjectScanner(
            workspace_registry=self.workspace_reg,
            project_registry=self.project_reg,
        )

    def render_menu(self, projects: list[Project]):
        """Render the workspace roots and discovered projects tables."""
        console.clear()
        banner_text = (
            "[bold cyan]AI MANAGER — PROJECT DISCOVERY & SELECTION[/bold cyan]\n"
            "[dim]Select a project to initiate autonomous software engineering tasks[/dim]"
        )
        console.print(Panel(banner_text, border_style="cyan"))

        # Approved Workspaces Panel
        workspaces = self.workspace_reg.list_workspaces()
        ws_lines = []
        if workspaces:
            for idx, ws in enumerate(workspaces, 1):
                ws_lines.append(f"[bold yellow]{idx}.[/] [white]{ws.path}[/] [dim]({ws.name})[/]")
        else:
            ws_lines.append("[italic red]No approved workspace roots configured.[/]")

        console.print(Panel("\n".join(ws_lines), title="[bold]Approved Workspace Roots[/]", border_style="yellow"))

        # Projects Table
        if projects:
            table = Table(title="[bold green]Discovered Projects[/]", border_style="green", expand=True)
            table.add_column("#", style="bold cyan", width=4)
            table.add_column("Project Name", style="bold white", width=22)
            table.add_column("Type / Framework", style="magenta", width=20)
            table.add_column("Filesystem Path", style="dim white")
            table.add_column("Git", style="green", width=6)

            for idx, p in enumerate(projects, 1):
                git_str = "[bold green]✓[/]" if p.git_repository_present else "[dim]-[/]"
                table.add_row(
                    str(idx),
                    p.name,
                    p.display_type,
                    p.path,
                    git_str,
                )
            console.print(table)
        else:
            console.print(
                Panel("[italic yellow]No projects discovered yet. Press [S] to scan approved workspaces.[/]", border_style="dim")
            )

        console.print("\n[bold cyan]Actions:[/] [bold][S][/]can  [bold][A][/]dd Workspace  [bold][R][/]emove Workspace  [bold][1-N][/] Select Project  [bold][Q][/]uit\n")

    def run_interactive(self, initial_scan: bool = True) -> Optional[Project]:
        """
        Run the interactive selection loop.
        Returns the chosen Project or None if user quits.
        """
        projects = self.project_reg.list_projects()
        if initial_scan or not projects:
            with console.status("[bold green]Scanning approved workspaces...[/bold green]", spinner="dots"):
                projects = self.scanner.scan()

        while True:
            projects = self.project_reg.list_projects()
            self.render_menu(projects)

            choice = Prompt.ask("[bold green]Selection[/]").strip()
            if not choice:
                continue

            upper = choice.upper()
            if upper == "Q":
                console.print("[yellow]Project selection cancelled.[/yellow]")
                return None

            elif upper == "S":
                with console.status("[bold green]Scanning approved workspaces...[/bold green]", spinner="dots"):
                    projects = self.scanner.scan()
                console.print(f"[bold green]✓ Scan complete. Discovered {len(projects)} project(s).[/]")
                continue

            elif upper == "A":
                new_path = Prompt.ask("Enter directory path to approve as workspace root")
                if new_path:
                    ok, msg = self.workspace_reg.add_workspace(new_path)
                    if ok:
                        console.print(f"[bold green]✓ {msg}[/]")
                        with console.status("[bold green]Scanning new workspace...[/bold green]"):
                            projects = self.scanner.scan()
                    else:
                        console.print(f"[bold red]✗ {msg}[/]")
                Prompt.ask("\nPress Enter to continue...")
                continue

            elif upper == "R":
                target = Prompt.ask("Enter workspace path or index number to remove")
                if target:
                    # Check numeric index
                    workspaces = self.workspace_reg.list_workspaces()
                    try:
                        idx = int(target) - 1
                        if 0 <= idx < len(workspaces):
                            target = workspaces[idx].path
                    except ValueError:
                        pass

                    if self.workspace_reg.remove_workspace(target):
                        console.print(f"[bold green]✓ Removed workspace: {target}[/]")
                        with console.status("[bold green]Updating project list...[/bold green]"):
                            projects = self.scanner.scan()
                    else:
                        console.print(f"[bold red]✗ Workspace not found: {target}[/]")
                Prompt.ask("\nPress Enter to continue...")
                continue

            # Check if selection is a numeric project index
            try:
                idx = int(choice)
                if 1 <= idx <= len(projects):
                    selected = projects[idx - 1]
                    console.print(f"\n[bold green]✓ Selected Project:[/] [bold white]{selected.name}[/] ({selected.display_type})")
                    console.print(f"[bold dim]Path:[/] [dim]{selected.path}[/]\n")
                    return selected
                else:
                    console.print(f"[red]Invalid selection: {choice}. Enter a number between 1 and {len(projects)}.[/red]")
            except ValueError:
                console.print(f"[red]Unknown command: '{choice}'. Use S, A, R, Q, or a project number.[/red]")

            Prompt.ask("\nPress Enter to continue...")
