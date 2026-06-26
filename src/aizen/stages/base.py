from __future__ import annotations

from abc import ABC, abstractmethod

from aizen.models import Stage, StageState, StageStatus


class BaseStage(ABC):
    @abstractmethod
    def run(self, stage: Stage, state: StageState, context: dict | None = None) -> StageState:
        ...
