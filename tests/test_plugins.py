from __future__ import annotations

from pathlib import Path

from aizen.models import Stage, StageState, StageStatus, StageType
from aizen.plugins.hooks import HookPoint, get_hook_registry
from aizen.plugins.loader import discover_plugins


def test_hook_registry():
    reg = get_hook_registry()
    reg.clear()

    calls: list[str] = []

    def my_hook(stage, state, ctx):
        calls.append(stage.id)

    reg.register(HookPoint.BEFORE_STAGE, my_hook)
    reg.trigger(HookPoint.BEFORE_STAGE, Stage(id="s1", type=StageType.SHELL), None, {})
    assert calls == ["s1"]

    reg.unregister(HookPoint.BEFORE_STAGE, my_hook)
    calls.clear()
    reg.trigger(HookPoint.BEFORE_STAGE, Stage(id="s2", type=StageType.SHELL), None, {})
    assert calls == []


def test_hook_multiple():
    reg = get_hook_registry()
    reg.clear()

    results: list[str] = []

    def fn1(stage, state, ctx):
        results.append("fn1")

    def fn2(stage, state, ctx):
        results.append("fn2")

    reg.register(HookPoint.AFTER_STAGE, fn1)
    reg.register(HookPoint.AFTER_STAGE, fn2)
    reg.trigger(HookPoint.AFTER_STAGE, Stage(id="s1", type=StageType.SHELL), None, {})
    assert results == ["fn1", "fn2"]
    reg.clear()


def test_hook_all_points_defined():
    expected = {"before_stage", "after_stage", "on_failure", "on_start", "on_complete"}
    actual = {h.value for h in HookPoint}
    assert actual == expected


def test_discover_plugins_no_dir(tmp_path: Path):
    plugins = discover_plugins(str(tmp_path / "nonexistent"))
    assert plugins == {}
