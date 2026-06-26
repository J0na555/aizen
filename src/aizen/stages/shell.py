from __future__ import annotations

import os
import shlex
import subprocess
from datetime import datetime, timezone

from aizen.models import Stage, StageState, StageStatus
from aizen.stages.base import BaseStage


class ShellRunner(BaseStage):
    def run(self, stage: Stage, state: StageState, context: dict | None = None) -> StageState:
        if not stage.command:
            state.status = StageStatus.FAILED
            state.error = "No command specified"
            state.completed_at = datetime.now(timezone.utc).isoformat()
            return state

        state.status = StageStatus.RUNNING
        state.started_at = state.started_at or datetime.now(timezone.utc).isoformat()

        env = os.environ.copy()
        env.update(stage.env)

        try:
            result = subprocess.run(
                stage.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=stage.timeout_s,
                env=env,
                cwd=context.get("project_dir") if context else None,
            )

            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr if output else result.stderr

            state.output = output

            if result.returncode == 0:
                state.status = StageStatus.COMPLETED
            else:
                state.status = StageStatus.FAILED
                state.error = result.stderr or f"Exit code: {result.returncode}"

        except subprocess.TimeoutExpired:
            state.status = StageStatus.FAILED
            state.error = f"Command timed out after {stage.timeout_s}s"

        except OSError as e:
            state.status = StageStatus.FAILED
            state.error = str(e)

        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state
