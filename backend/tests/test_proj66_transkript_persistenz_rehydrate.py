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

from fastapi.testclient import TestClient

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
from app.main import create_app

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
async def test_rehydrate_laedt_transkript_auch_fuer_claude(tmp_path, monkeypatch):
    """PROJ-71 (kehrt das alte PROJ-66-Verhalten um): Claude wird beim Rehydrate JETZT
    aus der DB vorbefüllt. Früher war es ausgenommen, weil der `--resume`-Ersatzlauf die
    out.log ab Offset 0 neu las und den Verlauf selbst rekonstruierte (DB-Load hätte
    dupliziert). Seit PROJ-71 seekt der Resume-Respawn ans out.log-Ende (kein Replay),
    also ist die DB die alleinige Rebuild-Quelle — ohne Load bliebe das Transkript nach
    einem Neustart leer."""
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
        {"role": "assistant", "kind": "text", "text": "hallo", "ts": "t2"},
    ]))
    mgr = SessionManager(repo=repo)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("claude", is_claude=True))

    await mgr.rehydrate()
    await _flush(mgr)

    rt = mgr.get("old")
    assert rt is not None
    assert [e.text for e in rt.transcript] == ["hi", "hallo"]


@pytest.mark.asyncio
async def test_rehydrate_mehrfacher_neustart_keine_dopplung_claude(tmp_path, monkeypatch):
    """PROJ-71-Kern: Mehrere Backend-Neustarts einer Claude-Session dürfen das
    Transkript NICHT vervielfachen (der gemeldete 2×/3×-Fehler). Da das out.log-Replay
    seit PROJ-71 entfällt, ist jeder Rehydrate ein sauberer Load desselben DB-Blobs —
    exakt das Codex-Verhalten, jetzt auch für Claude."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "old", "status": "waiting", "owner": "dev",
        "project_path": PROJECT, "model": "claude-opus-4-8", "permission_mode": "default",
        "engine": "claude", "created_at": "2026-07-07T10:00:00+00:00",
        "last_activity": "2026-07-07T10:00:00+00:00",
    })
    await repo.save_transcript("old", json.dumps([
        {"role": "assistant", "kind": "text", "text": "Erledigt.", "ts": "t1"},
    ]))
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("claude", is_claude=True))

    for _ in range(3):
        mgr = SessionManager(repo=repo)
        await mgr.rehydrate()
        await _flush(mgr)
        rt = mgr.get("old")
        assert [e.text for e in rt.transcript] == ["Erledigt."]


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


# ===========================================================================
# 5) QA — echte Route, echter Lifespan (AC1/AC2: End-to-End statt nur Manager-intern)
# ===========================================================================


def _seed_row(engine: str, session_id: str = "peppermint") -> dict:
    return {
        "session_id": session_id, "status": "waiting", "owner": "dev",
        "project_path": PROJECT, "model": "gpt-5.5", "permission_mode": "default",
        "engine": engine, "created_at": "2026-07-07T11:26:00+00:00",
        "last_activity": "2026-07-07T11:26:00+00:00",
    }


@pytest.mark.asyncio
async def test_route_get_session_returns_full_transcript_after_restart(tmp_path, monkeypatch):
    """AC1, end-to-end: echter FastAPI-Lifespan (Startup → rehydrate()) + echte
    GET /sessions/{id}-Route — nicht nur Manager-Interna. Simuliert exakt den
    Peppermint-Vorfall: 2 abgeschlossene Turns, dann ein Neustart (neue App-Instanz
    auf demselben Repo-File)."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert(_seed_row("codex"))
    await repo.save_transcript("peppermint", json.dumps([
        {"role": "user", "kind": "text", "text": "Turn 1 Frage", "ts": "t1"},
        {"role": "assistant", "kind": "text", "text": "Turn 1 Antwort", "ts": "t2"},
        {"role": "user", "kind": "text", "text": "Turn 2 Frage", "ts": "t3"},
        {"role": "assistant", "kind": "text", "text": "Turn 2 Antwort", "ts": "t4"},
    ]))
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("codex"))

    app = create_app(session_index_repo=repo)
    with TestClient(app) as client:  # triggert den echten Lifespan (Startup → rehydrate())
        resp = client.get("/sessions/peppermint")

    assert resp.status_code == 200
    texts = [e["text"] for e in resp.json()["transcript"]]
    assert texts == ["Turn 1 Frage", "Turn 1 Antwort", "Turn 2 Frage", "Turn 2 Antwort"]


@pytest.mark.asyncio
async def test_route_get_session_returns_full_transcript_for_opencode(tmp_path, monkeypatch):
    """AC2: dasselbe gilt für OpenCode (nicht nur Codex) — Scope der Spec ist ALLE
    Oneshot-Engines, nicht Codex-spezifisch."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert(_seed_row("opencode"))
    await repo.save_transcript("peppermint", json.dumps([
        {"role": "user", "kind": "text", "text": "hi", "ts": "t1"},
        {"role": "assistant", "kind": "text", "text": "hallo", "ts": "t2"},
    ]))
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("opencode"))

    app = create_app(session_index_repo=repo)
    with TestClient(app) as client:
        resp = client.get("/sessions/peppermint")

    assert resp.status_code == 200
    texts = [e["text"] for e in resp.json()["transcript"]]
    assert texts == ["hi", "hallo"]


@pytest.mark.asyncio
async def test_route_get_session_transcript_restored_for_claude(tmp_path, monkeypatch):
    """PROJ-71: Auch eine Claude-Session liefert nach einem Neustart ihr Transkript über
    die Route zurück (aus der DB rehydriert). Vor PROJ-71 war es hier leer, weil man sich
    auf das out.log-Replay verließ — das seit PROJ-71 entfällt (Seek-to-End statt Offset 0)."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    row = _seed_row("claude")
    row["model"] = "claude-opus-4-8"
    await repo.upsert(row)
    await repo.save_transcript("peppermint", json.dumps([
        {"role": "user", "kind": "text", "text": "hi", "ts": "t1"},
    ]))
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("claude", is_claude=True))

    app = create_app(session_index_repo=repo)
    with TestClient(app) as client:
        resp = client.get("/sessions/peppermint")

    assert resp.status_code == 200
    assert [e["text"] for e in resp.json()["transcript"]] == ["hi"]


# ===========================================================================
# 6) AC3 — nur der ungeschriebene Rest eines laufenden Turns geht verloren
# ===========================================================================


@pytest.mark.asyncio
async def test_only_unpersisted_inflight_turn_is_lost(tmp_path):
    """Turn 1 abgeschlossen + persistiert. Turn 2 beginnt (User-Eingabe persistiert
    den Zwischenstand), dann crasht der Prozess, BEVOR die Assistant-Antwort auf
    Turn 2 einen weiteren Persist-Zyklus auslöst (kein `_persist`-Aufruf mehr).
    Ein „Neustart" (neuer Manager auf demselben Repo) darf NUR den unpersistierten
    Assistant-Text von Turn 2 verlieren — Turn 1 UND die Turn-2-Frage bleiben."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = SessionManager(repo=repo)
    rt = _runtime(engine="codex")

    rt.transcript.append(TranscriptEntry("user", "text", "Turn 1 Frage", "t1"))
    rt.transcript.append(TranscriptEntry("assistant", "text", "Turn 1 Antwort", "t2"))
    mgr._persist(rt)  # Turn 1 abgeschlossen → persistiert
    await _flush(mgr)

    rt.transcript.append(TranscriptEntry("user", "text", "Turn 2 Frage", "t3"))
    mgr._persist(rt)  # z. B. der send_input-Persist-Aufruf
    await _flush(mgr)

    # "Crash" — Assistant-Antwort auf Turn 2 wird NIE persistiert.
    rt.transcript.append(TranscriptEntry("assistant", "text", "Turn 2 Antwort (verloren)", "t4"))

    saved = json.loads(await repo.load_transcript("s1"))
    assert [e["text"] for e in saved] == ["Turn 1 Frage", "Turn 1 Antwort", "Turn 2 Frage"]
    assert "Turn 2 Antwort (verloren)" not in [e["text"] for e in saved]


# ===========================================================================
# 7) Red-Team — Session-IDs mit SQL-Metazeichen (parametrisierte Queries)
# ===========================================================================


@pytest.mark.asyncio
async def test_transcript_repo_handles_malicious_session_id(tmp_path):
    """Session-IDs sind i. d. R. UUIDs, aber die Spalte ist TEXT ohne Format-Zwang —
    ein Session-ID-String mit SQL-Metazeichen darf keine andere Zeile
    beeinträchtigen (Nachweis, dass parametrisierte Queries greifen, keine
    String-Konkatenation)."""
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    evil_id = "s1'; DROP TABLE session_transcript; --"
    await repo.save_transcript("s1", json.dumps([{"role": "user", "kind": "text", "text": "echt", "ts": "t1"}]))
    await repo.save_transcript(evil_id, json.dumps([{"role": "user", "kind": "text", "text": "böse", "ts": "t1"}]))

    # Beide Zeilen unabhängig lesbar — kein Crash, keine Tabelle verschwunden.
    assert json.loads(await repo.load_transcript("s1"))[0]["text"] == "echt"
    assert json.loads(await repo.load_transcript(evil_id))[0]["text"] == "böse"

    await repo.delete(evil_id)
    assert await repo.load_transcript(evil_id) is None
    assert json.loads(await repo.load_transcript("s1"))[0]["text"] == "echt"  # unberührt
