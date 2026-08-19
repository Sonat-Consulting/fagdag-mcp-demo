"""Test client for the OAuth-secured MCP server.

Runs three checks in sequence:
  1. Request without a token         → expect 401
  2. Request with an invalid token   → expect 401
  3. Request with a valid Azure AD token via client credentials → call tools

Run with --print-token to acquire and print a token for use in MCP Inspector.

Required environment variables:
    AZURE_TENANT_ID      – Azure AD tenant ID
    AZURE_CLIENT_ID      – App registration client ID
    AZURE_CLIENT_SECRET  – Client secret created in the app registration
    AZURE_AUDIENCE       – Token audience (default: api://<AZURE_CLIENT_ID>)
    MCP_SERVER_URL       – MCP server URL (default: http://localhost:8037/mcp)
"""
import asyncio
import base64
import json
import os
import sys

import httpx
import msal
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.environ["AZURE_TENANT_ID"]
CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
CLIENT_SECRET = os.environ["AZURE_CLIENT_SECRET"]
AUDIENCE = os.environ.get("AZURE_AUDIENCE", f"api://{CLIENT_ID}")
SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8037/mcp")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = [f"{AUDIENCE}/.default"]
MCP_PROTOCOL_VERSION = "2025-03-26"


def acquire_token() -> str:
    """Acquire an Azure AD access token using the client credentials flow."""
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in result:
        print(f"    MSAL error: {result.get('error')}: {result.get('error_description')}")
        sys.exit(1)
    return result["access_token"]


def decode_token_claims(token: str) -> dict:
    """Base64-decode the token payload (no signature verification)."""
    try:
        payload_b64 = token.split(".")[1]
        # Pad to a multiple of 4 bytes for base64
        payload_b64 += "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


async def send_mcp(
    client: httpx.AsyncClient,
    method: str,
    params: dict,
    request_id: int,
    token: str | None = None,
    session_id: str | None = None,
) -> tuple[int, dict, str | None]:
    """Send one MCP JSONRPC request; return (status_code, body, session_id)."""
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    response = await client.post(
        SERVER_URL,
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        headers=headers,
        timeout=30,
    )
    new_session_id = response.headers.get("mcp-session-id", session_id)
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = parse_sse_response(response.text, request_id)
    return response.status_code, body, new_session_id


def parse_sse_response(response_text: str, request_id: int) -> dict:
    """Extract this request's JSON-RPC response from a FastMCP SSE stream."""
    for line in reversed(response_text.splitlines()):
        if not line.startswith("data: "):
            continue
        try:
            message = json.loads(line.removeprefix("data: "))
        except json.JSONDecodeError:
            continue
        if message.get("id") == request_id:
            return message
    return {"raw": response_text[:300]}


def extract_text(result: dict) -> str:
    """Pull the text value out of an MCP tool result."""
    content = result.get("result", result).get("content", [])
    texts = [item["text"] for item in content if isinstance(item, dict) and item.get("type") == "text"]
    return "\n".join(texts) if texts else json.dumps(result.get("result", result), indent=2)


async def main() -> None:
    print("=== MCP OAuth Test Client ===\n")
    all_passed = True

    # ------------------------------------------------------------------
    # Check 1 – no token
    # ------------------------------------------------------------------
    async with httpx.AsyncClient() as client:
        print("[1] Unauthenticated request (expect 401)...")
        status, body, _ = await send_mcp(client, "initialize", {}, request_id=0)
        ok = status == 401
        print(f"    Status: {status}  {'PASS' if ok else 'FAIL – expected 401'}")
        all_passed &= ok

        # ------------------------------------------------------------------
        # Check 2 – invalid token
        # ------------------------------------------------------------------
        print("\n[2] Invalid Bearer token (expect 401)...")
        status, body, _ = await send_mcp(
            client, "initialize", {}, request_id=0, token="this.is.not.a.valid.jwt"
        )
        ok = status == 401
        print(f"    Status: {status}  {'PASS' if ok else 'FAIL – expected 401'}")
        all_passed &= ok

    # ------------------------------------------------------------------
    # Acquire real token
    # ------------------------------------------------------------------
    print("\n[3] Acquiring Azure AD token via client credentials...")
    token = acquire_token()
    claims = decode_token_claims(token)
    print(f"    Token (first 60 chars): {token[:60]}...")
    print(f"    aud:   {claims.get('aud')}")
    print(f"    iss:   {claims.get('iss')}")
    print(f"    appid: {claims.get('appid', claims.get('azp', '(not present)'))}")

    # Print full token and exit if requested (for use with MCP Inspector)
    if "--print-token" in sys.argv:
        print(f"\nFull token (copy into MCP Inspector → Headers → Authorization: Bearer <token>):\n\n{token}\n")
        return

    # ------------------------------------------------------------------
    # Check 3 – valid token: initialize + tool calls
    # ------------------------------------------------------------------
    async with httpx.AsyncClient() as client:
        print("\n[4] MCP initialize with valid token...")
        status, body, session_id = await send_mcp(
            client, "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "oauth-test-client", "version": "1.0.0"},
            },
            request_id=1,
            token=token,
        )
        ok = status == 200
        print(f"    Status: {status}  {'PASS' if ok else 'FAIL'}")
        if ok:
            server_info = body.get("result", {}).get("serverInfo", {})
            print(f"    Server: {server_info}   Session: {session_id}")
        else:
            print(f"    Response: {body}")
        all_passed &= ok

        print("\n[5] Calling 'whoami' tool...")
        status, body, session_id = await send_mcp(
            client, "tools/call",
            {"name": "whoami", "arguments": {}},
            request_id=2,
            token=token,
            session_id=session_id,
        )
        ok = status == 200
        print(f"    Status: {status}  {'PASS' if ok else 'FAIL'}")
        print(f"    Result: {extract_text(body)}")
        all_passed &= ok

        print("\n[6] Calling 'echo' tool...")
        status, body, session_id = await send_mcp(
            client, "tools/call",
            {"name": "echo", "arguments": {"message": "Hello, secure world!"}},
            request_id=3,
            token=token,
            session_id=session_id,
        )
        ok = status == 200
        print(f"    Status: {status}  {'PASS' if ok else 'FAIL'}")
        print(f"    Result: {extract_text(body)!r}")
        all_passed &= ok

    print(f"\n{'=== All checks passed ===' if all_passed else '=== Some checks FAILED ==='}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
