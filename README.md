# DevPulse — Engineering Health Intelligence Agent

> Hackathon Track: Fivetran | May 2026

DevPulse analyses GitHub and Jira data synced by Fivetran and surfaces PR bottlenecks,
commit velocity anomalies, sprint health, and stale tickets — via a conversational agent
powered by Google Gemini + ADK.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| pip | latest |
| Node.js | 18+ (for optional Fivetran MCP server) |

---

## Quick start

### 1. Clone and install

```bash
git clone <repo-url>
cd devpulse
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Open .env and fill in the values (see table below)
```

**Credentials needed:**

| Variable | Where to get it |
|----------|-----------------|
| `GOOGLE_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `GCP_PROJECT_ID` | Google Cloud Console (top of any page) |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP → IAM → Service Accounts → create → download JSON key |
| `FIVETRAN_API_KEY` + `FIVETRAN_API_SECRET` | Fivetran Dashboard → Settings → API Config |
| `GITHUB_CONNECTOR_ID` | Fivetran → Connectors → GitHub → connector ID in URL |
| `JIRA_CONNECTOR_ID` | Same for Jira connector |
| `SLACK_WEBHOOK_URL` | Optional — Slack App → Incoming Webhooks |

### 3. Run without real credentials (mock mode)

Set `MOCK_MODE=true` in `.env`. The tools return realistic fixture data so you can
develop and demo without any cloud accounts. You **still need `GOOGLE_API_KEY`** for
the Gemini LLM calls.

```bash
# .env
MOCK_MODE=true
GOOGLE_API_KEY=your-key-here
```

---

## Running the backend

### FastAPI HTTP server (for frontend integration)

```bash
python agent/main.py
# → http://localhost:8000/health  (health check)
# → http://localhost:8000/docs    (Swagger UI — test all endpoints here)
```

> **Note:** The server binds to `0.0.0.0:8000`. Open `http://localhost:8000` in your
> browser — do **not** use `http://0.0.0.0:8000` (that address is invalid on Windows).

### Interactive CLI (for testing)

```bash
MODE=cli python agent/main.py
# or
MODE=cli MOCK_MODE=true python agent/main.py
```

### Daily digest job

```bash
python jobs/daily_digest.py
```

---

## BigQuery schema deployment

Run once after Fivetran has completed its first sync:

```bash
python schema/deploy_schema.py
```

Creates `agent_digests`, `agent_anomalies`, `agent_logs` tables and all five views
in the `devpulse` dataset. Safe to re-run (idempotent).

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check + mock mode status |
| `POST` | `/query` | Ask the agent a natural-language question |
| `GET` | `/connectors/status` | GitHub + Jira Fivetran sync freshness |
| `POST` | `/sync/trigger?connector=github` | Trigger an immediate Fivetran sync |
| `GET` | `/prs/open?min_age_days=3` | Open PRs older than N days |
| `GET` | `/sprint/health` | Active sprint burn-down metrics |
| `GET` | `/anomalies` | Current metric anomalies |
| `POST` | `/digest/generate` | Run the daily digest job |

### Example query request

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Which PRs have been waiting more than 5 days for review?", "session_id": "my-session-123"}'
```

---

## Project structure

```
devpulse/
├── agent/
│   ├── agent.py          # ADK agent factory + runner
│   ├── system_prompt.py  # Agent persona + hard rules
│   └── main.py           # Entry point (api or cli mode)
├── tools/
│   ├── bq_client.py      # BigQuery client singleton (mock-aware)
│   ├── bq_tools.py       # 7 BigQuery tools (read + write)
│   └── fivetran_tools.py # 3 Fivetran tools (status, list, trigger)
├── schema/
│   ├── tables.sql         # DDL for agent-managed BQ tables
│   ├── views.sql          # DDL for 5 BQ views
│   └── deploy_schema.py   # Idempotent schema deployer
├── jobs/
│   ├── daily_digest.py    # 9-step daily digest orchestrator
│   └── slack_notifier.py  # Optional Slack webhook poster
├── interface/
│   ├── api.py             # FastAPI HTTP server
│   └── cli.py             # Interactive terminal REPL
├── mock/
│   ├── fixtures.py        # Realistic fixture data
│   └── mock_client.py     # BigQuery mock stub
├── tests/
│   ├── test_fivetran_tools.py
│   └── test_bq_tools.py
├── docs/                  # PRD, TRD, DATA_SCHEMA, APP_FLOW
├── .env.example
└── requirements.txt
```

---

## Running tests

```bash
pytest tests/ -v
# All tests pass in MOCK_MODE — no credentials needed
```

---

## Architecture

```
User query
    │
    ▼
FastAPI /query endpoint
    │
    ▼
Google ADK Runner  ←── 10-turn InMemory session history
    │
    ▼
Gemini 1.5 Flash  ◄──── system_prompt.py (5 hard rules)
    │
    ├──► check_connector_status ──► Fivetran REST API
    ├──► query_open_prs          ──► BigQuery v_open_prs_aged
    ├──► query_commit_velocity   ──► BigQuery v_commit_velocity_daily
    ├──► query_stale_tickets     ──► BigQuery v_ticket_age_by_status
    ├──► query_sprint_health     ──► BigQuery v_sprint_burndown
    ├──► detect_anomalies        ──► BigQuery v_metric_baselines
    └──► write_digest            ──► BigQuery agent_digests
```

Data flows:
- **GitHub / Jira** → Fivetran (hourly sync) → BigQuery `devpulse` dataset
- **Agent writes** → `agent_digests`, `agent_anomalies`, `agent_logs`
