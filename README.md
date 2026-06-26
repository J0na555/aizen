# Aizen

Universal task orchestrator — a DAG-based workflow engine with AI backends, plugin support, and checkpoint/resume.

## Install

```bash
cd aizen
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

```bash
# Initialize in a project
aizen init

# Run a workflow
aizen run workflows/feature.yaml

# Check progress
aizen status

# Resume from last checkpoint
aizen resume
```

## Workflow Example

```yaml
name: "Build a new feature"
stages:
  - id: plan
    type: ai
    prompt: "Analyze the requirements and create a plan."
    model: claude-opus

  - id: code
    type: ai
    prompt: "Implement based on plan.md"
    depends_on: [plan]

  - id: verify
    type: shell
    command: "pytest tests/ -v"
    depends_on: [code]
    on_fail: retry
    max_retries: 2
```

## Plugins

Install community stages from `~/.aizen/plugins/`.

## License

MIT
