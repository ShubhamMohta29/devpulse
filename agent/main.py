"""DevPulse entry point.

Reads MODE env var:
  - "api"  (default) → starts the FastAPI server via uvicorn
  - "cli"             → starts the interactive terminal REPL

Usage:
    python agent/main.py                       # FastAPI on port 8000
    MODE=cli python agent/main.py              # interactive CLI
    MOCK_MODE=true MODE=cli python agent/main.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Make project root importable when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


def _start_api():
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    log.info("Starting DevPulse API on %s:%d", host, port)
    uvicorn.run("interface.api:app", host=host, port=port, reload=False)


def _start_cli():
    from agent.agent import create_runner
    runner, session_service = create_runner()

    from interface.cli import run_cli
    asyncio.run(run_cli(runner, session_service))


if __name__ == "__main__":
    mode = os.getenv("MODE", "api").lower()
    if mode == "cli":
        _start_cli()
    else:
        _start_api()
