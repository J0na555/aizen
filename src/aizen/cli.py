from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from aizen import __version__
from aizen._logging import setup_logging
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


def _version_callback(value: bool) -> None:
    if value:
        from aizen import __version__
        console.print(f"aizen {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    version: bool = typer.Option(False, "--version", help="Show version and exit", callback=_version_callback),
) -> None:
    setup_logging(verbose)


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
    dry_run: bool = typer.Option(False, "--dry-run", help="Print execution plan without running"),
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

    if dry_run:
        _print_dry_run_plan(wf)
        return

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
def list() -> None:
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
def list_runs() -> None:
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


@app.command()
def edit(
    stage_id: str = typer.Argument(..., help="Stage ID to edit"),
    workflow: str = typer.Option(None, "--workflow", "-w", help="Workflow file"),
) -> None:
    """Edit a stage's YAML definition in $EDITOR."""
    project_dir = Path.cwd().resolve()

    if not workflow:
        state = load(project_dir)
        if state is None:
            err_console.print("[red]No active workflow state or --workflow flag provided[/]")
            raise typer.Exit(1)
        wf_path = project_dir / "workflows" / f"{state.workflow_name}.yaml"
        if not wf_path.exists():
            err_console.print(f"[red]Could not locate workflow file for '{state.workflow_name}'[/]")
            raise typer.Exit(1)
    else:
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

    stages = raw.get("stages", [])
    stage_idx = None
    for i, s in enumerate(stages):
        if s.get("id") == stage_id:
            stage_idx = i
            break

    if stage_idx is None:
        err_console.print(f"[red]Stage '{stage_id}' not found in workflow[/]")
        raise typer.Exit(1)

    stage_yaml = yaml.dump(stages[stage_idx], default_flow_style=False, sort_keys=False)

    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(stage_yaml)
        tmp_path = f.name

    try:
        subprocess.call([editor, tmp_path])
        edited = yaml.safe_load(Path(tmp_path).read_text())
        if not edited:
            err_console.print("[red]Edited stage is empty — aborting[/]")
            raise typer.Exit(1)
        edited_stage = Stage.model_validate(edited)
        stages[stage_idx] = edited_stage.model_dump(mode="python", by_alias=True)
        raw["stages"] = stages
        wf_path.write_text(yaml.dump(raw, default_flow_style=False, sort_keys=False))
        console.print(f"[green]Stage '{stage_id}' updated[/]")
    except typer.Exit:
        raise
    except Exception as e:
        err_console.print(f"[red]Failed to update stage:[/] {e}")
        raise typer.Exit(1)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _compute_waves(stages: list[Stage]) -> list[list[Stage]]:
    deps = {s.id: set(s.depends_on) for s in stages}
    levels: dict[str, int] = {}

    def level_of(sid: str) -> int:
        if sid in levels:
            return levels[sid]
        if not deps.get(sid):
            levels[sid] = 0
            return 0
        lv = 0
        for d in deps[sid]:
            if d in deps:
                lv = max(lv, level_of(d) + 1)
        levels[sid] = lv
        return lv

    for s in stages:
        level_of(s.id)

    max_level = max(levels.values()) if levels else 0
    waves: list[list[Stage]] = [[] for _ in range(max_level + 1)]
    for s in stages:
        waves[levels[s.id]].append(s)
    return waves


def _print_dry_run_plan(wf: Workflow) -> None:
    waves = _compute_waves(wf.stages)

    console.print(f"\n[bold]Execution Plan:[/] [cyan]{wf.name}[/]")
    if wf.description:
        console.print(f"  {wf.description}")

    total = len(wf.stages)
    wave_count = len(waves)
    parallel_any = any(len(w) > 1 for w in waves)
    console.print(f"  {total} stage(s) across {wave_count} wave(s)"
                  f"{' (parallel capable)' if parallel_any else ''}")
    console.print()

    wave_table = Table(title="Execution Waves")
    wave_table.add_column("Wave", style="cyan", justify="right")
    wave_table.add_column("Stage", style="bold")
    wave_table.add_column("Type", style="yellow")
    wave_table.add_column("Approval", style="bold")
    wave_table.add_column("On Fail")
    wave_table.add_column("Retries")

    for i, wave in enumerate(waves):
        for j, s in enumerate(wave):
            label = f"Wave {i}" if j == 0 else ""
            approval = "[yellow]yes[/]" if s.requires_approval else "no"
            retries = str(s.max_retries) if s.max_retries > 0 else "-"
            on_fail = s.on_fail.value
            wave_table.add_row(label, s.id, s.type.value, approval, on_fail, retries)

    console.print(wave_table)

    approved = [s.id for s in wf.stages if s.requires_approval]
    if approved:
        console.print(f"\n[yellow]Approval required for:[/] {', '.join(approved)}")

    console.print("\n[dim]Dry run complete. No stages were executed.[/]")


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
