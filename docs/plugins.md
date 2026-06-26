# Plugins & Skills

Aizen's plugin system lets you extend the engine with custom stage runners and lifecycle hooks. Plugins are Python classes that integrate directly into the DAG execution pipeline.

## How Plugins Work

Plugins live in `~/.aizen/plugins/`. Each `.py` file can define:

- **Stage classes** — subclasses of `BaseStage` that implement a custom `run()` method
- **Hook functions** — registered via `register_hooks()` to observe or intercept execution

Aizen discovers plugins automatically on startup. No manual registration needed.

---

## Installing Plugins

### From a Git URL

```bash
aizen plugins install https://github.com/user/aizen-slack-plugin.git
```

This clones the repository into `~/.aizen/plugins/<repo-name>/`.

### Manually

```bash
mkdir -p ~/.aizen/plugins
cp my_plugin.py ~/.aizen/plugins/
```

### List installed plugins

```bash
aizen plugins list
```

---

## Creating a Plugin Stage

Create a Python file in `~/.aizen/plugins/`:

**~/.aizen/plugins/greeter.py:**

```python
from aizen.models import Stage, StageState, StageStatus
from aizen.stages.base import BaseStage
from datetime import datetime, timezone


class GreeterStage(BaseStage):
    """A simple stage that returns a greeting."""

    def run(
        self,
        stage: Stage,
        state: StageState,
        context: dict | None = None,
    ) -> StageState:
        state.status = StageStatus.RUNNING
        state.started_at = state.started_at or datetime.now(timezone.utc).isoformat()

        name = stage.variables.get("name", "world")
        state.output = f"Hello, {name}!"

        state.status = StageStatus.COMPLETED
        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state
```

**workflows/use-greeter.yaml:**

```yaml
name: "greeting"
stages:
  - id: greet
    type: plugin
    plugin: "GreeterStage"
    variables:
      name: "Aizen"
```

### Stage Class Conventions

- Inherit from `aizen.stages.base.BaseStage`
- Implement `run(self, stage, state, context)` returning `StageState`
- Use `stage.variables` for configuration
- Set `state.status`, `state.output`, `state.error` as needed
- Update `state.attempts`, `state.started_at`, `state.completed_at`

---

## Subdirectory Plugins

For larger plugins, use a package structure:

```
~/.aizen/plugins/
  my-skill/
    __init__.py
    main.py
    utils.py
    plugin.json
```

Discoverable classes in subdirectories are namespaced as `dirname.ClassName`:

```yaml
stages:
  - id: my-skill-step
    type: plugin
    plugin: "my-skill.SkillStage"
```

### Plugin Metadata

Include a `plugin.json` or `plugin.yaml` for dependency and version info:

```json
{
  "name": "my-skill",
  "version": "1.0.0",
  "description": "A skill for doing something useful",
  "author": "You",
  "hooks": ["before_stage"],
  "dependencies": ["requests>=2.28"],
  "stages": ["SkillStage"]
}
```

Aizen checks dependencies on discovery and logs warnings for missing packages.

---

## Hook System

Hooks let plugins observe or intercept the execution lifecycle without becoming stage runners.

### Hook Points

| Hook Point | Trigger | Signature |
|------------|---------|-----------|
| `BEFORE_STAGE` | Before each stage executes | `(stage, state, ctx)` |
| `AFTER_STAGE` | After each stage completes | `(stage, state, ctx)` |
| `ON_FAILURE` | When a stage fails | `(stage, state, ctx)` |
| `ON_START` | When the engine starts | `(synthetic_stage, None, ctx)` |
| `ON_COMPLETE` | When the engine finishes | `(synthetic_stage, None, ctx)` |

### Registering Hooks

Your plugin module can export a `register_hooks()` function that is called automatically on discovery:

**~/.aizen/plugins/monitor.py:**

```python
from aizen.plugins.hooks import HookPoint, get_hook_registry


def log_before_stage(stage, state, ctx):
    print(f"[monitor] Starting stage: {stage.id}")


def log_after_stage(stage, state, ctx):
    print(f"[monitor] Finished stage: {stage.id} — {state.status}")


def register_hooks():
    registry = get_hook_registry()
    registry.register(HookPoint.BEFORE_STAGE, log_before_stage)
    registry.register(HookPoint.AFTER_STAGE, log_after_stage)
```

### Hook Function Signature

All hook functions receive the same three arguments:

```python
def my_hook(
    stage: Stage,
    state: StageState | None,
    ctx: dict,
) -> None:
    ...
```

- `stage` — The stage being executed (or a synthetic stage for engine events)
- `state` — The current `StageState` (can be `None` for `ON_START`/`ON_COMPLETE`)
- `ctx` — The engine context dict (contains `project_dir`, `headless`, `ai_provider`, etc.)

---

## Plugin vs Built-in Stages

You can also register custom runners for new `StageType` values by calling `WorkflowEngine._resolve_runner()` — but the plugin system is the recommended path for custom stages.

Built-in stage types (`shell`, `ai`, `mcp`, `python`) are always available. Plugin stages use `type: plugin` and reference the class by name.

---

## Example: Full Plugin Package

**~/.aizen/plugins/notifier/__init__.py:**

```python
from .slack import SlackNotifier
from .discord import DiscordNotifier

__all__ = ["SlackNotifier", "DiscordNotifier"]
```

**~/.aizen/plugins/notifier/slack.py:**

```python
from aizen.models import Stage, StageState, StageStatus
from aizen.stages.base import BaseStage
from datetime import datetime, timezone


class SlackNotifier(BaseStage):
    def run(self, stage, state, context=None):
        state.status = StageStatus.RUNNING
        state.started_at = state.started_at or datetime.now(timezone.utc).isoformat()

        webhook = stage.variables.get("webhook_url")
        message = stage.variables.get("message", "No message")
        # ... send message to Slack ...
        state.output = f"Sent: {message}"

        state.status = StageStatus.COMPLETED
        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.attempts += 1
        return state
```

**~/.aizen/plugins/notifier/plugin.json:**

```json
{
  "name": "notifier",
  "version": "0.1.0",
  "description": "Send notifications to Slack and Discord",
  "dependencies": ["requests"],
  "stages": ["slack.SlackNotifier", "discord.DiscordNotifier"]
}
```

Usage in workflow:

```yaml
- id: notify-slack
  type: plugin
  plugin: "notifier.SlackNotifier"
  variables:
    webhook_url: "https://hooks.slack.com/..."
    message: "Deployment complete!"
```
