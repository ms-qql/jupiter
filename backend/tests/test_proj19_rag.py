"""PROJ-19 (#23) — Pointer/RAG über den Vault.

Deckt die Term-Zerlegung, das dichteste Fenster, das Relevanz-Ranking, die
Kontext-Ersparnis-Messung + Fallback sowie den Endpunkt ab.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.engine.vault import VaultService, _best_window, _rag_terms
from app.routes import vault as vault_route
from app.schemas.vault import VaultRagPreview


def _write(root, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def vault(tmp_path) -> VaultService:
    # Jupiter-Schreibbereich muss existieren (write_root).
    (tmp_path / "Agentic OS" / "Jupiter" / "Knowledge").mkdir(parents=True)
    return VaultService(vault_root=str(tmp_path), jupiter_subdir="Agentic OS/Jupiter")


# --- reine Helfer -----------------------------------------------------------

def test_rag_terms_filters_stopwords_and_short() -> None:
    assert _rag_terms("Wie ist der RLS Bug im Recovery") == ["rls", "bug", "recovery"]
    assert _rag_terms("der die das") == []


def test_best_window_picks_densest_region() -> None:
    text = "x" * 100 + "alpha beta" + "y" * 500 + "alpha beta gamma alpha"
    start, count = _best_window(text.lower(), ["alpha", "beta", "gamma"], 80)
    # Das dichtere zweite Cluster (4 Treffer) gewinnt → Start liegt im hinteren Bereich.
    assert start > 400
    assert count >= 3


# --- relevant_snippets ------------------------------------------------------

def test_relevant_snippets_ranks_by_terms_matched(vault, tmp_path) -> None:
    root = tmp_path
    _write(root, "a.md", "Recovery und RLS Bug treffen hier zusammen. " * 3)
    _write(root, "b.md", "Hier geht es nur um Recovery, sonst nichts.")
    _write(root, "c.md", "Völlig anderes Thema ohne Bezug.")
    out = vault.relevant_snippets("RLS Recovery Bug", top_n=5)
    assert [s["path"] for s in out][:2] == ["a.md", "b.md"]  # a trifft mehr Begriffe
    assert out[0]["terms_matched"] == 3
    assert "c.md" not in [s["path"] for s in out]


def test_relevant_snippets_empty_on_no_match(vault, tmp_path) -> None:
    _write(tmp_path, "a.md", "Nichts Relevantes.")
    assert vault.relevant_snippets("xyzzy quux", top_n=5) == []


# --- rag_preview (Messung + Fallback) ---------------------------------------

def test_rag_preview_measures_reduction(vault, tmp_path) -> None:
    _write(tmp_path, "big.md", "Intro. " * 200 + " RLS Bug Detail " + "Outro. " * 200)
    res = vault.rag_preview("RLS Bug", top_n=3)
    assert res["fallback"] is False
    assert res["context_chars"] < res["fulltext_chars"]  # Snippet < Volltext
    assert res["reduction_pct"] > 0


def test_rag_preview_fallback(vault, tmp_path) -> None:
    _write(tmp_path, "a.md", "Nichts dazu.")
    res = vault.rag_preview("nichtvorhanden", top_n=3)
    assert res["fallback"] is True
    assert res["reason"]
    assert res["snippets"] == []


# --- Endpunkt ---------------------------------------------------------------

def test_endpoint_rag_preview(vault, tmp_path) -> None:
    _write(tmp_path, "a.md", "Recovery RLS Bug ausführlich beschrieben. " * 5)
    app = FastAPI()
    app.state.vault = vault
    app.include_router(vault_route.router)
    client = TestClient(app)

    resp = client.get("/vault/rag/preview", params={"q": "RLS Bug", "top_n": 3})
    assert resp.status_code == 200
    data = VaultRagPreview.model_validate(resp.json())
    assert data.snippets and data.snippets[0].path == "a.md"
    assert data.fallback is False
