"""PROJ-59 — Bugfix: OpenCode-Session hängt nach „Stopp" in „Aktive Sessions".

Root Cause: Nach einem geordneten Backend-Neustart (Deploy) baut ``auto_resume_drained``
für eine wartende, self-resume-fähige oneshot-Session (OpenCode/Codex) einen frischen
``GenericCliDriver`` — ``start()`` nimmt für diesen Fall bewusst den frühen Return
(kein Prozess wird gespawnt, es wird nur die ``resume_id`` gemerkt; erst der nächste
``send_input`` startet einen echten Prozess). Klickte man in genau diesem Fenster auf
„Stopp", bevor ein neuer Turn lief, traf ``GenericCliDriver.stop()`` auf ``self._proc is
None`` und kehrte sofort zurück, OHNE das ``closed``-Event zu emittieren — der Manager
erfuhr nie vom Stop, der Status blieb aktiv und die Session hing für immer in
„Aktive Sessions" (bestätigt im Live-Index: `/stop` lieferte 200 OK, Status blieb
`running`, `last_activity` blieb eingefroren).

Fix: ``stop()`` emittiert das ``closed``-Event auch dann, wenn kein Prozess läuft.
"""
from __future__ import annotations

import pytest

from app.engine.base import StreamEvent
from app.engine.generic_cli_driver import GenericCliDriver
from app.engine.registry import EngineProfile


def _profile() -> EngineProfile:
    return EngineProfile(
        key="opencode",
        label="Fake OpenCode",
        driver="generic_cli",
        bin="does-not-matter",
        argv_template=["does-not-matter"],
        resume_argv_template=["does-not-matter", "{resume_id}"],
        adapter="opencode",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )


@pytest.mark.asyncio
async def test_stop_emits_closed_when_no_process_spawned_yet():
    """Self-Resume-Leerlauf (kein Prozess) — `stop()` muss trotzdem `closed` melden."""
    drv = GenericCliDriver(_profile())
    events: list[StreamEvent] = []

    async def on_event(e: StreamEvent) -> None:
        events.append(e)

    drv._on = on_event
    drv._resume_id = "resume-token-123"
    assert drv._proc is None  # nie gespawnt — genau der Zustand nach auto_resume_drained.

    await drv.stop()

    assert any(e.type == "system" and e.subtype == "closed" for e in events), events
