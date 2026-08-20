# Consultant Map — MCP server + client

An MCP server exposing consultant data from the `mcpdemo` database, plus a web
client where you type a question in a text field and get the matching consultants
drawn as dots on a map of Norway.

## Components

| File | Port | Purpose |
| --- | --- | --- |
| `server.py` | 8038 | FastMCP server over HTTP at `/mcp`, queries PostgreSQL |
| `client.py` | 8039 | FastAPI web app: MCP client + LLM tool-calling loop |
| `index.html` | — | UI: text field + Leaflet map |

### MCP tools

- `find_consultants(technology, min_years_experience, fylke, kommune, poststed, limit)` —
  joins `person → address → postnumbers` and returns each consultant with
  latitude/longitude. Years of experience is parsed out of the free-text
  `person.short_description` (e.g. "Backend engineer with 7 years ...").
- `list_technologies()` — every technology with a headcount.
- `consultant_stats()` — total consultants and distribution per county.

## Prerequisites

1. The database is running: `docker compose up -d db` from the repo root.
2. Optional: a local OpenAI-compatible LLM, e.g.
   `llama-server -m Qwen3.6-27B-Q4_K_M.gguf --port 8080 -c 4096`.
   Without it the client falls back to a simple keyword parser so the demo still works.

## Run

```bash
cd solutions/consultant_map
uv sync

# terminal 1
uv run python server.py

# terminal 2
uv run python client.py
```

Open <http://localhost:8039> and ask, for example:

- *Show a map of Norway. Draw a dot for each consultant that has at least 2 years of Python experience.*
- *Which consultants in Bergen know Kubernetes?*
- *How many consultants are there per county?*

## Configuration

| Variable | Default |
| --- | --- |
| `DATABASE_URL` | `postgresql://mcp:mcp@localhost:5432/mcpdemo` |
| `MCP_SERVER_URL` | `http://localhost:8038/mcp` |
| `LLM_BASE_URL` | `http://localhost:8080/v1` |
| `LLM_MODEL` | `local-model` |
| `LLM_API_KEY` | `no-key-needed` |
