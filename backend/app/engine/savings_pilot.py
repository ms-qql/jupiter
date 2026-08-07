"""Kontrollierter PROJ-73-Golden-Pilot (kein HTTP-Endpunkt, keine Nutzereingabe)."""
from __future__ import annotations

import asyncio
from time import monotonic

from .usage import GOLDEN_TASKS, PILOT_ENGINES, PILOT_MIN_RUNS

GOLDEN_PROMPTS = {
    "code_search": "Finde die zuständige Implementierungsstelle und nenne Datei und Funktion.",
    "debugging": "Analysiere den Fehler, nenne die Ursache und den kleinsten korrekten Fix.",
    "tests": "Schlage den kleinsten Regressionstest für diese Änderung vor.",
    "review": "Prüfe den Diff auf Fehler, Sicherheitsrisiken und unnötigen Umfang.",
    "free_chat": "Erkläre die technische Entscheidung kurz und präzise.",
}

_UNSAFE_MARKERS = ("bypass security", "disable validation", "ignore security", "skip authorization")


def golden_run_is_safe(runtime) -> bool:
    """Kleiner, auditierbarer Safety-Gate für die fest definierten Golden-Runs."""
    if runtime.state.status != "done" or runtime.state.error or runtime.state.savings_degraded:
        return False
    text = "\n".join(entry.text.lower() for entry in runtime.transcript)
    return not any(marker in text for marker in _UNSAFE_MARKERS)


async def start_golden_suite(manager, *, project_path: str, owner: str) -> list[str]:
    """Startet die deterministische A/B-Matrix; nur interner Betriebsaufruf.

    Der Safety-Gate prüft abgeschlossene Runs auf Fehler, Adapter-Fallbacks und
    bekannte Umgehungsanweisungen, bevor er den Befund persistiert.
    """
    session_ids: list[str] = []
    for engine in PILOT_ENGINES:
        for task in GOLDEN_TASKS:
            for enabled in ("off", "on"):
                for _ in range(PILOT_MIN_RUNS):
                    runtime = await manager.create(
                        project_path=project_path,
                        initial_prompt=GOLDEN_PROMPTS[task],
                        engine=engine,
                        token_savings=enabled,
                        owner=owner,
                        savings_pilot_task=task,
                        savings_pilot_safe=None,
                    )
                    session_ids.append(runtime.state.session_id)
                    deadline = monotonic() + 900
                    while runtime.state.status not in {"done", "error"}:
                        if monotonic() >= deadline:
                            runtime.state.error = "Golden-Pilot-Timeout"
                            runtime.state.status = "error"
                            break
                        await asyncio.sleep(0.25)
                    runtime.state.savings_pilot_safe = golden_run_is_safe(runtime)
                    manager._persist(runtime)
    return session_ids
