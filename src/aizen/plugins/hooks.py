from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from aizen.models import Stage, StageState

HookFn = Callable[..., None]


class HookPoint(str, Enum):
    BEFORE_STAGE = "before_stage"
    AFTER_STAGE = "after_stage"
    ON_FAILURE = "on_failure"
    ON_START = "on_start"
    ON_COMPLETE = "on_complete"


@dataclass
class HookRegistry:
    _hooks: dict[HookPoint, list[HookFn]] = field(default_factory=dict)

    def register(self, point: HookPoint, fn: HookFn) -> None:
        if point not in self._hooks:
            self._hooks[point] = []
        self._hooks[point].append(fn)

    def unregister(self, point: HookPoint, fn: HookFn) -> None:
        if point in self._hooks:
            self._hooks[point] = [h for h in self._hooks[point] if h is not fn]

    def trigger(self, point: HookPoint, stage: Stage, state: StageState, ctx: dict[str, Any]) -> None:
        for fn in self._hooks.get(point, []):
            fn(stage, state, ctx)

    def clear(self) -> None:
        self._hooks.clear()


_registry: HookRegistry | None = None


def get_hook_registry() -> HookRegistry:
    global _registry
    if _registry is None:
        _registry = HookRegistry()
    return _registry
