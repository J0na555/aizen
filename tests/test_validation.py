from __future__ import annotations

from aizen.models import OnFailStrategy, Stage, StageType, Workflow
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


def test_mcp_no_url():
    wf = Workflow(
        name="test",
        stages=[Stage(id="m", type=StageType.MCP)],
    )
    errors = validate_workflow(wf)
    assert any("url" in str(e).lower() for e in errors)


def test_mcp_with_url():
    wf = Workflow(
        name="test",
        stages=[Stage(id="m", type=StageType.MCP, command="http://localhost:8080")],
    )
    errors = validate_workflow(wf)
    assert not any("url" in str(e).lower() for e in errors)


def test_retry_requires_max_retries():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.SHELL, command="true", on_fail=OnFailStrategy.RETRY, max_retries=0)],
    )
    errors = validate_workflow(wf)
    assert any("max_retries" in str(e).lower() for e in errors)


def test_retry_valid_max_retries():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.SHELL, command="true", on_fail=OnFailStrategy.RETRY, max_retries=3)],
    )
    errors = validate_workflow(wf)
    assert not any("max_retries" in str(e).lower() for e in errors)


def test_self_referential_dependency():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.SHELL, command="true", depends_on=["a"])],
    )
    errors = validate_workflow(wf)
    assert any("depends on itself" in str(e).lower() for e in errors)


def test_env_values_must_be_strings():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.SHELL, command="true", env={"PORT": "8080"})],
    )
    errors = validate_workflow(wf)
    assert not errors


def test_timeout_must_be_positive():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.SHELL, command="true", timeout_s=-1)],
    )
    errors = validate_workflow(wf)
    assert any("timeout" in str(e).lower() for e in errors)


def test_timeout_zero_invalid():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.SHELL, command="true", timeout_s=0)],
    )
    errors = validate_workflow(wf)
    assert any("timeout" in str(e).lower() for e in errors)


def test_timeout_valid_positive():
    wf = Workflow(
        name="test",
        stages=[Stage(id="a", type=StageType.SHELL, command="true", timeout_s=30)],
    )
    errors = validate_workflow(wf)
    assert not any("timeout" in str(e).lower() for e in errors)
