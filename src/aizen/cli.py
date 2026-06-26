from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from aizen.config import (
    get_global_state_dir,
    load_global_config,
    load_project_config,
    register_project,
    save_project_config,
)
from aizen.engine import WorkflowEngine, WorkflowDeadlock, WorkflowFailed, WorkflowPaused
from aizen.validation import validate_workflow, ValidationError
from aizen.models import (
    Stage,
    StageStatus,
    StageType,
    Workflow,
    WorkflowState,
)
from aizen.plugins.installer import install_from_git, list_installed
from aizen.plugins.loader import discover_plugins
from aizen.state import (
    archive,
    clear,
    list_runs,
    load,
    reset,
    rollback,
    save,
)

app = typer.Typer(name="aizen", help="Universal task orchestrator")
console = Console()
err_console = Console(stderr=True)


@app.command()
def init(
    path: str = typer.Argument(".", help="Project path to initialize"),
) -> None:
    """Initialize aizen in a project directory."""
    project_dir = Path(path).resolve()
    state_dir = get_global_state_dir(project_dir)

    config_path = state_dir / "config.yaml"
    if not config_path.exists():
        default_config = {
            "name": project_dir.name,
            "default_workflow": None,
            "default_ai": "claude",
        }
        save_project_config(default_config, project_dir)
        console.print(f"[green]Created[/] {config_path}")

    register_project(project_dir)
    console.print(f"[green]Initialized aizen in[/] {project_dir}")


@app.command()
def run(
    workflow: str = typer.Argument(..., help="Path to workflow YAML file"),
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume from saved state"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Run independent stages in parallel"),
    headless: bool = typer.Option(False, "--headless", help="Non-interactive mode (no prompts)"),
) -> None:
    """Run a workflow."""
    project_dir = Path.cwd().resolve()
    wf_path = Path(workflow)
    if not wf_path.is_absolute():
        wf_path = project_dir / workflow

    if not wf_path.exists():
        err_console.print(f"[red]Workflow file not found:[/] {wf_path}")
        raise typer.Exit(1)

    raw = yaml.safe_load(wf_path.read_text())
    if not raw:
        err_console.print("[red]Empty workflow file[/]")
        raise typer.Exit(1)

    wf = Workflow.model_validate(raw)

    errors = validate_workflow(wf)
    if errors:
        err_console.print("[red]Workflow validation failed:[/]")
        for e in errors:
            err_console.print(f"  [red]-[/] {e}")
        raise typer.Exit(1)

    ctx: dict = {
        "project_dir": str(project_dir),
        "headless": headless,
        "ai_provider": load_project_config(project_dir).get("default_ai", "claude"),
    }

    if resume:
        state = load(project_dir)
        if state is None:
            err_console.print("[yellow]No saved state found. Starting fresh.[/]")
            state = reset(wf, project_dir)
        else:
            console.print(f"[blue]Resuming[/] workflow '{state.workflow_name}'")
    else:
        existing = load(project_dir)
        if existing is not None:
            answer = typer.confirm(
                f"Existing workflow '{existing.workflow_name}' found. Overwrite?"
            )
            if not answer:
                console.print("[yellow]Cancelled[/]")
                raise typer.Exit(0)
        state = reset(wf, project_dir)

    engine = WorkflowEngine(wf, state, ctx)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="Running workflow...", total=None)

        try:
            final = engine.run(parallel=parallel)
            _print_summary(final, wf)
        except WorkflowFailed as e:
            _print_summary(engine.state, wf)
            err_console.print(f"\n[red]Failed:[/] {e}")
            raise typer.Exit(1)
        except WorkflowDeadlock as e:
            err_console.print(f"\n[red]Deadlock:[/] {e}")
            raise typer.Exit(1)
        except WorkflowPaused:
            console.print("\n[yellow]Workflow paused. Resume with [bold]aizen resume[/][/]")


@app.command()
def status() -> None:
    """Show current workflow status."""
    state = load()
    if state is None:
        err_console.print("[yellow]No active workflow[/]")
        raise typer.Exit(0)

    table = Table(title=f"Workflow: {state.workflow_name}")
    table.add_column("Stage", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Attempts", justify="right")
    table.add_column("Error")

    for stage_id, ss in state.stages.items():
        status_style = {
            StageStatus.COMPLETED: "green",
            StageStatus.RUNNING: "blue",
            StageStatus.FAILED: "red",
            StageStatus.SKIPPED: "yellow",
            StageStatus.PAUSED: "yellow",
            StageStatus.PENDING: "white",
        }.get(ss.status, "white")

        table.add_row(
            stage_id,
            f"[{status_style}]{ss.status.value}[/]",
            str(ss.attempts) if ss.attempts > 0 else "-",
            ss.error or "-",
        )

    console.print(table)

    if state.running_stages:
        sid = next(iter(state.running_stages))
        current = state.stages.get(sid)
        if current and current.output:
            console.print(Panel(str(current.output)[:500], title=f"Running: {sid}"))


@app.command()
def pause() -> None:
    """Pause the running workflow.

    If the workflow is running in this terminal, press Ctrl+C.
    If running elsewhere, create a pause flag file.
    """
    flag = Path(".aizen/pause.flag")
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("pause")
    console.print("[yellow]Pause flag set. Engine will pause at next checkpoint.[/]")


@app.command()
def resume(
    workflow: str = typer.Option(None, "--workflow", "-w", help="Workflow file (uses saved state if omitted)"),
    headless: bool = typer.Option(False, "--headless", help="Non-interactive mode"),
) -> None:
    """Resume a paused workflow."""
    flag = Path(".aizen/pause.flag")
    if flag.exists():
        flag.unlink()

    if workflow:
        run(workflow=workflow, resume=True, headless=headless)
        return

    project_dir = Path.cwd().resolve()
    state = load(project_dir)
    if state is None:
        err_console.print("[red]No saved state found. Use --workflow to specify a workflow file.[/]")
        raise typer.Exit(1)

    console.print(f"[blue]Resuming[/] workflow '{state.workflow_name}'")

    ctx: dict = {
        "project_dir": str(project_dir),
        "headless": headless,
        "ai_provider": load_project_config(project_dir).get("default_ai", "claude"),
    }
    stages = [Stage(id=sid, type=StageType.SHELL) for sid in state.stages]
    wf = Workflow(name=state.workflow_name, stages=stages)
    engine = WorkflowEngine(wf, state, ctx)

    try:
        final = engine.run()
        _print_summary(final, wf)
    except WorkflowFailed as e:
        _print_summary(engine.state, wf)
        err_console.print(f"\n[red]Failed:[/] {e}")
        raise typer.Exit(1)
    except WorkflowDeadlock as e:
        err_console.print(f"\n[red]Deadlock:[/] {e}")
        raise typer.Exit(1)
    except WorkflowPaused:
        console.print("\n[yellow]Workflow paused. Resume with [bold]aizen resume[/][/]")


@app.command()
def rollback(
    stage_id: str = typer.Argument(..., help="Stage ID to rollback to"),
    workflow: str = typer.Option(..., "--workflow", "-w", help="Workflow file"),
) -> None:
    """Rollback to a specific stage, resetting downstream stages."""
    project_dir = Path.cwd().resolve()

    state = load(project_dir)
    if state is None:
        err_console.print("[red]No active workflow state found[/]")
        raise typer.Exit(1)

    wf_path = Path(workflow)
    if not wf_path.is_absolute():
        wf_path = project_dir / workflow
    if not wf_path.exists():
        err_console.print(f"[red]Workflow file not found:[/] {wf_path}")
        raise typer.Exit(1)
    raw = yaml.safe_load(wf_path.read_text())
    wf = Workflow.model_validate(raw)

    try:
        updated = rollback(stage_id, state, wf.stages)
        save(updated, project_dir)
        console.print(f"[green]Rolled back to[/] '{stage_id}'")
        status()
    except ValueError as e:
        err_console.print(f"[red]{e}[/]")
        raise typer.Exit(1)


@app.command()
def list_workflows() -> None:
    """List available workflows and plugins."""
    table = Table(title="Aizen Resources")
    table.add_column("Type", style="cyan")
    table.add_column("Name")
    table.add_column("Source")

    # Show built-in workflow templates
    wf_dir = Path.home() / ".aizen" / "workflows"
    if wf_dir.exists():
        for f in sorted(wf_dir.glob("*.yaml")):
            table.add_row("workflow", f.stem, str(wf_dir))
    else:
        table.add_row("workflow", "(no global workflows)", "")

    # Show project workflows
    local_wf = Path.cwd() / "workflows"
    if local_wf.exists():
        for f in sorted(local_wf.glob("*.yaml")):
            table.add_row("workflow", f.stem, str(local_wf))

    # Show plugins
    plugins = discover_plugins()
    for name in plugins:
        table.add_row("plugin", name, "~/.aizen/plugins/")

    # Show built-in stages
    for st in StageType:
        table.add_row("stage_type", st.value, "built-in")

    console.print(table)


@app.command()
def plugins(
    action: str = typer.Argument("list", help="Action: list, install"),
    name: str = typer.Argument(None, help="Plugin name or git URL to install"),
) -> None:
    """Manage plugins."""
    if action == "list":
        stages = discover_plugins()
        installed = list_installed()
        if stages:
            console.print("[bold]Stage plugins:[/]")
            for pname in stages:
                console.print(f"  [cyan]{pname}[/]")
        if installed:
            console.print("[bold]Installed packages:[/]")
            for pkg in installed:
                console.print(f"  [green]{pkg['name']}[/] ({pkg['stages']} files)")
        if not stages and not installed:
            console.print("[yellow]No plugins found in ~/.aizen/plugins/[/]")
    elif action == "install":
        if not name:
            err_console.print("[red]Plugin name or URL required[/]")
            raise typer.Exit(1)
        _install_plugin(name)
    else:
        err_console.print(f"[red]Unknown action: {action}[/]")
        raise typer.Exit(1)


@app.command()
def list_runs_command() -> None:
    """Show workflow run history."""
    runs = list_runs()
    if not runs:
        console.print("[yellow]No runs found[/]")
        return

    table = Table(title="Run History")
    table.add_column("Workflow")
    table.add_column("Status")
    table.add_column("Stages")
    table.add_column("Updated")

    for r in runs:
        style = {
            "completed": "green",
            "failed": "red",
            "in_progress": "blue",
            "paused": "yellow",
        }.get(r["status"], "white")

        table.add_row(
            r["workflow"],
            f"[{style}]{r['status']}[/]",
            f"{r['completed']}/{r['stages']}",
            r["updated_at"][:19],
        )

    console.print(table)


def _print_summary(state: WorkflowState, wf: Workflow) -> None:
    completed = sum(1 for s in state.stages.values() if s.status == StageStatus.COMPLETED)
    failed = sum(1 for s in state.stages.values() if s.status == StageStatus.FAILED)
    skipped = sum(1 for s in state.stages.values() if s.status == StageStatus.SKIPPED)
    total = len(wf.stages)

    summary = f"[bold]Workflow complete:[/] {completed}/{total} stages done"
    if failed:
        summary += f", [red]{failed} failed[/]"
    if skipped:
        summary += f", [yellow]{skipped} skipped[/]"

    console.print(f"\n{summary}")

    for stage in wf.stages:
        ss = state.stages.get(stage.id)
        if ss is None:
            continue
        icon = {
            StageStatus.COMPLETED: "[green]✓[/]",
            StageStatus.FAILED: "[red]✗[/]",
            StageStatus.SKIPPED: "[yellow]–[/]",
            StageStatus.PENDING: "[dim]·[/]",
            StageStatus.RUNNING: "[blue]→[/]",
        }.get(ss.status, "[dim]·[/]")
        console.print(f"  {icon} {stage.id}")


def _install_plugin(url: str) -> None:
    try:
        name = install_from_git(url)
        console.print(f"[green]Installed plugin:[/] {name}")
        target = Path.home() / ".aizen" / "plugins" / name
        py_files = list(target.rglob("*.py"))
        for py in py_files:
            rel = py.relative_to(Path.home() / ".aizen" / "plugins")
            console.print(f"  [dim]{rel}[/]")
    except (FileExistsError, RuntimeError) as e:
        err_console.print(f"[red]Failed to install:[/] {e}")
        raise typer.Exit(1)
