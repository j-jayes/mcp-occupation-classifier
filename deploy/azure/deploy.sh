#!/usr/bin/env bash
# Deploy both the MCP server and ADK agent to Azure Container Apps.
#
# Prerequisites:
#   - Azure CLI (az) installed and logged in
#   - AZURE_OPENAI_* set in environment (or in .env)
#   - MCP_API_KEY set for bearer-token auth
#
# Usage:
#   export OPENAI_API_KEY="sk-..."
#   bash deploy/azure/deploy.sh

set -euo pipefail

# ---------- configuration ----------
SUBSCRIPTION="${AZURE_SUBSCRIPTION_ID:-e9b64842-3c87-4665-ad56-86ae7c20fe4b}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-ssyk-classifier}"
LOCATION="${AZURE_LOCATION:-swedencentral}"
ENVIRONMENT="${AZURE_CONTAINER_ENV:-ssyk-env}"
ACR_NAME="${AZURE_ACR_NAME:-ssykclassifieracr}"

MCP_IMAGE="ssyk-mcp-server"
ADK_IMAGE="ssyk-adk-agent"

: "${AZURE_OPENAI_ENDPOINT:?Set AZURE_OPENAI_ENDPOINT before running this script}"
: "${AZURE_OPENAI_API_KEY:?Set AZURE_OPENAI_API_KEY before running this script}"
: "${AZURE_OPENAI_API_VERSION:?Set AZURE_OPENAI_API_VERSION before running this script}"
: "${AZURE_OPENAI_CHAT_DEPLOYMENT:?Set AZURE_OPENAI_CHAT_DEPLOYMENT before running this script}"
: "${AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT:?Set AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT before running this script}"
: "${MCP_API_KEY:?Set MCP_API_KEY before running this script}"
# -----------------------------------

echo "=== Setting subscription ==="
az account set --subscription "$SUBSCRIPTION"

echo "=== Creating resource group ==="
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

echo "=== Creating Azure Container Registry ==="
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none 2>/dev/null || echo "  (ACR already exists)"

echo "=== Building MCP server image ==="
az acr build \
  --registry "$ACR_NAME" \
  --image "${MCP_IMAGE}:latest" \
  --file services/mcp_server/Dockerfile \
  .

echo "=== Building ADK agent image ==="
az acr build \
  --registry "$ACR_NAME" \
  --image "${ADK_IMAGE}:latest" \
  --file services/adk_agent/Dockerfile \
  .

echo "=== Creating Container Apps environment ==="
az containerapp env create \
  --name "$ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none 2>/dev/null || echo "  (environment already exists)"

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

echo "=== Deploying MCP server (internal ingress) ==="
az containerapp create \
  --name "ssyk-mcp" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT" \
  --image "${ACR_LOGIN_SERVER}/${MCP_IMAGE}:latest" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --target-port 8000 \
  --ingress internal \
  --min-replicas 0 \
  --max-replicas 2 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
    "AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint" \
    "AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key" \
    "AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION}" \
    "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=${AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT}" \
    "MCP_API_KEY=secretref:mcp-api-key" \
    "FASTMCP_HOST=0.0.0.0" \
    "FASTMCP_PORT=8000" \
    "FASTMCP_PATH=/mcp" \
    "DATA_DIR=/app/data" \
  --secrets \
    "azure-openai-endpoint=${AZURE_OPENAI_ENDPOINT}" \
    "azure-openai-api-key=${AZURE_OPENAI_API_KEY}" \
    "mcp-api-key=${MCP_API_KEY}" \
  --output none 2>/dev/null || \
az containerapp update \
  --name "ssyk-mcp" \
  --resource-group "$RESOURCE_GROUP" \
  --image "${ACR_LOGIN_SERVER}/${MCP_IMAGE}:latest" \
  --output none

MCP_FQDN=$(az containerapp show \
  --name "ssyk-mcp" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

echo "  MCP internal FQDN: ${MCP_FQDN}"

echo "=== Deploying ADK agent (external ingress) ==="
az containerapp create \
  --name "ssyk-adk" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT" \
  --image "${ACR_LOGIN_SERVER}/${ADK_IMAGE}:latest" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --target-port 8080 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
    "AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint" \
    "AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key" \
    "AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION}" \
    "AZURE_OPENAI_CHAT_DEPLOYMENT=${AZURE_OPENAI_CHAT_DEPLOYMENT}" \
    "AZURE_API_BASE=secretref:azure-openai-endpoint" \
    "AZURE_API_KEY=secretref:azure-openai-api-key" \
    "AZURE_API_VERSION=${AZURE_OPENAI_API_VERSION}" \
    "MCP_SERVER_URL=https://${MCP_FQDN}/mcp" \
    "MCP_API_KEY=secretref:mcp-api-key" \
    "OPENAI_MODEL=azure/${AZURE_OPENAI_CHAT_DEPLOYMENT}" \
    "ADK_HOST=0.0.0.0" \
    "ADK_PORT=8080" \
  --secrets \
    "azure-openai-endpoint=${AZURE_OPENAI_ENDPOINT}" \
    "azure-openai-api-key=${AZURE_OPENAI_API_KEY}" \
    "mcp-api-key=${MCP_API_KEY}" \
  --output none 2>/dev/null || \
az containerapp update \
  --name "ssyk-adk" \
  --resource-group "$RESOURCE_GROUP" \
  --image "${ACR_LOGIN_SERVER}/${ADK_IMAGE}:latest" \
  --output none

ADK_FQDN=$(az containerapp show \
  --name "ssyk-adk" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

echo ""
echo "=== Deployment complete ==="
echo "Chat UI:    https://${ADK_FQDN}"
echo "API:        https://${ADK_FQDN}/api/chat"
echo "Health:     https://${ADK_FQDN}/health"
echo "MCP (int):  https://${MCP_FQDN}/mcp"
