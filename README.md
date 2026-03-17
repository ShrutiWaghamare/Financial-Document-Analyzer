## Financial Document Analyzer

AI-powered financial document analysis service built with **FastAPI** + **CrewAI** + **Azure OpenAI**. Upload a financial PDF (earnings update, annual report, etc.) and get a structured summary with investment and risk insights.

## Key features

- Multi-agent analysis (verifier → analyst → investment → risk)
- REST API with Swagger UI
- Async processing for long-running jobs (Celery + Redis)
- Job history and persisted results (SQLAlchemy + SQLite by default)

## Architecture (high level)

```
Client → FastAPI (main.py)
  ├─ sync: /analyze-sync, /analyze-data
  └─ async: /analyze → Redis queue → Celery worker (worker.py) → DB + outputs/

Crew orchestration: crew_runner.py → agents.py + task.py + tools.py → Azure OpenAI
Persistence: database.py (SQLAlchemy)
```

## Prerequisites

- Python 3.11 recommended (dependency compatibility)
- Azure OpenAI resource + chat deployment
- Redis (for async queue) — easiest via Docker

## Setup

```powershell
# Create a clean Python 3.11 environment (recommended)
conda create -n fin-doc-analyzer python=3.11 -y
conda activate fin-doc-analyzer

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```env
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=<your-deployment-name>
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Async queue (optional for /analyze-sync and /analyze-data)
REDIS_URL=redis://localhost:6379/0

# Database (SQLite by default)
DATABASE_URL=sqlite:///./financial.db

# Outputs
OUTPUTS_DIR=outputs
```

## Run locally

Open 3 terminals (same conda env activated).

### 1) Redis (Docker)

```powershell
docker-compose up -d redis
```

### 2) Celery worker

```powershell
celery -A worker.celery_app worker --loglevel=info --pool=solo
```

### 3) API server

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open Swagger UI:

- `http://localhost:8000/docs`

## API quickstart

- **Fast demo (sync):** `POST /analyze-sync` (upload PDF, get result immediately)
- **Production-style (async):** `POST /analyze` → poll `GET /result/{job_id}`

Example (sync):

```bash
curl -X POST "http://localhost:8000/analyze-sync" \
  -F "file=@data/your_report.pdf" \
  -F "query=Summarize in one paragraph (6-8 sentences) and end with a 1-sentence conclusion."
```

## Suggested interview queries

- One-paragraph summary: `Summarize this document in exactly one paragraph (6–8 sentences). Include key numbers if present and end with a 1-sentence conclusion.`
- Investment view: `Based only on this document, give a Buy/Hold/Sell view with 5 supporting points and 3 caveats.`
- Risks: `List the top 7 risks mentioned or implied. Categorize each risk and give a 1-line mitigation.`

## Project structure

```
main.py            # FastAPI routes + DB integration
crew_runner.py     # CrewAI orchestration (agent/task selection)
worker.py          # Celery worker (background analysis)
database.py        # SQLAlchemy models/session
agents.py          # Azure OpenAI + CrewAI agent definitions
task.py            # CrewAI tasks (verification, analysis, investment, risk)
tools.py           # PDF reading tool (and optional search)
docker-compose.yml # Redis for async queue
requirements.txt   # Python dependencies
data/              # Local PDFs for /analyze-data and uploads
outputs/           # Saved analysis outputs (job_id.txt)
financial.db       # SQLite DB (auto-created)
```

## Notes for production

- Use **Azure Cache for Redis** instead of local/Docker Redis.
- Prefer a managed DB (Postgres/Azure SQL) instead of SQLite.
- Store secrets in a managed secret store (e.g., Azure Key Vault / Container Apps secrets).
