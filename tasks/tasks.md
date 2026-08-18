# MCP Demo — Fagdag Tasks

This document describes the hands-on exercises for the MCP demo fagdag. Each task builds on the previous one. A reference solution for Task 1 is available in `solutions/postal_codes/`.

---

## Prerequisites

- Docker Desktop running with `docker compose up -d` (starts the PostgreSQL database)
- Python 3.12+ and `uv` installed
- Node.js 18+ (required for MCP Inspector)

Database connection details:

| Parameter | Value                                      |
|-----------|--------------------------------------------|
| Host      | `localhost:5432`                           |
| Database  | `mcpdemo`                                  |
| Username  | `mcp`                                      |
| Password  | `mcp`                                      |
| URL       | `postgresql://mcp:mcp@localhost:5432/mcpdemo` |

---

## Task 1 — Postal Code MCP Server

**Goal:** Build a minimal MCP server that exposes Norwegian postal code data from the database.

The `postnumbers` table contains the following columns: `postnummer`, `poststed`, `kommune`, `fylke`, `latitude`, `longitude`, and more. See `db/init/01_schema.sql` for the full schema.

### Steps

1. **Create the MCP server project.**
   Initialise a new `uv` project and add `fastmcp`, `psycopg`, and `uvicorn` as dependencies. Expose at least one tool that queries the `postnumbers` table and returns matching rows. The tool should accept filter parameters such as postal code number, district name, or municipality name.

2. **Test the server with MCP Inspector.**
   Start your server and connect to it using [MCP Inspector](https://github.com/modelcontextprotocol/inspector). Verify that the tool is listed, that it accepts input, and that it returns correct results.

3. **Connect the server to an LLM client and run a natural-language query.**
   Register the MCP server in your LLM client (for example Claude Desktop or a custom client). Ask the model to list all postal codes and district names in `TYSNES` kommune, and verify that it uses your MCP tool to retrieve the answer.

---

## Task 2 — Consultant Map

**Goal:** Make internal consultant data accessible to the sales team through an MCP server, and visualise results on a map.

The database contains four relevant tables:

| Table         | Description                                                        |
|---------------|--------------------------------------------------------------------|
| `person`      | Consultants with name, technologies, and project descriptions      |
| `address`     | Street address linked to a postal code                             |
| `postnumbers` | Postal codes with geographic coordinates (`latitude`, `longitude`) |
| `clients`     | Client companies with address and industry                         |
| `assignments` | Assignments linking consultants to clients                         |

### Steps

1. **Create an MCP server that exposes consultant data.**
   Implement tools that allow the LLM to query consultants, their addresses, and their associated geographic coordinates by joining the `person`, `address`, and `postnumbers` tables.

2. **Build a client that renders a map of Norway with one dot per consultant.**
   Write a Python or Node.js client that calls your MCP server, retrieves consultant locations, and plots them on a map of Norway. Use a library such as `folium`, `plotly`, or `matplotlib` with `cartopy`.

3. **Filter consultants by technology or skill.**
   Extend the MCP tool and the client so that the sales team can request a map showing only consultants with a specific technology listed in their `technologies` array (for example `Rust`, `PowerBI`, or `React`).

4. **Find consultants near a client location.**
   Add a tool that accepts a client name or address and returns consultants ordered by geographic distance from the client. The LLM should be able to answer questions such as _"Which consultants live within 50 km of our client in Bergen?"_ using the `latitude` and `longitude` columns in `postnumbers`.
