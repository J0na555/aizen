from __future__ import annotations

from pathlib import Path

import pytest

from aizen.models import Stage, StageState, StageStatus, StageType, Workflow, WorkflowState


@pytest.fixture
def sample_workflow() -> Workflow:
    return Workflow(
        name="test-workflow",
        stages=[
            Stage(id="build", type=StageType.SHELL, command="echo build"),
            Stage(id="test", type=StageType.SHELL, command="echo test", depends_on=["build"]),
            Stage(id="deploy", type=StageType.SHELL, command="echo deploy", depends_on=["test"]),
        ],
    )


@pytest.fixture
def dag_workflow() -> Workflow:
    return Workflow(
        name="dag",
        stages=[
            Stage(id="a", type=StageType.SHELL, command="echo a"),
            Stage(id="b", type=StageType.SHELL, command="echo b", depends_on=["a"]),
            Stage(id="c", type=StageType.SHELL, command="echo c", depends_on=["a"]),
            Stage(id="d", type=StageType.SHELL, command="echo d", depends_on=["b", "c"]),
        ],
    )


@pytest.fixture
def fresh_state(sample_workflow: Workflow) -> WorkflowState:
    stages = {
        s.id: StageState(stage_id=s.id)
        for s in sample_workflow.stages
    }
    return WorkflowState(workflow_name=sample_workflow.name, stages=stages)
