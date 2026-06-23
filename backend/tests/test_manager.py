"""Manager-Tests mit FakeDriver (async, kein Subprozess)."""
from __future__ import annotations

import pytest

from app.engine.events import StreamEvent
from app.engine.manager import DONE, WAITING, SessionManager

from .fakes import FakeDriver

# Ein garantiert existierendes Verzeichnis innerhalb der erlaubten Roots.
PROJECT = "/home/dev/projects/jupiter"


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


def _assistant(cache_read: int) -> StreamEvent:
    return StreamEvent("assistant", None, {"message": {"usage": {
        "input_tokens": 10, "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": 0, "output_tokens": 5}}})


def _result(cum_cache_read: int, window: int = 200_000) -> StreamEvent:
    return StreamEvent("result", "success", {"is_error": False, "num_turns": 3, "usage": {
        "input_tokens": 30, "cache_read_input_tokens": cum_cache_read,
        "cache_creation_input_tokens": 0, "output_tokens": 15},
        "modelUsage": {"m": {"contextWindow": window}}})


@pytest.mark.asyncio
async def test_context_fill_uses_current_turn_not_cumulative():
    """PROJ4-QA-3: Füllstand = Belegung des AKTUELLEN Turns, nicht die über alle Turns
    kumulierte result-Usage (die sonst fälschlich Richtung 100 % wächst)."""
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    # Aktueller Turn belegt 40k von 200k = 20 %. Das result-Event meldet kumuliert 120k.
    await rt.handle_event(_assistant(40_000))
    await rt.handle_event(_result(cum_cache_read=120_000))
    assert rt.state.context_fill_pct == 20.0   # 40k/200k — NICHT 60 % (120k/200k)


@pytest.mark.asyncio
async def test_context_fill_uses_model_window_from_result():
    """Das modellabhängige Kontextfenster (z. B. 1M) kommt aus dem result-Event."""
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="sonnet")
    await rt.handle_event(_assistant(100_000))
    await rt.handle_event(_result(cum_cache_read=500_000, window=1_000_000))
    assert rt.state.context_fill_pct == 10.0   # 100k/1M


@pytest.mark.asyncio
async def test_create_runs_initial_turn():
    rt = await _mgr().create(project_path=PROJECT, initial_prompt="Hallo", model="haiku")
    # init + assistant + result wurden synchron verarbeitet.
    assert rt.state.status == WAITING
    assert rt.state.model == "claude-haiku-4-5-20251001"
    assert rt.state.num_turns == 1
    assert rt.state.context_fill_pct > 0
    assert any(e.kind == "text" and "Hallo" in e.text for e in rt.transcript)


@pytest.mark.asyncio
async def test_send_input_appends_transcript():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Start", model="sonnet")
    await mgr.send_input(rt.state.session_id, "Mach weiter")
    text = mgr.transcript_text(rt.state.session_id)
    assert "Du: Mach weiter" in text
    assert "Claude:" in text


@pytest.mark.asyncio
async def test_stop_sets_done():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Start")
    await mgr.stop(rt.state.session_id)
    assert rt.state.status == DONE


@pytest.mark.asyncio
async def test_send_input_resumes_done_session():
    """An einer beendeten Session weiterarbeiten: send_input setzt sie fort."""
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Start", model="haiku")
    sid = rt.state.session_id
    await mgr.stop(sid)
    assert rt.state.status == DONE
    old_driver = rt.driver

    await mgr.send_input(sid, "Mach weiter")

    assert rt.state.status != DONE          # wieder aktiv
    assert rt.driver is not old_driver       # frischer Treiber (Resume)
    assert rt.driver.is_alive
    text = mgr.transcript_text(sid)
    assert "Du: Mach weiter" in text
    assert "Echo: Mach weiter" in text


def test_build_argv_resume_vs_new():
    """resume=True nutzt --resume statt --session-id."""
    from app.engine.base import LaunchSpec
    from app.engine.claude_driver import build_argv

    base = dict(session_id="abc", project_path=PROJECT, model="haiku", permission_mode="default")
    new_argv = build_argv(LaunchSpec(initial_prompt="x", **base))
    assert "--session-id" in new_argv and "--resume" not in new_argv

    res_argv = build_argv(LaunchSpec(initial_prompt="", resume=True, **base))
    assert "--resume" in res_argv
    assert res_argv[res_argv.index("--resume") + 1] == "abc"
    assert "--session-id" not in res_argv


@pytest.mark.asyncio
async def test_pause_blocks_input():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Start")
    await mgr.pause(rt.state.session_id)
    with pytest.raises(RuntimeError):
        await mgr.send_input(rt.state.session_id, "geht nicht")


@pytest.mark.asyncio
async def test_invalid_path_rejected():
    with pytest.raises(ValueError):
        await _mgr().create(project_path="/etc", initial_prompt="x")


@pytest.mark.asyncio
async def test_invalid_model_rejected():
    with pytest.raises(ValueError):
        await _mgr().create(project_path=PROJECT, initial_prompt="x", model="gpt-9")
