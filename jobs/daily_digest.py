"""Daily digest orchestrator.

Runs the full 9-step digest flow from APP_FLOW.md section 3.2:
  list_connectors → detect_anomalies → query_open_prs →
  query_commit_velocity → query_sprint_health →
  Gemini synthesis → write_digest → optional Slack POST

Usage:
    python jobs/daily_digest.py          # uses credentials from .env
    MOCK_MODE=true python jobs/daily_digest.py
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a script from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from tools.bq_tools import (
    detect_anomalies,
    query_commit_velocity,
    query_open_prs,
    query_sprint_health,
    write_digest,
)
from tools.fivetran_tools import list_connectors

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def _synthesise_narrative(context: dict) -> str:
    """Call Gemini directly to produce the digest narrative paragraph."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))
        model = genai.GenerativeModel(_GEMINI_MODEL)

        prompt = f"""
You are DevPulse, an engineering health agent. Write a concise daily digest
(3-5 bullet points, max 150 words) based on the following metrics. Be direct.
Flag any anomalies with severity. Do not mention individual developer names.

Data:
{json.dumps(context, indent=2, default=str)}

Format: Markdown bullet list. Start bullets with •
"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        log.warning("Gemini synthesis failed, using template fallback: %s", exc)
        return _template_narrative(context)


def _template_narrative(ctx: dict) -> str:
    open_prs   = ctx.get("open_pr_count", 0)
    stale_prs  = ctx.get("stale_pr_count", 0)
    commits    = ctx.get("commit_count_7d", 0)
    anomalies  = ctx.get("anomaly_count", 0)
    on_track   = ctx.get("sprint_on_track", False)

    lines = [
        f"• {open_prs} open PRs ({stale_prs} stale >3 days).",
        f"• {commits} commits in the past 7 days.",
        f"• Sprint is {'on track ✓' if on_track else 'at risk ⚠️'}.",
    ]
    if anomalies:
        lines.append(f"• {anomalies} anomaly/anomalies detected — review required.")
    return "\n".join(lines)


def run_digest() -> str:
    """Execute the full daily digest and return the digest_id."""
    log.info("── DevPulse Daily Digest ──────────────────────")
    today = datetime.now(timezone.utc).date().isoformat()

    # Step 1: Confirm all connectors are active
    log.info("Step 1: Listing connectors …")
    connectors = list_connectors()
    stale_connectors = [c for c in connectors if c.get("is_stale")]
    if stale_connectors:
        log.warning("Stale connectors: %s", [c.get("name") for c in stale_connectors])

    # Step 2: Detect anomalies
    log.info("Step 2: Detecting anomalies …")
    anomalies = detect_anomalies()
    log.info("  Found %d anomaly/anomalies.", len(anomalies))

    # Step 3: Open PRs older than 3 days
    log.info("Step 3: Querying open PRs …")
    open_prs  = query_open_prs(min_age_days=0)
    stale_prs = [pr for pr in open_prs if pr.get("age_days", 0) >= 3]
    log.info("  %d open PRs total, %d stale.", len(open_prs), len(stale_prs))

    # Step 4: Commit velocity (last 7 days vs previous 7 days)
    log.info("Step 4: Querying commit velocity …")
    velocity_7d   = query_commit_velocity(days=7)
    velocity_14d  = query_commit_velocity(days=14)
    commits_7d    = sum(r.get("commit_count", 0) for r in velocity_7d)
    commits_14d   = sum(r.get("commit_count", 0) for r in velocity_14d)
    commits_prev  = commits_14d - commits_7d
    log.info("  Commits this week: %d, prior week: %d", commits_7d, commits_prev)

    # Step 5: Sprint health
    log.info("Step 5: Querying sprint health …")
    sprint = query_sprint_health()
    on_track = sprint.get("is_on_track", False)
    log.info("  Sprint on-track: %s", on_track)

    # Step 6: Build context for Gemini synthesis
    context = {
        "digest_date":            today,
        "open_pr_count":          len(open_prs),
        "stale_pr_count":         len(stale_prs),
        "commit_count_7d":        commits_7d,
        "commit_count_prev_7d":   commits_prev,
        "anomaly_count":          len(anomalies),
        "anomaly_summary":        anomalies[:5],  # top 5 for context
        "sprint_on_track":        on_track,
        "sprint_pct_complete":    sprint.get("pct_complete", 0),
        "sprint_days_remaining":  sprint.get("days_remaining", 0),
        "stale_connector_names":  [c.get("name") for c in stale_connectors],
    }

    # Step 7: Gemini synthesis
    log.info("Step 6: Synthesising narrative with %s …", _GEMINI_MODEL)
    narrative = _synthesise_narrative(context)
    log.info("Narrative:\n%s", narrative)

    # Step 8: Persist digest
    log.info("Step 7: Writing digest to BigQuery …")
    digest_data = {**context, "narrative": narrative, "model_used": _GEMINI_MODEL}
    digest_id = write_digest(digest_data)
    log.info("  Digest ID: %s", digest_id)

    # Step 9: Optional Slack notification
    from jobs.slack_notifier import post_to_slack
    slack_msg = f"*DevPulse Daily Digest — {today}*\n\n{narrative}"
    post_to_slack(slack_msg)

    log.info("── Digest complete. ID: %s ─────────────────────", digest_id)
    return digest_id


if __name__ == "__main__":
    run_digest()
