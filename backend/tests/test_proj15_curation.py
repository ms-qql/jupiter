"""PROJ-15 — Vault Stufe 3: lebendes Gehirn, roh↔kuratiert, Kuratierung.

Deckt ab: Marker-Erkennung (curation), kuratierte Vault-Schicht (Knowledge/) inkl.
Append-Dedup + scoped Suche, der nicht-blockierende Wissens-Vorschlags-Flow im
Manager (Trigger/Entprellung/Freigeben/Editieren/Verwerfen, Vault-Fehler hält die
Card offen, Eingabe nie gesperrt) und der REST-Vertrag. Alles mit FakeDriver.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine import curation
from app.engine.events import StreamEvent
from app.engine.manager import AWAITING_APPROVAL, SessionManager
from app.engine.vault import VaultService
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"
_USAGE = {
    "input_tokens": 50, "output_tokens": 5,
    "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
}


def _assistant(text: str) -> StreamEvent:
    return StreamEvent(
        "assistant", None,
        {"message": {"content": [{"type": "text", "text": text}], "usage": _USAGE}},
    )


# --- Marker-Erkennung (reine Funktion) -------------------------------------

@pytest.mark.parametrize(
    "text,kind",
    [
        ("Der Bug behoben, jetzt grün.", "bug_geloest"),
        ("Wir haben uns entschieden: Postgres.", "adr"),
        ("Das war eine Sackgasse, Ansatz verworfen.", "sackgasse"),
    ],
)
def test_detect_marker_kinds(text, kind):
    m = curation.detect_marker(text)
    assert m is not None and m.kind == kind


def test_detect_marker_none_on_neutral_text():
    assert curation.detect_marker("Ich lese gerade die Datei.") is None
    assert curation.detect_marker("") is None


def test_build_proposal_is_pointer_not_fulltext():
    m = curation.detect_marker("bug behoben")
    title, body = curation.build_proposal(m, "x" * 5000, project_name="jupiter", session_id="abcd1234ef")
    assert "jupiter" in title and m.label in title
    assert "gekürzt" in body  # Auszug gekappt → kein Volltext
    assert "abcd1234" in body  # Quell-Pointer auf die Session


# --- Kuratierte Vault-Schicht (Knowledge/) ---------------------------------

def test_curated_note_lands_in_knowledge_with_frontmatter():
    v = VaultService()
    res = v.write_curated_note(
        title="Bug X — jupiter", body="Erkenntnis eins",
        source_session_id="sess-1234", marker="bug_geloest",
    )
    assert "Knowledge" in res.path and res.type == "curated"
    doc = v.read_file(res.path)
    assert doc["frontmatter"]["type"] == "curated"
    assert doc["frontmatter"]["source_session_id"] == "sess-1234"
    assert doc["frontmatter"]["curation_marker"] == "bug_geloest"
    assert "Erkenntnis eins" in doc["body"]


def test_curated_dedup_appends_same_topic():
    """Gleicher Titel ⇒ gleiche Datei ⇒ Append (Dedup), kein blindes Überschreiben."""
    v = VaultService()
    r1 = v.write_curated_note(title="Thema A — jupiter", body="erste Erkenntnis")
    r2 = v.write_curated_note(title="Thema A — jupiter", body="zweite Erkenntnis")
    assert r1.path == r2.path
    body = v.read_file(r1.path)["body"]
    assert "erste Erkenntnis" in body and "zweite Erkenntnis" in body


def test_search_curated_is_scoped_to_knowledge():
    v = VaultService()
    v.write(type="session_log", body="geheime rohdaten", title="roh", session_id="s1")
    v.write_curated_note(title="Kuratiert — jupiter", body="kuratierter befund")
    # curated-Scope sieht nur Knowledge/:
    assert v.search_curated("geheime rohdaten") == []
    assert any("befund" in h["excerpt"] for h in v.search_curated("kuratierter"))
    # all-Scope sieht beides:
    assert any("rohdaten" in h["excerpt"] for h in v.search("geheime rohdaten"))


# --- Manager: nicht-blockierender Vorschlags-Flow --------------------------

async def _session(vault: VaultService | None = None):
    mgr = SessionManager(driver_factory=FakeDriver, vault=vault or VaultService())
    runtime = await mgr.create(project_path=PROJECT, initial_prompt="hallo", model="haiku")
    return mgr, runtime


@pytest.mark.asyncio
async def test_marker_creates_nonblocking_proposal():
    mgr, rt = await _session()
    await rt.handle_event(_assistant("Der Bug behoben, alle Tests grün."))
    cards = [c for c in rt.pending.values() if c.card_type == "knowledge_proposal"]
    assert len(cards) == 1
    assert rt.state.status != AWAITING_APPROVAL  # blockiert NICHT
    assert cards[0].proposal_title and cards[0].proposal_body


@pytest.mark.asyncio
async def test_debounce_one_proposal_per_marker_kind():
    mgr, rt = await _session()
    await rt.handle_event(_assistant("Bug behoben."))
    await rt.handle_event(_assistant("Fehler behoben."))  # gleiche Art → kein zweiter
    cards = [c for c in rt.pending.values() if c.card_type == "knowledge_proposal"]
    assert len(cards) == 1


@pytest.mark.asyncio
async def test_input_not_blocked_by_proposal():
    mgr, rt = await _session()
    await rt.handle_event(_assistant("Bug behoben."))
    sid = rt.state.session_id
    await mgr.send_input(sid, "weiter so")  # darf NICHT werfen (Kuratierung blockiert nie)


@pytest.mark.asyncio
async def test_approve_writes_curated_note_edited():
    v = VaultService()
    mgr, rt = await _session(v)
    await rt.handle_event(_assistant("Wir haben uns entschieden: Single-Worker."))
    card = next(c for c in rt.pending.values() if c.card_type == "knowledge_proposal")
    mgr.resolve_decision(
        rt.state.session_id, card.decision_id, approve=True,
        edited_title="ADR Worker — jupiter", edited_body="Endgültig: ein Worker.",
    )
    hits = v.search_curated("Endgültig: ein Worker")
    assert hits and "Knowledge" in hits[0]["path"]
    assert card.decision_id not in rt.pending  # aufgelöst


@pytest.mark.asyncio
async def test_deny_writes_nothing():
    v = VaultService()
    mgr, rt = await _session(v)
    await rt.handle_event(_assistant("Sackgasse — verworfen."))
    card = next(c for c in rt.pending.values() if c.card_type == "knowledge_proposal")
    mgr.resolve_decision(rt.state.session_id, card.decision_id, approve=False)
    assert v.search_curated("Sackgasse") == []
    assert card.decision_id not in rt.pending


@pytest.mark.asyncio
async def test_vault_failure_keeps_card_open():
    v = VaultService()
    mgr, rt = await _session(v)
    await rt.handle_event(_assistant("Bug behoben."))
    card = next(c for c in rt.pending.values() if c.card_type == "knowledge_proposal")

    def _boom(**_kw):
        raise OSError("Vault nicht beschreibbar")

    v.write_curated_note = _boom  # type: ignore[method-assign]
    with pytest.raises(OSError):
        mgr.resolve_decision(rt.state.session_id, card.decision_id, approve=True)
    assert card.decision_id in rt.pending and card.state == "open"  # kein Verlust


# --- REST-Vertrag (End-to-End über echo → Marker) --------------------------

def test_api_proposal_approve_and_curated_search():
    client = TestClient(create_app(driver_factory=FakeDriver))
    with client:
        sid = client.post("/sessions", json={
            "project_path": PROJECT, "initial_prompt": "start", "model": "haiku",
        }).json()["session_id"]
        # Echo der Eingabe enthält den Marker → Vorschlag entsteht.
        client.post(f"/sessions/{sid}/input", json={"text": "bug behoben: der fix sitzt"})
        detail = client.get(f"/sessions/{sid}").json()
        props = [c for c in detail["pending_decisions"] if c["card_type"] == "knowledge_proposal"]
        assert len(props) == 1
        did = props[0]["decision_id"]

        r = client.post(f"/sessions/{sid}/decisions/{did}", json={
            "decision": "approve", "edited_body": "Kuratiert via API: Fix dokumentiert.",
        })
        assert r.status_code == 202

        hits = client.get("/vault/search", params={"q": "Kuratiert via API", "scope": "curated"}).json()
        assert hits["hits"] and "Knowledge" in hits["hits"][0]["path"]


def test_api_search_all_vs_curated_scope():
    client = TestClient(create_app(driver_factory=FakeDriver))
    with client:
        client.post("/vault/files", json={
            "type": "curated", "body": "scoped wissen alpha", "title": "Scope-Test — jupiter",
        })
        curated = client.get("/vault/search", params={"q": "scoped wissen alpha", "scope": "curated"}).json()
        assert curated["hits"]
        bad = client.get("/vault/search", params={"q": "x", "scope": "bogus"})
        assert bad.status_code == 422  # ungültiger scope


# --- QA-Härtung (Red-Team + Nachvollziehbarkeit) ---------------------------

def test_qa_curated_frontmatter_has_owner_and_created():
    """AC: Schreibvorgänge nachvollziehbar (owner + Zeitstempel)."""
    v = VaultService()
    res = v.write_curated_note(title="Nachweis — jupiter", body="x", owner="dev", source_session_id="s9")
    fm = v.read_file(res.path)["frontmatter"]
    assert fm["owner"] == "dev" and fm["created"] and fm["type"] == "curated"


def test_qa_curated_title_traversal_stays_in_knowledge():
    """Red-Team: bösartiger Titel (../) bricht NICHT aus dem Knowledge-Baum aus."""
    v = VaultService()
    res = v.write_curated_note(title="../../etc/passwd", body="x")
    assert "/Knowledge/" in f"/{res.path}" and ".." not in res.path
    assert v.read_file(res.path)["frontmatter"]["type"] == "curated"


def test_qa_curated_title_yaml_injection_safe():
    """Red-Team: YAML-Breakout im Titel überschreibt kein Frontmatter-Feld."""
    v = VaultService()
    res = v.write_curated_note(title='x"\nowner: hacker\nfoo: bar', body="b", owner="dev")
    fm = v.read_file(res.path)["frontmatter"]
    assert fm["owner"] == "dev" and "hacker" not in str(fm.get("owner"))


@pytest.mark.asyncio
async def test_qa_double_resolve_knowledge_raises():
    """Edge: ein bereits entschiedener Vorschlag ist weg → erneutes Auflösen 404 (KeyError)."""
    v = VaultService()
    mgr, rt = await _session(v)
    await rt.handle_event(_assistant("Bug behoben."))
    card = next(c for c in rt.pending.values() if c.card_type == "knowledge_proposal")
    mgr.resolve_decision(rt.state.session_id, card.decision_id, approve=False)
    with pytest.raises(KeyError):
        mgr.resolve_decision(rt.state.session_id, card.decision_id, approve=False)


@pytest.mark.asyncio
async def test_qa_curation_toggle_off_suppresses_proposals(monkeypatch):
    """Toggle: enable_curation=False → kein Marker-Scan (wie vor PROJ-15)."""
    monkeypatch.setattr(settings, "enable_curation", False)
    mgr, rt = await _session()
    await rt.handle_event(_assistant("Bug behoben — ADR getroffen — Sackgasse."))
    assert not [c for c in rt.pending.values() if c.card_type == "knowledge_proposal"]


@pytest.mark.asyncio
async def test_qa_blocking_card_still_blocks_input_regression():
    """Regression: echte (blockierende) Cards sperren die Eingabe weiterhin (PROJ4-QA-1)."""
    from app.engine.decisions import PendingDecision

    mgr, rt = await _session()
    rt.pending["x"] = PendingDecision(
        decision_id="x", session_id=rt.state.session_id, tool_name="Bash",
        action="a", excerpt="e", rationale="r", context={}, created_at="t",
        card_type="normal",
    )
    rt._futures["x"] = __import__("asyncio").get_event_loop().create_future()
    with pytest.raises(RuntimeError):
        await mgr.send_input(rt.state.session_id, "darf nicht durch")
