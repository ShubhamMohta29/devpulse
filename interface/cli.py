"""Interactive CLI REPL for DevPulse.

For development and testing. Replaced by the FastAPI + frontend in production.

Usage:
    python agent/main.py           # MODE=cli (default)
    MOCK_MODE=true python agent/main.py
"""

import asyncio
import logging
import os
import time
import uuid

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_BOLD    = "\033[1m"
_YELLOW  = "\033[33m"
_CYAN    = "\033[36m"
_GREEN   = "\033[32m"
_RED     = "\033[31m"
_RESET   = "\033[0m"


def _print_banner():
    mock_tag = f" {_YELLOW}[MOCK MODE]{_RESET}" if os.getenv("MOCK_MODE", "false").lower() == "true" else ""
    print(f"\n{_BOLD}{_CYAN}DevPulse{_RESET} — Engineering Health Agent{mock_tag}")
    print(f"Model: {os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')}")
    print("Type your question and press Enter. Ctrl-C to exit.\n")


async def _run_turn(runner, session_service, session_id: str, question: str) -> str:
    from google.genai import types as genai_types

    try:
        await session_service.get_session(app_name="devpulse", user_id=session_id, session_id=session_id)
    except Exception:
        await session_service.create_session(app_name="devpulse", user_id=session_id, session_id=session_id)

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=question)],
    )

    async for event in runner.run_async(user_id=session_id, session_id=session_id, new_message=message):
        if event.is_final_response():
            if event.content and event.content.parts:
                return event.content.parts[0].text or ""
    return ""


async def run_cli(runner, session_service) -> None:
    _print_banner()
    session_id = str(uuid.uuid4())
    print(f"Session: {session_id[:8]}…\n")

    while True:
        try:
            question = input(f"{_BOLD}You:{_RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{_GREEN}Goodbye.{_RESET}")
            break

        if not question:
            continue

        print(f"{_CYAN}Thinking…{_RESET}", end="", flush=True)
        start = time.monotonic()

        try:
            answer = await _run_turn(runner, session_service, session_id, question)
        except Exception as exc:
            print(f"\r{_RED}Error: {exc}{_RESET}")
            log.exception("CLI turn failed")
            continue

        elapsed = time.monotonic() - start
        print(f"\r{' ' * 14}\r", end="")  # clear "Thinking…"
        print(f"{_BOLD}DevPulse:{_RESET} {answer}")
        print(f"{_YELLOW}({elapsed:.1f}s){_RESET}\n")
