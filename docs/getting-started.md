# Getting Started with Aizen

Aizen is a DAG-based workflow orchestrator. Define pipelines as YAML, execute stages in dependency order, run in parallel, pause/resume mid-flight, and plug in AI backends or custom plugins.

## Installation

```bash
# Clone and install
git clone https://github.com/J0na555/aizen.git
cd aizen
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.10+.

Verify it works:

```bash
aizen --version
```

---

## Using Aizen with a New Project

### 1. Initialize

```bash
mkdir my-new-project
cd my-new-project
aizen init
```

This creates `.aizen/config.yaml` and registers the project globally.

### 2. Create a workflow

Create `workflows/pipeline.yaml`:

```yaml
name: "ci-pipeline"
description: "Lint, test, and build"

stages:
  - id: lint
    type: shell
    command: "ruff check src/"
    on_fail: continue

  - id: test
    type: shell
    command: "pytest tests/ -v"
    depends_on: [lint]
    timeout_s: 120

  - id: build
    type: shell
    command: "python -m build"
    depends_on: [test]
    requires_approval: true
```

### 3. Preview before running

```bash
aizen run workflows/pipeline.yaml --dry-run
```

Shows the execution plan: waves, stage types, approval gates, and retry policies.

### 4. Run it

```bash
aizen run workflows/pipeline.yaml
```

### 5. Check progress

```bash
aizen status
```

### 6. Resume after interruption

Press Ctrl+C during a run, or run `aizen pause` from another terminal. Resume later:

```bash
aizen resume
```

---

## Using Aizen with an Existing Project

You already have a codebase. You want to orchestrate a feature workflow across multiple stages.

### 1. Initialize aizen

```bash
cd your-existing-project
aizen init
```

### 2. Create a feature workflow

`workflows/add-dark-mode.yaml`:

```yaml
name: "Add dark mode toggle"
description: "Plan, implement, test, and deploy dark mode"

variables:
  feature: "dark-mode-toggle"

stages:
  - id: plan
    type: ai
    prompt: |
      Analyze the codebase at {{ feature }}.
      Create a plan with files to modify.
    model: claude-sonnet-4
    output: plan.md
    requires_approval: true

  - id: implement
    type: ai
    prompt: |
      Implement {{ feature }} following plan.md.
      Write the actual code changes.
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

### 3. Run the feature workflow

```bash
aizen run workflows/add-dark-mode.yaml --parallel
```

The `--parallel` flag runs `lint` and `test` concurrently after `implement` completes.

### 4. Iterate on a stage

Edit a stage's YAML without restarting the whole workflow:

```bash
aizen edit implement
```

This opens the stage definition in `$EDITOR`. Save and close to patch the workflow file.

### 5. Roll back if something goes wrong

```bash
aizen rollback implement
```

Resets `implement` and all downstream stages to PENDING so you can re-run from that point.

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `aizen init` | Initialize aizen in the current project |
| `aizen run <file>` | Execute a workflow |
| `aizen run <file> --dry-run` | Preview the execution plan |
| `aizen run <file> --parallel` | Run independent stages concurrently |
| `aizen run <file> --headless` | Non-interactive mode (auto-approve) |
| `aizen status` | Show current progress |
| `aizen pause` | Pause execution (or Ctrl+C) |
| `aizen resume` | Resume a paused workflow |
| `aizen rollback <id>` | Reset a stage and downstream stages |
| `aizen edit <id>` | Edit a stage's YAML definition |
| `aizen list` | List workflows, plugins, and stage types |
| `aizen list-runs` | Show run history |
| `aizen --version` | Show version |

---

## Next Steps

- [Workflow YAML Reference](workflows.md) — full stage field reference and examples
- [Plugins & Skills](plugins.md) — create custom stage runners and hooks
- [AI Backends](ai-backends.md) — configure Claude, Codex, Gemini, OpenCode
- [MCP Integration](mcp.md) — connect external tools via MCP servers
- [Advanced Guides](advanced.md) — parallel execution, variable interpolation, streaming, dry-run
