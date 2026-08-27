"""FastMCP server secured with Azure Active Directory Bearer token authentication.

The server acts as an OAuth 2.0 resource server: it never issues tokens.
Azure AD issues tokens, and this server validates them on every request using
Azure AD's public JWKS endpoint.

Required environment variables:
    AZURE_TENANT_ID  – Azure AD tenant / directory ID (GUID)
    AZURE_CLIENT_ID  – App registration client ID (GUID)

Optional environment variables:
    AZURE_AUDIENCE   – Token audience claim; defaults to api://<AZURE_CLIENT_ID>
"""
import logging
import os

import jwt
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import Context, FastMCP
from jwt import PyJWKClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TENANT_ID = os.environ["AZURE_TENANT_ID"]
CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
AUDIENCE = os.environ.get("AZURE_AUDIENCE", f"api://{CLIENT_ID}")
JWKS_URI = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
VALID_ISSUERS = (
    f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
    f"https://sts.windows.net/{TENANT_ID}/",
)

# Fetches and caches Azure AD's public RSA signing keys automatically
jwks_client = PyJWKClient(JWKS_URI, cache_keys=True)

mcp = FastMCP("SecureMCP")


@mcp.tool
async def whoami(ctx: Context) -> dict:
    """Return the authenticated caller check result.

    Use to verify that the MCP request passed Azure AD Bearer-token validation.
    Returns authenticated=true, the provider, and the SecureMCP server name;
    it does not return personal identity claims.
    """
    await ctx.info("whoami called by authenticated caller")
    return {
        "authenticated": True,
        "server": "SecureMCP",
        "auth_provider": "Azure Active Directory",
        "note": "Bearer token was validated against Azure AD JWKS before this tool ran.",
    }


@mcp.tool
async def echo(message: str, ctx: Context) -> str:
    """Echo text through the authenticated MCP server without side effects.

    Use for testing that an authenticated tool call reaches SecureMCP. This
    does not send, store, or transform the message.

    Args:
        message: Text to return, e.g. 'hello MCP'.
    """
    await ctx.info(f"echo called: {message!r}")
    return f"[Authenticated echo] {message}"


def create_app() -> FastAPI:
    """Create the FastAPI host application for the FastMCP server."""
    mcp_app = mcp.http_app(path="/mcp", transport="http")
    app = FastAPI(lifespan=mcp_app.lifespan)

    @app.middleware("http")
    async def validate_azure_ad_token(request: Request, call_next):
        """Reject any MCP request that does not carry a valid Azure AD Bearer token."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "unauthorized", "message": "Bearer token required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.removeprefix("Bearer ")
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=VALID_ISSUERS,
            )
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                {"error": "token_expired", "message": "Access token has expired"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            )
        except jwt.InvalidTokenError as exc:
            log.warning("Token validation failed: %s", exc)
            return JSONResponse(
                {"error": "invalid_token", "message": "Token validation failed"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            )

        log.info(
            "Authenticated: sub=%s appid=%s",
            claims.get("sub", "-"),
            claims.get("appid", claims.get("azp", "-")),
        )

        request.state.token_claims = claims
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    app.mount("/", mcp_app)
    return app


def main() -> None:
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8037, log_level="info")


if __name__ == "__main__":
    main()
