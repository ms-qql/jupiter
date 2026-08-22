"""Regressionstests — HermesChatDriver (PROJ-86) über den direkten `hermes chat`-Vertrag.

Deckt ab: getippte Nachricht landet in `-q` (nicht `-z`), Erst- und Folge-Turn
nutzen denselben `--continue`-Namen, Hermes-Metazeilen werden abgefangen, und eine
Reader-Exception hängt die Session nicht für immer.
"""
from __future__ import annotations

import asyncio
import os
import stat
import tempfile

import pytest

from app.engine.base import LaunchSpec
from app.engine.hermes_chat_driver import HermesChatDriver
from app.engine.registry import EngineProfile


def _write_fake_hermes(tmp_path, *, resume_ref: str = "hermes-ref-xyz", fail: bool = False) -> str:
    """Shell-Stub im `hermes chat -q`-Vertrag.

    - Druckt Assistant-Text + genau eine `session_id:`-Kontrollzeile auf stdout.
    - Bei `--resume <id>` wird eine andere Ref zurückgegeben (Folge-Turn erkennbar).
    - ``fail=True``: bricht mit stderr + Exit 1 OHNE Kontrollzeile ab (abgelehntes Resume).
    """
    script = tmp_path / "fake_hermes.sh"
    script.write_text(
        "#!/bin/bash\n"
        "ref=\"" + resume_ref + "\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--resume\" ]]; then ref=\"RESUMED-$2\"; fi\n"
        "  shift\n"
        "done\n"
        "if [[ \"" + ("1" if fail else "0") + "\" == \"1\" ]]; then\n"
        "  echo 'Hermes: resume abgelehnt (unbekannt)' >&2\n"
        "  exit 1\n"
        "fi\n"
        "echo 'Hallo vom Fake-Hermes'\n"
        "sleep 0.2\n"
        "echo \"session_id: $ref\"\n"
        "exit 0\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


@pytest.mark.anyio
async def test_first_input_creates_named_session(monkeypatch):
    """Erster Turn: Text in `-q`, legt genau die benannte Session an."""
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
    assert "-z" not in argv, f"Hermes darf nicht -z (One-Shot) nutzen: {argv}"
    q_index = argv.index("-q")
    assert argv[q_index + 1] == "Hallo Hermes, bitte X tun"
    assert "--resume" not in argv, f"Erst-Turn darf kein --resume tragen: {argv}"
    assert argv[argv.index("--continue") + 1] == "jupiter-s1"
    assert "--create-if-missing" in argv


@pytest.mark.anyio
async def test_follow_up_turn_uses_stable_session_name(monkeypatch):
    """Folge-Turn: derselbe benannte Hermes-Chat, ohne stdout-Resume-ID."""
    profile = EngineProfile(
        key="hermes", label="Hermes (Agent)", kind="engine", driver="generic_cli",
        models=["qwen3.5-397b-a17b"], bin="hermes",
    )
    driver = HermesChatDriver(profile, provider="anthropic", model="claude-fable-5")
    driver._spec = LaunchSpec(
        session_id="s1", project_path="/home/dev/projects", model="fable",
        permission_mode="bypassPermissions", initial_prompt="",
    )
    driver._resume_ref = "jupiter-s1"
    captured: dict[str, list[str]] = {}

    async def fake_spawn(argv, cwd, *, prompt=None):
        captured["argv"] = argv

    monkeypatch.setattr(driver, "_spawn", fake_spawn)

    await driver.send_input("Und jetzt weiter")

    argv = captured["argv"]
    assert "--resume" not in argv
    assert argv[argv.index("--continue") + 1] == "jupiter-s1"
    assert "--create-if-missing" not in argv


@pytest.mark.anyio
async def test_three_follow_up_turns_keep_stable_session_name(monkeypatch):
    profile = EngineProfile(
        key="hermes", label="Hermes (Agent)", kind="engine", driver="generic_cli",
        models=["qwen3.5-397b-a17b"], bin="hermes",
    )
    driver = HermesChatDriver(profile, provider="anthropic", model="claude-fable-5")
    driver._spec = LaunchSpec(
        session_id="s1", project_path="/home/dev/projects", model="fable",
        permission_mode="bypassPermissions", initial_prompt="",
    )
    driver._resume_ref = "jupiter-s1"
    captured: list[list[str]] = []

    async def fake_spawn(argv, cwd, *, prompt=None):
        captured.append(argv)

    monkeypatch.setattr(driver, "_spawn", fake_spawn)

    for text in ("Weiter 1", "Weiter 2", "Weiter 3"):
        await driver.send_input(text)

    assert all(argv[argv.index("--continue") + 1] == "jupiter-s1" for argv in captured)
    assert all("--create-if-missing" not in argv for argv in captured)


@pytest.mark.anyio
async def test_clean_turn_emits_waiting_without_id_dependency(tmp_path):
    """Sauberes Turn-Ende → waiting, unabhängig von der stdout-ID."""
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

    no_final_result = [
        e for e in events
        if e.type == "system" and e.subtype == "closed" and e.raw.get("reason") == "no_final_result"
    ]
    assert not no_final_result, f"Fälschlich als abgebrochen gemeldet: {events}"
    waiting = [e for e in events if e.type == "system" and e.subtype == "waiting"]
    assert waiting, f"Erfolgreicher Turn muss in waiting enden: {events}"
    assert driver.resume_id == "jupiter-s1"


@pytest.mark.anyio
async def test_control_line_not_shown_as_assistant_text(tmp_path):
    """Die `session_id:`-Zeile darf NICHT als Assistant-Nachricht erscheinen."""
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
        permission_mode="bypassPermissions", initial_prompt="Hallo",
    )
    await driver.start(spec, on_event)
    await asyncio.wait_for(driver._reader_task, timeout=5)
    if driver._stderr_task is not None:
        driver._stderr_task.cancel()

    assistant_texts = [
        e.raw.get("message", {}).get("content", [{}])[0].get("text", "")
        for e in events if e.type == "assistant"
    ]
    assert all("session_id:" not in t for t in assistant_texts), (
        f"Kontrollzeile als Chat-Text durchgeschlüpft: {assistant_texts}"
    )
    assert driver._intercept_line("↻ Resumed session test") is True


@pytest.mark.anyio
async def test_missing_control_line_still_completes_named_turn(tmp_path):
    """Der benannte Chat benötigt keine stdout-`session_id`."""
    script = tmp_path / "fake_hermes.sh"
    script.write_text(
        "#!/bin/bash\n"
        "echo 'Hallo ohne Ref'\n"
        "exit 0\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    profile = EngineProfile(
        key="hermes", label="Hermes (Agent)", kind="engine", driver="generic_cli",
        models=["qwen3.5-397b-a17b"], bin=str(script),
    )
    driver = HermesChatDriver(profile, provider="anthropic", model="claude-fable-5")

    events: list = []

    async def on_event(event):
        events.append(event)

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="fable",
        permission_mode="bypassPermissions", initial_prompt="Hallo",
    )
    await driver.start(spec, on_event)
    await asyncio.wait_for(driver._reader_task, timeout=5)
    if driver._stderr_task is not None:
        driver._stderr_task.cancel()

    assert not [e for e in events if e.type == "system" and e.subtype == "error"]
    assert [e for e in events if e.type == "system" and e.subtype == "waiting"]


@pytest.mark.anyio
async def test_rejected_resume_is_error(tmp_path):
    """Resume abgelehnt (rc != 0, keine ID) → deutscher Fehler + Hermes-Ursache."""
    profile = EngineProfile(
        key="hermes", label="Hermes (Agent)", kind="engine", driver="generic_cli",
        models=["qwen3.5-397b-a17b"], bin=_write_fake_hermes(tmp_path, fail=True),
    )
    driver = HermesChatDriver(profile, provider="anthropic", model="claude-fable-5")
    driver._spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="fable",
        permission_mode="bypassPermissions", initial_prompt="",
    )
    driver._resume_ref = "veraltet-123"

    events: list = []

    async def on_event(event):
        events.append(event)

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="fable",
        permission_mode="bypassPermissions", initial_prompt="Weiter",
    )
    await driver.start(spec, on_event)  # kein awaiting_first_input → Folge-Turn
    await asyncio.wait_for(driver._reader_task, timeout=5)
    if driver._stderr_task is not None:
        driver._stderr_task.cancel()

    errors = [e for e in events if e.type == "system" and e.subtype == "error"]
    assert errors, f"Abgelehntes Resume muss einen Fehler geben: {events}"
    assert "Hermes-Fortsetzung fehlgeschlagen" in errors[-1].raw.get("message", "")
    assert driver._resume_ref is None  # Benannter Chat verwendet keine Resume-ID.


@pytest.mark.anyio
async def test_reader_exception_does_not_hang_session_forever(tmp_path, monkeypatch):
    """Eine Ausnahme im Nachlauf (nach Prozessende) darf die Reader-Task nicht
    lautlos sterben lassen — sie muss ein sichtbares `system/error` erzeugen."""
    profile = EngineProfile(
        key="hermes", label="Hermes (Agent)", kind="engine", driver="generic_cli",
        models=["qwen3.5-397b-a17b"], bin=_write_fake_hermes(tmp_path),
    )
    driver = HermesChatDriver(profile, provider="anthropic", model="claude-fable-5")

    def boom(rc):
        raise RuntimeError("kaputte Kontrollzeile (simuliert)")

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
    for _ in range(50):
        if driver._reader_task.done():
            break
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.05)
    if driver._stderr_task is not None:
        driver._stderr_task.cancel()

    error_events = [e for e in events if e.type == "system" and e.subtype == "error"]
    assert error_events, f"Reader-Exception blieb unsichtbar: {events}"
    assert "kaputte Kontrollzeile" in error_events[-1].raw.get("message", "")
