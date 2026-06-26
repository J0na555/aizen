# MCP Integration

MCP (Model Context Protocol) stages let your workflows call external tools and services via HTTP. Use MCP to extend aizen with APIs, databases, search engines, or any HTTP-accessible service.

## How It Works

An MCP stage sends an HTTP POST request to a configured server URL. The server receives a JSON payload with the prompt and variables, and returns a JSON response.

**Request format:**

```json
{
  "prompt": "Your instruction or query",
  "variables": {
    "key": "value"
  }
}
```

**Response format:**

Plain text response returned as the stage output.

## Configuration

### Basic MCP Stage

```yaml
- id: fetch-data
  type: mcp
  command: "https://mcp.example.com/api"
  prompt: "Search for Python ORM libraries"
  variables:
    action: search
    query: "python orm"
```

### MCP with Timeout

```yaml
- id: slow-operation
  type: mcp
  command: "https://mcp.example.com/api"
  prompt: "Run a long analysis"
  timeout_s: 120
```

### MCP with Authentication

Configure API keys globally in `~/.aizen/config.yaml`:

```yaml
api_keys:
  my-mcp-server: "sk-..."
```

Then reference the key in the MCP stage context through the engine configuration. The MCP runner sends `Authorization: Bearer <key>` headers when `context["mcp_api_key"]` is set.

## Server URL Resolution

The server URL comes from one of these sources (in priority order):

1. `stage.command` — the `command` field on the MCP stage
2. `context["mcp_server_url"]` — set programmatically in the engine context

## Payload Details

The MCP runner sends a JSON payload with:

| Field | Source | Description |
|-------|--------|-------------|
| `prompt` | `stage.prompt` | The instruction or query |
| `variables` | `stage.variables` | Additional key-value data |

## Default Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Timeout | `60s` (or `stage.timeout_s`) | Request timeout |
| Auth header | `Authorization: Bearer` | Sent when `mcp_api_key` is in context |
| Content-Type | `application/json` | Fixed header |

## Error Handling

- Connection errors are caught and reported as stage failures
- Non-2xx responses are treated as failures
- Server-side errors are captured in `stage_state.error`

## Example: Custom MCP Server

Here's a minimal MCP server (Python + FastAPI) you can run locally:

**server.py:**

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Request(BaseModel):
    prompt: str
    variables: dict = {}


@app.post("/execute")
async def execute(req: Request):
    # Your custom logic here
    return {"result": f"Processed: {req.prompt}"}
```

**Run it:**

```bash
uvicorn server:app --port 8000
```

**workflows/mcp-demo.yaml:**

```yaml
name: "MCP Demo"
stages:
  - id: call-server
    type: mcp
    command: "http://localhost:8000"
    prompt: "Hello from aizen"
```

## Use Cases

- **Search** — Connect to a search API (Algolia, Meilisearch)
- **Database queries** — Run SQL via a query service
- **External APIs** — Call REST endpoints as part of your pipeline
- **Custom tools** — Wrap internal microservices as MCP endpoints
- **AI tool use** — Connect to an AI proxy that routes to tool-enhanced models
