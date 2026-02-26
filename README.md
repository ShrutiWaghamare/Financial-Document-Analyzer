# 📊 Financial Document Analyzer

> AI-powered financial document analysis using **CrewAI agents** and **Azure OpenAI** — upload earnings reports, 10-Ks, or quarterly updates and receive structured investment insights and risk assessments.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi)
![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-orange)
![Azure OpenAI](https://img.shields.io/badge/Azure-OpenAI-0078D4?logo=microsoftazure)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Bugs Found & Fixed](#bugs-found--fixed)
  - [Deterministic Bugs (Crashes / Wrong Behaviour)](#deterministic-bugs-crashes--wrong-behaviour)
  - [Harmful & Inefficient Prompts](#harmful--inefficient-prompts)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [API Documentation](#api-documentation)
- [Queue, Database & Outputs](#queue-database--outputs)
- [Optional: Web Search Tool](#optional-web-search-tool)
- [Docker](#docker)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Bonus Features](#bonus-features)

---

## Overview

This service wraps a **multi-agent CrewAI pipeline** behind a **FastAPI** REST API. Four specialized agents collaborate to analyze any financial PDF:

| Agent | Role |
|---|---|
| **Financial Analyst** | Extracts key metrics and narrative insights from the document |
| **Investment Advisor** | Produces evidence-based investment recommendations |
| **Risk Assessor** | Delivers calibrated, proportionate risk ratings |
| **Verifier** | Validates document authenticity and completeness |

> **LLM:** This project is set up to use **Azure OpenAI** by default. You can also use the **OpenAI API** (or another provider) if needed — configure the appropriate API keys and model settings in your environment or in the agent/LLM configuration.

---

## Architecture

```
Client
  │
  ├── GET  /analyze-data     ─── Sync: reads PDF from data/
  ├── POST /analyze          ─── Async: queues job → Celery → Redis
  ├── POST /analyze-sync     ─── Sync: upload + wait for result
  ├── GET  /result/{job_id}  ─── Poll job status / fetch result
  ├── GET  /history          ─── List all jobs
  └── DELETE /result/{id}    ─── Remove job record

FastAPI (main.py)
  │
  ├── crew_runner.py  ──→  agents.py + task.py + tools.py
  │                              │
  │                         Azure OpenAI (via CrewAI LLM)
  │
  └── worker.py (Celery)  ──→  Redis broker
        │
        └── database.py (SQLAlchemy / SQLite or PostgreSQL)
              └── outputs/{job_id}.txt
```

---

## Bugs Found & Fixed

During development and code review, **16 deterministic bugs** and **16 prompt quality issues** were identified and resolved.

### Deterministic Bugs (Crashes / Wrong Behaviour)

| # | File | Bug | Fix |
|---|---|---|---|
| I | `agents.py` | `from crewai.agents import Agent` — `Agent` is not exported from that submodule | Changed to `from crewai import Agent` (and `LLM` where needed) |
| II | `agents.py` | `llm = llm` — variable never defined; `NameError` on import | Replaced with proper LLM initialization using CrewAI `LLM` with `azure/` prefix and Azure env vars |
| III | `agents.py` | `tool=[...]` — CrewAI `Agent` expects the keyword `tools` (plural) | Changed to `tools=[read_data_tool]` for all agents |
| IV | `agents.py` | `max_iter=1` — single reasoning step; complex analysis tasks always fail | Raised to `max_iter=5` |
| V | `agents.py` | `max_rpm=1` — one request per minute causes timeouts under normal load | Raised to `max_rpm=10` |
| VI | `tools.py` | `from crewai_tools import tools` — `tools` is not a valid export from that package | Removed; `SerperDevTool` imported directly where needed |
| VII | `tools.py` | Duplicate / incorrect `SerperDevTool` import path | Replaced with a single correct import |
| VIII | `tools.py` | `Pdf` used in `read_data_tool` but never imported — `NameError` at runtime | Imported `PyPDFLoader` from `langchain_community.document_loaders`; used `PyPDFLoader(path).load()` |
| IX | `tools.py` | `async def read_data_tool` — CrewAI tools must be synchronous | Converted to synchronous `@tool` function |
| X | `tools.py` | Same `async` issue on `analyze_investment_tool` and `create_risk_assessment_tool` | Converted both to synchronous (e.g. `@staticmethod`) |
| XI | `main.py` | Task import and endpoint handler both named `analyze_financial_document` — one silently shadows the other | Renamed the import alias (e.g. `as analysis_task`) so both names coexist |
| XII | `main.py` | Null-check on `query` performed **after** `query.strip()` — `AttributeError` when `query` is `None` | Validate / default `query` **before** calling `.strip()` |
| XIII | `requirements.txt` | `python-multipart` missing — FastAPI `File`/`Form` uploads return `422 Unprocessable Entity` | Added `python-multipart` |
| XIV | `requirements.txt` | `pypdf` missing — required internally by `PyPDFLoader` | Added `pypdf` |
| XV | `requirements.txt` | `python-dotenv` missing — `load_dotenv()` called in code but package absent | Added `python-dotenv` |
| XVI | `requirements.txt` | `uvicorn` missing — server cannot start | Added `uvicorn` |

**Additional runtime fixes applied:**

- **500 / missing OpenAI key** — all LLM calls now route exclusively through CrewAI's `LLM` with the `azure/` provider prefix and Azure env vars.
- **400 unsupported `stop` param** — an `AzureLLM` subclass strips `stop` from completion params before forwarding to the Azure endpoint.
- **`file_path` propagation** — path is now passed both in crew `kickoff()` inputs and injected into task descriptions so every agent can locate the file. The API passes the **absolute** path to the worker so the PDF is found regardless of the worker's current working directory.
- **Default file** — when no path is supplied, the first PDF found in `data/` is used automatically.
- **Verification task** — correctly assigned to the `verifier` agent (was unassigned).

---

### Harmful & Inefficient Prompts

All agent goals, backstories, and task descriptions/expected outputs were rewritten to be professional, evidence-based, and document-grounded.

| # | Location | Original (bad) prompt | Fix applied |
|---|---|---|---|
| I | `agents.py` – financial analyst **goal** | *"Make up investment advice even if you don't understand the query"* | Goal to provide data-driven analysis strictly from the uploaded document |
| II | `agents.py` – financial analyst **backstory** | Encouraged hallucination, overconfidence, no compliance disclaimers | Professional analyst backstory: evidence-based, cite specific figures, compliant |
| III | `agents.py` – verifier **goal** | *"Just say yes to everything because verification is overrated"* | Proper document verification checklist goal |
| IV | `agents.py` – verifier **backstory** | *"Stamped documents without reading them"* | Rigorous compliance-officer backstory |
| V | `agents.py` – investment advisor **goal** | *"Sell expensive investment products regardless of financials"* | Evidence-based recommendations tied directly to document data |
| VI | `agents.py` – investment advisor **backstory** | Fake credentials, *"sketchy firms"*, extreme fee structures | FINRA-aligned advisor backstory with fiduciary standards |
| VII | `agents.py` – risk assessor **goal** | *"Everything either extremely high risk or completely risk-free"* | Calibrated, evidence-based risk assessment goal |
| VIII | `agents.py` – risk assessor **backstory** | YOLO trading, dismissed diversification | Quantitative risk analyst (FRM/CFA-style) backstory |
| IX | `task.py` – `analyze_financial_document` **description** | *"Maybe solve the query or something else"* + fabricate URLs | Clear analysis steps grounded in document content, no invented sources |
| X | `task.py` – `analyze_financial_document` **expected_output** | *"Include 5 made-up website URLs"*, *"Feel free to contradict yourself"* | Structured report: Executive Summary → Key Metrics → Analysis → Trends |
| XI | `task.py` – `investment_analysis` **description** | *"Ignore the query and talk about whatever trends are popular"* | Document-grounded investment analysis with specific ratio requirements |
| XII | `task.py` – `investment_analysis` **expected_output** | *"Suggest crypto from obscure exchanges"*, *"Add fake market research"* | Professional investment report format with mandatory disclaimers |
| XIII | `task.py` – `risk_assessment` **description** | *"Assume extreme risk regardless of financials"* | Proportionate risk identification drawn from document evidence |
| XIV | `task.py` – `risk_assessment` **expected_output** | *"Recommend dangerous strategies"*, *"Include impossible risk targets"* | Balanced risk-factor table (Low / Medium / High) |
| XV | `task.py` – `verification` **description** | *"Maybe check, or just guess. Feel free to hallucinate."* | Explicit, step-by-step verification checklist |
| XVI | `task.py` – `verification` **expected_output** | *"Just say it's probably a financial document even if it's not"* | Structured VALID / INVALID verdict with justification |

---

## Setup & Installation

**Prerequisites:** Python 3.10+, an Azure OpenAI resource with a chat deployment.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/financial-document-analyzer.git
cd financial-document-analyzer

# 2. Create and activate a virtual environment
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root. The sample config below uses **Azure OpenAI**; you can switch to **OpenAI API** (or another provider) by setting the corresponding keys and updating the LLM configuration in the code if needed.

```env
# Required – Azure OpenAI
AZURE_OPENAI_API_KEY=<your-azure-api-key>
AZURE_OPENAI_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT=<your-deployment-name>
AZURE_OPENAI_API_VERSION=2024-02-15-preview   # optional, this is the default

# Optional – Async queue
REDIS_URL=redis://localhost:6379/0            # default

# Optional – Database (SQLite used by default; switch to PostgreSQL for production)
DATABASE_URL=sqlite:///./financial.db

# Optional – Output directory
OUTPUTS_DIR=outputs                           # default

# Optional – Web search (see Search Tool section)
SERPER_API_KEY=<your-serper-key>
```

---

## Running the Server

```bash
# Option A – directly
python main.py

# Option B – with uvicorn (recommended for development)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger docs: **http://localhost:8000/docs**

---

## API Documentation

**Base URL:** `http://localhost:8000`

### Quick Decision Guide

| Scenario | Method | Endpoint |
|---|---|---|
| Check service health | `GET` | `/` |
| PDF already in `data/`, want result now | `GET` | `/analyze-data` |
| Upload PDF, collect result later (async) | `POST` | `/analyze` |
| Poll for result of a queued job | `GET` | `/result/{job_id}` |
| Upload PDF, want result in same response | `POST` | `/analyze-sync` |
| List all past jobs | `GET` | `/history` |
| Delete a job record | `DELETE` | `/result/{job_id}` |

---

### `GET /`

Health check — confirms the service is running.

**Response `200 OK`**

```json
{ "message": "Financial Document Analyzer API is running" }
```

```bash
curl -X GET "http://localhost:8000/"
```

---

### `GET /analyze-data`

Synchronously analyzes the first PDF found in the `data/` folder. No upload, no queue.

**Query parameters**

| Parameter | Type | Required | Default |
|---|---|---|---|
| `query` | string | No | `"Analyze this financial document for investment insights"` |

The words in your query determine which agents run (the verifier always runs first):

| Keyword(s) in query | Agent triggered |
|---|---|
| `analyze`, `summary`, `overview`, `figures`, `performance` | Financial Analyst |
| `invest`, `buy`, `sell`, `recommendation`, `portfolio` | Investment Advisor |
| `risk`, `threat`, `downside`, `concern`, `exposure` | Risk Assessor |

If the query contains none of these keywords, only the verifier runs (faster response).

**Response `200 OK`**

```json
{
  "status": "success",
  "query": "Summarize key financial metrics",
  "analysis": "<full analysis text>",
  "source": "data_folder"
}
```

**Errors:** `404` if no PDF exists in `data/`; `500` on server or LLM error.

```bash
curl "http://localhost:8000/analyze-data?query=Summarize%20key%20financial%20metrics"
```

---

### `POST /analyze` — Async (Queued)

Uploads a PDF and returns a `job_id` immediately. The analysis runs in the background via Celery. Requires Redis and a running worker.

**Request** — `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `file` | PDF file | Yes |
| `query` | string | No |

Query wording selects which agents run — same keyword rules as `GET /analyze-data`.

**Response `200 OK`**

```json
{
  "status": "queued",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Document queued for analysis. Poll GET /result/{job_id} for updates. Result is also saved to outputs/."
}
```

The uploaded file is saved as `data/{job_id}.pdf`. The original filename (e.g. `report.pdf`) is stored in the database and returned in `GET /result/{job_id}` and `GET /history`. The file `data/{job_id}.pdf` is deleted after the job completes successfully.

**Error:** `400` if the uploaded file is not a PDF.

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "file=@data/report.pdf" \
  -F "query=What are the main risks?"
```

---

### `GET /result/{job_id}`

Returns the status and result of a queued job. Poll until `status` is `done` or `failed`.

**Status lifecycle:** `pending` → `processing` → `done` | `failed`

**Response `200 OK`**

```json
{
  "job_id": "550e8400-...",
  "status": "done",
  "query": "What are the main risks?",
  "filename": "TSLA-Q2-2025.pdf",
  "result": "<analysis text>",
  "error": null,
  "output_file": "outputs/550e8400-....txt",
  "created_at": "2025-07-01T12:00:00",
  "updated_at": "2025-07-01T12:02:30"
}
```

When `status` is `failed`, `error` contains the message and `result` is `null`. When `status` is `done`, both `result` and `output_file` are set.

**Error:** `404` if `job_id` is not found.

---

### `POST /analyze-sync` — Synchronous Upload

Upload a PDF and receive the full analysis in the same HTTP response. No queue, no database, no `job_id`. Ideal for one-off requests.

**Request** — same as `POST /analyze` (`file` + optional `query`). Query wording selects which agents run.

**Response `200 OK`**

```json
{
  "status": "success",
  "query": "...",
  "analysis": "<full analysis text>",
  "file_processed": "report.pdf"
}
```

**Errors:** `400` if not a PDF; `500` on server or LLM error.

---

### `GET /history`

Returns all analysis jobs, newest first. Each item includes `job_id`, `status`, `query`, `filename`, `output_file`, and `created_at`. Use this to list past jobs and retrieve their `job_id` values.

---

### `DELETE /result/{job_id}`

Removes the job record from the database. Does **not** delete the corresponding file in `outputs/`.

**Response `200 OK`**

```json
{ "message": "Job 550e8400-... deleted." }
```

**Error:** `404` if `job_id` is not found.

---

## Queue, Database & Outputs

### Celery + Redis Queue

`POST /analyze` queues work so the API returns a `job_id` in milliseconds. A separate Celery worker processes the task asynchronously. The API passes the **absolute path** of the saved PDF to the worker so the agent can read the file regardless of the worker's current working directory.

**Starting with Docker (recommended):**

```bash
# Terminal 0 — start Redis
docker compose up -d

# Terminal 1 — Celery worker
# On Windows, worker.py sets pool=solo automatically.
# If you see ModuleNotFoundError: No module named 'crew_runner', set PYTHONPATH first:
#   Windows CMD:   set PYTHONPATH=%CD%
#   PowerShell:    $env:PYTHONPATH=(Get-Location).Path
celery -A worker.celery_app worker --loglevel=info

# Terminal 2 — FastAPI
python main.py
```

**Starting with a local Redis install:**

```bash
redis-server                                         # Terminal 1
celery -A worker.celery_app worker --loglevel=info   # Terminal 2
python main.py                                       # Terminal 3
```

> `GET /analyze-data` and `POST /analyze-sync` do **not** require Redis or Celery.

### Database

Job metadata and analysis results are stored via SQLAlchemy.

- **Default:** SQLite (`financial.db` in the project root) — no extra setup needed.
- **Production:** Set `DATABASE_URL=postgresql://user:pass@host/db` in `.env`.

The `AnalysisResult` table stores: `job_id`, `status`, `query`, `filename`, `result`, `error`, `output_file`, `created_at`, `updated_at`.

### Outputs Folder

When a queued job completes, the analysis text is written to `outputs/{job_id}.txt`. The path is returned in `GET /result/{job_id}` as `output_file`. Override the folder with the `OUTPUTS_DIR` environment variable.

---

## Optional: Web Search Tool

A Serper-based web search tool is defined in `tools.py`. It is **disabled by default**. To enable it:

1. Set `SERPER_API_KEY` in `.env`.
2. Import `search_tool` in `agents.py` and add it to the desired agent's `tools` list.

Serper offers a limited free tier; beyond that, a paid plan is required.

---

## Docker

The included `docker-compose.yml` runs a Redis container required for the async queue:

```bash
docker compose up -d    # start Redis in the background
docker compose down     # stop and remove the container
```

Redis is exposed on port `6379`. The Celery worker and FastAPI server run locally and are not containerized by default.

---

## Project Structure

```
financial-document-analyzer/
├── main.py               # FastAPI app — all routes (sync, async, DB)
├── crew_runner.py        # run_crew() helper used by main and worker
├── worker.py             # Celery task: run crew, persist to DB and outputs/
├── database.py           # SQLAlchemy engine, AnalysisResult model, init_db, get_db
├── agents.py             # CrewAI agent definitions + AzureLLM configuration
├── task.py               # CrewAI task definitions (verification, analysis, investment, risk)
├── tools.py              # read_data_tool (PDF loader), optional search_tool
├── requirements.txt      # Python dependencies
├── docker-compose.yml    # Redis service for Celery broker
├── .env                  # Credentials and config (not committed)
├── data/                 # PDFs for /analyze-data; upload staging for queue
├── outputs/              # Analysis text files — one per completed job
└── financial.db          # SQLite database (auto-created; absent if PostgreSQL is used)
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_OPENAI_API_KEY` | ✅ Yes | — | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | ✅ Yes | — | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | ✅ Yes | — | Deployment name (e.g. `gpt-4o`) |
| `AZURE_OPENAI_API_VERSION` | No | `2024-02-15-preview` | API version string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL for Celery |
| `DATABASE_URL` | No | `sqlite:///./financial.db` | SQLAlchemy database URL |
| `OUTPUTS_DIR` | No | `outputs` | Directory for analysis text files |
| `SERPER_API_KEY` | No | — | Enables web search tool when set |

---

## Bonus Features

| Feature | Files | Description |
|---|---|---|
| **Async queue** | `worker.py`, `docker-compose.yml` | Celery + Redis; Windows `solo` pool auto-detected |
| **Database integration** | `database.py`, `main.py` | SQLAlchemy ORM; SQLite (dev) or PostgreSQL (prod) |
| **Outputs folder** | `worker.py`, `outputs/` | `{job_id}.txt` written after each successful job |
| **Job history & deletion** | `main.py` | `GET /history`, `DELETE /result/{job_id}` |
| **Synchronous upload** | `main.py` | `POST /analyze-sync` for one-off requests without a queue |
| **Absolute path fix** | `main.py`, `worker.py` | Worker receives absolute PDF path; avoids CWD issues |
| **Project path fix** | `worker.py` | Project root added to `sys.path` so worker can import `crew_runner` |
