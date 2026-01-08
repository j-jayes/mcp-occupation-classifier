# Deploy to Google Cloud Run

This MCP server is designed for **public HTTPS** access (required by Copilot Studio), using **Streamable HTTP** at `/mcp`.

## Prereqs

- `gcloud` installed and authenticated
- A Google Cloud project with billing enabled

## Build + Deploy (Dockerfile via Cloud Build -> Cloud Run)

This repo is a monorepo, and `gcloud run deploy --source .` uses buildpacks that try to build the *root* Python project.
Because the root `pyproject.toml` is not meant to ship a wheel, buildpacks can fail.

Instead, build an image using the MCP server Dockerfile and deploy that image.

From the repo root:

```bash
gcloud config set project YOUR_PROJECT_ID

# Build the container image with Cloud Build.
# Uses the Dockerfile at services/mcp_server/Dockerfile with the repo root as build context
# (so it can bake data/ into the image).
gcloud builds submit \
  --config cloudbuild.yaml \
  .

# Deploy the built image to Cloud Run.
gcloud run deploy ssyk-mcp \
  --image gcr.io/YOUR_PROJECT_ID/ssyk-mcp \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8000 \
  --set-env-vars "FASTMCP_HOST=0.0.0.0,FASTMCP_PORT=8000,FASTMCP_PATH=/mcp"
```

Notes:
- Cloud Run sets `PORT`; the server reads `PORT` first, so `FASTMCP_PORT` is optional.
- If you want to restrict network access, use Cloud Run IAM + an API gateway/proxy. Copilot Studio typically requires public reachability.

## Secrets

If you want vector search and ingestion to use OpenAI embeddings:

```bash
gcloud secrets create OPENAI_API_KEY --data-file=-

gcloud run services update ssyk-mcp \
  --region europe-west1 \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest
```

## OAuth (RemoteAuthProvider)

You must provide OAuth settings for token verification and MCP discovery metadata:

```bash
gcloud run services update ssyk-mcp \
  --region europe-west1 \
  --set-env-vars \
    AUTH_ENABLED=true,\
    AUTH_JWKS_URI=https://YOUR_IDP/.well-known/jwks.json,\
    AUTH_ISSUER=https://YOUR_IDP,\
    AUTH_AUDIENCE=YOUR_API_AUDIENCE,\
    AUTHORIZATION_SERVERS=https://YOUR_IDP,\
    AUTH_ALLOWED_REDIRECT_URIS=https://*,http://localhost:*\
  --set-env-vars FASTMCP_BASE_URL=https://YOUR_CLOUD_RUN_HOSTNAME

PowerShell note: quote comma-separated lists, e.g. `--set-env-vars "A=1,B=2"`.
```

Important:
- `FASTMCP_BASE_URL` must be the **public** base URL (scheme + host) used by Copilot Studio.
- `AUTH_ALLOWED_REDIRECT_URIS` must allow the redirect URIs Copilot Studio uses during DCR.

## Verify

Once deployed, your MCP endpoint should be:

- `https://YOUR_SERVICE_URL/mcp`
