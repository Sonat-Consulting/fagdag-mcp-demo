"""FastMCP server exposing consultant data from the mcpdemo database."""

import os
from typing import Annotated, Literal

import psycopg
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Context, FastMCP
from pydantic import Field

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://mcp:mcp@localhost:5432/mcpdemo",
)

# Years of experience is only available as free text in person.short_description,
# e.g. "Backend engineer with 7 years building Python microservices...".
YEARS_EXPR = r"COALESCE(NULLIF(substring(p.short_description from '([0-9]+)\s+year'), '')::int, 0)"

mcp = FastMCP("ConsultantMap")


async def execute_query(cursor, query: str, params: list | None = None) -> None:
    """Send a query to PostgreSQL and print it to standard output."""
    print(f"SQL query:\n{query.strip()}\nSQL parameters: {params}", flush=True)
    await cursor.execute(query, params)


@mcp.tool
async def find_consultants(
    technology: Annotated[
        str | None,
        Field(description="Technology substring, e.g. 'Python', 'React', or 'Kubernetes'", min_length=1),
    ] = None,
    min_years_experience: Annotated[
        int | None,
        Field(description="Minimum years of professional experience, e.g. 5", ge=0, le=80),
    ] = None,
    fylke: Annotated[str | None, Field(description="Norwegian county substring, e.g. 'Oslo'", min_length=1)] = None,
    kommune: Annotated[str | None, Field(description="Norwegian municipality substring, e.g. 'Bergen'", min_length=1)] = None,
    poststed: Annotated[str | None, Field(description="Postal town substring, e.g. 'Trondheim'", min_length=1)] = None,
    limit: Annotated[int, Field(description="Maximum consultants to return (1-100), e.g. 20", ge=1, le=100)] = 50,
    ctx: Context = None,
) -> list[dict]:
    """Find consultants and their map coordinates.

    Find consultants in the internal consultant database. Use for staffing and
    map-based consultant discovery, not customer or project lookup.
    All supplied filters are combined with AND. String filters are
    case-insensitive substring matches.

    Returns a list of consultant objects containing name, email, technologies,
    years_experience, location fields, and latitude/longitude. An empty list
    means no consultant matched; do not retry unchanged. Results are ordered by
    experience and capped by limit.
    """
    conditions: list[str] = []
    params: list = []

    if technology is not None:
        experience_condition = (
            "EXISTS ("
            "  SELECT 1 FROM consultant_technology_experience cte"
            "  WHERE cte.person_id = p.id AND UPPER(cte.technology) LIKE %s"
        )
        params.append(f"%{technology.upper()}%")
        if min_years_experience is not None:
            experience_condition += " AND cte.years_experience >= %s"
            params.append(min_years_experience)
        conditions.append(experience_condition + ")")
    elif min_years_experience is not None:
        conditions.append(f"{YEARS_EXPR} >= %s")
        params.append(min_years_experience)
    if fylke is not None:
        conditions.append("UPPER(pn.fylke) LIKE %s")
        params.append(f"%{fylke.upper()}%")
    if kommune is not None:
        conditions.append("UPPER(pn.kommune) LIKE %s")
        params.append(f"%{kommune.upper()}%")
    if poststed is not None:
        conditions.append("UPPER(pn.poststed) LIKE %s")
        params.append(f"%{poststed.upper()}%")

    conditions.append("pn.latitude IS NOT NULL AND pn.longitude IS NOT NULL")

    query = f"""
        SELECT p.id,
               p.first_name || ' ' || p.last_name AS name,
               p.email_address,
               p.short_description,
               (
                   SELECT array_agg(DISTINCT t.name)
                   FROM assignments a3
                   JOIN assignment_technology at3 ON at3.assignment_id = a3.id
                   JOIN technology t ON t.id = at3.technology_id
                   WHERE a3.developer_id = p.id
               ) AS technologies,
               {YEARS_EXPR} AS years_experience,
               pn.postnummer,
               pn.poststed,
               pn.kommune,
               pn.fylke,
               pn.latitude,
               pn.longitude
        FROM person p
        JOIN address a ON a.id = p.address_id
        JOIN postnumbers pn ON pn.id = a.post_number_id
        WHERE {' AND '.join(conditions)}
        ORDER BY years_experience DESC, p.last_name, p.first_name
        LIMIT %s
    """  # noqa: S608
    params.append(limit)

    if ctx:
        await ctx.info(f"find_consultants params: {params}")

    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await execute_query(cur, query, params)
            return await cur.fetchall()


@mcp.tool
async def list_technology_experience(
    consultant_id: Annotated[int | None, Field(description="Consultant person ID, e.g. 42", ge=1)] = None,
    technology: Annotated[str | None, Field(description="Technology substring, e.g. 'Python'", min_length=1)] = None,
    limit: Annotated[int, Field(description="Maximum rows to return (1-1000)", ge=1, le=1000)] = 500,
    ctx: Context = None,
) -> list[dict]:
    """List assignment-derived technology experience.

    Filter by consultant ID, technology substring, or both. Returns rows with
    person_id, consultant name, technology, and years_experience. An empty list
    means no match; results are ordered by experience and capped by limit.
    """
    conditions: list[str] = []
    params: list = []

    if consultant_id is not None:
        conditions.append("person_id = %s")
        params.append(consultant_id)
    if technology is not None:
        conditions.append("UPPER(technology) LIKE %s")
        params.append(f"%{technology.upper()}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT person_id, first_name, last_name, technology, years_experience
        FROM consultant_technology_experience
        {where_clause}
        ORDER BY years_experience DESC, last_name, first_name, technology
        LIMIT %s
    """  # noqa: S608
    params.append(limit)

    if ctx:
        await ctx.info(f"list_technology_experience params: {params}")

    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await execute_query(cur, query, params)
            return await cur.fetchall()


@mcp.tool
async def list_current_assignments(
    consultant_id: Annotated[int | None, Field(description="Consultant person ID, e.g. 42", ge=1)] = None,
    is_assigned: Annotated[bool | None, Field(description="True for currently assigned, false for available")] = None,
    limit: Annotated[int, Field(description="Maximum rows to return (1-1000)", ge=1, le=1000)] = 500,
    ctx: Context = None,
) -> list[dict]:
    """List current assignment and availability data for consultants.

    Use is_assigned=true to find assigned consultants or false to find
    available consultants. Returns consultant, client, dates, remaining_days,
    and is_assigned. An empty list means no match.
    """
    conditions: list[str] = []
    params: list = []

    if consultant_id is not None:
        conditions.append("person_id = %s")
        params.append(consultant_id)
    if is_assigned is not None:
        conditions.append("is_assigned = %s")
        params.append(is_assigned)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT person_id, first_name, last_name, client_id, start_date, end_date,
               remaining_days, is_assigned
        FROM consultant_current_assignment
        {where_clause}
        ORDER BY is_assigned, end_date NULLS FIRST, last_name, first_name
        LIMIT %s
    """  # noqa: S608
    params.append(limit)

    if ctx:
        await ctx.info(f"list_current_assignments params: {params}")

    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await execute_query(cur, query, params)
            return await cur.fetchall()


@mcp.tool
async def list_consultant_assignments(
    consultant_id: Annotated[int | None, Field(description="Consultant person ID, e.g. 42", ge=1)] = None,
    client: Annotated[str | None, Field(description="Client name substring, e.g. 'Acme'", min_length=1)] = None,
    assignment_status: Annotated[
        Literal["current", "past", "future"] | None,
        Field(description="Assignment timing: current, past, or future"),
    ] = None,
    limit: Annotated[int, Field(description="Maximum assignments to return", ge=1, le=1000)] = 500,
    ctx: Context = None,
) -> list[dict]:
    """List consultant assignment history with client and project details.

    Filter by consultant ID, client substring, and assignment timing. Returns
    assignment ID, consultant and client details, role, dates, description, and
    technologies. An empty list means no match; results are newest first.
    """
    conditions: list[str] = []
    params: list = []

    if consultant_id is not None:
        conditions.append("p.id = %s")
        params.append(consultant_id)
    if client is not None:
        conditions.append("UPPER(c.name) LIKE %s")
        params.append(f"%{client.upper()}%")
    if assignment_status is not None:
        status_conditions = {
            "current": "CURRENT_DATE BETWEEN a.start_date AND a.end_date",
            "past": "a.end_date < CURRENT_DATE",
            "future": "a.start_date > CURRENT_DATE",
        }
        try:
            conditions.append(status_conditions[assignment_status.lower()])
        except KeyError as error:
            raise ValueError("assignment_status must be 'current', 'past', or 'future'") from error

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT a.id AS assignment_id,
               p.id AS consultant_id,
               p.first_name || ' ' || p.last_name AS consultant_name,
               c.id AS client_id,
               c.name AS client_name,
               c.industry AS client_industry,
               a.role,
               a.start_date,
               a.end_date,
               a.assignment_description,
               array_agg(t.name ORDER BY t.name) AS technologies
        FROM assignments a
        JOIN person p ON p.id = a.developer_id
        JOIN clients c ON c.id = a.client_id
        LEFT JOIN assignment_technology at ON at.assignment_id = a.id
        LEFT JOIN technology t ON t.id = at.technology_id
        {where_clause}
        GROUP BY a.id, p.id, c.id
        ORDER BY a.start_date DESC, a.id
        LIMIT %s
    """  # noqa: S608
    params.append(limit)

    if ctx:
        await ctx.info(f"list_consultant_assignments params: {params}")

    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await execute_query(cur, query, params)
            return await cur.fetchall()


@mcp.tool
async def list_technologies(ctx: Context = None) -> list[dict]:
    """List technologies used in consultant assignments.

    Returns rows with tech and consultant_count, ordered by headcount.
    Use this to discover supported technology filters before searching for
    consultants. An empty list means the database has no assignment data.
    """
    query = """
        SELECT t.name AS tech, COUNT(DISTINCT a.developer_id) AS consultant_count
        FROM technology t
        JOIN assignment_technology at ON at.technology_id = t.id
        JOIN assignments a ON a.id = at.assignment_id
        GROUP BY t.name
        ORDER BY consultant_count DESC, tech
    """  # noqa: S608
    if ctx:
        await ctx.info("list_technologies called")

    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await execute_query(cur, query)
            return await cur.fetchall()


@mcp.tool
async def consultant_stats(ctx: Context = None) -> dict:
    """Summarise consultant totals and distribution by Norwegian county.

    Returns total_consultants and per_fylke, where each per_fylke row contains
    fylke and consultant_count. Use this for aggregate reporting, not for
    finding individual consultants or assignments.
    """
    if ctx:
        await ctx.info("consultant_stats called")

    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await execute_query(cur, "SELECT COUNT(*) AS total FROM person")
            total = (await cur.fetchone())["total"]
            await execute_query(
                cur,
                """
                SELECT pn.fylke, COUNT(*) AS consultant_count
                FROM person p
                JOIN address a ON a.id = p.address_id
                JOIN postnumbers pn ON pn.id = a.post_number_id
                GROUP BY pn.fylke
                ORDER BY consultant_count DESC
                """
            )
            per_fylke = await cur.fetchall()

    return {"total_consultants": total, "per_fylke": per_fylke}


@mcp.resource("info://consultant-map")
async def server_info() -> str:
    """Read-only catalog of consultant-map tools and their PostgreSQL source."""
    return (
        "ConsultantMap MCP server. Tools: find_consultants (filter by technology, "
        "min_years_experience, fylke, kommune, poststed), list_technologies, "
        "list_consultant_assignments, list_technology_experience, "
        "list_current_assignments, consultant_stats. Data source: PostgreSQL "
        "'mcpdemo' database."
    )


def main() -> None:
    app = mcp.http_app(path="/mcp", transport="http")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    uvicorn.run(app, host="0.0.0.0", port=8038)


if __name__ == "__main__":
    main()
