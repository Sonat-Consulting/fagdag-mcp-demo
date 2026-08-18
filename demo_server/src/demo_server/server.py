import csv
import json
import os
import pathlib
import re
import urllib.request
from datetime import datetime, timezone

import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Context, FastMCP

mcp = FastMCP("DemoServer")

@mcp.tool
async def lookup_postal_code_csv(code: str, ctx: Context) -> dict:
    """Look up a Norwegian postal code.

    Returns the district name and municipality.
    """
    # parents[3] resolves to the repository root from demo-server/src/demo_server/
    path = pathlib.Path(__file__).resolve().parents[3] / "reference_data" / "Postnummer_med_koordinater_utf8.csv"

    if not path.exists():
        await ctx.info(f"Error: postal code data file not found at {path}")
        raise ValueError(
            "Postal code data file is missing. "
            f"Expected: {path}. "
            "Add Postnummer_med_koordinater_utf8.csv to reference_data and try again."
        )

    await ctx.info(f"Looking up postal code: {code}")
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter=","):
            if row.get("Postnummer") == code:
                await ctx.info(f"Found: {code} -> {row.get('Poststed')}")
                return row
    await ctx.info(f"Error: postal code {code!r} not found")
    raise ValueError(f"Postal code {code!r} not found")

@mcp.prompt
async def apologize_for_non_prime_postal_code(postal_code: int, ctx: Context) -> str:
    """Explain apologetically that a postal code is not prime."""
    await ctx.info(f"Generating apology for non-prime postal code: {postal_code}")
    return (
        f"I am sorry to report that postal code {postal_code} is not a prime number. "
        "It can be divided evenly by numbers other than 1 and itself, "
        "but it is still a perfectly valid postal code."
    )


@mcp.resource("info://demo-server")
async def server_info(ctx: Context) -> str:
    """General information about this demo MCP server."""
    await ctx.info("Resource read: info://demo-server")
    return (
        "DemoServer – a FastMCP demo for fagdag.\n"
        "Tools: lookup_postal_code_csv, get_current_temperature\n"
        "Prompts: apologize_for_non_prime_postal_code\n"
        "Resources: info://demo-server, postal-code://{code}"
    )


@mcp.resource("postal-code://{code}")
async def postal_code_resource(code: str, ctx: Context) -> str:
    """Return postal code details as plain text for the given code."""
    await ctx.info(f"Resource read: postal-code://{code}")
    path = pathlib.Path(__file__).resolve().parents[3] / "reference_data" / "Postnummer_med_koordinater_utf8.csv"
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter=","):
            if row.get("Postnummer") == code:
                return "\n".join(f"{k}: {v}" for k, v in row.items())
    return f"Postal code {code!r} not found."


@mcp.tool
async def get_current_temperature(ctx: Context) -> dict:
    """Get the current temperature at Bergen, Norway using the MET Norway seamless model."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=60.393&longitude=5.3242"
        "&hourly=temperature_2m"
        "&models=metno_seamless"
        "&forecast_days=3"
    )
    await ctx.info("Fetching forecast from open-meteo")
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)

    times = data["hourly"]["time"]
    temps = data["hourly"]["temperature_2m"]

    # Match the slot for the current UTC hour.
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    idx = next((i for i, t in enumerate(times) if t >= now), 0)

    result = {
        "location": "Bergen, Norway",
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "time": times[idx],
        "temperature_celsius": temps[idx],
    }
    await ctx.info(f"{result['temperature_celsius']}°C at {result['time']}")
    return result


def main() -> None:
    app = mcp.http_app(path="/mcp", transport="http")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    uvicorn.run(app, host="0.0.0.0", port=8035)


if __name__ == "__main__":
    main()
