# MCP Occupation Classifier (SSYK)

This repo hosts a **FastMCP server** that provides tools for:

- Classifying Swedish occupations into **SSYK** codes via hybrid search.
- Returning income statistics for an SSYK code (from pre-processed SCB-derived data).

The primary client is **Microsoft Copilot Studio**, connected over **Streamable HTTP** (SSE is not used).

## Server

Tools are implemented in [services/mcp_server/src/ssyk_mcp/server.py](services/mcp_server/src/ssyk_mcp/server.py):

- `classify_occupation(title, description=None) -> list[dict]`
- `get_income_statistics(ssyk_code) -> dict`

The server runs Streamable HTTP at `GET/POST <base>/mcp` (configurable).

## Run locally (Docker)

`docker compose up --build`

Tip: copy `.env.example` to `.env` and fill `OPENAI_API_KEY` if you want semantic (embedding) search.

Defaults:
- `http://localhost:8000/mcp`

## Run locally (Python)

- From the MCP server project: `cd services/mcp_server`
- Install deps: `uv sync`
- Run: `uv run python -m ssyk_mcp.server`

## OAuth 2.0 (RemoteAuthProvider)

OAuth is implemented using FastMCP `RemoteAuthProvider` + `JWTVerifier` in [services/mcp_server/src/ssyk_mcp/auth.py](services/mcp_server/src/ssyk_mcp/auth.py).

Set these environment variables:

- `AUTH_ENABLED=true`
- `AUTH_JWKS_URI=https://.../.well-known/jwks.json`
- `AUTH_ISSUER=https://issuer.example.com`
- `AUTH_AUDIENCE=<your-api-audience>`
- `AUTHORIZATION_SERVERS=https://issuer.example.com` (comma-separated; defaults to `AUTH_ISSUER`)
- `AUTH_ALLOWED_REDIRECT_URIS=<comma-separated patterns>`
- `FASTMCP_BASE_URL=https://your-public-domain` (used in MCP OAuth discovery metadata)

## Data

The server reads from `data/` (baked into the Docker image):

- `data/processed/ssyk_data.parquet`
- `data/processed/income_stats.json`

Pipelines to (re)build these live under [pipelines/](pipelines/).

## Copilot Studio

In Copilot Studio, use the MCP onboarding wizard to connect to your deployed MCP server URL (Streamable HTTP) and configure OAuth.

- Setup guide: [docs/copilot-studio.md](docs/copilot-studio.md)

See the Microsoft Learn article mirrored in [.github/microsoft-copilot-studio-mcp/index.html](.github/microsoft-copilot-studio-mcp/index.html).

## Deployment

- Google Cloud Run guide: [deploy/cloudrun.md](deploy/cloudrun.md)