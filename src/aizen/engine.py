from __future__ import annotations

import signal
import sys
from datetime import datetime, timezone
from typing import Any

from aizen.models import (
    Stage,
    StageStatus,
    StageType,
    Workflow,
    WorkflowState,
)
from aizen.plugins.hooks import HookPoint, get_hook_registry
from aizen.plugins.loader import discover_plugins
from aizen.stages.ai import AIRunner
from aizen.stages.base import BaseStage
from aizen.stages.mcp import MCPRunner
from aizen.stages.python import PythonRunner
from aizen.stages.shell import ShellRunner
from aizen.state import checkpoint, save


class WorkflowError(Exception):
    ...

class WorkflowFailed(WorkflowError):
    def __init__(self, stage_id: str, message: str = ""):
        self.stage_id = stage_id
        super().__init__(message or f"Stage '{stage_id}' failed")

class WorkflowDeadlock(WorkflowError):
    def __init__(self, pending: list[str]):
        self.pending = pending
        super().__init__(f"Deadlock detected. No ready stages: {pending}")

class WorkflowPaused(WorkflowError):
    ...


class WorkflowEngine:
    def __init__(
        self,
        workflow: Workflow,
        state: WorkflowState,
        context: dict[str, Any] | None = None,
    ):
        self.workflow = workflow
        self.state = state
        self.context = context or {}
        self._paused = False
        self._stage_index = {s.id: s for s in workflow.stages}

        self._runners: dict[StageType, BaseStage] = {
            StageType.SHELL: ShellRunner(),
            StageType.AI: AIRunner(),
            StageType.MCP: MCPRunner(),
            StageType.PYTHON: PythonRunner(),
        }

        self._hooks = get_hook_registry()
        self._headless = self.context.get("headless", False)
        if not self._headless:
            self._setup_signal_handlers()

        self._hooks.trigger(HookPoint.ON_START, Stage(id="__start__", type=StageType.SHELL), None, self.context)

    def _setup_signal_handlers(self) -> None:
        def handler(signum, frame):
            self._paused = True
            print("\nPausing after current stage... (SIGINT to resume, SIGTERM to quit)")

        def term_handler(signum, frame):
            raise WorkflowFailed("__sigterm__", "Forced stop (SIGTERM)")

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, term_handler)

    def run(self, parallel: bool = False, max_workers: int = 4) -> WorkflowState:
        while True:
            if self._paused:
                self.state.updated_at = datetime.now(timezone.utc).isoformat()
                save(self.state, self.context.get("project_dir"))
                raise WorkflowPaused("Execution paused by user")

            ready = self._get_ready_stages()
            if not ready:
                if self._all_done():
                    break
                failed_ids = [
                    s.id for s in self.workflow.stages
                    if self.state.stages.get(s.id)
                    and self.state.stages[s.id].status == StageStatus.FAILED
                    and s.on_fail.value != "continue"
                ]
                if failed_ids:
                    raise WorkflowFailed(failed_ids[0])
                pending = [
                    s.id for s in self.workflow.stages
                    if self.state.stages.get(s.id)
                    and self.state.stages[s.id].status == StageStatus.PENDING
                ]
                raise WorkflowDeadlock(pending)

            for stage in ready:
                if self._paused:
                    raise WorkflowPaused("Execution paused by user")
                self._execute_stage(stage)

        self.state.updated_at = datetime.now(timezone.utc).isoformat()
        save(self.state, self.context.get("project_dir"))
        self._hooks.trigger(HookPoint.ON_COMPLETE, Stage(id="__end__", type=StageType.SHELL), None, self.context)
        return self.state

    def _get_ready_stages(self) -> list[Stage]:
        ready: list[Stage] = []
        for stage in self.workflow.stages:
            ss = self.state.stages.get(stage.id)
            if ss is None or ss.status != StageStatus.PENDING:
                continue
            if all(
                self.state.stages.get(dep)
                and self.state.stages[dep].status == StageStatus.COMPLETED
                for dep in stage.depends_on
            ):
                ready.append(stage)
        return ready

    def _all_done(self) -> bool:
        terminal = {StageStatus.COMPLETED, StageStatus.SKIPPED}
        for stage in self.workflow.stages:
            ss = self.state.stages.get(stage.id)
            if ss is None:
                return False
            if ss.status == StageStatus.FAILED:
                s = self._stage_index.get(stage.id)
                if s and s.on_fail.value == "continue":
                    continue
            if ss.status not in terminal:
                return False
        return True

    def _execute_stage(self, stage: Stage) -> None:
        self.state.current_stage_id = stage.id

        ss = self.state.stages.get(stage.id)
        self._hooks.trigger(HookPoint.BEFORE_STAGE, stage, ss, self.context)

        if stage.requires_approval:
            if self._headless:
                answer = "y"
            else:
                print(f"  [approval required] Stage '{stage.id}' — run? (y/N): ", end="", flush=True)
                answer = sys.stdin.readline().strip().lower()
            if answer not in ("y", "yes"):
                checkpoint(self.state, stage.id, StageStatus.SKIPPED, project_dir=self.context.get("project_dir"))
                return

        runner = self._get_runner(stage)
        if runner is None:
            checkpoint(
                self.state, stage.id, StageStatus.FAILED,
                error=f"No runner for stage type '{stage.type.value}'",
                project_dir=self.context.get("project_dir"),
            )
            return

        result = runner.run(stage, ss, self.context)
        self.state.stages[stage.id] = result
        save(self.state, self.context.get("project_dir"))

        self._hooks.trigger(HookPoint.AFTER_STAGE, stage, result, self.context)

        if result.status == StageStatus.FAILED:
            self._hooks.trigger(HookPoint.ON_FAILURE, stage, result, self.context)
            self._handle_failure(stage, result)

    def _handle_failure(self, stage: Stage, result) -> None:
        if stage.on_fail.value == "stop":
            raise WorkflowFailed(stage.id, result.error or f"Stage '{stage.id}' failed")
        elif stage.on_fail.value == "retry" and result.attempts <= stage.max_retries:
            result.status = StageStatus.PENDING
            result.error = None
            result.completed_at = None
            self.state.stages[stage.id] = result
            save(self.state, self.context.get("project_dir"))
            self._execute_stage(stage)
        elif stage.on_fail.value == "continue":
            pass

    def _get_runner(self, stage: Stage) -> BaseStage | None:
        if stage.type == StageType.PLUGIN:
            plugins = discover_plugins()
            plugin_key = stage.plugin or stage.id
            cls = plugins.get(plugin_key)
            if cls is None:
                alt = plugin_key.split(".")[-1] if "." in plugin_key else None
                if alt:
                    for k, v in plugins.items():
                        if k.endswith("." + alt) or k == alt:
                            cls = v
                            break
            return cls() if cls else None
        return self._runners.get(stage.type)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
