# OAuth MCP Server — Azure Active Directory

A FastMCP server secured with **Azure Active Directory (Entra ID)** Bearer token authentication. Every MCP request must include a valid Azure AD access token. Tokens are validated using Azure AD's public JWKS endpoint — the server never issues tokens itself.

```
MCP Client  ──[1]──►  Azure AD (get token)
            ◄──[2]──  access_token (JWT)
            ──[3]──►  MCP Server  (Authorization: Bearer <token>)
                       └─ validates token via JWKS ──► 200 OK / 401
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| `uv` | any recent |
| Azure subscription | free tier is fine |

---

## Step 1 — Create an Azure App Registration

### 1.1 Register the app

1. Sign in to [portal.azure.com](https://portal.azure.com).
2. Go to **Microsoft Entra ID** → **App registrations** → **+ New registration**.
3. Fill in:
   - **Name**: `MCP OAuth Demo`
   - **Supported account types**: *Accounts in this organizational directory only*
   - **Redirect URI**: leave empty
4. Click **Register**.
5. On the **Overview** page, note:
   - **Application (client) ID** → `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`

### 1.2 Expose an API (set the token audience)

1. In the left menu, click **Expose an API**.
2. Click **Add** next to *Application ID URI*.
3. Accept the default `api://<client-id>` and click **Save**.

This URI becomes your `AZURE_AUDIENCE` (e.g. `api://00000000-0000-0000-0000-000000000000`).

> The server validates that every token's `aud` claim matches this URI exactly. If you change it here, update `AZURE_AUDIENCE` accordingly.

### 1.3 Create a client secret (for the test client)

1. Click **Certificates & secrets** → **Client secrets** → **+ New client secret**.
2. Description: `mcp-test`, Expiry: 90 days.
3. Click **Add**.
4. **Copy the secret Value immediately** — it is not shown again. This is your `AZURE_CLIENT_SECRET`.

> Never commit secrets to source control. Use environment variables or a secret manager.

### 1.4 (Optional) Add an app role for stricter access control

By default any client with a valid token for this audience can call the server. To limit access to specific clients only:

1. Click **App roles** → **+ Create app role**.
   - Display name: `MCP.Access`
   - Allowed member types: `Applications`
   - Value: `MCP.Access`
2. Click **Apply**, then **Save**.
3. Uncomment the role-enforcement block in `server.py`.
4. In the client app registration, grant the `MCP.Access` application permission and apply admin consent.

---

## Step 2 — Configure Environment Variables

Create a `.env` file in `solutions/OAuth/` (add it to `.gitignore`):

```env
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<your-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>
AZURE_AUDIENCE=api://<your-client-id>
```

Both `server.py` and `test_client.py` load this file automatically. Environment
variables already set in the shell take precedence over values in `.env`.

Or export them in your shell session:

```bash
export AZURE_TENANT_ID="..."
export AZURE_CLIENT_ID="..."
export AZURE_CLIENT_SECRET="..."
export AZURE_AUDIENCE="api://..."
```

---

## Step 3 — Install and Start the Server

```bash
cd solutions/OAuth
uv sync
uv run python server.py
```

The server starts on **http://localhost:8037**. You should see:

```
INFO:     Started server process [...]
INFO:     Uvicorn running on http://0.0.0.0:8037 (Press CTRL+C to quit)
```

---

## Step 4 — Verify Authentication

### Option A — Automated test client (recommended)

```bash
uv run python test_client.py
```

This runs six checks and prints PASS/FAIL for each:

```
=== MCP OAuth Test Client ===

[1] Unauthenticated request (expect 401)...
    Status: 401  PASS

[2] Invalid Bearer token (expect 401)...
    Status: 401  PASS

[3] Acquiring Azure AD token via client credentials...
    Token (first 60 chars): eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImtpZCI6Ij...
    aud:   api://00000000-0000-0000-0000-000000000000
    iss:   https://login.microsoftonline.com/<tenant>/v2.0
    appid: 00000000-0000-0000-0000-000000000000

[4] MCP initialize with valid token...
    Status: 200  PASS
    Server: {'name': 'SecureMCP', 'version': ...}   Session: ...

[5] Calling 'whoami' tool...
    Status: 200  PASS
    Result: {"authenticated": true, "server": "SecureMCP", ...}

[6] Calling 'echo' tool...
    Status: 200  PASS
    Result: '[Authenticated echo] Hello, secure world!'

=== All checks passed ===
```

### Option B — MCP Inspector

#### Paste a token (works with this server now)

1. Get a token to paste into Inspector:
   ```bash
   uv run python test_client.py --print-token
   ```
2. Open `mcp.json` in this folder and replace the placeholder value with
   `Bearer <paste token here>` in the `Authorization` header.
3. Start Inspector with that config:
   ```bash
   npx @modelcontextprotocol/inspector --config mcp.json
   ```
4. Click **Connect** on the `oauth` server and call the `whoami` or `echo` tools.

> Tokens expire after ~1 hour. Re-run `--print-token` and update `mcp.json` to
> get a fresh one. Since it holds a live token while in use, avoid committing
> it with a real value filled in.

#### Let Inspector acquire its own token

Inspector obtains tokens through an interactive OAuth 2.0 Authorization Code
flow with PKCE. It cannot use this project's `AZURE_CLIENT_SECRET`, because an
Inspector browser session is a public client and must not contain a secret.

1. In **Expose an API**, add a delegated scope such as `MCP.Access` and enable
   it for users and administrators.
2. Create a second app registration named `MCP Inspector`. This is the client
   application; keep the existing `MCP OAuth Demo` registration as the API.
3. In the Inspector registration, open **Authentication** and add the Inspector
   callback URI shown by the OAuth sign-in screen. For a locally hosted
   Inspector this is typically `http://localhost:6274/oauth/callback`. Add it
   as a **Single-page application** redirect URI, enable public client flows if
   Entra requests it, and do not create a client secret.
4. In **API permissions**, add **My APIs** → `MCP OAuth Demo` → delegated
   permission `MCP.Access`, then grant admin consent if your tenant requires it.
5. Configure the MCP server to advertise OAuth protected-resource metadata and
   Azure's authorization-server metadata. Inspector discovers these endpoints
   from the server's `401` response, opens the Entra sign-in page, and then
   sends the resulting Bearer token automatically on reconnect.

Azure endpoints for the configured tenant are:

```
Issuer:        https://login.microsoftonline.com/<tenant-id>/v2.0
Authorization: https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize
Token:         https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token
Metadata:      https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
Scope:         api://<api-client-id>/MCP.Access
```

> This server currently accepts and validates Bearer tokens, but its custom
> `AzureADMiddleware` does not yet expose MCP OAuth protected-resource metadata.
> Therefore Inspector cannot discover the Entra endpoints automatically today;
> use the paste-a-token flow above until the server is changed to use FastMCP's
> OAuth support or equivalent discovery endpoints are added.

### Option C — MCP Inspector with `--header` (ad-hoc)

Inspector v2 removed the inline Headers field from the connect screen; adding a
header there now requires a writable catalog (see Option B). For a quick,
one-off connection you can instead pass the header at launch:

```bash
TOKEN=$(uv run python test_client.py --print-token)
npx @modelcontextprotocol/inspector http://localhost:8037/mcp \
  --header "Authorization: Bearer $TOKEN"
```

Click **Connect** and call the `whoami` or `echo` tools. Re-run with a fresh
`$TOKEN` once it expires (~1 hour).

### Option D — curl

```bash
# Get a token
TOKEN=$(curl -s -X POST \
  "https://login.microsoftonline.com/$AZURE_TENANT_ID/oauth2/v2.0/token" \
  -d "grant_type=client_credentials" \
  -d "client_id=$AZURE_CLIENT_ID" \
  -d "client_secret=$AZURE_CLIENT_SECRET" \
  -d "scope=$AZURE_AUDIENCE/.default" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Without token → 401
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8037/mcp \
  -H "Content-Type: application/json" -d '{}'

# With token → MCP initialize
curl -s -X POST http://localhost:8037/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

---

## How It Works

1. **`AzureADMiddleware`** in `server.py` runs before every request reaches FastMCP.
2. It reads the `Authorization: Bearer <token>` header.
3. It calls `PyJWKClient.get_signing_key_from_jwt()`, which fetches and caches Azure AD's public keys from:
   ```
   https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys
   ```
4. It decodes and verifies the JWT, checking:
   | Claim | Expected value |
   |-------|----------------|
   | `aud` | `AZURE_AUDIENCE` |
   | `iss` | Azure AD v2 or v1 issuer URL for `AZURE_TENANT_ID` |
   | `exp` | must be in the future |
   | Signature | must be signed by Azure AD's RSA key |
5. If validation passes → request proceeds to the MCP handler and the tool runs.
6. If validation fails → `401 Unauthorized` is returned immediately, the MCP handler never runs.

---

## Troubleshooting

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `InvalidAudienceError` | Token `aud` ≠ `AZURE_AUDIENCE` | Verify Application ID URI in Step 1.2 matches `AZURE_AUDIENCE` |
| `InvalidIssuerError` | Token belongs to another tenant | Confirm `AZURE_TENANT_ID` matches the token's `iss` claim |
| `ExpiredSignatureError` | Token older than ~1 hour | Re-run `test_client.py` or `--print-token` |
| `AADSTS70011` from MSAL | Invalid scope | Ensure `AZURE_AUDIENCE` ends without a trailing slash and Application ID URI is set |
| `AADSTS700082` | Client secret expired | Create a new secret in Step 1.3 |
| Server returns 500 | Missing env var | Confirm `AZURE_TENANT_ID` and `AZURE_CLIENT_ID` are set before starting `server.py` |
