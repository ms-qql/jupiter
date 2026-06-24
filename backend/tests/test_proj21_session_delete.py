"""PROJ-21 — Session-Löschen / Cockpit-Aufräumen.

Deckt die Acceptance Criteria ab: Repository-`delete` (parametrisiert, idempotent),
`SessionManager.delete`/`cleanup_terminal` (terminal-only, 409 bei aktiv, Orphan-Kill
per SIGTERM, best-effort), und den API-Vertrag (204/404/409 + `/cleanup`).
"""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.session_index import (
    NullSessionIndexRepository,
    SqliteSessionIndexRepository,
)
from app.engine import manager as manager_mod
from app.engine.manager import (
    DONE,
    ERROR,
    SessionActiveError,
    SessionManager,
)
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _mgr(repo=None) -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver(), repo=repo)


async def _drain(mgr: SessionManager) -> None:
    for _ in range(5):
        pending = list(mgr._persist_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


# --- Repository ------------------------------------------------------------

@pytest.mark.asyncio
async def test_null_repo_delete_ist_noop():
    repo = NullSessionIndexRepository()
    await repo.delete("egal")  # darf nicht werfen
    assert await repo.list_all() == []


@pytest.mark.asyncio
async def test_repo_delete_entfernt_zeile_und_ist_idempotent(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert({"session_id": "s1", "status": "done"})
    await repo.upsert({"session_id": "s2", "status": "error"})
    await repo.delete("s1")
    ids = {r["session_id"] for r in await repo.list_all()}
    assert ids == {"s2"}
    # Idempotent: unbekannte ID wirft nicht.
    await repo.delete("does-not-exist")
    await repo.delete("s1")
    await repo.close()


# --- Manager: delete -------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_unbekannt_wirft_keyerror():
    mgr = _mgr()
    with pytest.raises(KeyError):
        await mgr.delete("nope")


@pytest.mark.asyncio
async def test_delete_aktive_session_abgelehnt(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    # Frisch erstellt → waiting/running = aktiv → nicht löschbar.
    with pytest.raises(SessionActiveError):
        await mgr.delete(rt.state.session_id)
    assert mgr.get(rt.state.session_id) is rt  # bleibt in der Registry


@pytest.mark.asyncio
async def test_delete_terminale_session_entfernt_registry_und_index(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = _mgr(repo=repo)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    sid = rt.state.session_id
    await mgr.stop(sid)  # → done (terminal)
    await _drain(mgr)
    assert rt.state.status == DONE
    await mgr.delete(sid)
    assert mgr.get(sid) is None
    assert await repo.list_all() == []


@pytest.mark.asyncio
async def test_delete_ueberlebt_keinen_restart(tmp_path, monkeypatch):
    """AC: nach delete taucht die Session auch nach Rehydrierung nicht mehr auf."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = _mgr(repo=repo)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    sid = rt.state.session_id
    await mgr.stop(sid)
    await _drain(mgr)
    await mgr.delete(sid)
    # Frischer Manager auf demselben Index = "Restart".
    mgr2 = _mgr(repo=repo)
    await mgr2.rehydrate()
    assert mgr2.get(sid) is None


@pytest.mark.asyncio
async def test_delete_best_effort_bei_db_fehler(tmp_path, monkeypatch):
    """repo.delete wirft → In-Memory wird trotzdem entfernt (degradiert zu Warnung)."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)

    class Boom(SqliteSessionIndexRepository):
        async def delete(self, session_id):  # type: ignore[override]
            raise RuntimeError("DB weg")

    mgr = _mgr(repo=Boom(str(tmp_path / "idx.db")))
    await mgr._repo.init()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    await mgr.stop(sid)
    await _drain(mgr)
    await mgr.delete(sid)  # darf NICHT werfen
    assert mgr.get(sid) is None


@pytest.mark.asyncio
async def test_delete_persistenz_aus_nur_in_memory(monkeypatch):
    """Edge: NullSessionIndexRepository (Persistenz aus) → Löschen wirkt nur
    In-Memory, kein Fehler."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    mgr = _mgr()  # Default = NullSessionIndexRepository
    assert isinstance(mgr._repo, NullSessionIndexRepository)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    await mgr.stop(sid)
    await mgr.delete(sid)  # darf nicht werfen
    assert mgr.get(sid) is None


# --- Manager: Orphan-Kill (SIGTERM) ---------------------------------------

@pytest.mark.asyncio
async def test_delete_killt_verwaisten_lebenden_prozess(tmp_path):
    """Verwaiste Session mit lebender PID → SIGTERM beendet den Prozess best-effort."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
        await repo.init()
        await repo.upsert({
            "session_id": "orphan", "status": "running", "owner": "dev",
            "project_path": PROJECT, "model": "haiku", "permission_mode": "default",
            "pid": proc.pid,
            "created_at": "2026-06-24T10:00:00+00:00",
            "last_activity": "2026-06-24T10:00:00+00:00",
        })
        mgr = _mgr(repo=repo)
        await mgr.rehydrate()
        rt = mgr.get("orphan")
        assert rt is not None and rt.state.status == ERROR  # verwaist, PID lebt noch
        await mgr.delete("orphan")
        assert mgr.get("orphan") is None
        # SIGTERM sollte den Schlaf-Prozess zeitnah beenden.
        for _ in range(50):
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        assert proc.poll() is not None  # Prozess wurde beendet
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


@pytest.mark.asyncio
async def test_delete_kill_fehler_blockiert_nicht(tmp_path, monkeypatch):
    """Edge: schlägt der SIGTERM fehl (Permission/Race), wird die Session trotzdem
    aus dem Index gelöscht (best-effort)."""
    real_kill = os.kill

    def flaky_kill(pid, sig):
        if sig == signal.SIGTERM:
            raise PermissionError("darf nicht killen")
        return real_kill(pid, sig)  # Lebendigkeits-Check (Signal 0) normal lassen

    monkeypatch.setattr(manager_mod.os, "kill", flaky_kill)

    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "orphan", "status": "running", "owner": "dev",
        "project_path": PROJECT, "model": "haiku", "permission_mode": "default",
        "pid": os.getpid(),  # lebende PID (dieser Prozess) — SIGTERM wird gemockt
        "created_at": "2026-06-24T10:00:00+00:00",
        "last_activity": "2026-06-24T10:00:00+00:00",
    })
    mgr = _mgr(repo=repo)
    await mgr.rehydrate()
    await mgr.delete("orphan")  # SIGTERM wirft → trotzdem gelöscht
    assert mgr.get("orphan") is None
    assert await repo.list_all() == []


# --- Manager: cleanup_terminal --------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_terminal_loescht_nur_terminale(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = _mgr(repo=repo)
    a = await mgr.create(project_path=PROJECT, initial_prompt="a", model="haiku")
    b = await mgr.create(project_path=PROJECT, initial_prompt="b", model="haiku")
    c = await mgr.create(project_path=PROJECT, initial_prompt="c", model="haiku")
    await mgr.stop(a.state.session_id)  # done
    await mgr.stop(b.state.session_id)  # done
    await _drain(mgr)
    # c bleibt aktiv (waiting/running).
    deleted = await mgr.cleanup_terminal()
    assert deleted == 2
    assert mgr.get(a.state.session_id) is None
    assert mgr.get(b.state.session_id) is None
    assert mgr.get(c.state.session_id) is c  # aktive Session übersprungen
    ids = {r["session_id"] for r in await repo.list_all()}
    assert ids == {c.state.session_id}


@pytest.mark.asyncio
async def test_cleanup_terminal_leer_gibt_null(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    mgr = _mgr()
    await mgr.create(project_path=PROJECT, initial_prompt="a", model="haiku")
    assert await mgr.cleanup_terminal() == 0  # nur eine aktive Session


# --- API -------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    app = create_app(driver_factory=lambda: FakeDriver())
    return TestClient(app)


def _create(client: TestClient) -> str:
    resp = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "Hallo", "model": "haiku"},
    )
    assert resp.status_code == 201
    return resp.json()["session_id"]


def test_api_delete_unbekannt_404(client: TestClient):
    r = client.delete("/sessions/gibt-es-nicht")
    assert r.status_code == 404
    assert r.json()["detail"] == "Session nicht gefunden."


def test_api_delete_aktive_409(client: TestClient):
    sid = _create(client)  # aktiv
    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 409
    assert "zuerst stoppen" in r.json()["detail"]


def test_api_delete_terminal_204_und_weg(client: TestClient):
    sid = _create(client)
    assert client.post(f"/sessions/{sid}/stop").status_code == 200  # → done
    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 204
    ids = {s["session_id"] for s in client.get("/sessions").json()}
    assert sid not in ids


def test_api_cleanup_loescht_terminale(client: TestClient):
    keep = _create(client)  # bleibt aktiv
    gone = _create(client)
    assert client.post(f"/sessions/{gone}/stop").status_code == 200  # → done
    r = client.post("/sessions/cleanup")
    assert r.status_code == 200
    assert r.json() == {"deleted": 1}
    ids = {s["session_id"] for s in client.get("/sessions").json()}
    assert keep in ids and gone not in ids
