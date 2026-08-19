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
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Context, FastMCP
from jwt import PyJWKClient
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

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


class AzureADMiddleware(BaseHTTPMiddleware):
    """Reject any MCP request that does not carry a valid Azure AD Bearer token."""

    async def dispatch(self, request: Request, call_next):
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
            claims.get("sub", "—"),
            claims.get("appid", claims.get("azp", "—")),
        )

        # To enforce a specific app role, uncomment and set the required role:
        # required_role = "MCP.Access"
        # if required_role not in claims.get("roles", []):
        #     return JSONResponse({"error": "forbidden", "message": f"Missing role: {required_role}"}, status_code=403)

        request.state.token_claims = claims
        return await call_next(request)


@mcp.tool
async def whoami(ctx: Context) -> dict:
    """Return a confirmation that the caller has been authenticated.

    The server validated the Azure AD Bearer token before this tool ran.
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
    """Echo back the provided message. Demonstrates a protected MCP tool.

    Args:
        message: The string to echo back.
    """
    await ctx.info(f"echo called: {message!r}")
    return f"[Authenticated echo] {message}"


def main() -> None:
    app = mcp.http_app(path="/mcp", transport="http")
    # AzureADMiddleware is added first → it sits inside CORS (innermost)
    app.add_middleware(AzureADMiddleware)
    # CORSMiddleware is outermost; it handles OPTIONS preflight before auth runs
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    uvicorn.run(app, host="0.0.0.0", port=8037, log_level="info")


if __name__ == "__main__":
    main()
