import os
from typing import Annotated
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

import psycopg
from fastmcp import Context, FastMCP
from pydantic import Field

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://mcp:mcp@localhost:5432/mcpdemo",
)

mcp = FastMCP("PostalCodes")


@mcp.tool
async def query_postnumbers(
    postnummer: Annotated[int | None, Field(description="Exact postal code number")] = None,
    poststed: Annotated[str | None, Field(description="Postal district name (partial match)")] = None,
    kommune: Annotated[str | None, Field(description="Municipality name (partial match)")] = None,
    ctx: Context = None,
) -> list[dict]:
    """Query Norwegian postal codes from the database.

    At least one filter must be provided. String filters are case-insensitive.
    Returns matching rows from the postnumbers table.
    """
    if postnummer is None and poststed is None and kommune is None:
        raise ValueError("At least one of postnummer, poststed, or kommune must be provided.")

    conditions: list[str] = []
    params: list = []

    if postnummer is not None:
        conditions.append("postnummer = %s")
        params.append(postnummer)
    if poststed is not None:
        conditions.append("UPPER(poststed) LIKE %s")
        params.append(f"%{poststed.upper()}%")
    if kommune is not None:
        conditions.append("UPPER(kommune) LIKE %s")
        params.append(f"%{kommune.upper()}%")

    query = f"SELECT postnummer, poststed, kommune, fylke, latitude, longitude FROM postnumbers WHERE {' AND '.join(conditions)} ORDER BY postnummer"  # noqa: S608

    if ctx:
        await ctx.info(f"SQL: {query} | params: {params}")

    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(query, params)
            return await cur.fetchall()



def main() -> None:
    app = mcp.http_app(path="/mcp", transport="http")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    uvicorn.run(app, host="0.0.0.0", port=8036)

if __name__ == "__main__":
    main()
