"""PROJ-19 (#26) — billige Späher-Agenten.

Deckt Kontext-Sammlung (RAG + Datei-Pointer), Prompt-Bau, Eskalations-Hinweis bei
dünnem Fazit und den Endpunkt (inkl. Feature-Flag) mit einem injizierten Fake-Runner
ab — kein echter ``claude``-Subprozess.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.engine.scout import ScoutService
from app.engine.vault import VaultService
from app.routes import agents as agents_route
from app.schemas.agents import ScoutResult


@pytest.fixture
def vault(tmp_path) -> VaultService:
    (tmp_path / "Agentic OS" / "Jupiter" / "Knowledge").mkdir(parents=True)
    (tmp_path / "notes.md").write_text(
        "Recovery RLS Bug: ausführliche Analyse des Problems. " * 5, encoding="utf-8"
    )
    return VaultService(vault_root=str(tmp_path), jupiter_subdir="Agentic OS/Jupiter")


def _capture_runner(box: dict):
    async def runner(prompt: str, model: str, cwd: str) -> str:
        box["prompt"] = prompt
        box["model"] = model
        return "Fazit: RLS-Bug liegt in der Recovery-Policy."
    return runner


@pytest.mark.asyncio
async def test_scout_uses_rag_context_and_cheap_model(vault) -> None:
    box: dict = {}
    svc = ScoutService(vault, runner=_capture_runner(box))
    res = await svc.scout(task="Wo ist der RLS-Bug?", query="RLS Recovery Bug")
    assert res.model_used == "haiku"  # günstiges Default-Modell
    assert "notes.md" in res.sources  # RAG-Kontext herangezogen
    assert "Kontext:" in box["prompt"] and "notes.md" in box["prompt"]
    assert res.usable is True
    assert res.summary.startswith("Fazit")


@pytest.mark.asyncio
async def test_scout_reads_explicit_path_pointers(vault) -> None:
    box: dict = {}
    svc = ScoutService(vault, runner=_capture_runner(box))
    res = await svc.scout(task="Fasse zusammen", paths=["notes.md", "fehlt.md"])
    assert res.sources == ["notes.md"]  # fehlender Pointer übersprungen, kein Hard-Fail


@pytest.mark.asyncio
async def test_scout_model_override_for_escalation(vault) -> None:
    box: dict = {}
    svc = ScoutService(vault, runner=_capture_runner(box))
    await svc.scout(task="x", model="opus")
    assert box["model"] == "opus"


@pytest.mark.asyncio
async def test_scout_thin_result_flags_escalation(vault) -> None:
    async def thin(prompt: str, model: str, cwd: str) -> str:
        return "ok"  # < _MIN_USABLE_CHARS
    svc = ScoutService(vault, runner=thin)
    res = await svc.scout(task="x", query="RLS")
    assert res.usable is False
    assert res.note and "größerem modell" in res.note.lower()


# --- Endpunkt ---------------------------------------------------------------

def _app(vault) -> FastAPI:
    app = FastAPI()

    async def runner(prompt: str, model: str, cwd: str) -> str:
        return "Fazit: alles klar und ausreichend lang."

    app.state.scout = ScoutService(vault, runner=runner)
    app.include_router(agents_route.router)
    return app


def test_endpoint_scout(vault) -> None:
    client = TestClient(_app(vault))
    resp = client.post("/agents/scout", json={"task": "Wo ist der Bug?", "query": "RLS"})
    assert resp.status_code == 200
    data = ScoutResult.model_validate(resp.json())
    assert data.usable is True
    assert data.model_used == "haiku"


def test_endpoint_scout_disabled(monkeypatch, vault) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "scout_enabled", False)
    client = TestClient(_app(vault))
    resp = client.post("/agents/scout", json={"task": "x"})
    assert resp.status_code == 503
