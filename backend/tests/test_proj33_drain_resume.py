"""PROJ-33 — Graceful Drain + Auto-Resume + Selbst-Restart-Gate.

Deterministisch über FakeDriver + echtes SQLite-Repo (tmp). Geprüft:
- Selbst-Restart-Erkennung (`_is_self_restart`) + das bypass-feste Gate in request_decision;
- `drain()` markiert aktive Sessions (drained_at) + persistiert synchron;
- `rehydrate()` unterscheidet gedraint (→ Auto-Resume-Kandidat) von Crash-Orphan;
- `auto_resume_drained()` setzt NUR gedrainte Sessions fort (kein Sturm bei Crash);
- globaler Schalter `auto_resume_on_restart`.
"""
from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.db.session_index import SqliteSessionIndexRepository
from app.engine.manager import (
    ERROR,
    RUNNING,
    SessionManager,
    _is_self_restart,
)

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _mgr(repo=None) -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver(), repo=repo)


async def _flush(mgr: SessionManager) -> None:
    """Best-effort-Persist-Tasks (create_task via to_thread) abwarten."""
    for _ in range(5):
        pending = list(mgr._persist_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


# --- Selbst-Restart-Erkennung ----------------------------------------------


def test_is_self_restart_matches_backend_and_deploy_and_reboot():
    assert _is_self_restart("Bash", {"command": "sudo systemctl restart jupiter-backend"}) is True
    assert _is_self_restart("Bash", {"command": "bash /home/dev/jupiter-deploy/deploy.sh main"}) is True
    assert _is_self_restart("Bash", {"command": "sudo reboot"}) is True


def test_is_self_restart_ignores_harmless_and_nonshell():
    assert _is_self_restart("Bash", {"command": "ls -la && git status"}) is False
    # Frontend-only Restart killt KEINE Sessions → nicht gegated.
    assert _is_self_restart("Bash", {"command": "systemctl restart jupiter-frontend"}) is False
    # Kein Shell-Tool → kann den Host nicht neustarten.
    assert _is_self_restart("Read", {"command": "systemctl restart jupiter-backend"}) is False
    assert _is_self_restart("Bash", {}) is False


@pytest.mark.asyncio
async def test_self_restart_gate_fires_even_in_bypass():
    """Ein Backend-Restart-Kommando öffnet eine self_restart-Card — auch im Bypass."""
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="hi", permission_mode="bypassPermissions"
    )
    task = asyncio.create_task(
        rt.request_decision("dec-r", "Bash", {"command": "sudo systemctl restart jupiter-backend"})
    )
    for _ in range(20):  # auf das Öffnen der Card warten
        if rt.pending:
            break
        await asyncio.sleep(0.01)
    cards = [c for c in rt.pending.values() if c.card_type == "self_restart"]
    assert len(cards) == 1
    # Ablehnen → der Tool-Aufruf wird NICHT ausgeführt.
    rt.resolve_decision("dec-r", approve=False, comment="Nicht den eigenen Host neustarten")
    outcome = await task
    assert outcome.behavior == "deny"


# --- drain() ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_drain_marks_active_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = _mgr(repo=repo)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    await _flush(mgr)

    await mgr.drain()  # awaitet die Persistenz synchron

    assert rt.state.drained_at is not None
    assert rt.driver._paused is True  # pausiert
    rows = {r["session_id"]: r for r in await repo.list_all()}
    assert rows[rt.state.session_id]["drained_at"] is not None


# --- rehydrate: gedraint vs. Crash-Orphan ----------------------------------


async def _seed_row(repo, *, sid, drained_at):
    await repo.upsert({
        "session_id": sid, "status": "running", "owner": "dev",
        "project_path": PROJECT, "model": "haiku", "permission_mode": "default",
        "pid": 2_147_483_000,  # tote PID
        "created_at": "2026-06-24T10:00:00+00:00",
        "last_activity": "2026-06-24T10:00:00+00:00",
        "drained_at": drained_at,
    })


@pytest.mark.asyncio
async def test_rehydrate_drained_is_resume_candidate(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed_row(repo, sid="drained", drained_at="2026-06-24T10:05:00+00:00")
    mgr = _mgr(repo=repo)
    await mgr.rehydrate()
    rt = mgr.get("drained")
    assert rt.state.status == ERROR
    assert rt.state.drained_at is not None  # bleibt → Auto-Resume-Kandidat
    assert "fortgesetzt" in (rt.state.error or "")
    await _flush(mgr)


@pytest.mark.asyncio
async def test_rehydrate_crash_orphan_is_not_resume_candidate(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed_row(repo, sid="crash", drained_at=None)
    mgr = _mgr(repo=repo)
    await mgr.rehydrate()
    rt = mgr.get("crash")
    assert rt.state.status == ERROR
    assert rt.state.drained_at is None
    assert "Verwaist" in (rt.state.error or "")
    await _flush(mgr)


# --- auto_resume_drained() --------------------------------------------------


@pytest.mark.asyncio
async def test_auto_resume_resumes_only_drained(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed_row(repo, sid="drained", drained_at="2026-06-24T10:05:00+00:00")
    await _seed_row(repo, sid="crash", drained_at=None)
    mgr = _mgr(repo=repo)
    await mgr.rehydrate()

    await mgr.auto_resume_drained()

    drained = mgr.get("drained")
    crash = mgr.get("crash")
    assert drained.state.status == RUNNING          # fortgesetzt
    assert drained.state.drained_at is None         # Flag gelöscht
    assert crash.state.status == ERROR              # Crash-Orphan NICHT fortgesetzt
    assert crash.state.drained_at is None
    await _flush(mgr)


@pytest.mark.asyncio
async def test_auto_resume_respects_global_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    monkeypatch.setattr(settings, "auto_resume_on_restart", False)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed_row(repo, sid="drained", drained_at="2026-06-24T10:05:00+00:00")
    mgr = _mgr(repo=repo)
    await mgr.rehydrate()

    await mgr.auto_resume_drained()

    rt = mgr.get("drained")
    assert rt.state.status == ERROR          # Schalter aus → kein Auto-Resume
    assert rt.state.drained_at is not None    # Flag bleibt (manueller Knopf/erneuter Versuch)
    await _flush(mgr)
