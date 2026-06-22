"""Live-Smoke-Test des echten ClaudeCodeDriver (verbraucht etwas Max-Quota).

Startet eine echte Claude-Session über den Manager, sendet einen Mini-Prompt,
wartet auf den ersten ``result`` und gibt Status + Transkript aus.

    conda run -n Dashboard --no-capture-output python backend/scripts/smoke_driver.py

NICHT Teil der pytest-Suite (würde Subscription-Quota verbrauchen).
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine.manager import SessionManager  # noqa: E402

PROJECT = "/home/dev/projects/jupiter"


async def main() -> int:
    mgr = SessionManager()  # echter ClaudeCodeDriver
    rt = await mgr.create(
        project_path=PROJECT,
        initial_prompt="Antworte nur mit dem Wort: OK",
        model="haiku",
    )
    sid = rt.state.session_id
    print(f"Session {sid} gestartet, Status={rt.state.status}")

    # Bis zu 60s auf Turn-Ende (waiting/done/error) warten.
    for _ in range(120):
        if rt.state.status in ("waiting", "done", "error"):
            break
        await asyncio.sleep(0.5)

    print(f"Status: {rt.state.status}")
    print(f"Modell: {rt.state.model}")
    print(f"Kontext-Füllstand: {rt.state.context_fill_pct} %  |  Tokens: {rt.state.tokens_used}")
    print(f"Kosten: ${rt.state.total_cost_usd}")
    if rt.state.error:
        print(f"FEHLER: {rt.state.error}")
    print("--- Transkript ---")
    print(mgr.transcript_text(sid))

    await mgr.stop(sid)
    return 0 if rt.state.status in ("waiting", "done") and not rt.state.error else 1


if __name__ == "__main__":
    _code = asyncio.run(main())
    print(f"MAIN RETURNED: {_code}")
    sys.exit(_code)
