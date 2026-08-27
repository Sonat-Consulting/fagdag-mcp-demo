# Solutions — running everything at once

Three independent MCP servers live here, each its own `uv` project:

| Solution | Port | Notes |
| --- | --- | --- |
| `postal_codes` | 8036 | No extra setup needed besides the database |
| `OAuth` | 8037 | Requires `AZURE_TENANT_ID` and `AZURE_CLIENT_ID` env vars, see [OAuth/README.md](OAuth/README.md) |
| `consultant_map` | 8038 | Server only (`client.py` on 8039 is separate, not started by the command below) |

## Start all three servers with one command

```bash
uv run solutions/start_all.py
```

This starts each server with `uv run python server.py` inside its own project directory
(so each uses its own virtualenv/dependencies), prefixes their log output with the
solution name, and stops all three on `Ctrl+C`. Make sure `docker compose up -d db` is
running first, and that the `AZURE_TENANT_ID`/`AZURE_CLIENT_ID` env vars are set if you
want the OAuth server to start successfully.

## Inspect and test all three at once

Start the servers as above, then in another terminal launch the Inspector with the
shared config, which pre-registers all three servers:

```bash
npx @modelcontextprotocol/inspector --config solutions/inspector.config.json
```

Open the printed URL, pick a server from the dropdown (`postal-codes`, `oauth`,
`consultant-map`), click **Connect**, and try its tools from the **Tools** tab. The
`oauth` server also requires a Bearer token — see [OAuth/README.md](OAuth/README.md)
for how to obtain one before connecting to it.
