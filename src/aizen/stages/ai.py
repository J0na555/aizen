from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.live import Live
from rich.text import Text

from aizen.ai.registry import get_registry
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
            registry = get_registry()
            client = registry.resolve(provider)
            ctx = dict(context or {})
            if stage.timeout_s:
                ctx["timeout_s"] = stage.timeout_s

            if stage.stream:
                result = self._run_streaming(client, stage, ctx)
            else:
                result = client.run(stage.prompt, model=stage.model, context=ctx)

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
        except TimeoutError:
            state.status = StageStatus.FAILED
            state.error = f"AI request timed out after {stage.timeout_s}s"
        except Exception as e:
            state.status = StageStatus.FAILED
            state.error = str(e)

        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state

    def _run_streaming(self, client, stage: Stage, ctx: dict) -> str:
        lines: list[str] = []
        with Live(Text(), refresh_per_second=10, vertical_overflow="visible") as live:
            for chunk in client.run_streaming(stage.prompt, model=stage.model, context=ctx):
                lines.append(chunk)
                content = "".join(lines)
                live.update(Text.from_ansi(content))
        return "".join(lines)
