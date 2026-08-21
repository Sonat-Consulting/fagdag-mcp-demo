# fagdag-mcp-demo

## Fagdag: Gi LLM-en tilgang til det den faktisk trenger

Et konsulentselskap har verdifulle ressurser lokalt: fagdata, interne tjenester og kundespesifikk kontekst. Samtidig brukes kraftige språkmodeller i skyen. Hvordan kan modellen bruke de lokale ressursene uten at vi bygger en ny, skreddersydd integrasjon for hvert eneste verktøy?

I denne fagdagen undersøker vi Model Context Protocol (MCP): en åpen protokoll som gir LLM-er en kontrollert og standardisert vei til verktøy, data og arbeidsflyter. Målet er å gå fra en chat som bare svarer, til en kundeorientert assistent som kan hente riktig lokal kontekst og utføre nyttige handlinger.

Vi ser på:

- hva en MCP-server er, og når den er et godt valg
- en praktisk demonstrasjon og øvelser med FastMCP
- autentisering og tilgangsstyring med Entra ID
- hvordan vi kan bygge en kundespesifikk chatklient med lokale ressurser

### Forberedelser

For å kunne delta i øvelsene bør du ha gjort dette på forhånd:

1. Klon repositoriet:

  ```bash
  git clone https://github.com/Sonat-Consulting/fagdag-mcp-demo.git
  cd fagdag-mcp-demo
  ```

2. Installer Docker Desktop (eller Docker Engine med Compose-plugin), Python 3.14+, [uv](https://docs.astral.sh/uv/) og Node.js 18+.

3. Last ned en lokal LLM-modell i GGUF-format, installer `llama.cpp`, og verifiser at `llama-server` kan starte modellen. Se Slack-tråden for installasjonsdetaljer: <https://sonatconsulting.slack.com/archives/C8ZUZMEDC/p1781776347083569>.

  ```bash
  llama-server -m /full/path/to/model.gguf --port 8080 -c 4096
  curl http://localhost:8080/health
  ```

4. Verifiser utviklingsverktøyene:

  ```bash
  docker compose version
  python3 --version
  uv --version
  node --version
  ```

This repository includes a PostgreSQL service running in Docker Compose.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- `docker compose` command available
- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+ (for MCP Inspector)

Check installation:

```bash
docker --version
docker compose version
python3 --version
uv --version
node --version
```

## Local LLM Setup

This project can use a local LLM served over HTTP using `llama-server`.

1. Install `llama.cpp` (which provides `llama-server`) if it is not already installed.

2. Place the model file where you want to run the command, or use an absolute model path.

3. Start the local LLM server:

```bash
llama-server -m Qwen3.6-27B-Q4_K_M.gguf --port 8080 -c 4096
```

If the model file is in another directory, use:

```bash
llama-server -m /full/path/to/Qwen3.6-27B-Q4_K_M.gguf --port 8080 -c 4096
```

4. Verify the server is reachable:

```bash
curl http://localhost:8080/health
```

If your setup exposes OpenAI-compatible routes, you can usually use:

- Base URL: `http://localhost:8080/v1`

### Local LLM Troubleshooting

### `llama-server: command not found`

Cause:
- `llama.cpp` is not installed or not on your PATH.

Fix:
- Install `llama.cpp` and ensure `llama-server` is available in your shell.

### Model file cannot be opened

Cause:
- Wrong path or filename for `Qwen3.6-27B-Q4_K_M.gguf`.

Fix:
- Use the absolute path in `-m` and verify file permissions.

### Port 8080 already in use

Cause:
- Another process is using port `8080`.

Fix:
- Stop the conflicting process or run with another port, for example `--port 8081`.

## Project Structure (relevant for Docker)

- `docker-compose.yml`: PostgreSQL service definition
- `db/init/`: SQL files executed during first database initialization
- `reference_data/`: external seed files used by SQL scripts (for example CSV)

## Database Configuration

From `docker-compose.yml`:

- Image: `postgres:16-alpine`
- Container: `mcp-demo-db`
- Database: `mcpdemo`
- User: `mcp`
- Password: `mcp`
- Host port: `5432` (mapped to container `5432`)

Connection string example:

```text
postgresql://mcp:mcp@localhost:5432/mcpdemo
```

## First-Time Setup

1. Ensure required seed data exists.

   The init SQL expects this file:

   - `reference_data/Postnummer_med_koordinater_utf8.csv`

   If this file is missing, initialization will fail.

2. Start the database service:

```bash
docker compose up -d db
```

3. Follow logs until ready:

```bash
docker compose logs -f db
```

4. Verify connection:

```bash
docker compose exec db psql -U mcp -d mcpdemo -c "select now();"
```

## Running psql Queries from Terminal

To run `psql` commands directly from your terminal (not inside the container), first export the database password, then connect to the database on `127.0.0.1`:

```bash
export PGPASSWORD='mcp'
psql -h 127.0.0.1 -U mcp -d mcpdemo -c "SELECT * FROM postnumbers WHERE postnummer = 5293;"
```

This connects to the PostgreSQL service running in Docker Compose. The password is required; export it as shown to avoid interactive prompts. Omit the `-c` option to start an interactive session:

```bash
psql -h 127.0.0.1 -U mcp -d mcpdemo
```

## Important: How Initialization Works

Postgres runs scripts in `/docker-entrypoint-initdb.d` only when the data directory is empty (first boot of the volume).

In this project, that means scripts in `db/init/` run only the first time `postgres-data` volume is created.

If you change SQL in `db/init/` and want it to run again, you must recreate the volume.

## Reset and Re-Seed Database

```bash
docker compose down -v
docker compose up -d db
docker compose logs -f db
```

This removes existing database data and re-runs all init scripts.

## Useful Commands

Start DB:

```bash
docker compose up -d db
```

Stop DB:

```bash
docker compose stop db
```

Stop and remove container (keep volume):

```bash
docker compose down
```

Stop and remove container + volume (full reset):

```bash
docker compose down -v
```

Open psql shell:

```bash
docker compose exec db psql -U mcp -d mcpdemo
```

Check table counts:

```bash
docker compose exec db psql -U mcp -d mcpdemo -c "select count(*) from person;"
docker compose exec db psql -U mcp -d mcpdemo -c "select count(*) from postnumbers;"
```

## Troubleshooting

### DB starts but tables/data are missing

Cause:
- Init scripts did not run because volume already existed.

Fix:
- Run a full reset:

```bash
docker compose down -v
docker compose up -d db
```

### Error reading CSV during init

Cause:
- Missing `reference_data/Postnummer_med_koordinater_utf8.csv`.

Fix:
- Add file to `reference_data/` and recreate volume:

```bash
docker compose down -v
docker compose up -d db
```

### Port 5432 already in use

Cause:
- Another service is bound to `5432`.

Fix:
- Stop conflicting service, or change port mapping in `docker-compose.yml`.

## Starting the MCP Demo Server

1. Install dependencies:

```bash
cd demo_server
uv sync
```

2. Ensure the postal code CSV exists:

  - `reference_data/Postnummer_med_koordinater_utf8.csv`

3. Start the server:

```bash
uv run demo-server
```

The server starts on `http://localhost:8035/mcp`.

This demo server does not require database environment variables.

## Testing with MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) is a browser-based tool for interacting with any running MCP server.

### Start the inspector

With the MCP server already running, open a new terminal and run:

```bash
npx @modelcontextprotocol/inspector
```

Open the URL printed in the terminal (typically `http://localhost:6274`).

### Connect to the server

In the inspector UI:

1. Set **Transport type** → `Streamable HTTP`
2. Set **URL** → `http://localhost:8035/mcp`
3. Click **Connect**

The **Tools**, **Resources**, and **Prompts** tabs will populate with everything registered on the server.

### Example tool calls

**`lookup_postal_code_csv`** — look up a postal code from the reference CSV:

```json
{ "code": "5003" }
```

**`get_current_temperature`** — fetch live temperature for Bergen, Norway via [Open-Meteo](https://open-meteo.com/) (no API key required):

```json
{}
```

### Example prompt

**`apologize_for_non_prime_postal_code`** — returns an apologetic explanation for a non-prime postal code:

```json
{ "postal_code": 5000 }
```

### Example resources

In the **Resources** tab, read these URIs:

- `info://demo-server`
- `postal-code://5003`
