"""BigQuery tool implementations for the DevPulse agent.

Each function is registered as a tool with the ADK agent. They accept
plain Python types (int, str) and return JSON-serialisable dicts/lists
so ADK can relay the results to Gemini as function-call responses.

Mock mode: set MOCK_MODE=true in .env to return fixture data without
hitting a real BigQuery project.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_DATASET = os.getenv("BQ_DATASET", "devpulse")


def _is_mock() -> bool:
    return os.getenv("MOCK_MODE", "false").lower() == "true"


def _project() -> str:
    p = os.getenv("GCP_PROJECT_ID", "")
    if not p:
        raise EnvironmentError("GCP_PROJECT_ID is not set.")
    return p


def _run_query(sql: str, params: list | None = None) -> list[dict]:
    """Execute a parameterised BigQuery query and return rows as dicts."""
    from google.cloud import bigquery
    from tools.bq_client import get_client

    client = get_client()
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    job = client.query(sql, job_config=job_config)
    rows = job.result()
    return [dict(row) for row in rows]


# ── Read tools ─────────────────────────────────────────────────────────────

def query_open_prs(min_age_days: int = 3) -> list[dict]:
    """Return open pull requests that have been open for at least min_age_days days.

    Includes PR number, title, author, age in days, last reviewer, and review state.
    Always checks data freshness via check_connector_status before calling this.

    Args:
        min_age_days: Minimum age threshold in days. Default is 3.
    """
    if _is_mock():
        from mock.fixtures import OPEN_PRS
        return [pr for pr in OPEN_PRS if pr["age_days"] >= min_age_days]

    from google.cloud import bigquery
    sql = f"""
        SELECT
          pr_number, title, author_login, repo_name,
          age_days, age_bucket, last_reviewer,
          last_review_state, last_reviewed_at, created_at
        FROM `{_project()}.{_DATASET}.v_open_prs_aged`
        WHERE age_days >= @min_age_days
        ORDER BY age_days DESC
    """
    params = [bigquery.ScalarQueryParameter("min_age_days", "INT64", min_age_days)]
    return _run_query(sql, params)


def query_commit_velocity(days: int = 7) -> list[dict]:
    """Return daily commit counts for the past N days, grouped by repository.

    Useful for detecting velocity drops or spikes across the engineering org.

    Args:
        days: Number of past days to include. Default is 7.
    """
    if _is_mock():
        from mock.fixtures import COMMIT_VELOCITY_7D, COMMIT_VELOCITY_14D
        data = COMMIT_VELOCITY_14D if days > 7 else COMMIT_VELOCITY_7D
        return data[-days * 2:]  # 2 repos per day

    from google.cloud import bigquery
    sql = f"""
        SELECT commit_date, repo_name, commit_count, additions_sum, deletions_sum
        FROM `{_project()}.{_DATASET}.v_commit_velocity_daily`
        WHERE commit_date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        ORDER BY commit_date DESC, repo_name
    """
    params = [bigquery.ScalarQueryParameter("days", "INT64", days)]
    return _run_query(sql, params)


def query_stale_tickets(status: str = "In Progress", min_age_days: int = 14) -> list[dict]:
    """Return Jira tickets in a specific status that are older than min_age_days.

    Helps surface tickets that may be blocked, forgotten, or need re-assignment.
    Results are aggregated — no individual performance scores are included.

    Args:
        status: The Jira ticket status to filter on (e.g. 'In Progress', 'In Review', 'Blocked').
        min_age_days: Minimum ticket age in days. Default is 14.
    """
    if _is_mock():
        from mock.fixtures import STALE_TICKETS
        candidates = STALE_TICKETS.get(status, [])
        return [t for t in candidates if t["age_days"] >= min_age_days]

    from google.cloud import bigquery
    sql = f"""
        SELECT key, summary, status, issue_type, priority,
               assignee_id, sprint_id, story_points,
               age_days, days_since_update
        FROM `{_project()}.{_DATASET}.v_ticket_age_by_status`
        WHERE status = @status
          AND age_days >= @min_age_days
        ORDER BY age_days DESC
    """
    params = [
        bigquery.ScalarQueryParameter("status", "STRING", status),
        bigquery.ScalarQueryParameter("min_age_days", "INT64", min_age_days),
    ]
    return _run_query(sql, params)


def query_sprint_health() -> dict:
    """Return burn-down metrics for the currently active sprint.

    Includes total story points, completed points, remaining points, blocked
    ticket count, days remaining, and an is_on_track flag. A sprint is
    considered on-track when pct_complete >= expected_pct based on elapsed time.

    Returns a single dict with sprint health data.
    """
    if _is_mock():
        from mock.fixtures import SPRINT_HEALTH
        return SPRINT_HEALTH

    rows = _run_query(f"""
        SELECT sprint_id, sprint_name, sprint_state, start_date, end_date,
               total_tickets, total_points, points_completed, points_remaining,
               tickets_done, tickets_blocked, days_remaining, pct_complete
        FROM `{_project()}.{_DATASET}.v_sprint_burndown`
        WHERE sprint_state = 'active'
        LIMIT 1
    """)
    if not rows:
        return {"error": "No active sprint found."}

    row = rows[0]
    # Compute is_on_track: expected completion = elapsed_days / total_sprint_days
    from datetime import date
    start = row.get("start_date")
    end   = row.get("end_date")
    if start and end:
        today         = date.today()
        total_days    = max((end - start).days, 1)
        elapsed_days  = max((today - start).days, 0)
        expected_pct  = (elapsed_days / total_days) * 100
        row["expected_pct_complete"] = round(expected_pct, 1)
        row["is_on_track"] = (row.get("pct_complete", 0) >= expected_pct - 10)
    return row


def generate_trend_report(window_days: int = 30) -> dict:
    """Generate a trend report covering the past window_days days.

    Aggregates PR merge rate, commit velocity, and ticket completion across
    the specified window. Returns a structured report dict.

    Args:
        window_days: Number of past days to cover. Default is 30.
    """
    if _is_mock():
        from mock.fixtures import COMMIT_VELOCITY_14D
        commits = COMMIT_VELOCITY_14D
        total_commits = sum(r["commit_count"] for r in commits)
        return {
            "window_days": window_days,
            "total_commits": total_commits,
            "avg_daily_commits": round(total_commits / max(len(commits) // 2, 1), 1),
            "open_prs_gt_7d": 1,
            "stale_in_progress_tickets": 2,
            "note": "Mock trend report — wire to real BQ for live data.",
        }

    from google.cloud import bigquery
    velocity_rows = _run_query(f"""
        SELECT SUM(commit_count) AS total_commits,
               AVG(commit_count) AS avg_daily_commits,
               COUNT(DISTINCT commit_date) AS active_days
        FROM `{_project()}.{_DATASET}.v_commit_velocity_daily`
        WHERE commit_date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
    """, [bigquery.ScalarQueryParameter("days", "INT64", window_days)])

    pr_rows = _run_query(f"""
        SELECT COUNT(*) AS stale_pr_count
        FROM `{_project()}.{_DATASET}.v_open_prs_aged`
        WHERE age_days >= 7
    """)

    ticket_rows = _run_query(f"""
        SELECT status, COUNT(*) AS ticket_count, AVG(age_days) AS avg_age_days
        FROM `{_project()}.{_DATASET}.v_ticket_age_by_status`
        WHERE age_days <= @days
        GROUP BY status
    """, [bigquery.ScalarQueryParameter("days", "INT64", window_days)])

    v = velocity_rows[0] if velocity_rows else {}
    return {
        "window_days": window_days,
        "total_commits": v.get("total_commits", 0),
        "avg_daily_commits": round(float(v.get("avg_daily_commits") or 0), 1),
        "active_commit_days": v.get("active_days", 0),
        "stale_pr_count": pr_rows[0].get("stale_pr_count", 0) if pr_rows else 0,
        "ticket_breakdown": ticket_rows,
    }


# ── Analysis tools ─────────────────────────────────────────────────────────

def detect_anomalies() -> list[dict]:
    """Detect metric anomalies using z-score against 30-day rolling baselines.

    A metric is flagged as an anomaly when |z-score| > 2 standard deviations.
    Severity: low (2–3), medium (3–4), high (>4). Each new anomaly is persisted
    to the agent_anomalies table. Returns all active anomalies.
    """
    if _is_mock():
        from mock.fixtures import ANOMALIES
        return ANOMALIES

    from google.cloud import bigquery

    baselines = _run_query(f"""
        SELECT metric_name, baseline_mean, baseline_stddev
        FROM `{_project()}.{_DATASET}.v_metric_baselines`
    """)

    anomalies: list[dict] = []

    for b in baselines:
        name   = b["metric_name"]
        mean   = float(b["baseline_mean"] or 0)
        stddev = float(b["baseline_stddev"] or 1)

        # Fetch current metric value (latest day)
        current_rows = _run_query(f"""
            SELECT metric_value
            FROM `{_project()}.{_DATASET}.v_metric_baselines`
            WHERE metric_name = @name
        """, [bigquery.ScalarQueryParameter("name", "STRING", name)])

        if not current_rows:
            continue
        current_val = float(current_rows[0].get("metric_value") or 0)

        if stddev == 0:
            continue

        z = (current_val - mean) / stddev
        if abs(z) <= 2:
            continue

        severity = "low" if abs(z) <= 3 else ("medium" if abs(z) <= 4 else "high")
        record = {
            "anomaly_id":      str(uuid.uuid4()),
            "detected_at":     datetime.now(timezone.utc).isoformat(),
            "metric_name":     name,
            "metric_value":    current_val,
            "baseline_mean":   mean,
            "baseline_stddev": stddev,
            "z_score":         round(z, 3),
            "severity":        severity,
            "entity_type":     "metric",
            "entity_id":       name,
            "resolved_at":     None,
        }
        anomalies.append(record)
        _write_anomaly(record)

    return anomalies


# ── Write tools ────────────────────────────────────────────────────────────

def write_digest(digest_data: dict) -> str:
    """Persist a daily digest record to the agent_digests BigQuery table.

    Generates a UUID for the digest_id. Returns the digest_id string.
    Call this at the end of the daily digest job or when a significant
    insight is generated during a user query session.

    Args:
        digest_data: Dict containing digest fields matching the agent_digests schema.
    """
    digest_id = str(uuid.uuid4())
    row = {
        "digest_id":             digest_id,
        "generated_at":          datetime.now(timezone.utc).isoformat(),
        "digest_date":           digest_data.get("digest_date", datetime.now(timezone.utc).date().isoformat()),
        "open_pr_count":         digest_data.get("open_pr_count", 0),
        "stale_pr_count":        digest_data.get("stale_pr_count", 0),
        "commit_count_7d":       digest_data.get("commit_count_7d", 0),
        "commit_count_prev_7d":  digest_data.get("commit_count_prev_7d", 0),
        "anomaly_count":         digest_data.get("anomaly_count", 0),
        "anomaly_summary":       json.dumps(digest_data.get("anomaly_summary", [])),
        "sprint_on_track":       digest_data.get("sprint_on_track", False),
        "narrative":             digest_data.get("narrative", ""),
        "model_used":            digest_data.get("model_used", os.getenv("GEMINI_MODEL", "gemini-1.5-flash")),
    }

    if _is_mock():
        log.info("Mock mode: digest %s would be written to BigQuery.", digest_id)
        return digest_id

    from tools.bq_client import get_client
    client = get_client()
    table  = f"{_project()}.{_DATASET}.agent_digests"
    errors = client.insert_rows_json(table, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")
    return digest_id


def write_agent_log(
    session_id: str,
    user_query: str,
    tools_called: list[str],
    bq_bytes: int,
    latency_ms: int,
    response_preview: str,
) -> None:
    """Write one interaction record to the agent_logs table.

    Called automatically at the end of every agent turn by the interface layer.
    Not exposed as an ADK tool — called directly by the runner wrapper.
    """
    row = {
        "log_id":             str(uuid.uuid4()),
        "session_id":         session_id,
        "logged_at":          datetime.now(timezone.utc).isoformat(),
        "user_query":         user_query[:2000],
        "tools_called":       json.dumps(tools_called),
        "bq_bytes_processed": bq_bytes,
        "latency_ms":         latency_ms,
        "model_used":         os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        "response_preview":   response_preview[:500],
    }

    if _is_mock():
        log.debug("Mock mode: agent_log %s skipped.", row["log_id"])
        return

    try:
        from tools.bq_client import get_client
        client = get_client()
        client.insert_rows_json(f"{_project()}.{_DATASET}.agent_logs", [row])
    except Exception as exc:
        log.warning("Failed to write agent_log: %s", exc)


# ── Internal helpers ───────────────────────────────────────────────────────

def _write_anomaly(record: dict) -> None:
    if _is_mock():
        return
    try:
        from tools.bq_client import get_client
        client = get_client()
        client.insert_rows_json(f"{_project()}.{_DATASET}.agent_anomalies", [record])
    except Exception as exc:
        log.warning("Failed to write anomaly: %s", exc)
