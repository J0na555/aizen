from __future__ import annotations

from aizen.models import (
    OnFailStrategy,
    Stage,
    StageState,
    StageStatus,
    StageType,
    Workflow,
    WorkflowState,
)


def test_stage_defaults():
    s = Stage(id="test", type=StageType.SHELL)
    assert s.id == "test"
    assert s.type == StageType.SHELL
    assert s.depends_on == []
    assert s.on_fail == OnFailStrategy.STOP
    assert s.requires_approval is False
    assert s.max_retries == 0
    assert s.timeout_s is None


def test_stage_status_enum():
    assert StageStatus.PENDING.value == "pending"
    assert StageStatus.COMPLETED.value == "completed"
    assert StageStatus.FAILED.value == "failed"
    assert StageStatus.SKIPPED.value == "skipped"
    assert StageStatus.RUNNING.value == "running"
    assert StageStatus.PAUSED.value == "paused"


def test_on_fail_strategy_enum():
    assert OnFailStrategy.STOP.value == "stop"
    assert OnFailStrategy.CONTINUE.value == "continue"
    assert OnFailStrategy.RETRY.value == "retry"


def test_workflow_creation():
    stages = [
        Stage(id="a", type=StageType.SHELL, command="echo a"),
        Stage(id="b", type=StageType.SHELL, command="echo b", depends_on=["a"]),
    ]
    wf = Workflow(name="test", stages=stages)
    assert wf.name == "test"
    assert len(wf.stages) == 2


def test_workflow_state_defaults():
    state = WorkflowState(workflow_name="test")
    assert state.workflow_name == "test"
    assert state.stages == {}
    assert state.current_stage_id is None
    assert state.created_at is not None


def test_stage_state_defaults():
    ss = StageState(stage_id="s1")
    assert ss.stage_id == "s1"
    assert ss.status == StageStatus.PENDING
    assert ss.attempts == 0
    assert ss.output is None
    assert ss.error is None
