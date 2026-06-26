from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx

from aizen.models import Stage, StageState, StageStatus
from aizen.stages.base import BaseStage


class MCPRunner(BaseStage):
    def run(self, stage: Stage, state: StageState, context: dict | None = None) -> StageState:
        ctx = context or {}
        server_url = stage.command or ctx.get("mcp_server_url", "")

        if not server_url:
            state.status = StageStatus.FAILED
            state.error = "No MCP server URL provided (set stage.command or context['mcp_server_url'])"
            state.completed_at = datetime.now(timezone.utc).isoformat()
            return state

        if not stage.prompt:
            state.status = StageStatus.FAILED
            state.error = "No prompt specified for MCP call"
            state.completed_at = datetime.now(timezone.utc).isoformat()
            return state

        state.status = StageStatus.RUNNING
        state.started_at = state.started_at or datetime.now(timezone.utc).isoformat()

        try:
            payload: dict[str, Any] = {
                "prompt": stage.prompt,
                "variables": stage.variables,
            }

            api_key = ctx.get("mcp_api_key") or ""
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            timeout = httpx.Timeout(stage.timeout_s or 60.0)

            with httpx.Client() as client:
                response = client.post(
                    server_url.rstrip("/") + "/execute",
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()

            state.output = data.get("output", data)
            state.status = StageStatus.COMPLETED

        except httpx.HTTPStatusError as e:
            state.status = StageStatus.FAILED
            state.error = f"MCP server returned {e.response.status_code}: {e.response.text}"
        except httpx.RequestError as e:
            state.status = StageStatus.FAILED
            state.error = f"MCP request failed: {e}"
        except json.JSONDecodeError as e:
            state.status = StageStatus.FAILED
            state.error = f"Invalid JSON response from MCP server: {e}"
        except Exception as e:
            state.status = StageStatus.FAILED
            state.error = str(e)

        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state
