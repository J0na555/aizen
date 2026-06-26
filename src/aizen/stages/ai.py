from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from aizen.models import Stage, StageState, StageStatus
from aizen.stages.base import BaseStage


class AIRunner(BaseStage):
    def run(self, stage: Stage, state: StageState, context: dict | None = None) -> StageState:
        if not stage.prompt:
            state.status = StageStatus.FAILED
            state.error = "No prompt specified"
            state.completed_at = datetime.now(timezone.utc).isoformat()
            return state

        state.status = StageStatus.RUNNING
        state.started_at = state.started_at or datetime.now(timezone.utc).isoformat()

        provider = (context or {}).get("ai_provider", "claude")
        output_path = stage.output

        try:
            if provider == "claude":
                result = self._run_claude(stage, context)
            elif provider == "opencode":
                result = self._run_opencode(stage, context)
            elif provider == "codex":
                result = self._run_codex(stage, context)
            else:
                result = self._run_claude(stage, context)

            state.output = result

            if output_path and result:
                project_dir = (context or {}).get("project_dir", ".")
                path = Path(project_dir) / output_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(result)

            state.status = StageStatus.COMPLETED

        except FileNotFoundError:
            state.status = StageStatus.FAILED
            state.error = f"'{provider}' CLI not found. Is it installed?"
        except subprocess.TimeoutExpired:
            state.status = StageStatus.FAILED
            state.error = f"AI request timed out after {stage.timeout_s}s"
        except Exception as e:
            state.status = StageStatus.FAILED
            state.error = str(e)

        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state

    def _run_claude(self, stage: Stage, context: dict | None = None) -> str:
        cmd = ["claude", "-p", stage.prompt]
        if stage.model:
            cmd.extend(["--model", stage.model])
        if stage.timeout_s:
            cmd.extend(["--timeout", str(stage.timeout_s)])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=stage.timeout_s)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or f"Claude exited with code {result.returncode}")
        return result.stdout.strip()

    def _run_opencode(self, stage: Stage, context: dict | None = None) -> str:
        cmd = ["opencode", "run", stage.prompt]
        if stage.model:
            cmd.extend(["--model", stage.model])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=stage.timeout_s)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or f"OpenCode exited with code {result.returncode}")
        return result.stdout.strip()

    def _run_codex(self, stage: Stage, context: dict | None = None) -> str:
        cmd = ["codex", "-p", stage.prompt]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=stage.timeout_s)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or f"Codex exited with code {result.returncode}")
        return result.stdout.strip()
