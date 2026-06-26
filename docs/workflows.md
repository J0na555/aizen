# Workflow YAML Reference

Workflows are defined as YAML files with a name and a list of stages. Each stage maps to a unit of work with a type, optional dependencies, and type-specific configuration.

## Minimal Workflow

```yaml
name: "hello-world"
stages:
  - id: greet
    type: shell
    command: "echo Hello, World!"
```

## Full Example

```yaml
name: "Build and Deploy"
description: "Full CI/CD pipeline with AI planning"
variables:
  branch: "main"
  feature: "dark-mode"

stages:
  - id: plan
    type: ai
    prompt: "Create an implementation plan for {{ feature }}"
    model: claude-sonnet-4
    output: plan.md
    requires_approval: true

  - id: lint
    type: shell
    command: "ruff check src/"
    on_fail: continue

  - id: test
    type: shell
    command: "pytest tests/ -v"
    depends_on: [lint]
    timeout_s: 120
    env:
      PYTHONPATH: "src"
    on_fail: retry
    max_retries: 2

  - id: build
    type: shell
    command: "python -m build"
    depends_on: [plan, test]
    requires_approval: true
```

## Stage Fields

### Core Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | **yes** | — | Unique stage identifier within the workflow |
| `type` | string | **yes** | — | One of: `shell`, `ai`, `mcp`, `python`, `plugin` |
| `depends_on` | list | no | `[]` | Stage IDs that must complete before this stage starts |
| `on_fail` | string | no | `"stop"` | Failure strategy: `"stop"`, `"continue"`, or `"retry"` |
| `max_retries` | int | no | `0` | Max retries (required when `on_fail: retry`) |
| `requires_approval` | bool | no | `false` | Prompt for confirmation before execution |
| `timeout_s` | int | no | — | Maximum execution time in seconds |
| `env` | dict | no | `{}` | Environment variables passed to the stage (values must be strings) |
| `variables` | dict | no | `{}` | Arbitrary key-value data passed to plugin/Python stages |

### Shell Stage (`type: shell`)

Runs a shell command and captures stdout/stderr.

```yaml
- id: lint
  type: shell
  command: "ruff check src/"
  on_fail: continue
  env:
    PYTHONPATH: "src"
```

| Field | Required | Description |
|-------|----------|-------------|
| `command` | **yes** | Shell command to execute |

### AI Stage (`type: ai`)

Sends a prompt to an AI backend (Claude, OpenCode, Codex, or Gemini).

```yaml
- id: generate-code
  type: ai
  prompt: "Write a Python function to validate email addresses"
  model: claude-sonnet-4
  output: generated_code.py
  stream: true
```

| Field | Required | Description |
|-------|----------|-------------|
| `prompt` | **yes** | The prompt or instruction sent to the AI |
| `model` | no | Model override (e.g. `"claude-sonnet-4"`) |
| `output` | no | File path to write the AI response to |
| `stream` | no | Enable real-time streaming of AI output to the terminal |

### MCP Stage (`type: mcp`)

Calls an MCP (Model Context Protocol) server via HTTP POST.

```yaml
- id: fetch-data
  type: mcp
  command: "https://mcp.example.com/api"
  prompt: "Search for Python ORM libraries"
  variables:
    action: search
    query: "python orm"
```

| Field | Required | Description |
|-------|----------|-------------|
| `command` | **yes** | MCP server URL |
| `prompt` | no | Prompt or instruction sent to the MCP server |
| `variables` | no | Additional payload data for the server |

### Python Stage (`type: python`)

Imports a Python module and calls a function.

```yaml
- id: validate
  type: python
  command: "myproject.validators.run_checks"
  variables:
    strict: true
```

| Field | Required | Description |
|-------|----------|-------------|
| `command` | **yes** | Python dotted path: `"module.function"` |

The function receives `stage`, `state`, `variables`, and `context` as keyword arguments.

### Plugin Stage (`type: plugin`)

Uses a community or custom plugin installed in `~/.aizen/plugins/`.

```yaml
- id: notify
  type: plugin
  plugin: "SlackNotifier"
  variables:
    channel: "#deploy"
    message: "Deployment complete"
```

| Field | Required | Description |
|-------|----------|-------------|
| `plugin` | **yes** | Plugin class name (or qualified `"dir.ClassName"` for subdirectory plugins) |
| `variables` | no | Arbitrary data passed to the plugin's `run()` method |

## On-Fail Strategies

| Strategy | Behavior |
|----------|----------|
| `"stop"` (default) | Immediately halts the entire workflow. Other stages are not executed. |
| `"continue"` | Marks the stage as failed and continues executing remaining stages. |
| `"retry"` | Resets the stage to PENDING and re-executes up to `max_retries` times. |

## Dependency Graphs

Stages form a directed acyclic graph (DAG) through `depends_on`. The engine resolves execution order automatically.

```yaml
stages:
  - id: a
    type: shell
    command: "echo a"

  - id: b
    type: shell
    command: "echo b"
    depends_on: [a]

  - id: c
    type: shell
    command: "echo c"
    depends_on: [a]

  - id: d
    type: shell
    command: "echo d"
    depends_on: [b, c]
```

Execution order: `a` → `b` and `c` (parallel) → `d`.

## Validation Rules

Aizen validates workflows before execution. The following rules are enforced:

| Rule | Condition |
|------|-----------|
| Name required | `name` must be non-empty |
| At least one stage | `stages` must contain at least one stage |
| Unique IDs | All stage `id` values must be unique |
| Valid dependencies | All `depends_on` references must exist |
| No cycles | The dependency graph must be acyclic |
| Shell requires command | `type: shell` must have a `command` |
| AI requires prompt | `type: ai` must have a `prompt` |
| Python requires command | `type: python` must have a `module.function` in `command` |
| Plugin requires name | `type: plugin` must have a `plugin` name |
| MCP requires URL | `type: mcp` must have a `command` (server URL) |
| Retry needs max_retries | `on_fail: retry` requires `max_retries >= 1` |
| No self-dependency | A stage cannot depend on itself |
| Env values are strings | All `env` values must be string types |
| Timeout is positive | `timeout_s` must be greater than 0 if set |

## Top-Level Variables

Use `variables` at the workflow level to define shared values accessible to all stages via variable interpolation.

```yaml
name: "Feature Workflow"
variables:
  feature: "dark-mode"
  branch: "feature/dark-mode"

stages:
  - id: implement
    type: ai
    prompt: "Implement the {{ feature }} feature"
```

See [Advanced Guides](advanced.md#variable-interpolation) for more details.
