from __future__ import annotations

from pathlib import Path

import pytest

from aizen.models import Stage, StageState, StageStatus, StageType
from aizen.plugins.hooks import HookPoint, get_hook_registry
from aizen.plugins.loader import discover_plugins
from aizen.plugins.registry import PluginInfo, _check_dependencies


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


def test_auto_register_hooks(tmp_path: Path, monkeypatch):
    plugin_file = tmp_path / "myplugin.py"
    plugin_file.write_text("""
from aizen.stages.base import BaseStage
from aizen.models import Stage, StageState

_hook_called = False

def register_hooks():
    global _hook_called
    _hook_called = True

class MyStage(BaseStage):
    def run(self, stage, state, context=None):
        state.output = "ok"
        return state
""")
    monkeypatch.setattr("aizen.plugins.loader.logger", DummyLogger())
    plugins = discover_plugins(str(tmp_path))
    assert "myplugin.MyStage" in plugins

    import myplugin
    assert myplugin._hook_called


def test_subdirectory_plugin(tmp_path: Path, monkeypatch):
    pkg_dir = tmp_path / "mypackage"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("""
from aizen.stages.base import BaseStage
from aizen.models import Stage, StageState

class PkgStage(BaseStage):
    def run(self, stage, state, context=None):
        state.output = "ok"
        return state
""")
    monkeypatch.setattr("aizen.plugins.loader.logger", DummyLogger())
    plugins = discover_plugins(str(tmp_path))
    assert "mypackage.PkgStage" in plugins


def test_dependency_check_warning(caplog):
    import logging
    caplog.set_level(logging.WARNING)
    info = PluginInfo(name="test-plugin", dependencies=["nonexistent_package_xyz"])
    _check_dependencies(info)
    assert any("test-plugin" in r.message and "nonexistent_package_xyz" in r.message for r in caplog.records)


def test_dependency_check_ok(caplog):
    import logging
    caplog.set_level(logging.WARNING)
    info = PluginInfo(name="test-plugin", dependencies=["json"])
    _check_dependencies(info)
    assert not any("test-plugin" in r.message for r in caplog.records)


class DummyLogger:
    def warning(self, *a, **kw):
        pass
    def debug(self, *a, **kw):
        pass
