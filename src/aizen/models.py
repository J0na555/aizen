from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StageType(str, Enum):
    SHELL = "shell"
    AI = "ai"
    MCP = "mcp"
    PYTHON = "python"
    PLUGIN = "plugin"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"


class OnFailStrategy(str, Enum):
    STOP = "stop"
    CONTINUE = "continue"
    RETRY = "retry"


class Stage(BaseModel):
    id: str
    type: StageType
    prompt: str | None = None
    command: str | None = None
    plugin: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    output: str | None = None
    model: str | None = None
    on_fail: OnFailStrategy = OnFailStrategy.STOP
    requires_approval: bool = False
    max_retries: int = 0
    timeout_s: int | None = None
    env: dict[str, str] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)


class Workflow(BaseModel):
    name: str
    description: str | None = None
    stages: list[Stage]
    variables: dict[str, Any] = Field(default_factory=dict)


class StageState(BaseModel):
    stage_id: str
    status: StageStatus = StageStatus.PENDING
    output: Any = None
    error: str | None = None
    attempts: int = 0
    started_at: str | None = None
    completed_at: str | None = None


class WorkflowState(BaseModel):
    workflow_name: str
    project_path: str | None = None
    stages: dict[str, StageState] = Field(default_factory=dict)
    current_stage_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    variables: dict[str, Any] = Field(default_factory=dict)


class AIConfig(BaseModel):
    provider: str = "claude"
    model: str | None = None
    api_key: str | None = None


class ProjectConfig(BaseModel):
    path: str
    default_workflow: str | None = None
    default_ai: str = "claude"


class GlobalConfig(BaseModel):
    api_keys: dict[str, str] = Field(default_factory=dict)
    default_model: str = "claude-sonnet"
    projects: list[ProjectConfig] = Field(default_factory=list)
    plugins_dir: str = "~/.aizen/plugins"
    workflows_dir: str = "~/.aizen/workflows"
