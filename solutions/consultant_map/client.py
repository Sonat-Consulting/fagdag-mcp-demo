"""MCP client with a web UI: type a question, get consultants plotted on a map of Norway."""

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastmcp import Client
from openai import AsyncOpenAI
from pydantic import BaseModel

MCP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8038/mcp")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "local-model")
LLM_API_KEY = os.getenv("LLM_API_KEY", "no-key-needed")
MAX_TOOL_ROUNDS = 4

SYSTEM_PROMPT = (
    "You are a consultant-staffing assistant for a Norwegian consultancy. "
    "Use the provided tools to answer questions about consultants. "
    "When the user asks for a map, call find_consultants with the right filters; "
    "the UI plots every returned consultant automatically. "
    "Answer in one or two short sentences."
)

app = FastAPI(title="Consultant Map Client")
llm = AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


class AskRequest(BaseModel):
    question: str


def _tool_result_to_python(result: Any) -> Any:
    """Normalise a FastMCP CallToolResult into plain Python data."""
    data = getattr(result, "data", None)
    if data is not None:
        return data
    texts = [block.text for block in getattr(result, "content", []) if hasattr(block, "text")]
    joined = "\n".join(texts)
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return joined


def _collect_points(payload: Any, points: list[dict]) -> None:
    """Pull anything with latitude/longitude out of a tool result."""
    rows = payload if isinstance(payload, list) else [payload]
    for row in rows:
        if isinstance(row, dict) and row.get("latitude") is not None and row.get("longitude") is not None:
            points.append(row)


def _fallback_arguments(question: str) -> dict:
    """Heuristic filter extraction used when no LLM is reachable."""
    args: dict = {}
    years = re.search(r"(\d+)\s*(?:\+|or more)?\s*year", question, re.IGNORECASE)
    if years:
        args["min_years_experience"] = int(years.group(1))
    known = [
        "Python", "TypeScript", "React", "FastAPI", "PostgreSQL", "Redis", "Docker",
        "Kubernetes", "Terraform", "Spark", "Airflow", "dbt", "DuckDB", "Flutter",
        "Dart", "Firebase", "Go", "Node.js", "AWS", "Pytest", "Selenium", "Cypress",
        "Vite", "CSS", "Playwright", "Grafana", "Prometheus", "SQLite",
    ]
    for tech in known:
        if re.search(rf"\b{re.escape(tech)}\b", question, re.IGNORECASE):
            args["technology"] = tech
            break
    return args


@app.post("/api/ask")
async def ask(request: AskRequest) -> dict:
    points: list[dict] = []

    async with Client(MCP_URL) as mcp_client:
        tools = await mcp_client.list_tools()
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools
        ]
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.question},
        ]

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                completion = await llm.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    tools=openai_tools,
                    temperature=0,
                )
                message = completion.choices[0].message
                if not message.tool_calls:
                    return {"answer": message.content or "", "points": points}

                messages.append(message.model_dump(exclude_none=True))
                for call in message.tool_calls:
                    arguments = json.loads(call.function.arguments or "{}")
                    result = _tool_result_to_python(
                        await mcp_client.call_tool(call.function.name, arguments)
                    )
                    _collect_points(result, points)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(result, default=str)[:20000],
                        }
                    )

            return {"answer": "Stopped after too many tool calls.", "points": points}

        except Exception as exc:  # noqa: BLE001 - demo falls back to direct tool use
            arguments = _fallback_arguments(request.question)
            result = _tool_result_to_python(await mcp_client.call_tool("find_consultants", arguments))
            _collect_points(result, points)
            return {
                "answer": (
                    f"LLM unavailable ({type(exc).__name__}), used direct query instead: "
                    f"{arguments or 'no filters'} - {len(points)} consultants found."
                ),
                "points": points,
            }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "index.html")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8039)


if __name__ == "__main__":
    main()
