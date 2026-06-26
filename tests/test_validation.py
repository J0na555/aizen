from __future__ import annotations

from aizen.models import Stage, StageType, Workflow
from aizen.validation import validate_workflow


def test_valid_workflow():
    wf = Workflow(
        name="test",
        stages=[
            Stage(id="a", type=StageType.SHELL, command="echo hi"),
            Stage(id="b", type=StageType.SHELL, command="echo there", depends_on=["a"]),
        ],
    )
    errors = validate_workflow(wf)
    assert errors == []


def test_missing_name():
    wf = Workflow(name="", stages=[])
    errors = validate_workflow(wf)
    assert any("name" in str(e).lower() for e in errors)


def test_empty_stages():
    wf = Workflow(name="test", stages=[])
    errors = validate_workflow(wf)
    assert any("must have at least one" in str(e).lower() for e in errors)


def test_duplicate_id():
    wf = Workflow(
        name="test",
        stages=[
            Stage(id="a", type=StageType.SHELL),
            Stage(id="a", type=StageType.SHELL),
        ],
    )
    errors = validate_workflow(wf)
    assert any("duplicate" in str(e).lower() for e in errors)


def test_missing_dep():
    wf = Workflow(
        name="test",
        stages=[
            Stage(id="a", type=StageType.SHELL, depends_on=["b"]),
        ],
    )
    errors = validate_workflow(wf)
    assert any("unknown" in str(e).lower() for e in errors)


def test_shell_no_command():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.SHELL)],
    )
    errors = validate_workflow(wf)
    assert any("no command" in str(e).lower() for e in errors)


def test_ai_no_prompt():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.AI)],
    )
    errors = validate_workflow(wf)
    assert any("no prompt" in str(e).lower() for e in errors)


def test_cycle_detected():
    wf = Workflow(
        name="test",
        stages=[
            Stage(id="a", type=StageType.SHELL, depends_on=["c"]),
            Stage(id="b", type=StageType.SHELL, depends_on=["a"]),
            Stage(id="c", type=StageType.SHELL, depends_on=["b"]),
        ],
    )
    errors = validate_workflow(wf)
    assert any("cycle" in str(e).lower() for e in errors)
