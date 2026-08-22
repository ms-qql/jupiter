"""Regressionstests — HermesChatDriver darf einen sauber beendeten Turn nicht als
Absturz melden, und der erste getippte Text darf nicht verworfen werden.

Bug 1 (Text verworfen): send_input spawnte den ersten Turn bei wartender Session
aus dem alten, leeren LaunchSpec statt aus einem neuen mit dem getippten Text.

Bug 2 (Fehlalarm "Prozess wurde beendet, ohne den Turn regulär abzuschließen"):
_read_stdout las die Usage-Datei (Resume-Ref) SOFORT beim Start des Readers,
lange bevor der Hermes-Prozess sie überhaupt geschrieben hat — die Basisklasse
sah daher nie eine Resume-Ref UND nie ein "result"-Event (Hermes' plaintext-
Adapter emittiert nie eins) und meldete jeden — auch einen völlig normal
beendeten — Turn als abgebrochen.
"""
from __future__ import annotations

import asyncio
import json
import os
import stat
import tempfile

import pytest

from app.engine.base import LaunchSpec
from app.engine.hermes_chat_driver import HermesChatDriver
from app.engine.registry import EngineProfile


def _write_fake_hermes(tmp_path, resume_ref: str = "hermes-ref-xyz") -> str:
    """Ein Shell-Stub, der sich wie die echte Hermes-CLI verhält: druckt Text auf
    stdout, schreibt die Usage-Datei ERST GANZ AM ENDE, exitet dann mit 0 —
    genau die Reihenfolge, die den Timing-Bug (Bug 2) real auslöst."""
    script = tmp_path / "fake_hermes.sh"
    script.write_text(
        "#!/bin/bash\n"
        "usage_file=\"\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--usage-file\" ]]; then usage_file=\"$2\"; fi\n"
        "  shift\n"
        "done\n"
        "echo 'Hallo vom Fake-Hermes'\n"
        "sleep 0.2\n"
        f"echo '{{\"session_id\": \"{resume_ref}\"}}' > \"$usage_file\"\n"
        "exit 0\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


@pytest.mark.anyio
async def test_first_send_input_uses_typed_text_not_empty_prompt(monkeypatch):
    """Bug 1."""
    profile = EngineProfile(
        key="hermes", label="Hermes (Agent)", kind="engine", driver="generic_cli",
        models=["qwen3.5-397b-a17b"], bin="hermes",
    )
    driver = HermesChatDriver(profile, provider="anthropic", model="claude-fable-5")
    driver._spec = LaunchSpec(
        session_id="s1", project_path="/home/dev/projects", model="fable",
        permission_mode="bypassPermissions", initial_prompt="",
    )
    driver._awaiting_first_input = True

    captured: dict[str, list[str]] = {}

    async def fake_spawn(argv, cwd, *, prompt=None):
        captured["argv"] = argv

    monkeypatch.setattr(driver, "_spawn", fake_spawn)

    await driver.send_input("Hallo Hermes, bitte X tun")

    assert driver._awaiting_first_input is False
    argv = captured["argv"]
    assert "Hallo Hermes, bitte X tun" in argv, argv
    z_index = argv.index("-z")
    assert argv[z_index + 1] == "Hallo Hermes, bitte X tun"


@pytest.mark.anyio
async def test_clean_turn_does_not_emit_no_final_result(tmp_path):
    """Bug 2 — echter Subprozess (kein Fake-Treiber), reproduziert die reale
    asyncio-Spawn-/Reader-Kette. Vor dem Fix: `closed` mit reason=no_final_result
    trotz rc=0 und vorhandener Usage-Datei. Nach dem Fix: `closed` ohne Reason."""
    profile = EngineProfile(
        key="hermes", label="Hermes (Agent)", kind="engine", driver="generic_cli",
        models=["qwen3.5-397b-a17b"], bin=_write_fake_hermes(tmp_path),
    )
    driver = HermesChatDriver(profile, provider="anthropic", model="claude-fable-5")

    events: list = []

    async def on_event(event):
        events.append(event)

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="fable",
        permission_mode="bypassPermissions", initial_prompt="Hallo Hermes",
    )
    await driver.start(spec, on_event)
    assert driver._reader_task is not None
    await asyncio.wait_for(driver._reader_task, timeout=5)
    if driver._stderr_task is not None:
        driver._stderr_task.cancel()

    # Sauberes, fortsetzbares Turn-Ende (rc=0 + Resume-Ref) → gar kein `closed`
    # (Session bleibt "wartet auf nächste Eingabe", siehe PROJ-48-Kommentar in
    # generic_cli_driver.py). Vor dem Fix kam hier fälschlich ein `closed` mit
    # reason=no_final_result, weil die Usage-Datei zu früh gelesen wurde.
    no_final_result = [
        e for e in events
        if e.type == "system" and e.subtype == "closed"
        and e.raw.get("reason") == "no_final_result"
    ]
    assert not no_final_result, (
        f"Fälschlich als abgebrochen gemeldet trotz sauberem rc=0-Turn-Ende: {events}"
    )
    assert driver._resume_ref == "hermes-ref-xyz"


@pytest.mark.anyio
async def test_reader_exception_does_not_hang_session_forever(tmp_path, monkeypatch):
    """Bug 3 (PROJ-47-Lücke) — eine Ausnahme im stdout-Reader (z. B. beim Auswerten der
    Usage-Datei) durfte die Task bisher fire-and-forget sterben lassen: kein Log, kein
    Event, die Session blieb für immer auf `running` stehen (Liveness erkennt den toten
    Prozess zwar separat als "tot", aber `state.status`/`state.error` werden
    ausschließlich vom Reader selbst gesetzt). `claude_driver.py` hatte für genau diesen
    Fall bereits einen `_on_reader_done`-Callback (PROJ-47) — `GenericCliDriver` (Basis
    von Hermes/Codex/OpenCode) nicht. Nach dem Fix: die Ausnahme erzeugt ein sichtbares
    `system/error`-Event statt eine stumm verschwundene Task."""
    profile = EngineProfile(
        key="hermes", label="Hermes (Agent)", kind="engine", driver="generic_cli",
        models=["qwen3.5-397b-a17b"], bin=_write_fake_hermes(tmp_path),
    )
    driver = HermesChatDriver(profile, provider="anthropic", model="claude-fable-5")

    def boom(rc):
        raise RuntimeError("kaputte Usage-Datei (simuliert)")

    monkeypatch.setattr(driver, "_after_process_exit", boom)

    events: list = []

    async def on_event(event):
        events.append(event)

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="fable",
        permission_mode="bypassPermissions", initial_prompt="Hallo Hermes",
    )
    await driver.start(spec, on_event)
    assert driver._reader_task is not None
    # Task selbst wirft (fire-and-forget) — nur der done-Callback darf das auffangen.
    for _ in range(50):
        if driver._reader_task.done():
            break
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.05)  # dem synchronen done-Callback Zeit geben, das Event zu schedulen
    if driver._stderr_task is not None:
        driver._stderr_task.cancel()

    error_events = [e for e in events if e.type == "system" and e.subtype == "error"]
    assert error_events, (
        f"Reader-Exception blieb unsichtbar — Session wäre für immer 'running' geblieben: {events}"
    )
    assert "kaputte Usage-Datei" in error_events[-1].raw.get("message", "")
