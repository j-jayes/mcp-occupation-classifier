# MCP Occupation Classifier (SSYK)

This repo hosts a **FastMCP server** that provides tools for:

- Classifying Swedish occupations into **SSYK** codes via hybrid search.
- Returning income statistics for an SSYK code (from pre-processed SCB-derived data).

It also includes a **Google ADK chatbot** that uses the MCP server as a tool,
powered by **LiteLLM** (Azure OpenAI preferred; OpenAI fallback).

## Architecture

```
Browser --> ADK Agent (port 8080) --> MCP Server (port 8000)
               |                          |
             LiteLLM (chat model)        Embeddings (vector search)
             Azure OpenAI / OpenAI       Azure OpenAI / OpenAI
```

## Deployed URLs (Azure Container Apps)

Current deployment endpoints (these can change if you delete/recreate the Container Apps):

- Frontend / ADK agent (public): https://ssyk-adk.wonderfultree-e1a11547.swedencentral.azurecontainerapps.io
- ADK API (non-streaming): https://ssyk-adk.wonderfultree-e1a11547.swedencentral.azurecontainerapps.io/api/chat
- ADK API (streaming/SSE): https://ssyk-adk.wonderfultree-e1a11547.swedencentral.azurecontainerapps.io/api/chat/stream
- ADK health: https://ssyk-adk.wonderfultree-e1a11547.swedencentral.azurecontainerapps.io/health
- MCP server (internal ingress): https://ssyk-mcp.internal.wonderfultree-e1a11547.swedencentral.azurecontainerapps.io/mcp

Notes:

- The MCP server is deployed with **internal ingress** in the Azure setup in this repo, so it is not reachable from the public internet.
- The MCP endpoint is **Streamable HTTP** at `/mcp` (FastMCP `transport="http"`), which is the transport Copilot Studio expects.

## Embedding dimensionality (1536)

This project intentionally standardizes on **1536-dimensional** embeddings (i.e. `text-embedding-3-small`).

- If you use **Azure OpenAI**, ensure `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` points to a deployment backed by `text-embedding-3-small`.
- If you use **OpenAI** directly, keep `EMBEDDING_MODEL=text-embedding-3-small`.

Mixing 1536-dim and 3072-dim embeddings will disable vector search (BM25-only fallback) and ingestion will refuse to write incompatible vectors.


## MCP Server

Tools are implemented in [services/mcp_server/src/ssyk_mcp/server.py](services/mcp_server/src/ssyk_mcp/server.py):

- `classify_occupation(title, description=None) -> list[dict]`
- `get_income_statistics(ssyk_code) -> dict`

The server runs Streamable HTTP at `GET/POST <base>/mcp` (configurable).

### API key auth (Bearer token)

For the Azure MCP server deployment, `MCP_API_KEY` is required to enable bearer-token auth (local runs may omit it).

Clients must send: `Authorization: Bearer <MCP_API_KEY>`

This is compatible with Copilot Studio’s “API key” auth mode (use a header, not query).

### Copilot Studio transport

Copilot Studio uses MCP over **Streamable HTTP** at `/mcp`.

- SSE transport is deprecated for Copilot Studio.
- `/mcp` is not a normal REST endpoint; `GET /mcp` in a browser may return `406 Not Acceptable` unless you are speaking MCP.

## ADK Chatbot

The ADK agent ([services/adk_agent/](services/adk_agent/)) connects to the MCP
server over Streamable HTTP and exposes a simple chat UI.

## Frontend

The frontend is served by the ADK agent and is available at the ADK base URL:

- https://ssyk-adk.wonderfultree-e1a11547.swedencentral.azurecontainerapps.io

It streams responses from `POST /api/chat/stream` and shows an MCP request/response trace.
Salary requests render a D3 chart and hovering shows percentile values.

## Run locally (Docker Compose)

```bash
cp .env.example .env
# Fill Azure OpenAI vars (preferred) OR OPENAI_API_KEY (fallback)
docker compose up --build
```

- MCP server: `http://localhost:8000/mcp`
- Chat UI: `http://localhost:8080`
- Chat API: `http://localhost:8080/api/chat`
- Chat stream (SSE): `http://localhost:8080/api/chat/stream`

## Run locally (Python)

**MCP server:**
```bash
cd services/mcp_server
uv sync
uv run python -m ssyk_mcp.server
```

**ADK agent:**
```bash
cd services/adk_agent
uv sync
uv run python -m adk_agent.app
```

## OAuth 2.0 (RemoteAuthProvider) (optional)

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

In Copilot Studio, use the MCP onboarding wizard to connect to your deployed MCP server URL (Streamable HTTP) and configure authentication.

Important: Copilot Studio needs a **public HTTPS** MCP endpoint. The Azure Container Apps deployment in this repo deploys the MCP server with **internal ingress**, so Copilot Studio cannot connect to it directly.

- Setup guide: [docs/copilot-studio.md](docs/copilot-studio.md)

See the Microsoft Learn article mirrored in [.github/microsoft-copilot-studio-mcp/index.html](.github/microsoft-copilot-studio-mcp/index.html).

## Deployment

- Azure Container Apps: [deploy/azure/README.md](deploy/azure/README.md)
