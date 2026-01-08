# Copilot Studio → MCP server onboarding

This repo exposes an MCP server over **Streamable HTTP** at:

- `https://<your-host>/mcp`

Copilot Studio supports **Streamable** transport (SSE is deprecated for Copilot Studio).

## 1) Deploy somewhere public (HTTPS)

Copilot Studio needs a public HTTPS endpoint (Cloud Run is a good fit).

- Deployment guide: [deploy/cloudrun.md](../deploy/cloudrun.md)

## 2) Add the MCP server in Copilot Studio

In Copilot Studio:

1. Open your agent
2. Go to **Tools** → **Add a tool** → **New tool** → **Model Context Protocol**
3. Fill:
   - **Server name**: e.g. `SSYK Occupation Classifier`
   - **Server description**: e.g. `Classifies occupations to SSYK and returns income stats`
   - **Server URL**: `https://<your-host>/mcp`

### Authentication choices

Copilot Studio supports:

- **None** (no auth)
- **API key** (header or query)
- **OAuth 2.0**

## 3) OAuth 2.0 (recommended) using Dynamic discovery (DCR)

This repo is set up to use FastMCP’s `RemoteAuthProvider` (OAuth 2.0 + Dynamic Client Registration).

Server-side env vars you must set (example):

- `AUTH_ENABLED=true`
- `AUTH_JWKS_URI=https://<issuer>/.well-known/jwks.json`
- `AUTH_ISSUER=https://<issuer>`
- `AUTH_AUDIENCE=<your-api-audience>`
- `FASTMCP_BASE_URL=https://<your-host>`
- `AUTH_ALLOWED_REDIRECT_URIS=<comma-separated patterns>`

In the MCP onboarding wizard:

1. Choose **OAuth 2.0**
2. Choose **Dynamic discovery** (preferred when your server supports DCR + discovery)
3. Create the tool, then create/select a connection and add it to your agent

Notes:

- `FASTMCP_BASE_URL` must match the public HTTPS base URL Copilot Studio uses.
- `AUTH_ALLOWED_REDIRECT_URIS` must allow Copilot Studio’s redirect/callback URLs used during authorization. If you don’t know them upfront, Copilot Studio may display a callback URL during setup (depending on the OAuth mode); add that URL at your IdP and/or expand the allowed patterns.

## 4) Expected behavior when testing with curl/browser

`/mcp` is not a normal REST endpoint.

- `GET /mcp` without MCP-specific headers may return `406 Not Acceptable`.
- Adding `Accept: text/event-stream` may still return `400 Missing session ID`.

That’s expected unless you’re speaking the MCP protocol (Copilot Studio does).

## References

- Microsoft Learn: Connect an agent to an existing MCP server
  - https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent
- Microsoft Learn: Troubleshooting MCP integration
  - https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-troubleshooting
