"""Slack notification utility.

Posts a plain-text or markdown message to a Slack incoming webhook.
If SLACK_WEBHOOK_URL is not set, this is a silent no-op so the rest
of the pipeline continues without error.
"""

import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


def post_to_slack(message: str, username: str = "DevPulse") -> None:
    """Post a message to the configured Slack webhook.

    No-op if SLACK_WEBHOOK_URL is empty. Logs a warning on HTTP failure
    but does not raise — digest delivery must not fail silently-hard.

    Args:
        message: The message text (plain text or Slack mrkdwn).
        username: Display name shown in Slack. Default: DevPulse.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        log.debug("SLACK_WEBHOOK_URL not set — skipping Slack notification.")
        return

    payload = {
        "username": username,
        "icon_emoji": ":chart_with_upwards_trend:",
        "text": message,
    }

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Slack notification sent successfully.")
    except httpx.HTTPStatusError as exc:
        log.warning("Slack webhook returned %s: %s", exc.response.status_code, exc.response.text)
    except Exception as exc:
        log.warning("Slack notification failed: %s", exc)
