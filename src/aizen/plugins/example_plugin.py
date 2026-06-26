from __future__ import annotations

from aizen.models import Stage, StageState
from aizen.plugins.hooks import HookPoint, get_hook_registry
from aizen.stages.base import BaseStage


class GreeterStage(BaseStage):
    """Example plugin stage that returns a greeting."""

    def run(self, stage: Stage, state: StageState, context: dict | None = None) -> StageState:
        from datetime import datetime, timezone
        from aizen.models import StageStatus

        state.status = StageStatus.RUNNING
        state.started_at = state.started_at or datetime.now(timezone.utc).isoformat()

        name = stage.variables.get("name", "world")
        state.output = f"Hello, {name}! (from plugin at {datetime.now(timezone.utc).isoformat()})"

        state.status = StageStatus.COMPLETED
        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state


def log_before_stage(stage, state, ctx):
    print(f"  [hook] before_stage: {stage.id}")


def register_hooks() -> None:
    registry = get_hook_registry()
    registry.register(HookPoint.BEFORE_STAGE, log_before_stage)
