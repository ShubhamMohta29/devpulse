"""Fivetran connector tools.

These wrap the Fivetran REST API (v1). The TRD specifies using the
Fivetran MCP server; the REST API delivers the same data and avoids
a separate Node.js process. Swap to ADK MCPToolset if preferred.

All functions return plain dicts/lists — ADK serialises these for
Gemini function-call responses automatically.
"""

import logging
import os
import time
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_FIVETRAN_BASE = "https://api.fivetran.com/v1"
_STALE_HOURS   = 4


def _is_mock() -> bool:
    return os.getenv("MOCK_MODE", "false").lower() == "true"


def _fivetran_client() -> httpx.Client:
    key    = os.getenv("FIVETRAN_API_KEY", "")
    secret = os.getenv("FIVETRAN_API_SECRET", "")
    if not key or not secret:
        raise EnvironmentError("FIVETRAN_API_KEY / FIVETRAN_API_SECRET not set.")
    return httpx.Client(auth=(key, secret), base_url=_FIVETRAN_BASE, timeout=15)


def _hours_ago(ts_str: str) -> float:
    """Return how many hours ago an ISO timestamp was."""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - ts
        return delta.total_seconds() / 3600
    except Exception:
        return 999.0


# ── Public tool functions ──────────────────────────────────────────────────

def check_connector_status(connector_id: str) -> dict:
    """Check the sync status of a Fivetran connector.

    Returns connector ID, service name, last successful sync timestamp,
    current status, and whether the data is considered stale (>4 hours old).

    Args:
        connector_id: The Fivetran connector ID to check.
    """
    if _is_mock():
        from mock.fixtures import CONNECTOR_STATUS
        # Return by connector_id or fall back to github fixture
        for v in CONNECTOR_STATUS.values():
            if v["connector_id"] == connector_id:
                return v
        # Unknown ID in mock — return a stale placeholder
        return {
            "connector_id": connector_id,
            "name": "Unknown (mock)",
            "service": "unknown",
            "status": "active",
            "last_successful_sync_at": "1970-01-01T00:00:00+00:00",
            "is_stale": True,
        }

    try:
        with _fivetran_client() as client:
            resp = client.get(f"/connectors/{connector_id}")
            resp.raise_for_status()
            data = resp.json()["data"]

            last_sync = data.get("succeeded_at") or data.get("created_at", "")
            is_stale  = _hours_ago(last_sync) > _STALE_HOURS

            return {
                "connector_id": connector_id,
                "name": data.get("schema", connector_id),
                "service": data.get("service", ""),
                "status": data.get("status", {}).get("sync_state", "unknown"),
                "last_successful_sync_at": last_sync,
                "is_stale": is_stale,
            }
    except httpx.HTTPStatusError as exc:
        log.warning("Fivetran API error for %s: %s", connector_id, exc)
        return {"connector_id": connector_id, "status": "error", "is_stale": True, "error": str(exc)}
    except Exception as exc:
        log.warning("Fivetran unreachable for %s: %s", connector_id, exc)
        return {"connector_id": connector_id, "status": "unreachable", "is_stale": True, "error": str(exc)}


def list_connectors() -> list[dict]:
    """List all connectors in the Fivetran account with their sync status.

    Returns a list of connectors, each with id, name, service, and last sync time.
    """
    if _is_mock():
        from mock.fixtures import CONNECTORS_LIST
        return CONNECTORS_LIST

    try:
        with _fivetran_client() as client:
            resp = client.get("/connectors")
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("items", [])
            return [
                {
                    "connector_id": c["id"],
                    "name": c.get("schema", c["id"]),
                    "service": c.get("service", ""),
                    "status": c.get("status", {}).get("sync_state", "unknown"),
                    "last_successful_sync_at": c.get("succeeded_at", ""),
                    "is_stale": _hours_ago(c.get("succeeded_at", "")) > _STALE_HOURS,
                }
                for c in items
            ]
    except Exception as exc:
        log.warning("list_connectors failed: %s", exc)
        return [{"status": "unreachable", "error": str(exc)}]


def trigger_sync(connector_id: str) -> dict:
    """Trigger an immediate sync for a Fivetran connector.

    Sends the trigger, then polls every 30 seconds for up to 5 minutes.
    Returns success status and the completed sync timestamp when done.

    Args:
        connector_id: The Fivetran connector ID to sync.
    """
    if _is_mock():
        from datetime import datetime, timezone
        return {
            "connector_id": connector_id,
            "success": True,
            "sync_completed_at": datetime.now(timezone.utc).isoformat(),
            "note": "Mock mode — no real sync triggered.",
        }

    try:
        with _fivetran_client() as client:
            resp = client.post(f"/connectors/{connector_id}/force")
            resp.raise_for_status()
    except Exception as exc:
        return {"connector_id": connector_id, "success": False, "error": str(exc)}

    # Poll until sync completes or we time out (300 s)
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(30)
        status = check_connector_status(connector_id)
        if not status.get("is_stale"):
            return {
                "connector_id": connector_id,
                "success": True,
                "sync_completed_at": status.get("last_successful_sync_at", ""),
            }

    return {
        "connector_id": connector_id,
        "success": False,
        "error": "Sync did not complete within 5 minutes.",
    }
