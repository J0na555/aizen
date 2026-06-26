from __future__ import annotations

from pathlib import Path

import yaml

from aizen.models import GlobalConfig, ProjectConfig

GLOBAL_CONFIG_DIR = Path.home() / ".aizen"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"
PROJECT_CONFIG_DIR = ".aizen"
PROJECT_CONFIG_FILE = "config.yaml"


def _ensure_global_dir() -> Path:
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return GLOBAL_CONFIG_DIR


def load_global_config() -> GlobalConfig:
    if GLOBAL_CONFIG_FILE.exists():
        raw = yaml.safe_load(GLOBAL_CONFIG_FILE.read_text())
        return GlobalConfig.model_validate(raw) if raw else GlobalConfig()
    return GlobalConfig()


def save_global_config(config: GlobalConfig) -> None:
    _ensure_global_dir()
    GLOBAL_CONFIG_FILE.write_text(
        yaml.dump(config.model_dump(mode="python", exclude_none=True), default_flow_style=False)
    )


def load_project_config(project_path: str | Path | None = None) -> dict:
    base = Path(project_path).resolve() if project_path else Path.cwd()
    config_file = base / PROJECT_CONFIG_DIR / PROJECT_CONFIG_FILE
    if config_file.exists():
        return yaml.safe_load(config_file.read_text()) or {}
    return {}


def save_project_config(config: dict, project_path: str | Path | None = None) -> None:
    base = Path(project_path).resolve() if project_path else Path.cwd()
    config_dir = base / PROJECT_CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / PROJECT_CONFIG_FILE).write_text(
        yaml.dump(config, default_flow_style=False)
    )


def register_project(path: str | Path) -> ProjectConfig:
    config = load_global_config()
    resolved = str(Path(path).resolve())
    existing = [p for p in config.projects if p.path == resolved]
    if not existing:
        pc = ProjectConfig(path=resolved)
        config.projects.append(pc)
        save_global_config(config)
        return pc
    return existing[0]


def get_global_state_dir(project_path: str | Path | None = None) -> Path:
    base = Path(project_path).resolve() if project_path else Path.cwd()
    state_dir = base / PROJECT_CONFIG_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir
