# MCP Occupation Classifier (SSYK)

This repo hosts a **FastMCP server** that provides tools for:

- Classifying Swedish occupations into **SSYK** codes via hybrid search.
- Returning income statistics for an SSYK code (from pre-processed SCB-derived data).

It also includes a **Google ADK chatbot** that uses the MCP server as a tool,
powered by OpenAI GPT-4o via LiteLLM.

## Architecture

```
Browser --> ADK Agent (port 8080) --> MCP Server (port 8000)
               |                          |
         OpenAI GPT-4o             OpenAI Embeddings
         (chat completion)         (vector search)

## Embedding dimensionality (1536)

This project intentionally standardizes on **1536-dimensional** embeddings (i.e. `text-embedding-3-small`).

- If you use **Azure OpenAI**, ensure `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` points to a deployment backed by `text-embedding-3-small`.
- If you use **OpenAI** directly, keep `EMBEDDING_MODEL=text-embedding-3-small`.

Mixing 1536-dim and 3072-dim embeddings will disable vector search (BM25-only fallback) and ingestion will refuse to write incompatible vectors.
```

## MCP Server

Tools are implemented in [services/mcp_server/src/ssyk_mcp/server.py](services/mcp_server/src/ssyk_mcp/server.py):

- `classify_occupation(title, description=None) -> list[dict]`
- `get_income_statistics(ssyk_code) -> dict`

The server runs Streamable HTTP at `GET/POST <base>/mcp` (configurable).

## ADK Chatbot

The ADK agent ([services/adk_agent/](services/adk_agent/)) connects to the MCP
server over Streamable HTTP and exposes a simple chat UI.

## Run locally (Docker Compose)

```bash
cp .env.example .env
# Fill OPENAI_API_KEY (required for chat + semantic search)
docker compose up --build
```

- MCP server: `http://localhost:8000/mcp`
- Chat UI: `http://localhost:8080`
- Chat API: `http://localhost:8080/api/chat`

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

## API key auth (Bearer token)

Set `MCP_API_KEY` to enable bearer-token auth.

Clients must send: `Authorization: Bearer <MCP_API_KEY>`

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

In Copilot Studio, use the MCP onboarding wizard to connect to your deployed MCP server URL (Streamable HTTP) and configure OAuth.

- Setup guide: [docs/copilot-studio.md](docs/copilot-studio.md)

See the Microsoft Learn article mirrored in [.github/microsoft-copilot-studio-mcp/index.html](.github/microsoft-copilot-studio-mcp/index.html).

## Deployment

- Azure Container Apps: [deploy/azure/README.md](deploy/azure/README.md)
