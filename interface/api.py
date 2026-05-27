"""DevPulse FastAPI HTTP server.

Exposes the ADK agent and data tools as REST endpoints that the
frontend can call. Session IDs are managed by the client; the server
keeps per-session conversation history in memory via ADK's
InMemorySessionService.

Start with: uvicorn interface.api:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

log = logging.getLogger(__name__)

# ── Shared state ───────────────────────────────────────────────────────────

_runner         = None
_session_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner, _session_service
    log.info("Initialising DevPulse agent …")
    from agent.agent import create_runner
    _runner, _session_service = create_runner()
    log.info("Agent ready.")
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="DevPulse API",
    description="Engineering Health Intelligence Agent — backend API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / response models ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    session_id: str
    latency_ms: int


class DigestResponse(BaseModel):
    digest_id: str
    message: str


class ConnectorStatusResponse(BaseModel):
    github: dict
    jira: dict


# ── Helper ─────────────────────────────────────────────────────────────────

async def _run_agent_query(session_id: str, question: str) -> str:
    """Run one turn through the ADK agent and return the text response."""
    from google.genai import types as genai_types

    # Ensure session exists
    session = await _session_service.get_session(app_name="devpulse", user_id=session_id, session_id=session_id)
    if session is None:
        await _session_service.create_session(app_name="devpulse", user_id=session_id, session_id=session_id)

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=question)],
    )

    response_text = ""
    async for event in _runner.run_async(
        user_id=session_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                response_text = event.content.parts[0].text or ""
            break

    return response_text


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — also returns mock mode status."""
    return {
        "status": "ok",
        "mock_mode": os.getenv("MOCK_MODE", "false").lower() == "true",
        "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    }


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Submit a natural-language question to the DevPulse agent.

    Pass a stable `session_id` to maintain multi-turn conversation history.
    If omitted, a new session is created for this request (stateless).
    """
    if _runner is None:
        raise HTTPException(status_code=503, detail="Agent not initialised.")

    session_id = req.session_id or str(uuid.uuid4())
    start      = time.monotonic()

    try:
        answer = await _run_agent_query(session_id, req.question)
    except Exception as exc:
        log.exception("Agent query failed")
        raise HTTPException(status_code=500, detail=str(exc))

    latency_ms = int((time.monotonic() - start) * 1000)

    # Fire-and-forget: log the interaction to BigQuery
    try:
        from tools.bq_tools import write_agent_log
        write_agent_log(
            session_id=session_id,
            user_query=req.question,
            tools_called=[],           # ADK doesn't expose tool trace here; extend if needed
            bq_bytes=0,
            latency_ms=latency_ms,
            response_preview=answer[:500],
        )
    except Exception as exc:
        log.warning("Could not write agent_log: %s", exc)

    return QueryResponse(answer=answer, session_id=session_id, latency_ms=latency_ms)


@app.get("/connectors/status", response_model=ConnectorStatusResponse)
async def connectors_status():
    """Return sync freshness for GitHub and Jira Fivetran connectors."""
    from tools.fivetran_tools import check_connector_status

    github_id = os.getenv("GITHUB_CONNECTOR_ID", "mock-github-connector-001")
    jira_id   = os.getenv("JIRA_CONNECTOR_ID",   "mock-jira-connector-001")

    return ConnectorStatusResponse(
        github=check_connector_status(github_id),
        jira=check_connector_status(jira_id),
    )


@app.post("/sync/trigger")
async def trigger_sync_endpoint(connector: str = "github"):
    """Trigger an immediate Fivetran sync for 'github' or 'jira'."""
    from tools.fivetran_tools import trigger_sync

    connector_map = {
        "github": os.getenv("GITHUB_CONNECTOR_ID", "mock-github-connector-001"),
        "jira":   os.getenv("JIRA_CONNECTOR_ID",   "mock-jira-connector-001"),
    }
    connector_id = connector_map.get(connector.lower())
    if not connector_id:
        raise HTTPException(status_code=400, detail="connector must be 'github' or 'jira'")

    result = trigger_sync(connector_id)
    return result


@app.post("/digest/generate", response_model=DigestResponse)
async def generate_digest():
    """Trigger the full daily digest job and return the digest ID."""
    try:
        from jobs.daily_digest import run_digest
        digest_id = run_digest()
        return DigestResponse(digest_id=digest_id, message="Digest generated successfully.")
    except Exception as exc:
        log.exception("Digest generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/anomalies")
async def get_anomalies():
    """Run anomaly detection and return active anomalies."""
    from tools.bq_tools import detect_anomalies
    anomalies = detect_anomalies()
    return {"anomalies": anomalies, "count": len(anomalies)}


@app.get("/sprint/health")
async def sprint_health():
    """Return burn-down metrics for the active sprint."""
    from tools.bq_tools import query_sprint_health
    return query_sprint_health()


@app.get("/prs/open")
async def open_prs(min_age_days: int = 3):
    """Return open PRs older than min_age_days days."""
    from tools.bq_tools import query_open_prs
    return {"prs": query_open_prs(min_age_days), "min_age_days": min_age_days}
