from __future__ import annotations

import importlib
import sys
from pathlib import Path

from aizen.stages.base import BaseStage


def discover_plugins(plugins_dir: str = "~/.aizen/plugins") -> dict[str, type[BaseStage]]:
    plugin_path = Path(plugins_dir).expanduser()
    if not plugin_path.exists():
        return {}

    if str(plugin_path) not in sys.path:
        sys.path.insert(0, str(plugin_path))

    plugins: dict[str, type[BaseStage]] = {}
    for py_file in sorted(plugin_path.glob("*.py")):
        if py_file.stem.startswith("_"):
            continue
        module = importlib.import_module(py_file.stem)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseStage) and attr is not BaseStage:
                plugins[f"{py_file.stem}.{attr_name}"] = attr
    return plugins
