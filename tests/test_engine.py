from __future__ import annotations

from pathlib import Path

import pytest

from aizen.models import (
    OnFailStrategy,
    Stage,
    StageState,
    StageStatus,
    StageType,
    Workflow,
    WorkflowState,
)
from aizen.state import reset


@pytest.fixture
def engine(tmp_path: Path, monkeypatch):
    from aizen.engine import WorkflowEngine
    from aizen.models import StageState, StageStatus

    monkeypatch.setattr("aizen.engine.save", lambda *a, **kw: None)

    def fake_checkpoint(state, stage_id, status, project_dir=None, output=None, error=None):
        if stage_id not in state.stages:
            state.stages[stage_id] = StageState(stage_id=stage_id)
        ss = state.stages[stage_id]
        ss.status = status
        ss.attempts += 1
        if output is not None:
            ss.output = output
        if error is not None:
            ss.error = error
        state.running_stages = {stage_id}
        return state

    monkeypatch.setattr("aizen.engine.checkpoint", fake_checkpoint)
    return WorkflowEngine


def make_workflow(stages: list[Stage]) -> Workflow:
    return Workflow(name="test", stages=stages)


def make_state(wf: Workflow) -> WorkflowState:
    return reset(wf)


def test_linear_workflow(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command="true", depends_on=["b"]),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    final = eng.run()
    assert all(s.status == StageStatus.COMPLETED for s in final.stages.values())


def test_parallel_dag(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="d", type=StageType.SHELL, command="true", depends_on=["b", "c"]),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    final = eng.run()
    assert all(s.status == StageStatus.COMPLETED for s in final.stages.values())


def test_failure_stops(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="exit 1"),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    from aizen.engine import WorkflowFailed
    with pytest.raises(WorkflowFailed):
        eng.run()


def test_failure_continue(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="exit 1", on_fail=OnFailStrategy.CONTINUE),
        Stage(id="b", type=StageType.SHELL, command="true"),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    final = eng.run()
    assert final.stages["a"].status == StageStatus.FAILED
    assert final.stages["b"].status == StageStatus.COMPLETED


def test_failure_retry_then_success(engine):
    class RetryShellRunner:
        def __init__(self):
            self._attempts = 0

        def run(self, stage, state, context=None):
            self._attempts += 1
            state.attempts = self._attempts
            if self._attempts < 2:
                state.status = StageStatus.FAILED
                state.error = "attempt failed"
            else:
                state.status = StageStatus.COMPLETED
            return state

    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true", on_fail=OnFailStrategy.RETRY, max_retries=2),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    eng._runners[StageType.SHELL] = RetryShellRunner()
    final = eng.run()
    assert final.stages["a"].status == StageStatus.COMPLETED


def test_deadlock(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true", depends_on=["nonexistent"]),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    from aizen.engine import WorkflowDeadlock
    with pytest.raises(WorkflowDeadlock):
        eng.run()


def test_approval_skip(engine, monkeypatch):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true", requires_approval=True),
    ])
    state = make_state(wf)
    monkeypatch.setattr("sys.stdin.readline", lambda: "n\n")
    eng = engine(wf, state, {"headless": False})
    final = eng.run()
    assert final.stages["a"].status == StageStatus.SKIPPED


def test_resume(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command="true", depends_on=["b"]),
    ])
    state = make_state(wf)
    state.stages["a"].status = StageStatus.COMPLETED
    eng = engine(wf, state, {"headless": True})
    final = eng.run()
    assert final.stages["b"].status == StageStatus.COMPLETED
    assert final.stages["c"].status == StageStatus.COMPLETED


def test_empty_workflow(engine):
    wf = make_workflow([])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    final = eng.run()
    assert final.stages == {}


def test_parallel_execution(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="d", type=StageType.SHELL, command="true", depends_on=["b", "c"]),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    final = eng.run(parallel=True)
    assert all(s.status == StageStatus.COMPLETED for s in final.stages.values())


def test_parallel_multiwave(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="d", type=StageType.SHELL, command="true", depends_on=["b"]),
        Stage(id="e", type=StageType.SHELL, command="true", depends_on=["c"]),
        Stage(id="f", type=StageType.SHELL, command="true", depends_on=["d", "e"]),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    final = eng.run(parallel=True)
    assert all(s.status == StageStatus.COMPLETED for s in final.stages.values())


def test_parallel_failure_stops(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="exit 1", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="d", type=StageType.SHELL, command="true", depends_on=["b", "c"]),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    from aizen.engine import WorkflowFailed
    with pytest.raises(WorkflowFailed):
        eng.run(parallel=True)
    assert state.stages["a"].status == StageStatus.COMPLETED
    assert state.stages["b"].status == StageStatus.FAILED
    assert state.stages["d"].status == StageStatus.PENDING


def test_parallel_retry_isolation(engine):
    class RetryShellRunner:
        def __init__(self):
            self._attempts = 0
        def run(self, stage, state, context=None):
            self._attempts += 1
            state.attempts = self._attempts
            if self._attempts < 2:
                state.status = StageStatus.FAILED
                state.error = "attempt failed"
            else:
                state.status = StageStatus.COMPLETED
            return state

    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="echo a", on_fail=OnFailStrategy.RETRY, max_retries=2),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    eng._runners[StageType.SHELL] = RetryShellRunner()
    final = eng.run(parallel=True)
    assert final.stages["a"].status == StageStatus.COMPLETED
    assert final.stages["a"].attempts == 2


def test_interpolate_stage_output(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL),
        Stage(id="b", type=StageType.SHELL, command='echo ${stages.a.output}'),
    ])
    state = make_state(wf)
    state.stages["a"].status = StageStatus.COMPLETED
    state.stages["a"].output = "hello"
    eng = engine(wf, state, {"headless": True})
    resolved = eng._interpolate(wf.stages[1])
    assert resolved.command == "echo hello"
    assert wf.stages[1].command == 'echo ${stages.a.output}'


def test_interpolate_stage_error(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL),
        Stage(id="b", type=StageType.SHELL, command='echo ${stages.a.error}'),
    ])
    state = make_state(wf)
    state.stages["a"].status = StageStatus.FAILED
    state.stages["a"].error = "something broke"
    eng = engine(wf, state, {"headless": True})
    resolved = eng._interpolate(wf.stages[1])
    assert resolved.command == "echo something broke"


def test_interpolate_variables(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command='echo ${variables.foo}'),
    ])
    state = make_state(wf)
    state.variables["foo"] = "bar"
    eng = engine(wf, state, {"headless": True})
    resolved = eng._interpolate(wf.stages[0])
    assert resolved.command == "echo bar"


def test_interpolate_stage_field(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command='echo ${stage.id}'),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    resolved = eng._interpolate(wf.stages[0])
    assert resolved.command == "echo a"


def test_interpolate_unknown_passthrough(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command='echo ${unknown.path}'),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    resolved = eng._interpolate(wf.stages[0])
    assert resolved.command == 'echo ${unknown.path}'


def test_interpolate_env_values(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL),
        Stage(id="b", type=StageType.SHELL, env={"MSG": "${stages.a.output}"}),
    ])
    state = make_state(wf)
    state.stages["a"].status = StageStatus.COMPLETED
    state.stages["a"].output = "hello"
    eng = engine(wf, state, {"headless": True})
    resolved = eng._interpolate(wf.stages[1])
    assert resolved.env["MSG"] == "hello"


def test_interpolate_variables_field(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, variables={"msg": "Hello ${stage.id}"}),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    resolved = eng._interpolate(wf.stages[0])
    assert resolved.variables["msg"] == "Hello a"


def test_interpolate_in_run(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="printf hello"),
        Stage(id="b", type=StageType.SHELL, command='echo ${stages.a.output}', depends_on=["a"]),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    final = eng.run()
    assert final.stages["a"].status == StageStatus.COMPLETED
    assert final.stages["b"].status == StageStatus.COMPLETED
    assert "hello" in (final.stages["b"].output or "")


def test_interpolate_output_chaining(engine):
    wf = make_workflow([
        Stage(id="a", type=StageType.SHELL, command="printf first"),
        Stage(id="b", type=StageType.SHELL, command="printf second", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command='echo ${stages.a.output}-${stages.b.output}', depends_on=["b"]),
    ])
    state = make_state(wf)
    eng = engine(wf, state, {"headless": True})
    final = eng.run()
    assert final.stages["c"].status == StageStatus.COMPLETED
    output = final.stages["c"].output or ""
    assert "first" in output
    assert "second" in output
