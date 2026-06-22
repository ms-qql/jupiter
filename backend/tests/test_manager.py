"""Manager-Tests mit FakeDriver (async, kein Subprozess)."""
from __future__ import annotations

import pytest

from app.engine.manager import DONE, WAITING, SessionManager

from .fakes import FakeDriver

# Ein garantiert existierendes Verzeichnis innerhalb der erlaubten Roots.
PROJECT = "/home/dev/projects/jupiter"


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


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
