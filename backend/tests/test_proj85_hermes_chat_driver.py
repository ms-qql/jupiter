"""Regressionstest — HermesChatDriver.send_input darf den ersten getippten Text
NICHT verwerfen, wenn die Session noch auf die Erst-Eingabe wartet
(_awaiting_first_input). Bug: der erste Turn wurde aus dem alten, noch leeren
LaunchSpec gespawnt (`-z ""`), statt aus einem neuen Spec mit dem echten Text —
Hermes bekam einen leeren Prompt, der Text ging verloren.
"""
from __future__ import annotations

import pytest

from app.engine.base import LaunchSpec
from app.engine.hermes_chat_driver import HermesChatDriver
from app.engine.registry import EngineProfile


class _Profile(EngineProfile):
    pass


@pytest.mark.anyio
async def test_first_send_input_uses_typed_text_not_empty_prompt(monkeypatch):
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
    # Vorher (Bug): argv enthielt "-z", "" — der Text landete nirgends.
    z_index = argv.index("-z")
    assert argv[z_index + 1] == "Hallo Hermes, bitte X tun"
