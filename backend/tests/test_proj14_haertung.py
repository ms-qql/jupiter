"""PROJ-14 — Härtung des Engine-Treibers: Limit paralleler Sessions + Persistenz.

Testet beide Bausteine gegen die Acceptance Criteria:
- konfigurierbares Limit, klare Ablehnung (429), nur aktive Zustände zählen;
- SQLite-Live-Index (Spiegel), Rehydrierung nach Restart (verwaist), Best-effort.
"""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from app.config import clamp_session_limit, settings
from app.db.session_index import SqliteSessionIndexRepository
from app.engine.manager import (
    ACTIVE_STATES,
    ERROR,
    SessionLimitError,
    SessionManager,
)
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _mgr(repo=None) -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver(), repo=repo)


async def _drain(mgr: SessionManager) -> None:
    """Wartet die best-effort-Persist-Tasks ab (laufen via to_thread im Executor)."""
    for _ in range(5):
        pending = list(mgr._persist_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


# --- Limit ----------------------------------------------------------------

def test_clamp_session_limit_klemmt_auf_minimum():
    assert clamp_session_limit(0) == 1
    assert clamp_session_limit(-5) == 1
    assert clamp_session_limit(7) == 7


@pytest.mark.asyncio
async def test_limit_lehnt_ueber_grenze_ab(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 2)
    mgr = _mgr()
    await mgr.create(project_path=PROJECT, initial_prompt="a", model="haiku")
    await mgr.create(project_path=PROJECT, initial_prompt="b", model="haiku")
    assert mgr.active_count() == 2
    with pytest.raises(SessionLimitError):
        await mgr.create(project_path=PROJECT, initial_prompt="c", model="haiku")


@pytest.mark.asyncio
async def test_nur_aktive_zustaende_zaehlen(monkeypatch):
    """done/error blockieren keinen Slot — nach Stop ist wieder Platz."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 1)
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="a", model="haiku")
    with pytest.raises(SessionLimitError):
        await mgr.create(project_path=PROJECT, initial_prompt="b", model="haiku")
    await mgr.stop(rt.state.session_id)  # → done
    assert mgr.active_count() == 0
    # Slot frei → nächste Erstellung klappt.
    await mgr.create(project_path=PROJECT, initial_prompt="c", model="haiku")


@pytest.mark.asyncio
async def test_limit_race_atomar(monkeypatch):
    """Zwei gleichzeitige Creates am Limit → höchstens das Limit wird zugelassen."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 1)
    mgr = _mgr()
    results = await asyncio.gather(
        mgr.create(project_path=PROJECT, initial_prompt="a", model="haiku"),
        mgr.create(project_path=PROJECT, initial_prompt="b", model="haiku"),
        return_exceptions=True,
    )
    ok = [r for r in results if not isinstance(r, Exception)]
    rejected = [r for r in results if isinstance(r, SessionLimitError)]
    assert len(ok) == 1 and len(rejected) == 1
    assert mgr.active_count() == 1


def test_api_limit_liefert_429(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 1)
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        body = {"project_path": PROJECT, "initial_prompt": "x", "model": "haiku"}
        assert client.post("/sessions", json=body).status_code == 201
        r = client.post("/sessions", json=body)
        assert r.status_code == 429
        assert "Limit" in r.json()["detail"]
        # Limit-Status-Endpoint.
        meta = client.get("/sessions/limits").json()
        assert meta == {"max_parallel_sessions": 1, "active": 1}


# --- Persistenz (SQLite-Repository) ---------------------------------------

@pytest.mark.asyncio
async def test_sqlite_repo_roundtrip(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "sub" / "idx.db"))
    await repo.init()  # legt Datei + Verzeichnis an
    await repo.upsert({"session_id": "s1", "status": "running", "owner": "dev"})
    await repo.upsert({"session_id": "s1", "status": "done"})  # Update via PK
    await repo.upsert({"session_id": "s2", "status": "waiting"})
    rows = await repo.list_all()
    by_id = {r["session_id"]: r for r in rows}
    assert by_id["s1"]["status"] == "done"  # upsert hat aktualisiert
    assert by_id["s2"]["status"] == "waiting"
    await repo.close()


@pytest.mark.asyncio
async def test_create_spiegelt_in_live_index(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = _mgr(repo=repo)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    await _drain(mgr)
    rows = await repo.list_all()
    assert len(rows) == 1
    assert rows[0]["session_id"] == rt.state.session_id
    assert rows[0]["project_path"] == PROJECT


@pytest.mark.asyncio
async def test_db_ausfall_ist_best_effort(tmp_path):
    """upsert wirft → create/_safe_upsert dürfen NICHT scheitern (In-Memory führt)."""

    class Boom(SqliteSessionIndexRepository):
        async def upsert(self, row):  # type: ignore[override]
            raise RuntimeError("DB weg")

    mgr = _mgr(repo=Boom(str(tmp_path / "idx.db")))
    await mgr._repo.init()
    # create scheduled best-effort-Persist → der Fehler darf die Session nicht killen.
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    await _drain(mgr)
    assert rt.state.session_id in {r.state.session_id for r in mgr.list()}
    # _safe_upsert reicht die Exception nicht nach oben durch.
    await mgr._safe_upsert({"session_id": "x", "status": "running"})


# --- Rehydrierung nach Restart --------------------------------------------

@pytest.mark.asyncio
async def test_rehydrate_markiert_aktive_als_verwaist(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    # Simuliere eine vor dem Restart "running" persistierte Session mit toter PID.
    await repo.upsert({
        "session_id": "old", "status": "running", "owner": "dev",
        "project_path": PROJECT, "model": "haiku", "permission_mode": "default",
        "pid": 2_147_483_000,  # praktisch garantiert nicht existent
        "created_at": "2026-06-23T10:00:00+00:00",
        "last_activity": "2026-06-23T10:00:00+00:00",
    })
    mgr = _mgr(repo=repo)
    await mgr.rehydrate()
    rt = mgr.get("old")
    assert rt is not None
    assert rt.state.status == ERROR  # verwaist
    assert "Verwaist" in (rt.state.error or "")
    assert mgr.active_count() == 0  # zählt nicht mehr aktiv
    await _drain(mgr)
    # Korrigierter Status wurde zurückgespiegelt.
    rows = {r["session_id"]: r for r in await repo.list_all()}
    assert rows["old"]["status"] == ERROR


@pytest.mark.asyncio
async def test_rehydrate_in_memory_gewinnt(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = _mgr(repo=repo)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    await _drain(mgr)
    sid = rt.state.session_id
    status_before = rt.state.status
    await mgr.rehydrate()  # darf die lebende In-Memory-Session nicht überschreiben
    assert mgr.get(sid) is rt
    assert rt.state.status == status_before


def test_pid_alive_helper():
    assert SessionManager._pid_alive(os.getpid()) is True
    assert SessionManager._pid_alive(None) is False
    assert SessionManager._pid_alive(2_147_483_000) is False


def test_active_states_konstante():
    assert "done" not in ACTIVE_STATES and "error" not in ACTIVE_STATES
    assert {"starting", "running", "waiting", "awaiting_approval"} == set(ACTIVE_STATES)
