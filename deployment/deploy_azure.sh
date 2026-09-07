#!/usr/bin/env bash
# Deploy Mega AI Legal Control Plane to Azure Container Apps.
#
# Prerequisites:
#   - Azure CLI installed and authenticated (`az login`).
#   - The `containerapp` extension: `az extension add --name containerapp`.
#   - No local Docker build required - `az containerapp up` builds the
#     image remotely via ACR Tasks from the Dockerfile in this repo.
#
# Usage:
#   OPENAI_API_KEY=sk-... ./deployment/deploy_azure.sh
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-mega-ai-legal-rg}"
LOCATION="${LOCATION:-southeastasia}"
APP_NAME="${APP_NAME:-mega-ai-legal-chatbot}"
ENV_NAME="${ENV_NAME:-mega-ai-legal-env}"

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

az containerapp up \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --environment "$ENV_NAME" \
  --source . \
  --target-port 8501 \
  --ingress external \
  --env-vars \
    "OPENAI_API_KEY=${OPENAI_API_KEY:-}" \
    "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}" \
    "OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_EXPORTER_OTLP_ENDPOINT:-}"

echo "Deployed. Fetch the public URL with:"
echo "  az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv"
