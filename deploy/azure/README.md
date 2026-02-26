# Azure Deployment

Deploys both the MCP server and ADK chatbot to **Azure Container Apps** in the `swedencentral` region.

## Architecture

```
Internet --> ADK Agent (external, port 8080) --> MCP Server (internal, port 8000)
                 |                                      |
            OpenAI GPT-4o                         OpenAI Embeddings
```

- **MCP server**: internal ingress only (not publicly accessible)
- **ADK agent**: external ingress (serves the chat UI and API)

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed
- Logged in: `az login`
- Subscription access: `e9b64842-3c87-4665-ad56-86ae7c20fe4b`
- Azure CLI logged in: `az login`
- Azure OpenAI configured in your environment (or `.env`):
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_API_VERSION`
  - `AZURE_OPENAI_CHAT_DEPLOYMENT` (e.g. `gpt-4o-mini`)
  - `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` (e.g. `embed-3-small`)

## Deploy

```bash
export MCP_API_KEY="your-secret"   # required (enables bearer-token auth)

# Azure OpenAI (required)
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_API_VERSION="2024-12-01-preview"
export AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4o-mini"
export AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT="embed-3-small"

# Run from the repo root
bash deploy/azure/deploy.sh
```

Windows PowerShell alternative:

```powershell
# From the repo root
./deploy/azure/deploy.ps1
```

The script will:
1. Create resource group `rg-ssyk-classifier` in `swedencentral`
2. Create Azure Container Registry `ssykclassifieracr`
3. Build and push both Docker images
4. Create a Container Apps environment
5. Deploy MCP server (internal) and ADK agent (external)
6. Print the public URL for the chat UI

## Update images

After code changes, re-run the deploy script. It will rebuild images and update
the running container apps.

## Configuration

Override defaults via environment variables:

| Variable | Default | Description |
|---|---|---|
| `AZURE_SUBSCRIPTION_ID` | `e9b64842-...` | Azure subscription |
| `AZURE_RESOURCE_GROUP` | `rg-ssyk-classifier` | Resource group name |
| `AZURE_LOCATION` | `swedencentral` | Azure region |
| `AZURE_CONTAINER_ENV` | `ssyk-env` | Container Apps environment |
| `AZURE_ACR_NAME` | `ssykclassifieracr` | Container Registry name |

## Notes

- This deployment uses Azure Container Apps:
  - `ssyk-mcp` is deployed with **internal** ingress.
  - `ssyk-adk` is deployed with **external** ingress.
- Both services read Azure OpenAI settings from environment variables (matching `docker-compose.yml`).

## Tear down

```bash
az group delete --name rg-ssyk-classifier --yes --no-wait
```

## TODO

- [ ] Tear down existing GCP Cloud Run deployment and Artifact Registry
  resources from the previous deployment (`europe-west1`, project-specific).
  Run `gcloud run services delete ssyk-mcp --region europe-west1` and clean
  up the Artifact Registry repository.
