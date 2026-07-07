"""PROJ-63 — GenericCliDriver mit ``transport="tmux"`` (Codex/OpenCode-Rollout zuerst).

Verdrahtungs-Tests: dieselbe Fake-CLI/Profil-Konstruktion wie ``test_proj48_codex.py``
(``sys.executable`` + winziges Python-Skript, kein echter Codex/OpenCode-Aufruf), aber
mit ``LaunchSpec(transport="tmux")`` — deckt ab:
- Einzelner Turn läuft vollständig über eine echte tmux-Session (Datei-Redirect-Prompt,
  kein PTY-Fehler), Status/Usage/Transkript identisch zum direct-Pfad.
- Multi-Turn-Resume respawnt dieselbe tmux-Session (Kontext bleibt über die resume_id
  erhalten) — Kernkriterium "kein zweiter paralleler Agent mit demselben Kontext".
- Nicht-Null-Exitcode → Fehler-Event mit stderr-Text (Exit-Marker-Zeile herausgefiltert).
- ``stop()`` beendet die tmux-Session tatsächlich (nicht nur ein System-Event, siehe
  Regressions-Falle: ``self._proc`` bleibt im tmux-Modus IMMER None).
- Default (``transport`` nicht gesetzt) bleibt "direct" — keine Verhaltensänderung ohne
  explizite Opt-in.
"""
from __future__ import annotations

import shutil
import sys

import pytest

from app.engine.base import LaunchSpec
from app.engine.events import extract_text
from app.engine.generic_cli_driver import GenericCliDriver
from app.engine.registry import EngineProfile

pytestmark = pytest.mark.skipif(
    shutil.which("tmux") is None, reason="tmux ist auf diesem Host nicht installiert"
)

# Gleiches Muster wie FAKE_CODEX in test_proj48_codex.py.
FAKE_CODEX = r'''
import sys, json
args = sys.argv[1:]
prompt = sys.stdin.read().strip()
if "resume" in args:
    i = args.index("resume")
    rid = args[i + 1] if i + 1 < len(args) else ""
    print(json.dumps({"type": "thread.started", "thread_id": rid}))
    print(json.dumps({"type": "turn.started"}))
    print(json.dumps({"item": {"type": "agent_message", "text": "resumed:%s:%s" % (prompt, rid)},
                      "type": "item.completed"}))
    print(json.dumps({"type": "turn.completed",
                      "usage": {"input_tokens": 200, "cached_input_tokens": 50,
                                "output_tokens": 10, "reasoning_output_tokens": 5}}))
else:
    print(json.dumps({"type": "thread.started", "thread_id": "TID-TMUX"}))
    print(json.dumps({"type": "turn.started"}))
    print(json.dumps({"item": {"type": "agent_message", "text": "hi:%s" % prompt},
                      "type": "item.completed"}))
    print(json.dumps({"type": "turn.completed",
                      "usage": {"input_tokens": 100, "cached_input_tokens": 20,
                                "output_tokens": 5, "reasoning_output_tokens": 0}}))
'''

FAKE_FAIL = "import sys; sys.stdin.read(); sys.stderr.write('boom\\n'); sys.exit(7)\n"


def _fake_profile(tmp_path, *, script_body: str = FAKE_CODEX, resumable: bool = True) -> EngineProfile:
    script = tmp_path / "fake_codex.py"
    script.write_text(script_body, encoding="utf-8")
    prof = EngineProfile(
        key="codex",
        label="Fake Codex (tmux)",
        driver="generic_cli",
        bin=sys.executable,
        argv_template=[str(script), "exec", "--json", "-"],
        adapter="codex",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )
    if resumable:
        prof.resume_argv_template = [str(script), "exec", "--json", "resume", "{resume_id}", "-"]
    return prof


def _collector():
    events: list = []

    async def on_event(e):
        events.append(e)

    return events, on_event


def _texts(events) -> list[str]:
    return [t for e in events if e.type == "assistant" and (t := extract_text(e))]


@pytest.mark.asyncio
async def test_single_turn_over_tmux(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "tmuxdata"))
    prof = _fake_profile(tmp_path)
    drv = GenericCliDriver(prof)
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s-tmux-1", project_path=str(tmp_path), model="gpt-5.5",
        permission_mode="default", initial_prompt="erste", transport="tmux",
    )
    try:
        await drv.start(spec, on)
        await drv._reader_task
        assert _texts(events) == ["hi:erste"]
        assert drv.pid is not None  # echte OS-PID des Pane-Prozesses
    finally:
        await drv.stop()


@pytest.mark.asyncio
async def test_multi_turn_resume_over_tmux_keeps_context(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "tmuxdata"))
    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s-tmux-2", project_path=str(tmp_path), model="gpt-5.5",
        permission_mode="default", initial_prompt="erste", transport="tmux",
    )
    try:
        await drv.start(spec, on)
        await drv._reader_task
        assert drv.supports_self_resume is True
        assert drv.is_alive is False  # Turn fertig, Prozess weg (oneshot)

        first_session = drv._transport_obj.tmux_session
        await drv.send_input("zweite")
        await drv._reader_task

        # Respawn traf dieselbe tmux-Session (stabile Identität über beide Turns).
        assert drv._transport_obj.tmux_session == first_session
        assert _texts(events) == ["hi:erste", "resumed:zweite:TID-TMUX"]
    finally:
        await drv.stop()


@pytest.mark.asyncio
async def test_nonzero_exit_reports_stderr_without_marker_line(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "tmuxdata"))
    prof = _fake_profile(tmp_path, script_body=FAKE_FAIL, resumable=False)
    drv = GenericCliDriver(prof)
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s-tmux-3", project_path=str(tmp_path), model="x",
        permission_mode="default", initial_prompt="hi", transport="tmux",
    )
    try:
        await drv.start(spec, on)
        await drv._reader_task
        errors = [e for e in events if e.type == "system" and e.subtype == "error"]
        assert len(errors) == 1
        msg = errors[0].raw["message"]
        assert "boom" in msg
        assert "__JUPITER_TMUX_EXIT__" not in msg
    finally:
        await drv.stop()


@pytest.mark.asyncio
async def test_stop_actually_kills_tmux_session(tmp_path, monkeypatch):
    """Regressionsfalle: `self._proc` bleibt im tmux-Modus IMMER None — ohne den
    eigenen tmux-Zweig in `stop()` wuerde der `proc is None`-Fall greifen und NUR
    ein System-Event emittieren, ohne die tmux-Session tatsaechlich zu beenden."""
    from app.config import settings

    # Ein Skript, das laenger liefe als der Test warten will (long-lived-artig
    # simuliert über sleep) — testet, dass stop() aktiv killt statt nur zu warten.
    script = tmp_path / "fake_slow.py"
    script.write_text(
        "import sys, time; sys.stdin.read(); time.sleep(30)\n", encoding="utf-8"
    )
    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "tmuxdata"))
    prof = EngineProfile(
        key="codex", label="Fake Slow", driver="generic_cli", bin=sys.executable,
        argv_template=[str(script), "exec", "--json", "-"],
        adapter="codex", prompt_via="stdin", input_format="text", oneshot=True,
    )
    drv = GenericCliDriver(prof)
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s-tmux-4", project_path=str(tmp_path), model="x",
        permission_mode="default", initial_prompt="hi", transport="tmux",
    )
    await drv.start(spec, on)
    transport = drv._transport_obj
    assert await transport.session_exists() is True

    await drv.stop()
    # Reader-Task laesst sich sauber abwarten (poll-basiertes EOF-Erkennen nach dem
    # Kill, kein hängender Task/keine "Task was destroyed"-Warnung beim Testende).
    import asyncio

    await asyncio.wait_for(drv._reader_task, timeout=2.0)

    assert await transport.session_exists() is False


@pytest.mark.asyncio
async def test_default_transport_is_direct_without_explicit_opt_in(tmp_path):
    """Ohne ``transport="tmux"`` bleibt ALLES beim heutigen direkten Pfad — keine
    Verhaltensaenderung fuer bestehende Aufrufer, die das neue Feld nicht kennen."""
    prof = _fake_profile(tmp_path, resumable=False)
    drv = GenericCliDriver(prof)
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s-direct-default", project_path=str(tmp_path), model="gpt-5.5",
        permission_mode="default", initial_prompt="erste",
    )
    try:
        await drv.start(spec, on)
        await drv._reader_task
        assert drv._transport_mode == "direct"
        assert drv._transport_obj is None
        assert drv._proc is not None
        assert _texts(events) == ["hi:erste"]
    finally:
        await drv.stop()
