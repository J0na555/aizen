# AI Backends

Aizen supports multiple AI providers for `type: ai` stages. Backends are auto-detected from your `PATH` and selected via configuration or per-stage model overrides.

## Supported Backends

| Backend | CLI Binary | Command | Model Flag |
|---------|-----------|---------|------------|
| Claude | `claude` | `claude -p <prompt>` | `--model` |
| Codex | `codex` | `codex -p <prompt>` | — |
| Gemini | `gemini` | `gemini run <prompt>` | `--model` |
| OpenCode | `opencode` | `opencode run <prompt>` | `--model` |

## Auto-Detection

On startup, Aizen checks which AI CLIs are available on your `PATH`:

```bash
aizen status  # shows available AI backends in logs
```

Only backends whose CLI binary is found are registered. If you run `type: ai` without a matching backend, the stage fails with a clear error.

## Configuration

### Per-Project Default

Set the default AI provider in `.aizen/config.yaml`:

```yaml
name: my-project
default_ai: claude
```

### Global Configuration

Set API keys in `~/.aizen/config.yaml`:

```yaml
api_keys:
  claude: "sk-ant-..."
  opencode: "sk-..."
```

API keys are passed to the AI CLI as environment variables when available.

### Per-Stage Override

Each AI stage can specify a model override:

```yaml
- id: plan
  type: ai
  prompt: "Analyze the requirements"
  model: claude-sonnet-4
```

The `model` field is passed directly to the CLI's `--model` flag (when supported).

## Using AI Stages

### Basic AI Prompt

```yaml
- id: generate
  type: ai
  prompt: "Write a Python function to validate email addresses"
```

### AI with Output File

Write the AI response to a file for later stages:

```yaml
- id: plan
  type: ai
  prompt: "Create a detailed implementation plan"
  output: plan.md
```

### Streaming AI Output

For long-running prompts, enable real-time streaming:

```yaml
- id: analyze
  type: ai
  prompt: "Analyze this codebase and provide recommendations"
  stream: true
```

With `stream: true`, the AI's response is displayed token-by-token in the terminal (like a real-time chat).

### Chaining AI Stages

Combine outputs from multiple AI stages using [variable interpolation](advanced.md#variable-interpolation):

```yaml
- id: plan
  type: ai
  prompt: "Design the architecture"
  model: claude-sonnet-4

- id: implement
  type: ai
  prompt: "Implement based on the plan: ${stages.plan.output}"
  depends_on: [plan]
```

## Adding a Custom Backend

You can register additional AI backends programmatically via the registry.

Create a plugin or script:

```python
from aizen.ai.base import AIClient
from aizen.ai.registry import get_registry


class MyCustomClient(AIClient):
    def run(self, prompt, model=None, context=None):
        # Call your custom AI API
        return "response text"


get_registry().register("my-ai", MyCustomClient())
```

Then use it in workflows:

```yaml
- id: custom-prompt
  type: ai
  prompt: "Do something"
  model: my-ai
```

## How Backend Selection Works

1. The stage runner reads `context["ai_provider"]`
2. Falls back to `ProjectConfig.default_ai` (`.aizen/config.yaml`)
3. Falls back to `"claude"` as the hardcoded default
4. The registry resolves the provider name to a registered client
5. If the CLI is not on `PATH`, the stage fails with `FileNotFoundError`
