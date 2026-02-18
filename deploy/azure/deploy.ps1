Param(
  [string]$SubscriptionId = $(if ($env:AZURE_SUBSCRIPTION_ID) { $env:AZURE_SUBSCRIPTION_ID } else { "e9b64842-3c87-4665-ad56-86ae7c20fe4b" }),
  [string]$ResourceGroup = $(if ($env:AZURE_RESOURCE_GROUP) { $env:AZURE_RESOURCE_GROUP } else { "rg-ssyk-classifier" }),
  [string]$Location = $(if ($env:AZURE_LOCATION) { $env:AZURE_LOCATION } else { "swedencentral" }),
  [string]$ContainerEnv = $(if ($env:AZURE_CONTAINER_ENV) { $env:AZURE_CONTAINER_ENV } else { "ssyk-env" }),
  [string]$AcrName = $(if ($env:AZURE_ACR_NAME) { $env:AZURE_ACR_NAME } else { "ssykclassifieracr" }),
  [string]$McpAppName = "ssyk-mcp",
  [string]$AdkAppName = "ssyk-adk"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Import-DotEnvIfNeeded {
  $dotenvPath = Join-Path $PSScriptRoot '..\..\..\.env'
  if (-not (Test-Path $dotenvPath)) { return }

    foreach ($raw in Get-Content $dotenvPath) {
      $line = $raw.Trim()
      if (-not $line) { continue }
      if ($line.StartsWith('#')) { continue }
      $idx = $line.IndexOf('=')
      if ($idx -lt 1) { continue }
      $key = $line.Substring(0, $idx).Trim()
      if ($key.StartsWith('export ')) { $key = $key.Substring(7).Trim() }
      $value = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
      if (-not $key) { continue }

      $existing = [Environment]::GetEnvironmentVariable($key, 'Process')
      if ([string]::IsNullOrWhiteSpace($existing)) {
        [Environment]::SetEnvironmentVariable($key, $value, 'Process')
      }
    }
}

Import-DotEnvIfNeeded

$required = @(
  'AZURE_OPENAI_ENDPOINT',
  'AZURE_OPENAI_API_KEY',
  'AZURE_OPENAI_API_VERSION',
  'AZURE_OPENAI_CHAT_DEPLOYMENT',
  'AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT'
)

$missing = @()
foreach ($k in $required) {
  $v = [Environment]::GetEnvironmentVariable($k, 'Process')
  if ([string]::IsNullOrWhiteSpace($v)) { $missing += $k }
}
if ($missing.Count -gt 0) {
  throw "Missing required env vars: $($missing -join ', ')"
}

Write-Host "=== Setting subscription ==="
az account set --subscription $SubscriptionId | Out-Null

Write-Host "=== Creating resource group ==="
az group create --name $ResourceGroup --location $Location --output none | Out-Null

Write-Host "=== Ensuring containerapp extension ==="
az extension add --name containerapp --upgrade --only-show-errors | Out-Null

Write-Host "=== Creating Azure Container Registry ==="
try {
  az acr create --resource-group $ResourceGroup --name $AcrName --sku Basic --admin-enabled true --output none | Out-Null
} catch {
  Write-Host "  (ACR already exists)"
}

Write-Host "=== Building MCP server image ==="
az acr build --registry $AcrName --image "ssyk-mcp-server:latest" --file services/mcp_server/Dockerfile .

Write-Host "=== Building ADK agent image ==="
az acr build --registry $AcrName --image "ssyk-adk-agent:latest" --file services/adk_agent/Dockerfile .

Write-Host "=== Creating Container Apps environment ==="
try {
  az containerapp env create --name $ContainerEnv --resource-group $ResourceGroup --location $Location --output none | Out-Null
} catch {
  Write-Host "  (environment already exists)"
}

$acrLoginServer = az acr show --name $AcrName --query loginServer -o tsv
$acrUsername = az acr credential show --name $AcrName --query username -o tsv
$acrPassword = az acr credential show --name $AcrName --query "passwords[0].value" -o tsv

$mcpApiKey = if ($env:MCP_API_KEY) { $env:MCP_API_KEY } else { "" }

Write-Host "=== Deploying MCP server (internal ingress) ==="
try {
  az containerapp create `
    --name $McpAppName `
    --resource-group $ResourceGroup `
    --environment $ContainerEnv `
    --image "$acrLoginServer/ssyk-mcp-server:latest" `
    --registry-server $acrLoginServer `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --target-port 8000 `
    --ingress internal `
    --min-replicas 0 `
    --max-replicas 2 `
    --cpu 0.5 `
    --memory 1.0Gi `
    --secrets `
      "azure-openai-endpoint=$($env:AZURE_OPENAI_ENDPOINT)" `
      "azure-openai-api-key=$($env:AZURE_OPENAI_API_KEY)" `
      "mcp-api-key=$mcpApiKey" `
    --env-vars `
      "AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint" `
      "AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key" `
      "AZURE_OPENAI_API_VERSION=$($env:AZURE_OPENAI_API_VERSION)" `
      "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=$($env:AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT)" `
      "MCP_API_KEY=secretref:mcp-api-key" `
      "FASTMCP_HOST=0.0.0.0" `
      "FASTMCP_PORT=8000" `
      "DATA_DIR=/app/data" `
    --output none | Out-Null
} catch {
  az containerapp update --name $McpAppName --resource-group $ResourceGroup --image "$acrLoginServer/ssyk-mcp-server:latest" --output none | Out-Null
}

$mcpFqdn = az containerapp show --name $McpAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
Write-Host "  MCP internal FQDN: $mcpFqdn"

Write-Host "=== Deploying ADK agent (external ingress) ==="
try {
  az containerapp create `
    --name $AdkAppName `
    --resource-group $ResourceGroup `
    --environment $ContainerEnv `
    --image "$acrLoginServer/ssyk-adk-agent:latest" `
    --registry-server $acrLoginServer `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --target-port 8080 `
    --ingress external `
    --min-replicas 0 `
    --max-replicas 3 `
    --cpu 0.5 `
    --memory 1.0Gi `
    --secrets `
      "azure-openai-endpoint=$($env:AZURE_OPENAI_ENDPOINT)" `
      "azure-openai-api-key=$($env:AZURE_OPENAI_API_KEY)" `
      "mcp-api-key=$mcpApiKey" `
    --env-vars `
      "AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint" `
      "AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key" `
      "AZURE_OPENAI_API_VERSION=$($env:AZURE_OPENAI_API_VERSION)" `
      "AZURE_OPENAI_CHAT_DEPLOYMENT=$($env:AZURE_OPENAI_CHAT_DEPLOYMENT)" `
      "AZURE_API_BASE=secretref:azure-openai-endpoint" `
      "AZURE_API_KEY=secretref:azure-openai-api-key" `
      "AZURE_API_VERSION=$($env:AZURE_OPENAI_API_VERSION)" `
      "MCP_SERVER_URL=https://$mcpFqdn/mcp" `
      "MCP_API_KEY=secretref:mcp-api-key" `
      "OPENAI_MODEL=azure/$($env:AZURE_OPENAI_CHAT_DEPLOYMENT)" `
      "ADK_HOST=0.0.0.0" `
      "ADK_PORT=8080" `
    --output none | Out-Null
} catch {
  az containerapp update --name $AdkAppName --resource-group $ResourceGroup --image "$acrLoginServer/ssyk-adk-agent:latest" --output none | Out-Null
}

$adkFqdn = az containerapp show --name $AdkAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "=== Deployment complete ==="
Write-Host "Chat UI:    https://$adkFqdn"
Write-Host "API:        https://$adkFqdn/api/chat"
Write-Host "Health:     https://$adkFqdn/health"
Write-Host "MCP (int):  https://$mcpFqdn/mcp"
