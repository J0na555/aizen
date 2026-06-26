from __future__ import annotations

from aizen.ai.base import AIClient
from aizen.ai.claude import ClaudeClient
from aizen.ai.codex import CodexClient
from aizen.ai.gemini import GeminiClient
from aizen.ai.opencode import OpenCodeClient


class AIRegistry:
    _instance: AIRegistry | None = None

    def __init__(self) -> None:
        self._clients: dict[str, AIClient] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        self.register("claude", ClaudeClient())
        self.register("opencode", OpenCodeClient())
        self.register("codex", CodexClient())
        self.register("gemini", GeminiClient())

    def register(self, name: str, client: AIClient) -> None:
        self._clients[name] = client

    def get(self, name: str) -> AIClient | None:
        return self._clients.get(name)

    def list_available(self) -> dict[str, AIClient]:
        return {name: client for name, client in self._clients.items() if self._is_available(client)}

    def _is_available(self, client: AIClient) -> bool:
        if hasattr(client, "is_available") and callable(client.is_available):
            return client.is_available()
        return True

    def resolve(self, name: str) -> AIClient:
        client = self.get(name)
        if client is None:
            msg = f"Unknown AI provider: {name}"
            raise ValueError(msg)
        available = self.list_available()
        if name not in available:
            msg = f"AI provider '{name}' not available (CLI not found on PATH)"
            raise FileNotFoundError(msg)
        return client


def get_registry() -> AIRegistry:
    if AIRegistry._instance is None:
        AIRegistry._instance = AIRegistry()
    return AIRegistry._instance
