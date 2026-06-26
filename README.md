# Aizen

Universal task orchestrator — a DAG-based workflow engine with multi-AI backends, plugin support, parallel execution, variable interpolation, streaming AI output, and checkpoint/resume.

Pipeline stages run shell commands, AI prompts (Claude, OpenCode, Codex, Gemini), MCP server calls, or Python functions. Workflows are defined as YAML, executed in dependency order, and can be run in parallel, paused/resumed, or dry-run before execution.

```
aizen run workflows/pipeline.yaml --parallel
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | New project setup, existing project workflows, quick reference |
| [Workflows](docs/workflows.md) | Full YAML reference, stage types, validation rules |
| [Plugins & Skills](docs/plugins.md) | Create custom runners, hook system, installation |
| [AI Backends](docs/ai-backends.md) | Claude, Codex, Gemini, OpenCode setup and configuration |
| [MCP Integration](docs/mcp.md) | Connect external tools via MCP servers |
| [Advanced Guides](docs/advanced.md) | Parallel execution, variable interpolation, dry-run, streaming, resume |

## Install

```bash
git clone https://github.com/J0na555/aizen.git
cd aizen
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.10+.

## Quick Start

```bash
# Initialize aizen in a project
cd my-project
aizen init

# Run a workflow
aizen run workflows/feature.yaml

# Run independent stages in parallel
aizen run workflows/feature.yaml --parallel

# Preview without executing
aizen run workflows/feature.yaml --dry-run

# Check progress
aizen status

# Pause (Ctrl+C during run) and resume
aizen resume

# Roll back to a specific stage
aizen rollback plan

# Edit a stage's YAML in $EDITOR
aizen edit plan

# List available workflows and plugins
aizen list

# View run history
aizen list-runs

# Show version
aizen --version
```

## Workflow YAML Reference

Workflows are YAML files with a name and a list of stages. Each stage has a type, optional dependencies, and type-specific configuration.

### Stage Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | string | **required** | Unique stage identifier |
| `type` | string | **required** | One of: `shell`, `ai`, `mcp`, `python`, `plugin` |
| `command` | string | null | Shell command, Python `module.function`, or MCP endpoint |
| `prompt` | string | null | AI prompt (for `ai` type stages) |
| `depends_on` | list | `[]` | Stage IDs that must complete before this one starts |
| `output` | string | null | File path to write stage output to |
| `model` | string | null | AI model override (e.g. `claude-sonnet-4`) |
| `on_fail` | string | `"stop"` | `"stop"`, `"continue"`, or `"retry"` |
| `max_retries` | int | `0` | Max retry attempts (when `on_fail: retry`) |
| `requires_approval` | bool | `false` | Prompt before running this stage |
| `timeout_s` | int | null | Timeout in seconds |
| `env` | dict | `{}` | Environment variables for shell stages |
| `variables` | dict | `{}` | Custom variables passed to Python/plugin stages |
| `plugin` | string | null | Plugin stage name (for `plugin` type) |

### Stage Types

**`shell`** — Runs a shell command and captures stdout.
```yaml
- id: lint
  type: shell
  command: "ruff check src/"
  on_fail: continue
```

**`ai`** — Sends a prompt to an AI CLI (auto-detected: claude, opencode, codex, gemini).
```yaml
- id: plan
  type: ai
  prompt: "Analyze the requirements and create an implementation plan."
  model: claude-sonnet-4
  output: plan.md
```

**`mcp`** — Calls an MCP (Model Context Protocol) server via HTTP POST.
```yaml
- id: fetch-data
  type: mcp
  command: "https://mcp.example.com/api/tool"
  variables:
    action: "search"
    query: "python orm"
```

**`python`** — Imports a Python module and calls a function.
```yaml
- id: validate
  type: python
  command: "myproject.validators.run_checks"
```

**`plugin`** — Uses a community plugin installed in `~/.aizen/plugins/`.
```yaml
- id: notify
  type: plugin
  plugin: "SlackNotifier"
  variables:
    channel: "#deploy"
```

### On-Fail Strategies

- **`stop`** (default) — Immediately halts the workflow. Other stages are not executed.
- **`continue`** — Marks the stage as failed but continues executing remaining stages.
- **`retry`** — Resets the stage to pending and retries up to `max_retries` times.

### Full Example

```yaml
name: "Build and deploy feature"
description: "Plan, implement, test, and deploy a new feature"
variables:
  feature: "dark-mode-toggle"

stages:
  - id: plan
    type: ai
    prompt: |
      Analyze the requirements for implementing {{ feature }}.
      Create a detailed plan in plan.md.
    model: claude-sonnet-4
    output: plan.md
    requires_approval: true

  - id: implement
    type: ai
    prompt: "Implement {{ feature }} following plan.md"
    model: claude-sonnet-4
    depends_on: [plan]

  - id: lint
    type: shell
    command: "ruff check src/"
    depends_on: [implement]
    on_fail: continue

  - id: test
    type: shell
    command: "pytest tests/ -v"
    depends_on: [implement]
    on_fail: retry
    max_retries: 2
    timeout_s: 120

  - id: deploy
    type: shell
    command: "git push && gh workflow run deploy.yml"
    depends_on: [lint, test]
    requires_approval: true
```

## CLI Commands

### `aizen init [path]`

Creates `.aizen/config.yaml` in the project directory and registers it in the global project list (`~/.aizen/config.yaml`).

### `aizen run [options] <workflow.yaml>`

Loads a workflow YAML, validates it, resolves the DAG, and executes stages in dependency order.

- `--resume / -r` — Resume from the last saved checkpoint instead of starting fresh.
- `--parallel / -p` — Run independent stages concurrently (up to 4 workers).
- `--headless` — Non-interactive mode. Auto-approves approval gates, no prompts.
- `--dry-run` — Print execution plan (waves, types, approval gates, retries) without running anything.

On Ctrl+C, the engine pauses after the current stage and saves state. Run `aizen resume` to continue.

### `aizen status`

Renders a Rich table of current workflow progress: each stage with its status, attempt count, and error message.

### `aizen pause`

Creates a `.aizen/pause.flag` file. The engine checks for this file at each checkpoint. (In the same terminal, just press Ctrl+C.)

### `aizen resume [--workflow <file>]`

Clears the pause flag and resumes execution from the last saved state. Optionally specify a workflow file if the state doesn't have one.

### `aizen rollback <stage_id>`

Resets the specified stage and all transitive downstream dependencies to PENDING. Other stages keep their current status.

### `aizen list`

Shows available workflows from `~/.aizen/workflows/` and the project's `workflows/` directory, plus discovered plugins and built-in stage types.

### `aizen plugins [list|install] [url]`

- `list` — Shows discovered stage plugins and installed packages.
- `install <git-url>` — Clones a git repository into `~/.aizen/plugins/`.

### `aizen list-runs`

Shows workflow run history, including current state and archived runs in `.aizen/runs/`.

### `aizen edit <stage_id>`

Opens the stage's YAML definition in `$EDITOR`. On save, validates and patches the workflow file. Uses current workflow from saved state, or specify `--workflow <file>`.

### `aizen --version`

Prints the installed package version.

## Architecture

```
~/.aizen/                          # Global config directory
  config.yaml                      # API keys, project registry
  plugins/                         # Installed stage plugins

project/
  .aizen/
    config.yaml                    # Per-project settings
    state.json                     # Current workflow state (checkpoint)
    runs/                          # Archived workflow runs
      <timestamp>-<name>.json
  workflows/
    feature.yaml                   # Workflow definitions
```

### Modules

| Module | Description |
|---|---|
| `models.py` | Pydantic models: `Stage`, `Workflow`, `StageState`, `WorkflowState`, `GlobalConfig`, `ProjectConfig` |
| `config.py` | Global (`~/.aizen/config.yaml`) and per-project (`.aizen/config.yaml`) config loader/saver |
| `state.py` | State management: save/load/reset/rollback/checkpoint/list_runs/archive/clear |
| `engine.py` | DAG execution engine with dependency resolution, pause/resume, deadlock detection, retry logic |
| `validation.py` | Workflow validation: cycle detection, missing deps, duplicate IDs, type-specific field checks |
| `cli.py` | Typer CLI with Rich output for all commands |
| `stages/base.py` | Abstract `BaseStage` class for runners |
| `stages/shell.py` | Shell subprocess runner with env/timeout/cwd support |
| `stages/ai.py` | AI prompt runner — dispatches to registered backends via `AIRegistry` |
| `stages/mcp.py` | MCP server HTTP POST runner |
| `stages/python.py` | Python function import-and-call runner |
| `ai/base.py` | Abstract `AIClient` interface |
| `ai/claude.py` | `ClaudeClient` — wraps `claude -p` |
| `ai/opencode.py` | `OpenCodeClient` — wraps `opencode run` |
| `ai/codex.py` | `CodexClient` — wraps `codex -p` |
| `ai/gemini.py` | `GeminiClient` — wraps `gemini run` |
| `ai/registry.py` | `AIRegistry` — singleton that auto-detects available AI CLIs via `shutil.which()` |
| `plugins/loader.py` | Discovers `BaseStage` subclasses from `.py` files in `~/.aizen/plugins/` |
| `plugins/installer.py` | Git clone/uninstall/list for plugin packages |
| `plugins/hooks.py` | Hook system: `before_stage`, `after_stage`, `on_failure`, `on_start`, `on_complete` |
| `plugins/registry.py` | Plugin metadata model (`PluginInfo`) and discovery of `plugin.json`/`plugin.yaml` |

### DAG Execution

1. Engine loads workflow and resolves all dependencies into an internal DAG.
2. On each iteration, `_get_ready_stages()` finds all stages whose dependencies are all `COMPLETED`.
3. Each ready stage is dispatched to the appropriate runner via `_get_runner()`.
4. After each stage, state is checkpointed to `.aizen/state.json`.
5. If a stage fails: `stop` raises `WorkflowFailed`, `continue` marks but keeps going, `retry` resets to PENDING and re-executes.
6. If no stages are ready but some remain pending, `WorkflowDeadlock` is raised.
7. Signal handlers: SIGINT pauses (raises `WorkflowPaused`), SIGTERM kills (raises `WorkflowFailed`).

### AI Backend Auto-Detection

The registry checks `PATH` for available AI CLIs:

```
$ aizen status  # (internal)
  Available: opencode, codex, gemini
  (claude not on PATH)
```

The `ai_provider` key in the run context selects the backend. Falls back to `claude` (checks `ProjectConfig.default_ai`, then hardcoded default).

### Plugin System

Plugins are Python classes extending `BaseStage`:

```python
# ~/.aizen/plugins/my_plugin.py
from aizen.models import Stage, StageState, StageStatus
from aizen.stages.base import BaseStage
from datetime import datetime, timezone

class MyStage(BaseStage):
    def run(self, stage, state, context=None):
        state.status = StageStatus.RUNNING
        state.started_at = state.started_at or datetime.now(timezone.utc).isoformat()
        state.output = f"Hello, {stage.variables.get('name', 'world')}!"
        state.status = StageStatus.COMPLETED
        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state
```

Hooks let plugins observe or intercept execution:

```python
from aizen.plugins.hooks import HookPoint, get_hook_registry

def log_before(stage, state, ctx):
    print(f"[hook] about to run {stage.id}")

registry = get_hook_registry()
registry.register(HookPoint.BEFORE_STAGE, log_before)
```

Hook points: `before_stage`, `after_stage`, `on_failure`, `on_start`, `on_complete`.

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

77 tests covering models, state management, DAG engine, config, plugins, workflow validation, parallel execution, variable interpolation, streaming, logging, dry-run, and integration.
