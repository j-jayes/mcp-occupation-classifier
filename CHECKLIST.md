# MCP Server Migration Checklist

This repo is being refocused to be **MCP server only** (Copilot Studio as the client), using **Streamable HTTP** and **OAuth 2.0 (RemoteAuthProvider)**.

## Done
- [x] Switch server from SSE to Streamable HTTP (FastMCP `transport="http"`)
- [x] Add Remote OAuth scaffolding (`RemoteAuthProvider` + `JWTVerifier`)
- [x] Remove Google ADK agent service
- [x] Update docker-compose to only run MCP server
- [x] Bake `data/` into the MCP server image
- [x] Update README and add Copilot Studio onboarding guide

## Next
- [ ] Confirm FastMCP version compatibility and dependency install (`uv sync`)
- [x] Build + run locally and verify MCP endpoint at `/mcp`
- [x] Deploy to Google Cloud Run and verify public HTTPS endpoint
- [ ] Configure `OPENAI_API_KEY` via Secret Manager on Cloud Run
- [ ] Connect Microsoft Copilot Studio to the deployed MCP server (OAuth)

## Auth configuration notes
- `AUTH_ENABLED=true`
- `AUTH_JWKS_URI=https://.../.well-known/jwks.json`
- `AUTH_ISSUER=https://issuer.example.com`
- `AUTH_AUDIENCE=<your-api-audience>`
- `AUTHORIZATION_SERVERS=https://issuer.example.com` (comma-separated)
- `AUTH_ALLOWED_REDIRECT_URIS=<comma-separated patterns>` (required for non-local clients like Copilot Studio)
- `FASTMCP_BASE_URL=https://your-public-domain` (used for discovery metadata)
