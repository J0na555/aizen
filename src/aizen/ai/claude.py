from __future__ import annotations

import shutil
import subprocess
from collections.abc import Generator

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

    def run_streaming(self, prompt: str, model: str | None = None, context: dict | None = None) -> Generator[str, None, str]:
        if not self.is_available():
            raise FileNotFoundError("claude CLI not found")
        cmd = ["claude", "-p", prompt]
        if model:
            cmd.extend(["--model", model])
        lines: list[str] = []
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            for line in proc.stdout:
                lines.append(line)
                yield line
            proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(stderr or f"Claude exited with code {proc.returncode}")
        full = "".join(lines).strip()
        return full
