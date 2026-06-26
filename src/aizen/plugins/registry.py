from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PLUGINS_DIR = Path.home() / ".aizen" / "plugins"


class PluginInfo(BaseModel):
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    hooks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)


def load_plugin_meta(plugin_dir: Path) -> PluginInfo | None:
    for meta_file in ("plugin.json", "plugin.yaml", "plugin.yml"):
        path = plugin_dir / meta_file
        if path.exists():
            raw = path.read_text()
            if meta_file.endswith((".yaml", ".yml")):
                import yaml
                data = yaml.safe_load(raw)
            else:
                data = json.loads(raw)
            return PluginInfo(**data)
    return None


def save_plugin_meta(info: PluginInfo, plugin_dir: Path) -> None:
    path = plugin_dir / "plugin.json"
    path.write_text(info.model_dump_json(indent=2))


def discover_all() -> dict[str, PluginInfo]:
    if not PLUGINS_DIR.exists():
        return {}
    plugins: dict[str, PluginInfo] = {}
    for entry in sorted(PLUGINS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        meta = load_plugin_meta(entry)
        if meta:
            plugins[meta.name] = meta
    return plugins


def get_plugin_info(name: str) -> PluginInfo | None:
    return discover_all().get(name)
