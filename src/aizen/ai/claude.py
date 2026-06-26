from __future__ import annotations

import shutil
import subprocess

from aizen.ai.base import AIClient


class ClaudeClient(AIClient):
    def __init__(self) -> None:
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is None:
            self._available = shutil.which("claude") is not None
        return self._available

    def run(self, prompt: str, model: str | None = None, context: dict | None = None) -> str:
        if not self.is_available():
            raise FileNotFoundError("claude CLI not found")
        cmd = ["claude", "-p", prompt]
        if model:
            cmd.extend(["--model", model])
        timeout = (context or {}).get("timeout_s")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or f"Claude exited with code {result.returncode}")
        return result.stdout.strip()
