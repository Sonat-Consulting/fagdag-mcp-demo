# Postal Codes — MCP server

A FastMCP server that exposes Norwegian postal codes from the `mcpdemo` PostgreSQL
database as a single MCP tool. It runs over Streamable HTTP on port `8036` at `/mcp`.

## MCP tool

`query_postnumbers(postnummer, poststed, kommune)`

| Parameter | Type | Matching |
| --- | --- | --- |
| `postnummer` | `int` | exact |
| `poststed` | `str` | partial, case-insensitive |
| `kommune` | `str` | partial, case-insensitive |

At least one filter must be provided, otherwise the tool raises an error. Each row
returned contains `postnummer`, `poststed`, `kommune`, `fylke`, `latitude`, `longitude`.
The generated SQL and its parameters are sent back to the client as an MCP `info` log
message, which makes the tool call easy to follow in the Inspector.

## Prerequisites

1. The database is running (from the repository root):

   ```bash
   docker compose up -d db
   docker compose exec db psql -U mcp -d mcpdemo -c "select count(*) from postnumbers;"
   ```

2. Dependencies are installed:

   ```bash
   cd solutions/postal_codes
   uv sync
   ```

## Start the server

```bash
cd solutions/postal_codes
uv run python server.py
```

The console script defined in `pyproject.toml` does the same thing:

```bash
uv run postal-codes
```

Either way the server listens on `http://localhost:8036/mcp`. CORS is wide open and
`Mcp-Session-Id` is exposed, so browser-based clients (including MCP Inspector) can
connect directly. Stop it with `Ctrl+C`.

## Run the Inspector

### Option A: `fastmcp dev inspector` (simplest)

FastMCP starts the server over stdio *and* the Inspector in one command, so you do not
need the HTTP server running in another terminal:

```bash
cd solutions/postal_codes
uv run fastmcp dev inspector server.py
```

The command prints a URL for the Inspector UI (typically `http://localhost:6274`).
Open it, click **Connect**, then open the **Tools** tab and call `query_postnumbers`.
Auto-reload is on by default, so editing `server.py` restarts the server.

Note that this path imports the `mcp` object from `server.py` and speaks stdio — the
`uvicorn.run(...)` in `main()` is never executed, so port `8036` stays free.

### Option B: Inspector against the running HTTP server

Start the server as described above, then in a second terminal:

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector UI:

1. **Transport type** → `Streamable HTTP`
2. **URL** → `http://localhost:8036/mcp`
3. Click **Connect**

### Example tool calls

Look up one postal code:

```json
{ "postnummer": 5003 }
```

→ `[{"postnummer": 5003, "poststed": "BERGEN", "kommune": "BERGEN", "fylke": "VESTLAND", "latitude": 60.3985975533942, "longitude": 5.32558120132157}]`

Every postal code whose district name contains "bergen" (132 rows):

```json
{ "poststed": "bergen" }
```

All postal codes in a municipality:

```json
{ "kommune": "voss" }
```

Combine filters (they are AND-ed together):

```json
{ "poststed": "bergen", "kommune": "bergen" }
```

Trigger the validation error:

```json
{}
```

### Calling the server with plain `curl`

Useful when you want to see the raw protocol. Streamable HTTP requires the session id
from `initialize` to be echoed on later requests:

```bash
SID=$(curl -s -D - -o /dev/null -X POST http://localhost:8036/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}' \
  | awk '/mcp-session-id/ {print $2}' | tr -d '\r')

curl -s -X POST http://localhost:8036/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

curl -s -X POST http://localhost:8036/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"query_postnumbers","arguments":{"postnummer":5003}}}'
```

## Testing with `llama-server`

This server has no client of its own — it is an MCP server, and the LLM only reaches it
through an MCP client. To test the whole chain with a local model, start `llama-server`
with its OpenAI-compatible API, then run a small client that lists the tools from MCP,
hands them to the model, and executes whatever the model asks for.

### 1. Start the model

```bash
llama-server -m Qwen3.6-27B-Q4_K_M.gguf --port 8080 -c 4096 --jinja
curl http://localhost:8080/health
```

`--jinja` matters: without the model's own chat template, `llama-server` cannot emit
OpenAI-style `tool_calls` and the tools will simply be ignored.

### 2. Check that the model will call a tool at all

The quickest smoke test is a single request with the tool schema inlined — no MCP
involved yet. You are only checking whether the response contains `tool_calls`:

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "local-model",
    "temperature": 0,
    "messages": [
      {"role": "system", "content": "You look up Norwegian postal codes. The database is the only source of truth: always call query_postnumbers, never answer from memory."},
      {"role": "user", "content": "Which municipality is postal code 5003 in?"}
    ],
    "tools": [{
      "type": "function",
      "function": {
        "name": "query_postnumbers",
        "description": "Query Norwegian postal codes from the database. At least one filter must be provided.",
        "parameters": {
          "type": "object",
          "properties": {
            "postnummer": {"type": "integer", "description": "Exact postal code number"},
            "poststed": {"type": "string", "description": "Postal district name (partial match)"},
            "kommune": {"type": "string", "description": "Municipality name (partial match)"}
          }
        }
      }
    }]
  }'
```

A model that plays along answers with `"tool_calls": [{"function": {"name": "query_postnumbers", "arguments": "{\"postnummer\": 5003}"}}]` and no content.
A model that "knows" Norwegian geography may instead answer `Postal code 5003 is in Bergen`
straight from its weights — which is exactly the failure mode MCP exists to fix, and a
good thing to show during the demo. Sharpening the system prompt, or asking about
something the model cannot possibly know (`Which postal codes are in kommune Voss?`),
usually pushes it towards the tool.

Avoid `"tool_choice": "required"` with `llama-server` — some builds crash on it. Use
`"auto"` (the default) and lean on the system prompt instead.

### 3. Full loop: llama-server + MCP client

Save this next to `server.py` as `llm_test.py`:

```python
"""Minimal tool-calling loop: llama-server decides, the MCP server answers."""

import asyncio
import json
import sys

from fastmcp import Client
from openai import AsyncOpenAI

MCP_URL = "http://localhost:8036/mcp"
LLM = AsyncOpenAI(base_url="http://localhost:8080/v1", api_key="no-key-needed")

SYSTEM_PROMPT = (
    "You answer questions about Norwegian postal codes. The database reached through "
    "query_postnumbers is the only source of truth - always call it, never answer from "
    "memory. Keep the final answer to one or two sentences."
)


async def ask(question: str) -> str:
    async with Client(MCP_URL) as mcp:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in await mcp.list_tools()
        ]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        for _ in range(4):
            completion = await LLM.chat.completions.create(
                model="local-model", messages=messages, tools=tools, temperature=0
            )
            message = completion.choices[0].message
            if not message.tool_calls:
                return message.content or ""

            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                arguments = json.loads(call.function.arguments or "{}")
                print(f"-> {call.function.name}({arguments})")
                result = await mcp.call_tool(call.function.name, arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result.data, default=str)[:20000],
                    }
                )

        return "Gave up after too many tool calls."


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Which municipality is postal code 5003 in?"
    print(asyncio.run(ask(question)))
```

With the MCP server running in one terminal and `llama-server` in another:

```bash
uv run --with openai python llm_test.py "Which municipality is postal code 5003 in?"
uv run --with openai python llm_test.py "List the postal codes in kommune Voss."
uv run --with openai python llm_test.py "What are the coordinates of 5293?"
uv run --with openai python llm_test.py "How many postal codes have poststed Bergen?"
```

`--with openai` is needed because `openai` is not a dependency of this project; add it
to `pyproject.toml` if you want to keep the client around.

Each `->` line shows the arguments the model chose, so you can see whether it picked
`postnummer`, `poststed`, or `kommune` — and the FastMCP server logs the SQL it built
from them.

## Configuration

| Variable | Default | Used for |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://mcp:mcp@localhost:5432/mcpdemo` | PostgreSQL connection |

Host and port (`0.0.0.0:8036`) and the MCP path (`/mcp`) are hard-coded in `main()`.

## Troubleshooting

**`connection refused` / `password authentication failed` on a tool call** — the database
is not running or `DATABASE_URL` is wrong. Check `docker compose ps` from the repository
root.

**`relation "postnumbers" does not exist`** — the init scripts never ran. Recreate the
volume: `docker compose down -v && docker compose up -d db`.

**`Address already in use` on port 8036** — another copy of the server is still running;
stop it, or use `fastmcp dev inspector server.py`, which does not bind the port.

**Inspector connects but `Tools` is empty** — check that the transport is `Streamable HTTP`
and the URL ends in `/mcp`.

**The model answers without ever calling the tool** — see step 2 above; this is model
behaviour, not a server problem.
