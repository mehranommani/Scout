# Scout — Setup Guide

AI-powered company intelligence. Enter a company or product name; the agent scrapes public sources, validates the data, and generates a structured research report.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker + Compose | v24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Ollama | latest | [ollama.com](https://ollama.com/) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) |
| Python | 3.11+ | [python.org](https://python.org/) |

Pull the required Ollama models:

```bash
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

---

## Quick Start

### Step 1 — Run setup (one time only)

```bash
bash setup.sh
```

This automatically:
- Generates `.env` with secure random secrets
- Creates `frontend/.env.local`
- Starts Docker infrastructure (PostgreSQL, Qdrant, Langfuse)
- Creates Python venv and installs backend dependencies
- Installs frontend Node dependencies

At the end it prints the Langfuse admin password — **save it**.

---

### Step 2 — Start backend (terminal 1)

```bash
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/api/health
# → {"status":"ok","db":true,"qdrant":true,"ollama":true}
```

Or with Make:

```bash
make backend
```

---

### Step 3 — Start frontend (terminal 2)

```bash
cd frontend && npm run dev
```

Or with Make:

```bash
make frontend
```

Open: [http://localhost:3000](http://localhost:3000)

---

### Step 4 — Set up Langfuse evaluators (one time only)

#### 4a. Add the Ollama LLM connection in the UI

1. Open [http://localhost:3001](http://localhost:3001) and log in with the credentials printed by `setup.sh`
2. Go to **Settings → LLM Connections → Add**
3. Fill in:
   - Provider: **OpenAI** (Ollama is OpenAI-compatible)
   - Base URL: `http://host.docker.internal:11434/v1`
   - API Key: `ollama`
   - Model name: `qwen2.5:14b`

#### 4b. Insert evaluator templates

```bash
bash backend/setup_langfuse_evals.sh
```

Or with Make:

```bash
make evals
```

This creates three LLM-as-judge evaluators that auto-run on every new trace:
- `eval/factual_grounding` — detects hallucinated facts
- `eval/specific_facts` — checks for concrete verifiable data
- `eval/no_active_bias` — verifies founders are not presented as currently active

---

## Daily Use (after first-time setup)

```bash
# Start infrastructure (if Docker is not running)
make infra

# Terminal 1 — backend
make backend

# Terminal 2 — frontend
make frontend

# Run tests
make test

# Health check
make health
```

---

## Project Structure

```
scout/
├── setup.sh                     # One-time setup script
├── Makefile                     # Common commands
├── docker-compose.yml
├── .env.example                 # Template — setup.sh fills this in automatically
│
├── backend/
│   ├── main.py                  # FastAPI app — all HTTP endpoints
│   ├── config.py                # All settings (loaded from .env)
│   ├── db.py                    # PostgreSQL via asyncpg
│   ├── qdrant_store.py          # Qdrant vector store
│   ├── langfuse_client.py       # Langfuse SDK + structural validation
│   ├── requirements.txt
│   ├── setup_langfuse_evals.sh  # One-time evaluator provisioning
│   ├── agent/
│   │   ├── graph.py             # LangGraph state machine
│   │   ├── nodes.py             # All node functions
│   │   └── state.py             # AgentState TypedDict
│   └── mcp_tools/
│       ├── server.py            # FastMCP tool server
│       └── scrapers/
│           ├── wikidata.py
│           ├── opencorporates.py
│           ├── crunchbase.py
│           ├── linkedin.py
│           └── duckduckgo.py
│
├── frontend/
│   └── src/app/
│       ├── page.tsx             # Home / search
│       ├── research/[sessionId] # Live progress (SSE)
│       ├── reports/             # Report list + detail
│       ├── eval/                # Evaluation dashboard
│       ├── sources/             # Data source health
│       └── settings/            # Config viewer
│
└── tests/
    ├── test_api.py
    ├── test_agent_nodes.py
    └── test_scrapers.py
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/research` | Start a research session → `{session_id}` |
| `GET` | `/api/research/{id}/stream` | SSE progress stream |
| `GET` | `/api/reports/{id}` | Fetch a completed report |
| `GET` | `/api/reports` | List all reports |
| `GET` | `/api/stats` | Aggregate metrics |
| `GET` | `/api/eval` | Per-report evaluation rows |
| `GET` | `/api/config` | Current agent configuration |
| `GET` | `/api/health` | Service health check |

---

## Configuration Reference

All settings live in `backend/config.py` and are loaded from `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `qwen2.5:14b` | Ollama model for report generation |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model for vector embeddings |
| `VALIDATION_MIN_TEXT_LENGTH` | `500` | Minimum report character count |
| `VALIDATION_MIN_RELEVANCY` | `0.65` | Minimum structural score to pass |
| `VALIDATION_MAX_RETRIES` | `3` | Max regeneration attempts before storing best |
| `REPORTS_PAGE_LIMIT` | `500` | Max reports returned by `/api/reports` |
| `EVAL_ROWS_LIMIT` | `500` | Max rows returned by `/api/eval` |

---

## Data Sources

| Source | Type | API Key Required |
|--------|------|-----------------|
| Wikidata | Free SPARQL | No |
| DuckDuckGo | Free web search | No |
| OpenCorporates | REST API | Yes (`OPENCORPORATES_API_KEY`) |
| Crunchbase | REST API | Yes (`CRUNCHBASE_API_KEY`) |
| LinkedIn | Stealth scraper | No |

Sources without an API key are automatically skipped. DuckDuckGo and Wikidata always run.

---

## Running Tests

```bash
make test
# or
cd tests && python3 -m pytest -v
```

Tests run fully offline using mocked HTTP responses — no running backend required.

---

## Deployment Checklist

Before deploying to production:

- [ ] Add your production domain to `allow_origins` in `backend/main.py`
- [ ] Add production URLs to `frontend/.env.local` (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_LANGFUSE_URL`)
- [ ] Set `NEXTAUTH_URL` in `docker-compose.yml` to your production Langfuse URL
- [ ] Set `LANGFUSE_HOST` to the public URL of your Langfuse instance
- [ ] Use a reverse proxy (nginx/Caddy) with TLS in front of both services
- [ ] Run `npm run build` and serve with `npm start` (not `npm run dev`)
- [ ] Back up the `postgres_data` and `qdrant_data` Docker volumes
