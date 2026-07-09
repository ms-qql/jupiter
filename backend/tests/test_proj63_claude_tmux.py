"""PROJ-63 — ClaudeCodeDriver mit ``transport="tmux"`` (Rollout-Schritt 5: Claude aktiviert).

Anders als Codex/OpenCode (oneshot, ein Prozess pro Turn) ist Claude LANG-lebig:
derselbe Prozess bleibt über mehrere Turns am Leben, Folge-Eingaben laufen über die
Kontroll-FIFO (``exec 9<>fifo``-Selbst-Open hält stdin offen). Verdrahtungs-Tests mit
einer winzigen Fake-``claude``-CLI (echte tmux-Session, kein echter Claude-Aufruf):
- Einzelner Turn läuft vollständig über eine echte tmux-Session (Prompt über die FIFO,
  stream-json-Ausgabe über out.log).
- Multi-Turn über DENSELBEN Prozess (gleiche PID/Session — kein Respawn, das ist der
  Kernunterschied zum oneshot-Pfad).
- ``stop()`` beendet die tmux-Session tatsächlich (``self._proc`` bleibt im tmux-Modus None).
- Default (``transport`` nicht gesetzt) bleibt "direct" — keine Verhaltensänderung ohne Opt-in.
"""
from __future__ import annotations

import asyncio
import shutil
import sys

import pytest

from app.engine.base import LaunchSpec
from app.engine.claude_driver import ClaudeCodeDriver
from app.engine.events import extract_text

pytestmark = pytest.mark.skipif(
    shutil.which("tmux") is None, reason="tmux ist auf diesem Host nicht installiert"
)

# Fake-`claude`: liest stream-json-User-Envelopes zeilenweise von stdin (der FIFO) und
# echo't jeden Prompt als Claude-artiges assistant+result-Event. Blockierendes readline()
# → long-lived (Prozess bleibt zwischen Turns am Leben, sieht nie EOF dank FIFO-Trick).
FAKE_CLAUDE_BODY = r'''
import sys, json
while True:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
        text = obj["message"]["content"][0]["text"]
    except Exception:
        continue
    out = "echo:%s" % text
    print(json.dumps({"type": "assistant",
                      "message": {"content": [{"type": "text", "text": out}]}}), flush=True)
    print(json.dumps({"type": "result", "subtype": "success",
                      "is_error": False, "result": out}), flush=True)
'''


def _fake_claude_bin(tmp_path) -> str:
    script = tmp_path / "fake_claude.py"
    script.write_text("#!" + sys.executable + "\n" + FAKE_CLAUDE_BODY, encoding="utf-8")
    script.chmod(0o755)
    return str(script)


def _collector():
    events: list = []

    async def on_event(e):
        events.append(e)

    return events, on_event


def _texts(events) -> list[str]:
    return [t for e in events if e.type == "assistant" and (t := extract_text(e))]


async def _wait_until(pred, *, timeout: float = 6.0, interval: float = 0.1) -> bool:
    waited = 0.0
    while waited < timeout:
        if pred():
            return True
        await asyncio.sleep(interval)
        waited += interval
    return pred()


@pytest.mark.asyncio
async def test_single_turn_over_tmux(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "tmuxdata"))
    monkeypatch.setattr(settings, "claude_bin", _fake_claude_bin(tmp_path))
    drv = ClaudeCodeDriver()
    events, on = _collector()
    spec = LaunchSpec(
        session_id="c-tmux-1", project_path=str(tmp_path), model="haiku",
        permission_mode="default", initial_prompt="erste", transport="tmux",
    )
    try:
        await drv.start(spec, on)
        assert await _wait_until(lambda: "echo:erste" in _texts(events))
        assert drv.is_alive is True  # long-lived: Prozess bleibt nach dem Turn am Leben
        assert drv.pid is not None  # echte OS-PID des Pane-Prozesses
    finally:
        await drv.stop()


@pytest.mark.asyncio
async def test_multi_turn_uses_same_long_lived_process(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "tmuxdata"))
    monkeypatch.setattr(settings, "claude_bin", _fake_claude_bin(tmp_path))
    drv = ClaudeCodeDriver()
    events, on = _collector()
    spec = LaunchSpec(
        session_id="c-tmux-2", project_path=str(tmp_path), model="haiku",
        permission_mode="default", initial_prompt="erste", transport="tmux",
    )
    try:
        await drv.start(spec, on)
        assert await _wait_until(lambda: "echo:erste" in _texts(events))
        session_before = drv._transport_obj.tmux_session
        pid_before = drv.pid

        await drv.send_input("zweite")
        assert await _wait_until(lambda: "echo:zweite" in _texts(events))

        # KEIN Respawn: dieselbe Session UND dieselbe PID über beide Turns (Kern-
        # unterschied zum oneshot-Pfad, der je Turn einen neuen Prozess spawnt).
        assert drv._transport_obj.tmux_session == session_before
        assert drv.pid == pid_before
        assert _texts(events) == ["echo:erste", "echo:zweite"]
    finally:
        await drv.stop()


@pytest.mark.asyncio
async def test_stop_actually_kills_tmux_session(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "tmuxdata"))
    monkeypatch.setattr(settings, "claude_bin", _fake_claude_bin(tmp_path))
    drv = ClaudeCodeDriver()
    events, on = _collector()
    spec = LaunchSpec(
        session_id="c-tmux-3", project_path=str(tmp_path), model="haiku",
        permission_mode="default", initial_prompt="hi", transport="tmux",
    )
    await drv.start(spec, on)
    transport = drv._transport_obj
    assert await transport.session_exists() is True

    await drv.stop()
    await asyncio.wait_for(drv._reader_task, timeout=3.0)
    assert await transport.session_exists() is False


@pytest.mark.asyncio
async def test_default_transport_is_direct_without_explicit_opt_in(tmp_path, monkeypatch):
    """Ohne ``transport="tmux"`` bleibt alles beim heutigen direkten Subprozess-Pfad."""
    from app.config import settings

    monkeypatch.setattr(settings, "claude_bin", _fake_claude_bin(tmp_path))
    drv = ClaudeCodeDriver()
    events, on = _collector()
    spec = LaunchSpec(
        session_id="c-direct-default", project_path=str(tmp_path), model="haiku",
        permission_mode="default", initial_prompt="erste",
    )
    try:
        await drv.start(spec, on)
        assert await _wait_until(lambda: "echo:erste" in _texts(events))
        assert drv._transport_mode == "direct"
        assert drv._transport_obj is None
        assert drv._proc is not None
    finally:
        await drv.stop()
