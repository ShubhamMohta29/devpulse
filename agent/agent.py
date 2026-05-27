"""ADK agent factory for DevPulse.

Creates and returns a configured Google ADK Agent with all ten tools
registered. Call create_agent() once at startup; the returned agent
instance is thread-safe and reusable across requests.

Also exports create_runner() which wraps the agent in an ADK Runner
backed by an in-memory session store.
"""

import logging
import os

from dotenv import load_dotenv

from agent.system_prompt import SYSTEM_PROMPT
from tools.bq_tools import (
    detect_anomalies,
    generate_trend_report,
    query_commit_velocity,
    query_open_prs,
    query_sprint_health,
    query_stale_tickets,
    write_digest,
)
from tools.fivetran_tools import (
    check_connector_status,
    list_connectors,
    trigger_sync,
)

load_dotenv()

log = logging.getLogger(__name__)

_TOOLS = [
    # Fivetran / connector tools
    check_connector_status,
    list_connectors,
    trigger_sync,
    # BigQuery read tools
    query_open_prs,
    query_commit_velocity,
    query_stale_tickets,
    query_sprint_health,
    generate_trend_report,
    # BigQuery analysis + write tools
    detect_anomalies,
    write_digest,
]


def create_agent():
    """Instantiate and return the DevPulse ADK agent.

    The agent model defaults to GEMINI_MODEL env var (default: gemini-1.5-flash).
    All ten tools defined in the TRD are registered.
    """
    from google.adk.agents import Agent

    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    log.info("Creating DevPulse agent with model=%s, tools=%d", model, len(_TOOLS))

    agent = Agent(
        name="devpulse_agent",
        model=model,
        description=(
            "Engineering Health Intelligence Agent. Analyses GitHub and Jira data "
            "synced via Fivetran to surface PR bottlenecks, commit velocity anomalies, "
            "sprint health, and stale tickets."
        ),
        instruction=SYSTEM_PROMPT,
        tools=_TOOLS,
    )
    return agent


def create_runner(agent=None):
    """Wrap an agent in an ADK Runner with in-memory session management.

    The runner handles multi-turn conversation history (up to 10 turns kept
    by the InMemorySessionService). Each unique session_id gets independent
    history so multiple users can converse concurrently.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    if agent is None:
        agent = create_agent()

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="devpulse",
        session_service=session_service,
    )
    return runner, session_service
