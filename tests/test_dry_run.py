from __future__ import annotations

from pathlib import Path

from aizen.models import OnFailStrategy, Stage, StageType, Workflow
from aizen.cli import _compute_waves, _print_dry_run_plan


def test_compute_waves_simple():
    stages = [
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command="true", depends_on=["b"]),
    ]
    waves = _compute_waves(stages)
    assert len(waves) == 3
    assert [s.id for s in waves[0]] == ["a"]
    assert [s.id for s in waves[1]] == ["b"]
    assert [s.id for s in waves[2]] == ["c"]


def test_compute_waves_parallel():
    stages = [
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="c", type=StageType.SHELL, command="true", depends_on=["a"]),
        Stage(id="d", type=StageType.SHELL, command="true", depends_on=["b", "c"]),
    ]
    waves = _compute_waves(stages)
    assert len(waves) == 3
    assert [s.id for s in waves[0]] == ["a"]
    assert sorted(s.id for s in waves[1]) == ["b", "c"]
    assert [s.id for s in waves[2]] == ["d"]


def test_compute_waves_no_deps():
    stages = [
        Stage(id="a", type=StageType.SHELL, command="true"),
        Stage(id="b", type=StageType.SHELL, command="true"),
        Stage(id="c", type=StageType.SHELL, command="true"),
    ]
    waves = _compute_waves(stages)
    assert len(waves) == 1
    assert len(waves[0]) == 3


def test_dry_run_plan_produces_output(capsys):
    wf = Workflow(
        name="test-wf",
        stages=[
            Stage(id="a", type=StageType.SHELL, command="true"),
            Stage(id="b", type=StageType.SHELL, command="true", depends_on=["a"]),
        ],
    )
    _print_dry_run_plan(wf)
    captured = capsys.readouterr()
    assert "test-wf" in captured.out
    assert "Dry run complete" in captured.out
    assert "Wave" in captured.out
