"""PROJ-74 — rehydrate() soll bei tmux-transportierten Sessions die echte Pane-
Liveness prüfen, statt jede Session ohne `drained_at` pauschal als ERROR/verwaist
zu markieren.

Root Cause (vor dem Fix): `SessionManager.rehydrate()` setzte `state.status = ERROR`
unconditional für jede vorher aktive Session ohne `drained_at` — der bereits
vorhandene `_pid_alive()`-Check floss nur in den Fehlertext ein, nie in die
Status-Entscheidung selbst. Eine nach PROJ-63 langlebige tmux-Pane, die einen
harten Backend-Absturz (kein geordnetes `drain()`) unabhängig überlebt, wurde
dadurch fälschlich als verwaist geführt — inkl. Herausfallen aus `active_count()`
(zählt nur `ACTIVE_STATES`), obwohl der Agent real weiterlief.

Diese Tests spawnen ECHTE tmux-Sessions (Muster analog zu
`test_proj63_tmux_transport.py`) — kein echter claude/codex-Aufruf, ein winziges
Fake-Python-Skript als CLI-Stand-in.
"""
from __future__ import annotations

import asyncio
import shutil
import sys

import pytest

from app.config import settings
from app.db.session_index import SqliteSessionIndexRepository
from app.engine.manager import ERROR, RUNNING, SessionManager
from app.engine.transport import TmuxTransport

from .fakes import FakeDriver

pytestmark = pytest.mark.skipif(
    shutil.which("tmux") is None, reason="tmux ist auf diesem Host nicht installiert"
)

PROJECT = "/home/dev/projects/jupiter"

# Langlebiger Fake-CLI-Stand-in (wie in test_proj63_tmux_transport.py) — bleibt am
# Leben, bis die Pane extern beendet wird, genau wie Claude im tmux-Langzeitmodus.
FAKE_LONG_LIVED = r'''
import sys, json
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    print(json.dumps({"type": "result", "text": "ECHO:" + line}))
    sys.stdout.flush()
'''


def _write_script(tmp_path, name: str, body: str) -> list[str]:
    script = tmp_path / name
    script.write_text(body, encoding="utf-8")
    return [sys.executable, str(script)]


def _mgr(repo=None) -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver(), repo=repo)


async def _flush(mgr: SessionManager) -> None:
    """Best-effort-Persist-Tasks abwarten (Muster aus test_proj33_drain_resume.py)."""
    for _ in range(5):
        pending = list(mgr._persist_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


async def _seed_tmux_row(repo, *, sid, pid=2_147_483_000):
    """Simuliert die Live-Index-Zeile einer Session, die VOR einem harten
    Backend-Absturz aktiv lief (kein `drained_at`, transport='tmux')."""
    await repo.upsert({
        "session_id": sid, "status": "running", "owner": "dev",
        "project_path": PROJECT, "model": "haiku", "permission_mode": "default",
        "pid": pid,
        "created_at": "2026-07-17T10:00:00+00:00",
        "last_activity": "2026-07-17T10:00:00+00:00",
        "drained_at": None,
        "transport": "tmux",
    })


# ===========================================================================
# TmuxTransport.pane_alive_after_restart() — die neue, `_spawned`-freie Sonde
# ===========================================================================


@pytest.mark.asyncio
async def test_pane_alive_after_restart_true_for_live_pane_from_fresh_instance(tmp_path):
    """Kern der Lücke: eine frisch KONSTRUIERTE Instanz (wie bei rehydrate() nach
    einem Neustart) hat `_spawned=False` — `_probe_alive()`/`refresh_liveness()`
    würden daher IMMER `False` liefern, obwohl die Pane (von einer ANDEREN Instanz
    vor dem Neustart gespawnt) nachweislich noch lebt."""
    argv = _write_script(tmp_path, "fake.py", FAKE_LONG_LIVED)
    spawner = TmuxTransport("proj74-alive", data_dir=str(tmp_path / "data"))
    try:
        await spawner.spawn(argv, cwd=str(tmp_path), long_lived=True)

        fresh = TmuxTransport("proj74-alive", data_dir=str(tmp_path / "data"))
        assert fresh._spawned is False  # Ausgangslage: wie nach einem Neustart.
        assert await fresh.refresh_liveness() is False  # bestehendes Gate greift (erwartet).
        assert await fresh.pane_alive_after_restart() is True  # neue Sonde umgeht das Gate korrekt.
    finally:
        await spawner.kill()
        spawner.cleanup_files()


@pytest.mark.asyncio
async def test_pane_alive_after_restart_false_for_unknown_session(tmp_path):
    fresh = TmuxTransport("proj74-nonexistent", data_dir=str(tmp_path / "data"))
    assert await fresh.pane_alive_after_restart() is False


@pytest.mark.asyncio
async def test_pane_alive_after_restart_false_for_dead_pane_in_existing_session(tmp_path):
    """QA-BUG-2a: unterscheidet sich von `..._unknown_session` — hier EXISTIERT die
    tmux-Session noch (PROJ-63: `remain-on-exit on`), nur die Pane selbst ist tot
    (z. B. ein Oneshot-Turn, der schon vor dem Absturz durchgelaufen war). Beide
    Fälle müssen `False` liefern, aber über unterschiedliche tmux-Antworten
    (`has-session` rc != 0 vs. `pane_dead == 1`) — vorher unbewiesen."""
    argv = [sys.executable, "-c", "pass"]  # beendet sich sofort selbst.
    transport = TmuxTransport("proj74-dead-pane", data_dir=str(tmp_path / "data"))
    try:
        await transport.spawn(argv, cwd=str(tmp_path), long_lived=False)
        await transport.wait()  # auf das Prozessende warten (remain-on-exit hält die Pane).

        assert await transport.session_exists() is True  # Session existiert weiterhin.
        fresh = TmuxTransport("proj74-dead-pane", data_dir=str(tmp_path / "data"))
        assert await fresh.pane_alive_after_restart() is False
    finally:
        await transport.kill()
        transport.cleanup_files()


# ===========================================================================
# SessionManager.rehydrate() — die eigentliche Reproduktion + der Fix
# ===========================================================================


@pytest.mark.asyncio
async def test_rehydrate_tmux_pane_still_alive_is_not_orphaned(tmp_path, monkeypatch):
    """Die Reproduktion: vor dem Fix landete dieser Fall IMMER in ERROR
    (`state.status = ERROR` unconditional), obwohl die Pane nachweislich lebt."""
    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "data"))
    argv = _write_script(tmp_path, "fake.py", FAKE_LONG_LIVED)
    sid = "proj74-rehydrate-alive"
    # Kein `data_dir`-Override -> nutzt `settings.tmux_data_dir`, exakt wie
    # `manager.rehydrate()` es beim echten `TmuxTransport(sid)`-Aufruf auch tut.
    transport = TmuxTransport(sid)
    try:
        await transport.spawn(argv, cwd=str(tmp_path), long_lived=True)

        repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
        await repo.init()
        await _seed_tmux_row(repo, sid=sid)

        mgr = _mgr(repo=repo)
        await mgr.rehydrate()

        rt = mgr.get(sid)
        assert rt.state.status != ERROR
        assert rt.state.status == RUNNING  # unverändert übernommen, nicht herabgestuft.
        assert "Verwaist" not in (rt.state.error or "")
        assert "reanimieren" in (rt.state.error or "")
        await _flush(mgr)
    finally:
        await transport.kill()
        transport.cleanup_files()


@pytest.mark.asyncio
async def test_rehydrate_tmux_pane_dead_is_still_orphaned(tmp_path, monkeypatch):
    """Gegenprobe: existiert die tmux-Pane nicht (mehr), bleibt das bisherige,
    konservative ERROR/verwaist-Verhalten unverändert (fail-safe)."""
    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "data"))
    sid = "proj74-rehydrate-dead"
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed_tmux_row(repo, sid=sid)

    mgr = _mgr(repo=repo)
    await mgr.rehydrate()

    rt = mgr.get(sid)
    assert rt.state.status == ERROR
    assert "Verwaist" in (rt.state.error or "")
    await _flush(mgr)


@pytest.mark.asyncio
async def test_rehydrate_tmux_binary_missing_does_not_abort_whole_batch(tmp_path, monkeypatch):
    """QA-BUG-1-Regression: vor dem Fix fing `pane_alive_after_restart()` nur
    `TransportError` ab — ein `FileNotFoundError` (fehlendes `tmux`-Binary, z. B.
    PATH-Drift zwischen Original-Spawn und Neustart) riss den GESAMTEN
    `rehydrate()`-Durchlauf ab, sodass auch eine völlig unbeteiligte
    `direct`-Session (Zeile B, nach der defekten tmux-Zeile A) nie rehydriert wurde.
    Reproduziert und unabhängig verifiziert im QA-Pass zu PROJ-74."""
    monkeypatch.setattr(settings, "tmux_bin", "definitely-not-a-real-tmux-binary-xyz")
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await _seed_tmux_row(repo, sid="a-tmux-orphan")
    await repo.upsert({
        "session_id": "b-should-still-rehydrate", "status": "running", "owner": "dev",
        "project_path": PROJECT, "model": "haiku", "permission_mode": "default",
        "pid": 456, "created_at": "2026-07-17T10:00:00+00:00",
        "last_activity": "2026-07-17T10:00:00+00:00", "drained_at": None,
        "transport": "direct",
    })

    mgr = _mgr(repo=repo)
    await mgr.rehydrate()  # darf NICHT werfen — vor dem Fix: FileNotFoundError.

    assert mgr.get("a-tmux-orphan").state.status == ERROR  # konservativ: tmux-Fehler → "tot".
    assert mgr.get("b-should-still-rehydrate") is not None  # unbeteiligte Zeile bleibt rehydriert.
    assert mgr.get("b-should-still-rehydrate").state.status == ERROR
    await _flush(mgr)
    await _flush(mgr)
