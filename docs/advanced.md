# Advanced Guides

## Parallel Execution

By default, stages execute sequentially. With `--parallel`, Aizen runs all ready stages concurrently — stages whose dependencies are all satisfied and have no interdependencies between them.

### Usage

```bash
aizen run workflows/pipeline.yaml --parallel
```

### How It Works

The engine computes execution "waves" from the DAG:

```
Wave 0: a
Wave 1: b, c   ← these run concurrently
Wave 2: d
```

Stages in the same wave have no dependencies on each other and can safely run in parallel.

### Worker Count

Control parallelism with `max_workers` (default: 4):

```yaml
# In .aizen/config.yaml
max_workers: 8
```

Or set it in the workflow file.

### Thread Safety

Aizen uses `threading.Lock` to protect shared state during parallel execution. State is saved to disk in batches after each wave completes, not per-stage.

### Example

```yaml
name: "Parallel Build"
stages:
  - id: lint
    type: shell
    command: "ruff check src/"

  - id: typecheck
    type: shell
    command: "mypy src/"

  - id: test
    type: shell
    command: "pytest tests/ -v"
    depends_on: [lint, typecheck]
```

With `--parallel`, `lint` and `typecheck` run concurrently. `test` waits for both to finish.

---

## Variable Interpolation

Aizen supports `${...}` expressions in `prompt`, `command`, `env`, and `variables` fields. Expressions are resolved at runtime, just before a stage executes.

### Expression Reference

| Expression | Resolves To | Example |
|------------|-------------|---------|
| `${stages.<id>.output}` | Output of another completed stage | `${stages.plan.output}` |
| `${stages.<id>.error}` | Error message of a failed stage | `${stages.lint.error}` |
| `${variables.<key>}` | A runtime variable from the workflow state | `${variables.feature}` |
| `${stage.<field>}` | A field on the current stage | `${stage.id}` |

### Stage Output Chaining

Pass one stage's output to another stage's prompt:

```yaml
- id: plan
  type: ai
  prompt: "Create an implementation plan"

- id: implement
  type: ai
  prompt: "Implement based on this plan: ${stages.plan.output}"
  depends_on: [plan]
```

### Using Variables

Define workspace-level variables and reference them across stages:

```yaml
name: "Feature Pipeline"
variables:
  feature: "dark-mode-toggle"
  branch: "feature/dark-mode"

stages:
  - id: plan
    type: ai
    prompt: "Plan the implementation of ${variables.feature}"

  - id: implement
    type: ai
    prompt: "Implement ${variables.feature}"
    depends_on: [plan]
```

### Commands with Interpolation

```yaml
- id: deploy
  type: shell
  command: "git checkout -b ${variables.branch}"
```

### Environment Variables

```yaml
- id: test
  type: shell
  command: "pytest tests/"
  env:
    FEATURE_FLAG: "${variables.feature}"
    STAGE_OUTPUT: "${stages.build.output}"
```

### Behavior

- Unknown expressions are passed through unchanged (no error)
- Interpolation happens on a deep copy of the stage to avoid mutating the original definition
- Runtime `variables` are mutable across stages
- Stage output interpolation only works for stages that have already completed

---

## Dry-Run Mode

Preview the execution plan without running anything:

```bash
aizen run workflows/pipeline.yaml --dry-run
```

Outputs a table showing:

| Column | Description |
|--------|-------------|
| Wave | Execution wave number (DAG level) |
| Stage | Stage ID |
| Type | Stage type (shell, ai, mcp, etc.) |
| Approval | Whether the stage requires approval |
| On Fail | Failure handling strategy |
| Retries | Maximum retry count |

Use dry-run to verify your DAG logic, check which stages run in parallel, and confirm approval gates before actual execution.

---

## Streaming AI Output

For `type: ai` stages, set `stream: true` to see the AI response token-by-token in real time:

```yaml
- id: analyze
  type: ai
  prompt: "Analyze this codebase"
  stream: true
```

### How It Works

- The engine uses `subprocess.Popen` instead of `subprocess.run`
- Lines are yielded as the AI CLI produces them
- A Rich `Live` display renders the output in real time
- The final aggregated output is stored in the stage state

### Fallback

If a backend doesn't support true streaming, it falls back to collecting the full output and yielding it as a single chunk.

---

## Checkpoint & Resume

Aizen saves state after every stage. If execution is interrupted, you can resume from the last checkpoint.

### Checkpoint Flow

1. Each completed/failed/skipped stage triggers a state save to `.aizen/state.json`
2. If you press Ctrl+C, the engine finishes the current stage then raises `WorkflowPaused`
3. Cross-terminal pause: run `aizen pause` from another terminal to set `.aizen/pause.flag`
4. The engine checks for this flag between stages

### Resuming

```bash
# After Ctrl+C or aizen pause:
aizen resume
```

The resume command:

1. Clears the pause flag
2. Loads state from `.aizen/state.json`
3. Rebuilds the workflow structure from the saved state
4. Continues execution from where it left off

### Resuming with a specific workflow file

If the saved state doesn't have a matching workflow file:

```bash
aizen resume --workflow workflows/pipeline.yaml
```

### Archiving

After a successful run, archive the run history:

```bash
# Archives are created automatically on completion
# View archived runs:
aizen list-runs
```

Archived runs are stored in `.aizen/runs/<timestamp>-<name>.json`.

---

## Logging

### Verbose Mode

Enable debug logging with `--verbose`:

```bash
aizen run workflows/pipeline.yaml --verbose
```

### Log Format

```
2024-01-01 12:00:00 [INFO] aizen.engine: Starting stage 'build'
2024-01-01 12:00:00 [DEBUG] aizen.engine: interpolated prompt: "..."
```

### Log Filters

Long prompts are truncated to 200 characters in log output to keep logs readable.

### Log Levels

| Flag | Level |
|------|-------|
| (default) | `INFO` |
| `--verbose, -v` | `DEBUG` |

---

## Editing Stages

Modify a stage's YAML definition mid-workflow:

```bash
aizen edit plan
```

This opens the stage's YAML in `$EDITOR` (default: `vi`). Save and close to update the workflow file. The stage is validated before the file is written.

### Specify a workflow file

```bash
aizen edit plan --workflow workflows/my-pipeline.yaml
```

### Edit Flow

1. Aizen locates the workflow file (from saved state or `--workflow`)
2. Finds the stage by ID
3. Dumps the stage to a temp YAML file
4. Opens `$EDITOR`
5. On save, validates the edited stage with the `Stage` model
6. Patches the original workflow YAML with the changes
7. Cleans up the temp file

---

## Rolling Back

Reset a stage and all its downstream dependencies to PENDING:

```bash
aizen rollback plan
```

This allows you to re-run from that point forward without restarting the entire workflow.

- Stages upstream of the target keep their current status
- The target stage and all transitive dependents are reset
- State is saved after rollback

### Required

You must provide the workflow file to reload stage definitions:

```bash
aizen rollback plan --workflow workflows/pipeline.yaml
```
