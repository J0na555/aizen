from __future__ import annotations

import threading
from pathlib import Path
from time import sleep

import pytest
import yaml

from aizen.engine import WorkflowEngine
from aizen.models import Stage, StageState, StageStatus, StageType, Workflow
from aizen.state import load, reset


def test_full_workflow_run(tmp_path: Path):
    """End-to-end: linear workflow runs all stages to completion."""
    wf = Workflow(
        name="e2e",
        stages=[
            Stage(id="s1", type=StageType.SHELL, command="echo hello"),
            Stage(id="s2", type=StageType.SHELL, command="echo world", depends_on=["s1"]),
            Stage(id="s3", type=StageType.SHELL, command="echo done", depends_on=["s2"]),
        ],
    )
    state = reset(wf, project_dir=tmp_path)
    ctx = {"project_dir": str(tmp_path), "headless": True, "ai_provider": "claude"}
    engine = WorkflowEngine(wf, state, ctx)
    final = engine.run()

    assert final.stages["s1"].status == StageStatus.COMPLETED
    assert final.stages["s2"].status == StageStatus.COMPLETED
    assert final.stages["s3"].status == StageStatus.COMPLETED
    assert final.stages["s1"].output == "hello\n"
    assert "world" in final.stages["s2"].output


def test_workflow_with_parallel_and_variables(tmp_path: Path):
    """End-to-end: parallel workflow with variables interpolation."""
    wf = Workflow(
        name="parallel-vars",
        stages=[
            Stage(id="a", type=StageType.SHELL, command="echo hello"),
            Stage(id="b", type=StageType.SHELL, command="echo world"),
            Stage(id="c", type=StageType.SHELL, command="echo '${stages.a.output} ${stages.b.output}'", depends_on=["a", "b"]),
        ],
    )
    state = reset(wf, project_dir=tmp_path)
    ctx = {"project_dir": str(tmp_path), "headless": True, "ai_provider": "claude"}
    engine = WorkflowEngine(wf, state, ctx)
    final = engine.run(parallel=True)

    assert final.stages["a"].status == StageStatus.COMPLETED
    assert final.stages["b"].status == StageStatus.COMPLETED
    assert final.stages["c"].status == StageStatus.COMPLETED
    assert "hello" in final.stages["c"].output
    assert "world" in final.stages["c"].output


def test_checkpoint_and_resume(tmp_path: Path):
    """Mid-run interruption via pause flag, then resume and complete."""
    wf = Workflow(
        name="resume-test",
        stages=[
            Stage(id="first", type=StageType.SHELL, command="echo first && sleep 1"),
            Stage(id="second", type=StageType.SHELL, command="echo second", depends_on=["first"]),
            Stage(id="third", type=StageType.SHELL, command="echo third", depends_on=["second"]),
        ],
    )
    state = reset(wf, project_dir=tmp_path)
    ctx = {"project_dir": str(tmp_path), "headless": True, "ai_provider": "claude"}

    flag = Path(tmp_path) / ".aizen" / "pause.flag"
    flag.parent.mkdir(parents=True, exist_ok=True)

    def set_pause_flag():
        sleep(0.2)
        flag.write_text("pause")

    timer = threading.Timer(0.05, set_pause_flag)
    timer.start()

    engine = WorkflowEngine(wf, state, ctx)
    try:
        engine.run()
    except Exception as e:
        from aizen.engine import WorkflowPaused
        if not isinstance(e, WorkflowPaused):
            raise

    # State persisted after interruption
    loaded = load(project_dir=tmp_path)
    assert loaded is not None
    assert loaded.stages["first"].status == StageStatus.COMPLETED
    assert loaded.stages["second"].status == StageStatus.PENDING
    assert loaded.stages["third"].status == StageStatus.PENDING

    # Remove pause flag and resume with original workflow definitions
    if flag.exists():
        flag.unlink()

    resumed_engine = WorkflowEngine(wf, loaded, ctx)
    final = resumed_engine.run()

    assert final.stages["first"].status == StageStatus.COMPLETED
    assert final.stages["second"].status == StageStatus.COMPLETED
    assert final.stages["third"].status == StageStatus.COMPLETED
    assert "first" in final.stages["first"].output
    assert "second" in final.stages["second"].output
    assert "third" in final.stages["third"].output



