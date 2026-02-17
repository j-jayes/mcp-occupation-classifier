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
- `OPENAI_API_KEY` set in your environment

## Deploy

```bash
export OPENAI_API_KEY="sk-..."
export MCP_API_KEY="your-secret"   # optional

# Run from the repo root
bash deploy/azure/deploy.sh
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

## Tear down

```bash
az group delete --name rg-ssyk-classifier --yes --no-wait
```

## TODO

- [ ] Tear down existing GCP Cloud Run deployment and Artifact Registry
  resources from the previous deployment (`europe-west1`, project-specific).
  Run `gcloud run services delete ssyk-mcp --region europe-west1` and clean
  up the Artifact Registry repository.
