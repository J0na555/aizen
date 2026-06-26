from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator


class AIClient(ABC):
    @abstractmethod
    def run(self, prompt: str, model: str | None = None, context: dict | None = None) -> str:
        ...

    def run_streaming(self, prompt: str, model: str | None = None, context: dict | None = None) -> Generator[str, None, str]:
        result = self.run(prompt, model, context)
        yield result
        return result
