from __future__ import annotations

import subprocess
from pathlib import Path

PLUGINS_DIR = Path.home() / ".aizen" / "plugins"


def install_from_git(url: str) -> str:
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    target = PLUGINS_DIR / repo_name

    if target.exists():
        raise FileExistsError(f"Plugin '{repo_name}' already installed at {target}")

    result = subprocess.run(
        ["git", "clone", url, str(target)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone {url}: {result.stderr}")

    return repo_name


def uninstall(name: str) -> None:
    target = PLUGINS_DIR / name
    if not target.exists():
        raise FileNotFoundError(f"Plugin '{name}' not found at {target}")
    import shutil
    shutil.rmtree(target)


def list_installed() -> list[dict]:
    if not PLUGINS_DIR.exists():
        return []
    items: list[dict] = []
    for entry in sorted(PLUGINS_DIR.iterdir()):
        if entry.is_dir() and not entry.name.startswith("_"):
            py_files = list(entry.rglob("*.py"))
            items.append({
                "name": entry.name,
                "path": str(entry),
                "stages": len(py_files),
            })
    return items
