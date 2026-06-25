"""PROJ-22 — Multi-Agent-Dispatch-Schicht + Vertrag-zuerst/Koordinator.

Deckt die Acceptance Criteria ab:
- Verteilungsplan aus features/INDEX.md (Topo-Sort über die Abhängigkeiten-Spalte,
  blocked-Markierung, zirkuläre/fehlende Abhängigkeit als Warnung).
- Dispatch in eine Flotte (Koordinator + Kind-Sessions mit ticket_id +
  parent_coordinator_id), Eltern-Kind im Live-Index sichtbar.
- Live-Sicht, Pause, manuelle Umverteilung, API-Vertrag als Vault-Pointer.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.coordinator import CoordinatorService, build_plan
from app.engine.manager import SessionManager
from app.engine.policy import DENY, PolicyDecision, policy_store
from app.engine.vault import VaultService
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _write_index(tmp_path, body: str) -> str:
    """Legt ein Projekt mit features/INDEX.md unter tmp an, gibt den Projektpfad zurück."""
    proj = tmp_path / "proj"
    (proj / "features").mkdir(parents=True)
    (proj / "features" / "INDEX.md").write_text(body, encoding="utf-8")
    return str(proj)


_HEADER = "| ID | Feature | Prio | Status | Abhängigkeiten | Spec |\n|----|----|----|----|----|----|\n"


# --- Plan (reine Logik) ----------------------------------------------------

def test_plan_topo_order_und_blocking(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_index(
        tmp_path,
        _HEADER
        + "| PROJ-1 | Auth | P0 | Planned | — | [Spec](a.md) |\n"
        + "| PROJ-2 | Liste | P0 | Planned | PROJ-1 | [Spec](b.md) |\n",
    )
    plan = build_plan(proj)
    items = {it["ticket_id"]: it for it in plan["items"]}
    assert plan["warnings"] == []
    # PROJ-1 ist sofort verteilbar, PROJ-2 wartet auf PROJ-1.
    assert items["PROJ-1"]["order"] == 1 and items["PROJ-1"]["blocked"] is False
    assert items["PROJ-2"]["order"] == 2 and items["PROJ-2"]["blocked"] is True
    assert "PROJ-1" in items["PROJ-2"]["blocked_reason"]
    # Rolle/Skill/Modell aus der abgeleiteten Phase (Planned → architecture).
    assert items["PROJ-1"]["role"] == "architect"
    assert items["PROJ-1"]["skill"] == "abc-architecture"
    assert items["PROJ-1"]["model"] == "opus"
    assert items["PROJ-2"]["dependencies"] == ["PROJ-1"]


def test_plan_excludes_deployed_and_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_index(
        tmp_path,
        _HEADER
        + "| PROJ-1 | Fertig | P0 | Deployed | — | [Spec](a.md) |\n"
        + "| PROJ-2 | Approved-Feat | P0 | Approved | — | [Spec](b.md) |\n"
        + "| PROJ-3 | Offen | P0 | In Progress | — | [Spec](c.md) |\n",
    )
    plan = build_plan(proj)
    ids = {it["ticket_id"] for it in plan["items"]}
    assert ids == {"PROJ-3"}  # deployed + approved fallen raus
    # In Progress → nächste Phase backend.
    assert plan["items"][0]["skill"] == "abc-backend"


def test_plan_missing_dependency_warns_but_not_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_index(
        tmp_path,
        _HEADER + "| PROJ-5 | X | P1 | Planned | PROJ-99 | [Spec](a.md) |\n",
    )
    plan = build_plan(proj)
    assert any("PROJ-99" in w for w in plan["warnings"])
    # Eine UNBEKANNTE Abhängigkeit blockiert nicht (nur Warnung).
    assert plan["items"][0]["blocked"] is False


def test_plan_circular_dependency_warns(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_index(
        tmp_path,
        _HEADER
        + "| PROJ-1 | A | P0 | Planned | PROJ-2 | [Spec](a.md) |\n"
        + "| PROJ-2 | B | P0 | Planned | PROJ-1 | [Spec](b.md) |\n",
    )
    plan = build_plan(proj)
    assert any("zirkul" in w.lower() for w in plan["warnings"])
    assert all(it["blocked"] for it in plan["items"])


def test_plan_no_index_returns_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = tmp_path / "leer"
    proj.mkdir()
    plan = build_plan(str(proj))
    assert plan["items"] == []
    assert plan["warnings"]


def test_plan_path_outside_roots_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    with pytest.raises(ValueError):
        build_plan("/etc")


# --- API -------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    app = create_app(driver_factory=lambda: FakeDriver())
    return TestClient(app)


def _dispatch(client: TestClient, items=None) -> dict:
    items = items or [
        {"ticket_id": "PROJ-1", "title": "Auth", "status": "Planned",
         "role": "backend", "skill": "abc-backend", "engine": "claude",
         "model": "sonnet", "order": 1, "dependencies": [], "blocked": False},
        {"ticket_id": "PROJ-2", "title": "Liste", "status": "Planned",
         "role": "frontend", "skill": "abc-frontend", "engine": "claude",
         "model": "sonnet", "order": 2, "dependencies": [], "blocked": False},
    ]
    resp = client.post("/coordinator/dispatch", json={"project_path": PROJECT, "items": items})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_plan_endpoint(client: TestClient):
    r = client.post("/coordinator/plan", json={"project_path": PROJECT})
    assert r.status_code == 200
    body = r.json()
    assert body["project_path"].endswith("jupiter")
    assert isinstance(body["items"], list)


def test_plan_endpoint_bad_path_400(client: TestClient):
    r = client.post("/coordinator/plan", json={"project_path": "/etc"})
    assert r.status_code == 400


def test_dispatch_creates_fleet(client: TestClient):
    fleet = _dispatch(client)
    coord = fleet["coordinator"]
    assert coord["role"] == "coordinator"
    assert len(fleet["children"]) == 2
    tickets = {c["ticket_id"] for c in fleet["children"]}
    assert tickets == {"PROJ-1", "PROJ-2"}
    for c in fleet["children"]:
        assert c["parent_coordinator_id"] == coord["session_id"]
    # Eltern-Kind im Live-Index (GET /sessions) sichtbar.
    sessions = client.get("/sessions").json()
    by_id = {s["session_id"]: s for s in sessions}
    assert by_id[coord["session_id"]]["child_session_ids"]
    assert set(coord["child_session_ids"]) == {c["session_id"] for c in fleet["children"]}


def test_dispatch_skips_blocked_items(client: TestClient):
    items = [
        {"ticket_id": "PROJ-1", "title": "A", "status": "Planned", "role": "backend",
         "skill": "abc-backend", "engine": "claude", "model": "sonnet", "order": 1,
         "dependencies": [], "blocked": False},
        {"ticket_id": "PROJ-2", "title": "B", "status": "Planned", "role": "frontend",
         "skill": "abc-frontend", "engine": "claude", "model": "sonnet", "order": 2,
         "dependencies": ["PROJ-1"], "blocked": True, "blocked_reason": "wartet"},
    ]
    fleet = _dispatch(client, items)
    assert {c["ticket_id"] for c in fleet["children"]} == {"PROJ-1"}


def test_fleet_endpoint_and_404(client: TestClient):
    fleet = _dispatch(client)
    cid = fleet["coordinator"]["session_id"]
    r = client.get(f"/coordinator/{cid}/fleet")
    assert r.status_code == 200
    assert len(r.json()["children"]) == 2
    # Eine normale Session ist KEIN Koordinator → 404.
    sid = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "hi", "model": "haiku"}
    ).json()["session_id"]
    assert client.get(f"/coordinator/{sid}/fleet").status_code == 404


def test_pause_toggles(client: TestClient):
    cid = _dispatch(client)["coordinator"]["session_id"]
    r = client.post(f"/coordinator/{cid}/pause", json={"paused": True})
    assert r.status_code == 200 and r.json()["paused"] is True
    r = client.post(f"/coordinator/{cid}/pause", json={"paused": False})
    assert r.json()["paused"] is False


def test_reassign_replaces_child(client: TestClient):
    fleet = _dispatch(client)
    cid = fleet["coordinator"]["session_id"]
    old_id = next(c["session_id"] for c in fleet["children"] if c["ticket_id"] == "PROJ-1")
    r = client.post(
        f"/coordinator/{cid}/reassign",
        json={"ticket_id": "PROJ-1", "role": "qa", "engine": "claude"},
    )
    assert r.status_code == 200, r.text
    children = {c["ticket_id"]: c for c in r.json()["children"]}
    # PROJ-1 hat jetzt eine NEUE Kind-Session mit Rolle qa; die alte ist aus der Flotte.
    assert children["PROJ-1"]["session_id"] != old_id
    assert children["PROJ-1"]["role"] == "qa"
    assert "PROJ-2" in children  # andere Kinder unberührt


def test_reassign_unknown_ticket_404(client: TestClient):
    cid = _dispatch(client)["coordinator"]["session_id"]
    r = client.post(f"/coordinator/{cid}/reassign", json={"ticket_id": "PROJ-999"})
    assert r.status_code == 404


# --- Red-Team / Härtung ----------------------------------------------------

def test_mutations_reject_non_coordinator_session(client: TestClient):
    """pause/reassign/contract dürfen NUR auf einer Koordinator-Session greifen —
    eine normale Session (oder eine fremde ID) → 404 (keine Fremd-Steuerung)."""
    sid = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "hi", "model": "haiku"}
    ).json()["session_id"]
    assert client.post(f"/coordinator/{sid}/pause", json={"paused": True}).status_code == 404
    assert client.post(
        f"/coordinator/{sid}/reassign", json={"ticket_id": "PROJ-1"}
    ).status_code == 404
    assert client.post(
        f"/coordinator/{sid}/contract", json={"body": "x"}
    ).status_code == 404
    # Komplett unbekannte ID ebenso.
    assert client.get("/coordinator/nope/fleet").status_code == 404


def test_dispatch_path_outside_roots_400(client: TestClient):
    items = [{"ticket_id": "PROJ-1", "title": "A", "status": "Planned", "role": "backend",
              "skill": "abc-backend", "engine": "claude", "model": "sonnet", "order": 1,
              "dependencies": [], "blocked": False}]
    r = client.post("/coordinator/dispatch", json={"project_path": "/etc", "items": items})
    assert r.status_code == 400


def test_contract_body_too_long_422(client: TestClient):
    from app.config import MAX_INPUT_CHARS

    cid = _dispatch(client)["coordinator"]["session_id"]
    r = client.post(
        f"/coordinator/{cid}/contract",
        json={"body": "x" * (MAX_INPUT_CHARS + 1)},
    )
    assert r.status_code == 422


def test_dispatch_requires_items(client: TestClient):
    """Leerer Plan → 422 (kein Dispatch ohne mindestens ein Ticket)."""
    r = client.post("/coordinator/dispatch", json={"project_path": PROJECT, "items": []})
    assert r.status_code == 422


def test_contract_writes_pointer_to_fleet(client: TestClient):
    fleet = _dispatch(client)
    cid = fleet["coordinator"]["session_id"]
    r = client.post(
        f"/coordinator/{cid}/contract",
        json={"body": "# API-Vertrag\n\nGET /x → {id}", "title": "Vertrag-Test"},
    )
    assert r.status_code == 200, r.text
    pointer = r.json()["path"]
    assert pointer.endswith(".md")
    # Pointer am Koordinator UND an allen Kindern (geteilt, kein Volltext).
    refreshed = client.get(f"/coordinator/{cid}/fleet").json()
    assert refreshed["contract_pointer"] == pointer
    assert refreshed["coordinator"]["contract_pointer"] == pointer
    assert all(c["contract_pointer"] == pointer for c in refreshed["children"])


# --- M1: Dispatch unter der Trust-Policy (PROJ-10) -------------------------

def test_dispatch_denied_by_policy_403(client: TestClient, monkeypatch):
    """Eine deny-Regel auf „Ticket verteilen" untersagt den Dispatch hart (403)."""
    monkeypatch.setattr(
        policy_store,
        "evaluate",
        lambda *a, **k: PolicyDecision(level=DENY, rule="test", reason="verboten"),
    )
    items = [{"ticket_id": "PROJ-1", "title": "A", "status": "Planned", "role": "backend",
              "skill": "abc-backend", "engine": "claude", "model": "sonnet", "order": 1,
              "dependencies": [], "blocked": False}]
    r = client.post("/coordinator/dispatch", json={"project_path": PROJECT, "items": items})
    assert r.status_code == 403
    assert "verboten" in r.json()["detail"]
    # Es darf KEINE Session entstanden sein.
    assert all(s["role"] != "coordinator" for s in client.get("/sessions").json())


# --- M3: Slot-Limit → einreihen + automatisch nachrücken -------------------

@pytest.mark.asyncio
async def test_queue_and_drain(monkeypatch):
    """Bei vollem Engine-Slot werden Resttickets eingereiht (nicht verloren) und vom
    Drain nachgerückt, sobald ein Slot frei wird."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 2)
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    svc = CoordinatorService(mgr, VaultService())
    items = [
        {"ticket_id": f"PROJ-{n}", "title": f"T{n}", "status": "Planned", "role": "backend",
         "skill": "abc-backend", "engine": "claude", "model": "sonnet", "order": n,
         "dependencies": [], "blocked": False}
        for n in (1, 2, 3)
    ]
    fleet = await svc.dispatch(PROJECT, items)
    cid = fleet["coordinator"]["session_id"]
    # Koordinator (1 Slot) + 1 Kind (2 Slots) = Limit → 2 Tickets eingereiht.
    assert len(fleet["children"]) == 1
    assert fleet["queued"] == ["PROJ-2", "PROJ-3"]
    # Eingereihte IDs reisen auch im Koordinator-Session-Snapshot mit (Cockpit).
    assert fleet["coordinator"]["queued_ticket_ids"] == ["PROJ-2", "PROJ-3"]

    # Einen Slot frei machen → Drain rückt genau EIN Ticket nach.
    await mgr.stop(fleet["children"][0]["session_id"])
    await svc.drain_all()
    assert svc.fleet(cid)["queued"] == ["PROJ-3"]


@pytest.mark.asyncio
async def test_drain_skips_paused(monkeypatch):
    """Ein pausierter Koordinator rückt NICHTS nach (Pause hält den Dispatch an)."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 2)
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    svc = CoordinatorService(mgr, VaultService())
    items = [
        {"ticket_id": f"PROJ-{n}", "title": f"T{n}", "status": "Planned", "role": "backend",
         "skill": "abc-backend", "engine": "claude", "model": "sonnet", "order": n,
         "dependencies": [], "blocked": False}
        for n in (1, 2, 3)
    ]
    fleet = await svc.dispatch(PROJECT, items)
    cid = fleet["coordinator"]["session_id"]
    svc.set_paused(cid, True)
    await mgr.stop(fleet["children"][0]["session_id"])  # Slot frei
    await svc.drain_all()
    assert svc.fleet(cid)["queued"] == ["PROJ-2", "PROJ-3"]  # nichts nachgerückt
