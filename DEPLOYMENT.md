# Deployment Guide

Three ways to run Mega AI — Singapore Legal Control Plane Chatbot: locally,
on Azure Container Apps, or on Google Cloud Run. All three run the same
`Dockerfile` / `streamlit run app.py` process on port `8501`.

## Environment variables

Copy `.env.example` to `.env` and fill in what you need (all optional -
the app falls back to a deterministic offline mock parser if no LLM key
is set):

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | **Free tier.** Enables live Groq (`openai/gpt-oss-20b`) neural parsing and chat replies - tried first |
| `OPENAI_API_KEY` | Enables live OpenAI (`gpt-4o-mini`) neural parsing, and the OpenAI moderation endpoint for content safety |
| `ANTHROPIC_API_KEY` | Enables live Anthropic (`claude-3-5-sonnet`) neural parsing (used if Groq/OpenAI keys absent) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Optional real OTLP collector (Dynatrace, OTel Collector) in addition to the in-app span viewer |
| `OTEL_EXPORTER_OTLP_HEADERS` | Comma-separated `key=value` headers for the OTLP exporter (e.g. `Authorization=Api-Token ...`) |

## 1. Local deployment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # then edit .env if using a real LLM key
streamlit run app.py
```

Or via Docker:

```powershell
docker build -t mega-ai-legal-chatbot .
docker run -p 8501:8501 --env-file .env mega-ai-legal-chatbot
```

Visit `http://localhost:8501`.

## 2. Azure deployment (Azure Container Apps)

Prerequisites: [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli),
authenticated via `az login`, and the Container Apps extension:

```powershell
az extension add --name containerapp
```

Run the deployment script from the repo root (builds remotely via ACR
Tasks - no local Docker build required):

```powershell
$env:OPENAI_API_KEY = "sk-..."          # optional
bash deployment/deploy_azure.sh
```

Configurable via environment variables before running the script:
`RESOURCE_GROUP`, `LOCATION` (default `southeastasia`), `APP_NAME`,
`ENV_NAME`. Get the deployed URL with:

```bash
az containerapp show --name mega-ai-legal-chatbot --resource-group mega-ai-legal-rg \
  --query properties.configuration.ingress.fqdn -o tsv
```

## 3. GCP deployment (Cloud Run)

Prerequisites: [gcloud CLI](https://cloud.google.com/sdk/docs/install),
authenticated via `gcloud auth login`, and a GCP project with billing
enabled.

```powershell
$env:PROJECT_ID = "my-gcp-project"
$env:OPENAI_API_KEY = "sk-..."          # optional
bash deployment/deploy_gcp.sh
```

Configurable via environment variables: `PROJECT_ID` (required),
`REGION` (default `asia-southeast1`), `SERVICE_NAME`. Get the deployed
URL with:

```bash
gcloud run services describe mega-ai-legal-chatbot --region asia-southeast1 \
  --format='value(status.url)'
```

## Notes on GovOps telemetry in production

- Without `OTEL_EXPORTER_OTLP_ENDPOINT` set, spans are only captured
  in-memory and rendered in the Streamlit "GovOps & Telemetry Panel" -
  this is fine for demos but not persisted across container restarts.
- For real production observability, point `OTEL_EXPORTER_OTLP_ENDPOINT`
  at your APM platform (Dynatrace, an OpenTelemetry Collector feeding
  Datadog/Grafana, etc.) so traces, FinOps cost spans, and SAFR
  disposition verdicts are durably queryable.
