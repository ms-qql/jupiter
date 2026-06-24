"""PROJ-33 — QA: Akzeptanzkriterien-Vervollständigung + Red-Team.

Ergänzt die Entwickler-Tests (test_proj33_is_alive.py, test_proj33_drain_resume.py) um
die für die Abnahme entscheidenden adversariellen Fälle:
- Self-Restart-Gate: Freigeben → allow; harmloses Kommando läuft (auch im Bypass) durch;
- Resume-Sturm-Schutz: scheitert das Auto-Resume, wird drained_at gelöscht (genau EIN Versuch);
- Session-Limit (PROJ-14) wird beim Auto-Resume gewahrt;
- Kontinuität: eine auto-resumte Session nimmt wieder Eingaben an;
- drain() überspringt terminale Sessions.
"""
from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.db.session_index import SqliteSessionIndexRepository
from app.engine.manager import DONE, ERROR, RUNNING, SessionManager

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


class BoomStartDriver(FakeDriver):
    """Treiber, dessen start() scheitert — simuliert ein fehlschlagendes claude --resume."""

    async def start(self, spec, on_event) -> None:  # type: ignore[override]
        raise RuntimeError("resume kaputt")


def _mgr(repo=None, driver_factory=None) -> SessionManager:
    return SessionManager(driver_factory=driver_factory or (lambda: FakeDriver()), repo=repo)


async def _flush(mgr: SessionManager) -> None:
    for _ in range(5):
        pending = list(mgr._persist_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


async def _seed(repo, *, sid, drained_at):
    await repo.upsert({
        "session_id": sid, "status": "running", "owner": "dev",
        "project_path": PROJECT, "model": "haiku", "permission_mode": "default",
        "pid": 2_147_483_000, "created_at": "2026-06-24T10:00:00+00:00",
        "last_activity": "2026-06-24T10:00:00+00:00", "drained_at": drained_at,
    })


# --- Self-Restart-Gate: Freigeben + Durchlass harmloser Kommandos ----------


@pytest.mark.asyncio
async def test_self_restart_gate_approve_allows():
    """Freigeben der Host-Neustart-Card → der Aufruf darf laufen (allow)."""
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", permission_mode="bypassPermissions")
    task = asyncio.create_task(
        rt.request_decision("d1", "Bash", {"command": "bash deploy.sh main"})
    )
    for _ in range(20):
        if rt.pending:
            break
        await asyncio.sleep(0.01)
    assert any(c.card_type == "self_restart" for c in rt.pending.values())
    rt.resolve_decision("d1", approve=True)
    outcome = await task
    assert outcome.behavior == "allow"


@pytest.mark.asyncio
async def test_harmless_command_not_gated_in_bypass():
    """Ein normales Kommando öffnet KEINE self_restart-Card und läuft im Bypass durch."""
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", permission_mode="bypassPermissions")
    outcome = await rt.request_decision("d2", "Bash", {"command": "pytest -q"})
    assert outcome.behavior == "allow"
    assert not any(c.card_type == "self_restart" for c in rt.pending.values())


# --- Resume-Sturm-Schutz + Session-Limit -----------------------------------


@pytest.mark.asyncio
async def test_auto_resume_failure_clears_flag_no_storm(tmp_path, monkeypatch):
    """Scheitert das Auto-Resume, wird drained_at gelöscht (genau EIN Versuch) und die
    Session bleibt ERROR — ein erneuter Neustart löst KEINEN weiteren Auto-Versuch aus."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed(repo, sid="drained", drained_at="2026-06-24T10:05:00+00:00")
    mgr = _mgr(repo=repo, driver_factory=lambda: BoomStartDriver())
    await mgr.rehydrate()

    await mgr.auto_resume_drained()

    rt = mgr.get("drained")
    assert rt.state.status == ERROR
    assert rt.state.drained_at is None                       # Flag gelöscht → kein Retry-Sturm
    assert "fehlgeschlagen" in (rt.state.error or "").lower()
    await _flush(mgr)


@pytest.mark.asyncio
async def test_auto_resume_respects_session_limit(tmp_path, monkeypatch):
    """Bei Limit=1 wird nur EINE gedrainte Session fortgesetzt; die andere bleibt mit
    gesetztem drained_at zurück (kein Limit-Bypass; manuell/später fortsetzbar)."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 1)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed(repo, sid="d1", drained_at="2026-06-24T10:05:00+00:00")
    await _seed(repo, sid="d2", drained_at="2026-06-24T10:05:00+00:00")
    mgr = _mgr(repo=repo)
    await mgr.rehydrate()

    await mgr.auto_resume_drained()

    statuses = sorted(mgr.get(s).state.status for s in ("d1", "d2"))
    assert statuses == [ERROR, RUNNING]          # genau eine fortgesetzt
    assert mgr.active_count() == 1               # Limit gewahrt
    # Die nicht-fortgesetzte behält ihr Flag (Kandidat für späteren Versuch/Knopf).
    pending_flag = [mgr.get(s).state.drained_at for s in ("d1", "d2") if mgr.get(s).state.status == ERROR]
    assert pending_flag == [pending_flag[0]] and pending_flag[0] is not None
    await _flush(mgr)


# --- Kontinuität: resumte Session ist wieder nutzbar -----------------------


@pytest.mark.asyncio
async def test_resumed_session_accepts_input(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed(repo, sid="drained", drained_at="2026-06-24T10:05:00+00:00")
    mgr = _mgr(repo=repo)
    await mgr.rehydrate()
    await mgr.auto_resume_drained()

    rt = mgr.get("drained")
    assert rt.state.status == RUNNING
    await mgr.send_input("drained", "weiter gehts")  # darf nicht werfen
    assert "weiter gehts" in rt.driver.sent
    await _flush(mgr)


# --- drain() überspringt terminale Sessions --------------------------------


@pytest.mark.asyncio
async def test_drain_skips_terminal_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = _mgr(repo=repo)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    await mgr.stop(rt.state.session_id)          # → DONE (terminal)
    assert rt.state.status == DONE
    await _flush(mgr)

    await mgr.drain()

    assert rt.state.drained_at is None           # terminale Session NICHT gedraint
    await _flush(mgr)
