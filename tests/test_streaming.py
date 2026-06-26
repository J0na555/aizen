from __future__ import annotations

from collections.abc import Generator

import pytest

from aizen.ai.base import AIClient
from aizen.models import Stage, StageState, StageStatus, StageType
from aizen.stages.ai import AIRunner


class MockStreamClient(AIClient):
    def run(self, prompt: str, model: str | None = None, context: dict | None = None) -> str:
        return "blocking result"

    def run_streaming(self, prompt: str, model: str | None = None, context: dict | None = None) -> Generator[str, None, str]:
        chunks = ["hello ", "world", " from ", "stream"]
        for c in chunks:
            yield c
        return "hello world from stream"


class MockBlockClient(AIClient):
    def run(self, prompt: str, model: str | None = None, context: dict | None = None) -> str:
        return "blocking result"


def test_base_fallback_to_run():
    client = MockBlockClient()
    results = list(client.run_streaming("test"))
    assert results == ["blocking result"]


def test_streaming_aggregation(monkeypatch):
    runner = AIRunner()
    stage = Stage(id="s1", type=StageType.AI, prompt="test prompt", stream=True)
    state = StageState(stage_id="s1")

    def mock_registry():
        class MockRegistry:
            def resolve(self, name):
                return MockStreamClient()
        return MockRegistry()

    monkeypatch.setattr("aizen.stages.ai.get_registry", mock_registry)
    result = runner.run(stage, state, {"ai_provider": "mock"})
    assert result.status == StageStatus.COMPLETED
    assert result.output == "hello world from stream"


def test_blocking_fallback(monkeypatch):
    runner = AIRunner()
    stage = Stage(id="s1", type=StageType.AI, prompt="test prompt", stream=False)
    state = StageState(stage_id="s1")

    def mock_registry():
        class MockRegistry:
            def resolve(self, name):
                return MockBlockClient()
        return MockRegistry()

    monkeypatch.setattr("aizen.stages.ai.get_registry", mock_registry)
    result = runner.run(stage, state, {"ai_provider": "mock"})
    assert result.status == StageStatus.COMPLETED
    assert result.output == "blocking result"
