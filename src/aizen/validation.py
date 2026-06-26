from __future__ import annotations

from aizen.models import OnFailStrategy, Stage, StageType, Workflow


class ValidationError(Exception):
    def __init__(self, message: str, stage_id: str | None = None):
        self.stage_id = stage_id
        super().__init__(message)


def validate_workflow(wf: Workflow) -> list[ValidationError]:
    errors: list[ValidationError] = []

    if not wf.name:
        errors.append(ValidationError("Workflow name is required"))

    if not wf.stages:
        errors.append(ValidationError("Workflow must have at least one stage"))
        return errors

    ids = set()
    for stage in wf.stages:
        if not stage.id:
            errors.append(ValidationError("Stage must have an id"))
            continue
        if stage.id in ids:
            errors.append(ValidationError(f"Duplicate stage id: '{stage.id}'", stage.id))
        ids.add(stage.id)

    for stage in wf.stages:
        for dep in stage.depends_on:
            if dep not in ids:
                errors.append(ValidationError(
                    f"Stage '{stage.id}' depends on unknown stage '{dep}'", stage.id
                ))

    if _has_cycle(wf.stages):
        errors.append(ValidationError("Workflow contains a cycle"))

    for stage in wf.stages:
        if stage.type == StageType.SHELL and not stage.command:
            errors.append(ValidationError(f"Shell stage '{stage.id}' has no command", stage.id))
        if stage.type == StageType.AI and not stage.prompt:
            errors.append(ValidationError(f"AI stage '{stage.id}' has no prompt", stage.id))
        if stage.type == StageType.PYTHON and not stage.command:
            errors.append(ValidationError(f"Python stage '{stage.id}' has no module.function", stage.id))
        if stage.type == StageType.PLUGIN and not stage.plugin:
            errors.append(ValidationError(f"Plugin stage '{stage.id}' has no plugin name", stage.id))
        if stage.type == StageType.MCP and not stage.command:
            errors.append(ValidationError(f"MCP stage '{stage.id}' requires a server URL in command", stage.id))
        if stage.on_fail == OnFailStrategy.RETRY and stage.max_retries < 1:
            errors.append(ValidationError(
                f"Stage '{stage.id}' has on_fail=retry but max_retries={stage.max_retries} (must be >= 1)", stage.id
            ))
        if stage.id in stage.depends_on:
            errors.append(ValidationError(f"Stage '{stage.id}' depends on itself", stage.id))
        for k, v in stage.env.items():
            if not isinstance(v, str):
                errors.append(ValidationError(
                    f"Stage '{stage.id}' env['{k}'] must be a string, got {type(v).__name__}", stage.id
                ))
        if stage.timeout_s is not None and stage.timeout_s <= 0:
            errors.append(ValidationError(f"Stage '{stage.id}' has timeout_s={stage.timeout_s} (must be positive)", stage.id))

    return errors


def _has_cycle(stages: list[Stage]) -> bool:
    graph: dict[str, list[str]] = {s.id: list(s.depends_on) for s in stages}
    visited: set[str] = set()
    path: set[str] = set()

    def dfs(node: str) -> bool:
        if node in path:
            return True
        if node in visited:
            return False
        visited.add(node)
        path.add(node)
        for dep in graph.get(node, []):
            if dep in graph and dfs(dep):
                return True
        path.remove(node)
        return False

    for node in graph:
        if dfs(node):
            return True
    return False
