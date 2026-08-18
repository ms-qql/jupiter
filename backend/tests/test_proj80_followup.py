"""PROJ-80 — Fortsetzbare Paket-Sessions für den Feature-Koordinator (Backend).

Deckt die Kern-Acceptance-Criteria + Edge-Cases ab:
- Follow-up an ein abgeschlossenes Paket nutzt dieselbe Session (Kontext-erhaltend).
- Fehlende / gelöschte Session, nicht abgeschlossenes Paket, manuelle Übernahme
  und offene Decision Card werden mit 409 abgelehnt (kein stiller Neustart).
- Der Abschlussbeleg wird vor dem Senden geleert — der nächste Beleg entscheidet neu.
- Das eng geschnittene Capability-Token (Scope: feature_id + Aktion) wird akzeptiert,
  falscher Scope/Owner mit 401/403 abgewiesen.
- context_status taucht im FeaturePackageRead auf; das Token wird der Koordinator-
  Session-Umgebung injiziert.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app

from .fakes import FakeDriver

_HEADER = "| ID | Feature | Prio | Status | Abhängigkeiten | Spec |\n|----|----|----|----|----|----|\n"
_PROJ79_INDEX = _HEADER + (
    "| PROJ-101 | Feature X | P1 | Planned | — | [Spec](PROJ-101-x.md) |\n"
)


def _write_project(tmp_path, body: str = _PROJ79_INDEX) -> str:
    proj = tmp_path / "proj"
    (proj / "features").mkdir(parents=True)
    (proj / "features" / "INDEX.md").write_text(body, encoding="utf-8")
    return str(proj)


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    app = create_app(driver_factory=lambda: FakeDriver())
    # Einheitlich Single-User/Bootstrap-Verhalten (siehe test_proj79).
    async def _no_users():
        return False

    monkeypatch.setattr(app.state.auth, "has_users", _no_users)
    return TestClient(app)


def _dispatch(client: TestClient, proj: str) -> dict:
    plan = client.post("/coordinator/feature-plan",
                       json={"project_path": proj, "feature_id": "PROJ-101"}).json()
    resp = client.post("/coordinator/feature-dispatch",
                       json={"project_path": proj, "feature_id": "PROJ-101", "items": plan["items"]})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _complete(client: TestClient, fid: str, pkg_id: str, success: bool = True) -> dict:
    proof = {
        "role": "architect",
        "result_state": "success" if success else "failed",
        "artifacts": ["features/PROJ-101-x.md"],
        "checks": [{"name": "review", "result": "ok"}],
    }
    r = client.post(f"/coordinator/features/{fid}/packages/{pkg_id}/complete", json=proof)
    assert r.status_code == 200, r.text
    return r.json()


def _pkg_session(client, fid, pkg_id):
    run = client.get(f"/coordinator/features/{fid}").json()
    return next(p for p in run["packages"] if p["package_id"] == pkg_id)["session_id"]


def _set_pkg(client, coord_sid, pkg_id, **fields):
    coord = client.app.state.manager.get(coord_sid)
    pkg = next(p for p in coord.state.feature_packages if p["package_id"] == pkg_id)
    pkg.update(fields)
    return pkg


# --- Kern: Follow-up nutzt dieselbe Session --------------------------------
# PROJ-101.2 (review-architecture) fährt die claude-Engine → im Test FakeDriver,
# sodass send_input deterministisch auf dieselbe Session schreibt (kein echter
# Codex/OpenCode-Subprozess). PROJ-101.1 wird zuerst abgeschlossen, um .2 zu starten.


def test_followup_sends_to_same_session(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    coord_sid = run["coordinator"]["session_id"]
    _complete(client, fid, "PROJ-101.1")  # startet PROJ-101.2
    sid = _pkg_session(client, fid, "PROJ-101.2")
    _complete(client, fid, "PROJ-101.2")

    r = client.post(
        f"/coordinator/features/{fid}/packages/PROJ-101.2/followup",
        json={"instruction": "behebe BUG-3 aus dem QA-Lauf"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    pkg = {p["package_id"]: p for p in body["packages"]}["PROJ-101.2"]
    # Dasselbe Paket, dieselbe Session — Kontext erhalten, kein Neustart.
    assert pkg["session_id"] == sid
    assert pkg["status"] == "läuft"
    # Vor dem Senden geleert: der nächste strukturierte Beleg entscheidet neu.
    assert pkg["proof"] is None
    assert pkg["last_safe_state"] is None
    child = client.app.state.manager.get(sid)
    assert "behebe BUG-3 aus dem QA-Lauf" in child.driver.sent


def test_followup_requires_fresh_proof_afterwards(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    coord_sid = run["coordinator"]["session_id"]
    _complete(client, fid, "PROJ-101.1")
    _set_pkg(client, coord_sid, "PROJ-101.2", status="erfolgreich",
             proof={"package_id": "PROJ-101.2", "result_state": "success", "artifacts": ["x"], "checks": []})
    client.post(f"/coordinator/features/{fid}/packages/PROJ-101.2/followup",
                json={"instruction": "nochmal"})
    # Nach Follow-up ist der alte Erfolg weg — erst ein neuer Beleg zählt wieder.
    coord = client.app.state.manager.get(coord_sid)
    pkg = next(p for p in coord.state.feature_packages if p["package_id"] == "PROJ-101.2")
    assert pkg["status"] == "läuft"
    assert pkg["proof"] is None


# --- Edge-Cases: klare Ablehnung statt stillem Neustart ---------------------


def test_followup_missing_session_rejected(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    coord_sid = run["coordinator"]["session_id"]
    _set_pkg(client, coord_sid, "PROJ-101.1", status="erfolgreich", session_id=None)
    r = client.post(f"/coordinator/features/{fid}/packages/PROJ-101.1/followup",
                    json={"instruction": "x"})
    assert r.status_code == 409
    assert "nicht auffindbar" in r.json()["detail"]


def test_followup_not_completed_rejected(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)  # PROJ-101.1 läuft noch
    fid = run["feature_id"]
    r = client.post(f"/coordinator/features/{fid}/packages/PROJ-101.1/followup",
                    json={"instruction": "x"})
    assert r.status_code == 409


def test_followup_manual_takeover_rejected(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    coord_sid = run["coordinator"]["session_id"]
    _set_pkg(client, coord_sid, "PROJ-101.1", status="manuell")
    r = client.post(f"/coordinator/features/{fid}/packages/PROJ-101.1/followup",
                    json={"instruction": "x"})
    assert r.status_code == 409
    assert "manuell" in r.json()["detail"]


def test_followup_blocked_by_open_decision_card(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    # Fehlgeschlagener Beleg → Gesamtlauf blockiert (offene Decision Card).
    _complete(client, fid, "PROJ-101.1", success=False)
    r = client.post(f"/coordinator/features/{fid}/packages/PROJ-101.1/followup",
                    json={"instruction": "x"})
    assert r.status_code == 409


# --- Capability-Token (eng geschnitten) ------------------------------------


def _cap_token(client, coord_sid, fid, actions):
    return client.app.state.auth.issue_coordinator_capability(
        coord_sid, fid, settings.default_owner, actions
    )


def test_followup_via_capability_token(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    coord_sid = run["coordinator"]["session_id"]
    _complete(client, fid, "PROJ-101.1")  # startet PROJ-101.2
    _complete(client, fid, "PROJ-101.2")
    token = _cap_token(client, coord_sid, fid, ["package_followup", "feature_read"])
    r = client.post(
        f"/coordinator/features/{fid}/packages/PROJ-101.2/followup",
        json={"instruction": "via token"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text


def test_followup_wrong_feature_capability_rejected(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    coord_sid = run["coordinator"]["session_id"]
    _complete(client, fid, "PROJ-101.1")
    token = _cap_token(client, coord_sid, "999", ["package_followup"])
    r = client.post(
        f"/coordinator/features/{fid}/packages/PROJ-101.1/followup",
        json={"instruction": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_capability_cannot_plan_another_feature(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    token = _cap_token(
        client, run["coordinator"]["session_id"], run["feature_id"], ["feature_plan"]
    )
    r = client.post(
        "/coordinator/feature-plan",
        json={"project_path": proj, "feature_id": "PROJ-999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_followup_wrong_action_capability_rejected(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    coord_sid = run["coordinator"]["session_id"]
    _complete(client, fid, "PROJ-101.1")
    token = _cap_token(client, coord_sid, fid, ["feature_read"])
    r = client.post(
        f"/coordinator/features/{fid}/packages/PROJ-101.1/followup",
        json={"instruction": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_followup_requires_token_when_users_exist(client, tmp_path, monkeypatch):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    _complete(client, fid, "PROJ-101.1")

    async def _has_users():
        return True

    monkeypatch.setattr(client.app.state.auth, "has_users", _has_users)
    r = client.post(f"/coordinator/features/{fid}/packages/PROJ-101.1/followup",
                    json={"instruction": "x"})  # kein Token
    assert r.status_code == 401


# --- Sichtbarkeit + Env-Injektion -----------------------------------------


def test_context_status_present_in_feature_read(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    r = client.get(f"/coordinator/features/{fid}")
    assert r.status_code == 200
    for p in r.json()["packages"]:
        assert "context_status" in p  # Feld existiert (None = Erststart)


def test_coordinator_capability_injected_into_env(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    coord_sid = run["coordinator"]["session_id"]
    coord = client.app.state.manager.get(coord_sid)
    assert coord.state.env is not None
    assert "JUPITER_COORDINATOR_TOKEN" in coord.state.env
    assert coord.state.env["JUPITER_COORDINATOR_TOKEN"]
    assert coord.state.env["JUPITER_API_URL"] == settings.coordinator_api_url
