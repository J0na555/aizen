from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aizen.config import get_global_state_dir as get_state_dir
from aizen.models import Stage, StageState, StageStatus, Workflow, WorkflowState

STATE_FILE = "state.json"
RUNS_DIR = "runs"


def _state_path(project_dir: str | Path | None = None) -> Path:
    return get_state_dir(project_dir) / STATE_FILE


def _runs_dir(project_dir: str | Path | None = None) -> Path:
    d = get_state_dir(project_dir) / RUNS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(state: WorkflowState, project_dir: str | Path | None = None) -> Path:
    path = _state_path(project_dir)
    state.updated_at = datetime.now(timezone.utc).isoformat()
    path.write_text(state.model_dump_json(indent=2))
    return path


def load(project_dir: str | Path | None = None) -> WorkflowState | None:
    path = _state_path(project_dir)
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    return WorkflowState.model_validate(raw)


def reset(
    workflow: Workflow,
    project_dir: str | Path | None = None,
    variables: dict[str, Any] | None = None,
) -> WorkflowState:
    state = WorkflowState(
        workflow_name=workflow.name,
        project_path=str(Path(project_dir).resolve()) if project_dir else str(Path.cwd().resolve()),
        stages={s.id: StageState(stage_id=s.id) for s in workflow.stages},
        variables=variables or workflow.variables.copy(),
    )
    save(state, project_dir)
    return state


def _find_downstream(stage_id: str, stages: list[Stage]) -> set[str]:
    downstream: set[str] = set()
    queue = [stage_id]
    while queue:
        current = queue.pop()
        for s in stages:
            if s.id != current and current in s.depends_on and s.id not in downstream:
                downstream.add(s.id)
                queue.append(s.id)
    return downstream


def rollback(
    stage_id: str,
    state: WorkflowState,
    stages: list[Stage],
) -> WorkflowState:
    stage_ids = {s.id for s in stages}
    if stage_id not in stage_ids:
        raise ValueError(f"Stage '{stage_id}' not found in workflow")

    downstream = _find_downstream(stage_id, stages)
    downstream.add(stage_id)

    for sid in list(state.stages.keys()):
        if sid in downstream:
            state.stages[sid] = StageState(stage_id=sid)

    state.running_stages = {stage_id}
    state.updated_at = datetime.now(timezone.utc).isoformat()
    return state


def checkpoint(
    state: WorkflowState,
    stage_id: str,
    status: StageStatus,
    project_dir: str | Path | None = None,
    output: Any = None,
    error: str | None = None,
) -> WorkflowState:
    if stage_id not in state.stages:
        state.stages[stage_id] = StageState(stage_id=stage_id)

    ss = state.stages[stage_id]
    ss.status = status
    ss.attempts += 1
    ss.started_at = ss.started_at or datetime.now(timezone.utc).isoformat()

    if status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.SKIPPED):
        ss.completed_at = datetime.now(timezone.utc).isoformat()

    if output is not None:
        ss.output = output
    if error is not None:
        ss.error = error

    state.running_stages = {stage_id}
    save(state, project_dir)
    return state


def list_runs(project_dir: str | Path | None = None) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []

    current = load(project_dir)
    if current is not None:
        runs.append(
            {
                "workflow": current.workflow_name,
                "status": _overall_status(current),
                "stages": len(current.stages),
                "completed": sum(1 for s in current.stages.values() if s.status == StageStatus.COMPLETED),
                "failed": sum(1 for s in current.stages.values() if s.status == StageStatus.FAILED),
                "created_at": current.created_at,
                "updated_at": current.updated_at,
                "file": str(_state_path(project_dir)),
            }
        )

    runs_dir = _runs_dir(project_dir)
    for f in sorted(runs_dir.glob("*.json"), reverse=True):
        try:
            raw = json.loads(f.read_text())
            ws = WorkflowState.model_validate(raw)
            runs.append(
                {
                    "workflow": ws.workflow_name,
                    "status": _overall_status(ws),
                    "stages": len(ws.stages),
                    "completed": sum(1 for s in ws.stages.values() if s.status == StageStatus.COMPLETED),
                    "failed": sum(1 for s in ws.stages.values() if s.status == StageStatus.FAILED),
                    "created_at": ws.created_at,
                    "updated_at": ws.updated_at,
                    "file": str(f),
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue

    return runs


def archive(state: WorkflowState, project_dir: str | Path | None = None) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    archive_file = _runs_dir(project_dir) / f"{timestamp}-{state.workflow_name}.json"
    archive_file.write_text(state.model_dump_json(indent=2))
    return archive_file


def clear(project_dir: str | Path | None = None) -> None:
    path = _state_path(project_dir)
    if path.exists():
        path.unlink()


def _overall_status(state: WorkflowState) -> str:
    if not state.stages:
        return "empty"
    statuses = [s.status for s in state.stages.values()]
    if any(s == StageStatus.RUNNING for s in statuses):
        return "running"
    if any(s == StageStatus.FAILED for s in statuses):
        return "failed"
    if any(s == StageStatus.PAUSED for s in statuses):
        return "paused"
    if all(s == StageStatus.COMPLETED for s in statuses):
        return "completed"
    if all(s in (StageStatus.COMPLETED, StageStatus.SKIPPED) for s in statuses):
        return "completed"
    return "in_progress"
