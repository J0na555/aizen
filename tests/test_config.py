from __future__ import annotations

from pathlib import Path

from aizen.config import load_global_config, load_project_config, save_project_config


def test_global_config_default():
    cfg = load_global_config()
    assert cfg.default_model == "claude-sonnet"
    assert cfg.plugins_dir == "~/.aizen/plugins"


def test_project_config_roundtrip(tmp_path: Path):
    data = {"name": "testproj", "default_ai": "opencode"}
    save_project_config(data, tmp_path)
    loaded = load_project_config(tmp_path)
    assert loaded.get("name") == "testproj"
    assert loaded.get("default_ai") == "opencode"


def test_project_config_defaults(tmp_path: Path):
    cfg = load_project_config(tmp_path)
    assert cfg == {}
