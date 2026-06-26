from __future__ import annotations

from pathlib import Path

import pytest

from aizen.models import StageState, StageStatus


def test_reset(sample_workflow, tmp_path: Path):
    from aizen.state import reset

    state = reset(sample_workflow, project_dir=tmp_path)
    assert state.workflow_name == "test-workflow"
    assert len(state.stages) == 3
    for s in sample_workflow.stages:
        assert state.stages[s.id].status == StageStatus.PENDING
    # Verify persistence
    state_file = tmp_path / ".aizen" / "state.json"
    assert state_file.exists()


def test_save_and_load(sample_workflow, tmp_path: Path):
    from aizen.state import load, reset, save

    state = reset(sample_workflow, project_dir=tmp_path)
    state.stages["build"].status = StageStatus.COMPLETED
    save(state, project_dir=tmp_path)

    loaded = load(project_dir=tmp_path)
    assert loaded is not None
    assert loaded.workflow_name == "test-workflow"
    assert loaded.stages["build"].status == StageStatus.COMPLETED


def test_rollback(dag_workflow, tmp_path: Path):
    from aizen.state import reset, rollback

    state = reset(dag_workflow, project_dir=tmp_path)
    state.stages["a"].status = StageStatus.COMPLETED
    state.stages["b"].status = StageStatus.COMPLETED
    state.stages["c"].status = StageStatus.COMPLETED

    updated = rollback("b", state, dag_workflow.stages)
    assert updated.stages["b"].status == StageStatus.PENDING
    assert updated.stages["d"].status == StageStatus.PENDING
    assert updated.stages["c"].status == StageStatus.COMPLETED


def test_archive(sample_workflow, tmp_path: Path):
    from aizen.state import archive, reset

    state = reset(sample_workflow, project_dir=tmp_path)

    archive(state, project_dir=tmp_path)
    runs_dir = tmp_path / ".aizen" / "runs"
    assert runs_dir.exists()
    archives = list(runs_dir.iterdir())
    assert len(archives) >= 1


def test_list_runs(sample_workflow, tmp_path: Path):
    from aizen.state import archive, list_runs, reset, save

    state = reset(sample_workflow, project_dir=tmp_path)
    state.stages["build"].status = StageStatus.COMPLETED
    state.stages["test"].status = StageStatus.COMPLETED
    state.stages["deploy"].status = StageStatus.COMPLETED
    save(state, project_dir=tmp_path)
    archive(state, project_dir=tmp_path)

    runs = list_runs(project_dir=tmp_path)
    assert len(runs) >= 1
    current = [r for r in runs if r["file"].endswith("state.json")]
    archived = [r for r in runs if not r["file"].endswith("state.json")]
    assert current[0]["status"] == "completed"
    assert archived[0]["status"] == "completed"
    assert archived[0]["stages"] == 3
    assert archived[0]["completed"] == 3


def test_clear(sample_workflow, tmp_path: Path):
    from aizen.state import clear, load, reset, save

    state = reset(sample_workflow, project_dir=tmp_path)
    save(state, project_dir=tmp_path)
    clear(project_dir=tmp_path)
    loaded = load(project_dir=tmp_path)
    assert loaded is None
