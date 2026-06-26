from __future__ import annotations

import importlib
from datetime import datetime, timezone

from aizen.models import Stage, StageState, StageStatus
from aizen.stages.base import BaseStage


class PythonRunner(BaseStage):
    def run(self, stage: Stage, state: StageState, context: dict | None = None) -> StageState:
        if not stage.command:
            state.status = StageStatus.FAILED
            state.error = "No module.function specified in stage.command"
            state.completed_at = datetime.now(timezone.utc).isoformat()
            return state

        state.status = StageStatus.RUNNING
        state.started_at = state.started_at or datetime.now(timezone.utc).isoformat()

        try:
            module_path, _, func_name = stage.command.rpartition(".")
            if not module_path or not func_name:
                raise ValueError(
                    f"Invalid format: '{stage.command}'. Expected 'module.function'"
                )

            module = importlib.import_module(module_path)
            func = getattr(module, func_name)

            kwargs = {
                "stage": stage.model_dump(),
                "state": state.model_dump(),
                "variables": stage.variables,
                "context": context or {},
            }

            result = func(**kwargs)
            state.output = result
            state.status = StageStatus.COMPLETED

        except ModuleNotFoundError as e:
            state.status = StageStatus.FAILED
            state.error = f"Module not found: {e}"
        except AttributeError as e:
            state.status = StageStatus.FAILED
            state.error = f"Function not found: {e}"
        except Exception as e:
            state.status = StageStatus.FAILED
            state.error = str(e)

        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state
