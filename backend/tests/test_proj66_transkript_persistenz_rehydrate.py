"""PROJ-66 — Session-Transkript von Oneshot-Engines übersteht Backend-Neustart.

Live-Vorfall: Codex-Session "Peppermint" verlor nach jedem Backend-Neustart ihr
komplettes Transkript, weil ``SessionRuntime.transcript`` nur im RAM existiert und
``rehydrate()`` bei jedem Neustart eine frische, leere Runtime baut.

Geprüft:
- Repo-Ebene: ``session_transcript`` speichert/liest/löscht (Roundtrip, Ersetzen,
  Lösch-Kaskade analog ``session_context``).
- ``_persist`` sichert das UI-Transkript UNCONDITIONAL (jeder Status, jede Engine) —
  anders als ``session_context`` (nur bei SETTLED-Status), weil hier kein Turn-
  Rohkontext, sondern das reine Anzeige-Transkript gesichert wird.
- ``rehydrate()`` spielt das Transkript nur für Nicht-Claude-Engines zurück; Claude
  bleibt unverändert (Regressionstest gegen PROJ-14/17/33 — kein Doppel-Replay).
- Ein tatsächlicher Absturz (ERROR) bleibt korrekt erkennbar — die Rehydrierung
  ändert nichts an der Status-Logik, nur am Transkript-Inhalt.
- Korrupter/kaputter Transkript-JSON degradiert auf ein leeres Transkript, crasht
  aber nicht (Red-Team-Robustheit, analog PROJ-56).
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.db.session_index import SqliteSessionIndexRepository
from app.engine.manager import (
    DONE,
    ERROR,
    RUNNING,
    WAITING,
    SessionManager,
    SessionRuntime,
    SessionState,
    TranscriptEntry,
)
from app.engine import manager as mgr_module
from app.engine.base import EngineDriver, EventHandler, LaunchSpec

PROJECT = "/home/dev/projects/jupiter"


async def _flush(mgr: SessionManager) -> None:
    for _ in range(6):
        pending = list(mgr._persist_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


class _Profile:
    def __init__(self, key: str, *, is_claude: bool = False) -> None:
        self.key = key
        self.is_claude = is_claude
        self.driver = "claude" if is_claude else "generic_cli"


class _DeadDriver(EngineDriver):
    """Fake-Treiber ohne Prozess — genügt für Persist-/Rehydrate-Tests."""

    @property
    def is_alive(self) -> bool:
        return False

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:  # pragma: no cover
        pass

    async def send_input(self, text: str) -> None:  # pragma: no cover
        pass

    async def pause(self) -> None:  # pragma: no cover
        pass

    async def stop(self) -> None:  # pragma: no cover
        pass


def _runtime(*, engine: str, status: str = WAITING) -> SessionRuntime:
    state = SessionState(
        session_id="s1", owner="dev", project_path=PROJECT, model="m",
        permission_mode="default", engine=engine, status=status,
    )
    return SessionRuntime(state, _DeadDriver())


# ===========================================================================
# 1) Repo-Ebene: session_transcript speichern/lesen/löschen
# ===========================================================================


@pytest.mark.asyncio
async def test_session_transcript_save_load_delete(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    assert await repo.load_transcript("s1") is None  # noch nichts

    entries = [{"role": "user", "kind": "text", "text": "hi", "ts": "t1"}]
    await repo.save_transcript("s1", json.dumps(entries))
    assert json.loads(await repo.load_transcript("s1")) == entries

    # Ersetzen (kein Duplikat, PK = session_id)
    entries2 = entries + [{"role": "assistant", "kind": "text", "text": "hallo", "ts": "t2"}]
    await repo.save_transcript("s1", json.dumps(entries2))
    assert len(json.loads(await repo.load_transcript("s1"))) == 2

    # Löschen der Session entfernt auch das Transkript
    await repo.delete("s1")
    assert await repo.load_transcript("s1") is None


# ===========================================================================
# 2) _persist — Transkript unconditional sichern (jeder Status, jede Engine)
# ===========================================================================


@pytest.mark.asyncio
async def test_persist_saves_transcript_even_mid_turn(tmp_path):
    """Anders als session_context (nur SETTLED) wird das UI-Transkript auch bei
    RUNNING gesichert — ein Neustart mitten im Turn verliert höchstens den seit dem
    letzten Append ungeschriebenen Rest, nicht den gesamten bisherigen Verlauf."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = SessionManager(repo=repo)
    rt = _runtime(engine="codex", status=RUNNING)
    rt.transcript.append(TranscriptEntry("user", "text", "hi", "t1"))

    mgr._persist(rt)
    await _flush(mgr)

    saved = json.loads(await repo.load_transcript("s1"))
    assert saved == [{"role": "user", "kind": "text", "text": "hi", "ts": "t1"}]


@pytest.mark.asyncio
async def test_persist_overwrites_full_transcript_blob(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = SessionManager(repo=repo)
    rt = _runtime(engine="codex")
    rt.transcript.append(TranscriptEntry("user", "text", "hi", "t1"))
    mgr._persist(rt)
    await _flush(mgr)

    rt.transcript.append(TranscriptEntry("assistant", "text", "hallo", "t2"))
    mgr._persist(rt)
    await _flush(mgr)

    saved = json.loads(await repo.load_transcript("s1"))
    assert [e["text"] for e in saved] == ["hi", "hallo"]


# ===========================================================================
# 3) rehydrate() — nur für Nicht-Claude-Engines zurückspielen
# ===========================================================================


@pytest.mark.asyncio
async def test_rehydrate_laedt_transkript_fuer_codex(tmp_path, monkeypatch):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "old", "status": "waiting", "owner": "dev",
        "project_path": PROJECT, "model": "gpt-5.5", "permission_mode": "default",
        "engine": "codex", "created_at": "2026-07-07T10:00:00+00:00",
        "last_activity": "2026-07-07T10:00:00+00:00",
    })
    await repo.save_transcript("old", json.dumps([
        {"role": "user", "kind": "text", "text": "hi", "ts": "t1"},
        {"role": "assistant", "kind": "text", "text": "hallo", "ts": "t2"},
    ]))
    mgr = SessionManager(repo=repo)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("codex"))

    await mgr.rehydrate()
    await _flush(mgr)

    rt = mgr.get("old")
    assert rt is not None
    assert [e.text for e in rt.transcript] == ["hi", "hallo"]


@pytest.mark.asyncio
async def test_rehydrate_laedt_transkript_nicht_fuer_claude(tmp_path, monkeypatch):
    """Regression: Claude bewahrt seinen Verlauf über den nativen --resume-Ersatzlauf.
    Ein zusätzliches Vorbefüllen hier würde zu doppelten Einträgen führen, sobald die
    Session später fortgesetzt wird und die Events erneut streamen — deshalb bewusst
    NICHT geladen, Verhalten bleibt exakt wie vor PROJ-66."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "old", "status": "waiting", "owner": "dev",
        "project_path": PROJECT, "model": "claude-opus-4-8", "permission_mode": "default",
        "engine": "claude", "created_at": "2026-07-07T10:00:00+00:00",
        "last_activity": "2026-07-07T10:00:00+00:00",
    })
    await repo.save_transcript("old", json.dumps([
        {"role": "user", "kind": "text", "text": "hi", "ts": "t1"},
    ]))
    mgr = SessionManager(repo=repo)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("claude", is_claude=True))

    await mgr.rehydrate()
    await _flush(mgr)

    rt = mgr.get("old")
    assert rt is not None
    assert rt.transcript == []


@pytest.mark.asyncio
async def test_rehydrate_echter_absturz_bleibt_error_transkript_trotzdem_geladen(tmp_path, monkeypatch):
    """Ein tatsächlicher Absturz (ERROR, kein sauberes Ende) bleibt korrekt als ERROR
    erkennbar — PROJ-66 ändert nur den Transkript-Inhalt, nicht die Status-Logik."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "old", "status": "error", "owner": "dev",
        "project_path": PROJECT, "model": "gpt-5.5", "permission_mode": "default",
        "engine": "codex", "created_at": "2026-07-07T10:00:00+00:00",
        "last_activity": "2026-07-07T10:00:00+00:00", "error": "API-Fehler 500",
    })
    await repo.save_transcript("old", json.dumps([
        {"role": "user", "kind": "text", "text": "hi", "ts": "t1"},
    ]))
    mgr = SessionManager(repo=repo)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("codex"))

    await mgr.rehydrate()
    await _flush(mgr)

    rt = mgr.get("old")
    assert rt.state.status == ERROR
    assert [e.text for e in rt.transcript] == ["hi"]


@pytest.mark.asyncio
async def test_rehydrate_mehrfacher_neustart_keine_dopplung(tmp_path, monkeypatch):
    """Mehrfache Neustarts hintereinander (wie im Peppermint-Vorfall) dürfen das
    Transkript nicht duplizieren — jeder Rehydrate-Lauf liest denselben Blob neu."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "old", "status": "waiting", "owner": "dev",
        "project_path": PROJECT, "model": "gpt-5.5", "permission_mode": "default",
        "engine": "codex", "created_at": "2026-07-07T10:00:00+00:00",
        "last_activity": "2026-07-07T10:00:00+00:00",
    })
    await repo.save_transcript("old", json.dumps([
        {"role": "user", "kind": "text", "text": "hi", "ts": "t1"},
    ]))
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("codex"))

    for _ in range(3):
        mgr = SessionManager(repo=repo)
        await mgr.rehydrate()
        await _flush(mgr)
        rt = mgr.get("old")
        assert [e.text for e in rt.transcript] == ["hi"]


# ===========================================================================
# 4) Red-Team — korrupter Transkript-JSON degradiert, crasht nicht
# ===========================================================================


@pytest.mark.asyncio
async def test_rehydrate_corrupt_transcript_degrades_not_crashes(tmp_path, monkeypatch):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "old", "status": "waiting", "owner": "dev",
        "project_path": PROJECT, "model": "gpt-5.5", "permission_mode": "default",
        "engine": "codex", "created_at": "2026-07-07T10:00:00+00:00",
        "last_activity": "2026-07-07T10:00:00+00:00",
    })
    await repo.save_transcript("old", "{das ist kein gültiges json[[")
    mgr = SessionManager(repo=repo)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("codex"))

    await mgr.rehydrate()  # darf nicht werfen
    await _flush(mgr)

    rt = mgr.get("old")
    assert rt is not None
    assert rt.transcript == []
