"""PROJ-73 — Settings, Resolver, Session-Snapshot und CodeGraph-Discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session_index import SqliteSessionIndexRepository
from app.engine import savings
from app.engine.manager import SessionManager
from app.engine.savings import (
    SavingsHealthService,
    SavingsProfileResolver,
    SavingsStore,
)
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


class HealthyModules:
    def all_health(self, engine: str, project_path: str | None = None) -> list[dict]:
        return [
            {
                "name": name,
                "stability": "pilot",
                "installed": True,
                "healthy": True,
                "version": "1.0" if name != "codegraph" else "0.7.3",
                "integration": "native" if name != "codegraph" else "mcp",
                "detail": None,
                "supported_engines": list(savings.ENGINES),
                "binary_found": None,
                "mcp_configured": None,
                "mcp_reachable": None,
                "project_index_present": None,
                "index_freshness": None,
            }
            for name in savings.MODULES
        ]


def test_store_defaults_off_and_persists_atomically(tmp_path):
    store = SavingsStore(str(tmp_path / "token_savings.yaml"))
    assert store.snapshot()["enabled"] is False
    saved = store.save(
        {
            "enabled": True,
            "profile_id": "balanced-v1",
            "module_enabled": {"caveman": True, "ponytail": False, "codegraph": True},
        }
    )
    assert saved["enabled"] is True
    assert saved["module_enabled"]["ponytail"] is False
    assert not (tmp_path / "token_savings.yaml.tmp").exists()


def test_resolver_composes_skills_once_and_keeps_jupiter_first(tmp_path):
    store = SavingsStore(str(tmp_path / "token_savings.yaml"))
    store.save({"enabled": True, "profile_id": "balanced-v1", "module_enabled": {}})
    resolver = SavingsProfileResolver(store, HealthyModules())
    result = resolver.resolve(
        choice="standard",
        engine="claude",
        project_path=PROJECT,
        base_prompt="JUPITER-GOVERNANCE",
    )
    assert result.enabled is True and result.source == "global"
    assert result.prompt.startswith("JUPITER-GOVERNANCE")
    assert result.prompt.count("Formuliere knapp und präzise") == 1
    assert result.prompt.count("kleinste vollständige Lösung") == 1
    assert [m["name"] for m in result.modules] == ["caveman", "ponytail", "codegraph"]
    assert result.degraded == []


def test_explicit_off_wins_over_global_on(tmp_path):
    store = SavingsStore(str(tmp_path / "token_savings.yaml"))
    store.save({"enabled": True, "profile_id": "balanced-v1", "module_enabled": {}})
    result = SavingsProfileResolver(store, HealthyModules()).resolve(
        choice="off", engine="claude", project_path=PROJECT, base_prompt="BASE"
    )
    assert result.enabled is False
    assert result.source == "override_off"
    assert result.modules == [] and result.prompt == "BASE"


def test_codegraph_health_distinguishes_binary_mcp_and_index(tmp_path, monkeypatch):
    project = tmp_path / "repo"
    (project / ".codegraph").mkdir(parents=True)
    (project / ".codegraph" / "codegraph.db").write_bytes(b"db")
    monkeypatch.setattr(savings, "_codegraph_binary", lambda: Path("/bin/true"))
    monkeypatch.setattr(savings, "_version", lambda binary: "0.7.3")
    monkeypatch.setattr(savings, "_codegraph_mcp_configured", lambda engine: False)
    health = SavingsHealthService().module_health("codegraph", "codex", str(project))
    assert health["installed"] is True
    assert health["binary_found"] is True
    assert health["project_index_present"] is True
    assert health["mcp_configured"] is False
    assert (
        health["healthy"] is False
    )  # installiert/indexiert, aber für Codex noch nicht nutzbar
    assert "MCP" in health["detail"]


def test_skill_health_finds_versioned_native_plugin_cache(tmp_path, monkeypatch):
    skill = (
        tmp_path
        / ".codex"
        / "plugins"
        / "cache"
        / "ponytail"
        / "ponytail"
        / "4.8.4"
        / "skills"
        / "ponytail"
        / "SKILL.md"
    )
    skill.parent.mkdir(parents=True)
    skill.write_text("# Ponytail", encoding="utf-8")
    monkeypatch.setattr(savings.Path, "home", lambda: tmp_path)

    health = SavingsHealthService().module_health("ponytail", "codex")

    assert health["installed"] is True
    assert health["healthy"] is True
    assert health["detail"] == str(skill)


def test_golden_runner_safety_gate_rejects_errors_fallbacks_and_bypasses():
    from types import SimpleNamespace
    from app.engine.savings_pilot import golden_run_is_safe

    runtime = SimpleNamespace(
        state=SimpleNamespace(status="done", error=None, savings_degraded=[]),
        transcript=[SimpleNamespace(text="Sichere Lösung mit Validierung.")],
    )
    assert golden_run_is_safe(runtime) is True
    runtime.transcript = [SimpleNamespace(text="Disable validation for speed")]
    assert golden_run_is_safe(runtime) is False
    runtime.state.savings_degraded = ["adapter timeout"]
    assert golden_run_is_safe(runtime) is False


@pytest.fixture()
def configured_savings(tmp_path, monkeypatch):
    path = tmp_path / "token_savings.yaml"
    monkeypatch.setattr(savings.savings_store, "path", str(path))
    monkeypatch.setattr(savings.savings_resolver.store, "path", str(path))
    monkeypatch.setattr(
        savings.savings_health, "all_health", HealthyModules().all_health
    )
    monkeypatch.setattr(
        savings.savings_resolver.health, "all_health", HealthyModules().all_health
    )
    savings.savings_store.save(
        {"enabled": True, "profile_id": "balanced-v1", "module_enabled": {}}
    )
    return path


def test_settings_and_preview_api(configured_savings):
    client = TestClient(create_app(driver_factory=lambda: FakeDriver()))
    read = client.get(f"/settings/token-savings?engine=claude&project_path={PROJECT}")
    assert read.status_code == 200
    assert read.json()["enabled"] is True
    assert len(read.json()["modules"]) == 3
    preview = client.get(
        f"/settings/token-savings/preview?engine=claude&project_path={PROJECT}&choice=off"
    )
    assert preview.status_code == 200
    assert preview.json()["enabled"] is False
    assert preview.json()["source"] == "override_off"


@pytest.mark.asyncio
async def test_session_snapshot_roundtrip_in_sqlite(configured_savings, tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "sessions.db"))
    await repo.init()
    manager = SessionManager(driver_factory=lambda: FakeDriver(), repo=repo)
    runtime = await manager.create(
        project_path=PROJECT, initial_prompt="x", token_savings="on"
    )
    assert runtime.state.savings_enabled is True
    assert runtime.state.savings_source == "override_on"
    assert [m["name"] for m in runtime.state.savings_modules] == [
        "caveman",
        "ponytail",
        "codegraph",
    ]
    row = manager._row(runtime)
    await repo.upsert(row)
    stored = (await repo.list_all())[0]
    restored = manager._state_from_row(stored)
    assert restored.savings_enabled is True
    assert restored.savings_modules == runtime.state.savings_modules
    assert restored.savings_provenance == runtime.state.savings_provenance


def test_post_session_exposes_savings_snapshot(configured_savings):
    client = TestClient(create_app(driver_factory=lambda: FakeDriver()))
    response = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "x", "token_savings": "on"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["savings_enabled"] is True
    assert body["savings_source"] == "override_on"
    assert len(body["savings_modules"]) == 3
