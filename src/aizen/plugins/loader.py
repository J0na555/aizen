from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

from aizen.stages.base import BaseStage

logger = logging.getLogger("aizen.plugins.loader")


def _import_module(name: str, path: Path) -> object | None:
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    try:
        return importlib.import_module(name)
    except Exception as e:
        logger.warning("Failed to import plugin module '%s': %s", name, e)
        return None


def _extract_stages(module: object, prefix: str) -> dict[str, type[BaseStage]]:
    stages: dict[str, type[BaseStage]] = {}
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, BaseStage) and attr is not BaseStage:
            stages[f"{prefix}.{attr_name}"] = attr
    return stages


def _try_register_hooks(module: object) -> None:
    register = getattr(module, "register_hooks", None)
    if callable(register):
        try:
            register()
            logger.debug("Auto-registered hooks from %s", getattr(module, "__name__", "?"))
        except Exception as e:
            logger.warning("register_hooks() failed in %s: %s", getattr(module, "__name__", "?"), e)


def discover_plugins(plugins_dir: str = "~/.aizen/plugins") -> dict[str, type[BaseStage]]:
    plugin_path = Path(plugins_dir).expanduser()
    if not plugin_path.exists():
        return {}

    if str(plugin_path) not in sys.path:
        sys.path.insert(0, str(plugin_path))

    plugins: dict[str, type[BaseStage]] = {}

    # Scan top-level .py files
    for py_file in sorted(plugin_path.glob("*.py")):
        if py_file.stem.startswith("_"):
            continue
        module = _import_module(py_file.stem, py_file)
        if module is None:
            continue
        _try_register_hooks(module)
        plugins.update(_extract_stages(module, py_file.stem))

    # Scan subdirectory packages
    for entry in sorted(plugin_path.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        init_file = entry / "__init__.py"
        if not init_file.exists():
            continue
        module = _import_module(entry.name, init_file)
        if module is None:
            continue
        _try_register_hooks(module)
        plugins.update(_extract_stages(module, entry.name))

    return plugins
