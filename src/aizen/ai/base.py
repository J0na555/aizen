from __future__ import annotations

from abc import ABC, abstractmethod


class AIClient(ABC):
    @abstractmethod
    def run(self, prompt: str, model: str | None = None, context: dict | None = None) -> str:
        ...
