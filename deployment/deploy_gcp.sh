#!/usr/bin/env bash
# Deploy Mega AI Legal Control Plane to Google Cloud Run.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (`gcloud auth login`).
#   - A GCP project with billing enabled.
#   - No local Docker build required - `gcloud run deploy --source .`
#     builds the image remotely via Cloud Build from the Dockerfile in
#     this repo.
#
# Usage:
#   PROJECT_ID=my-gcp-project OPENAI_API_KEY=sk-... ./deployment/deploy_gcp.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your GCP project id}"
REGION="${REGION:-asia-southeast1}"
SERVICE_NAME="${SERVICE_NAME:-mega-ai-legal-chatbot}"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8501 \
  --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY:-},ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-},OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_EXPORTER_OTLP_ENDPOINT:-}"

echo "Deployed. Fetch the public URL with:"
echo "  gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)'"
