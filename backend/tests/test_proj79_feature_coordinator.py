"""PROJ-79 — Featurezentrierter Koordinator mit autonomem Abschluss (Backend).

Deckt die Kern-Acceptance-Criteria ab:
- Interner Plan für EIN Feature (nur nötige Pakete, Abhängigkeiten, Schreibbereiche,
  rollenbezogene Abschlussbelege) — startet NICHTS.
- Dispatch erzeugt eine Feature-Lauf-Koordinator-Session + startet nur bereite Pakete.
- Kind-Session endet nicht als „fertig" ohne Abschlussbeleg (Beleg-Prüfung).
- Abhängige Pakete starten erst nach bestandenem Beleg des Vorgängers.
- Pause + Decision (retry/abort) steuern den Gesamtlauf.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engine.coordinator import (
    FeatureCoordinatorService,
    build_feature_plan,
)
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
    return TestClient(app)


# --- Plan (reine Logik) -----------------------------------------------------


def test_feature_plan_derives_packages(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_project(tmp_path)
    plan = build_feature_plan(proj, "PROJ-101")
    ids = [p["package_id"] for p in plan["items"]]
    assert ids == [
        "PROJ-101.1", "PROJ-101.2", "PROJ-101.3", "PROJ-101.4", "PROJ-101.5", "PROJ-101.6",
    ]
    by_id = {p["package_id"]: p for p in plan["items"]}
    assert by_id["PROJ-101.1"]["required_proof"] == "architecture"
    assert by_id["PROJ-101.2"]["dependencies"] == ["PROJ-101.1"]
    assert by_id["PROJ-101.3"]["dependencies"] == ["PROJ-101.1"]
    assert set(by_id["PROJ-101.4"]["dependencies"]) == {"PROJ-101.2", "PROJ-101.3"}
    assert by_id["PROJ-101.4"]["required_proof"] == "qa"
    assert by_id["PROJ-101.2"]["write_scope"] == ["backend/"]


def test_feature_plan_unknown_feature_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_project(tmp_path)
    with pytest.raises(ValueError):
        build_feature_plan(proj, "PROJ-999")


def test_feature_plan_deployed_has_no_work(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_project(
        tmp_path,
        _HEADER + "| PROJ-101 | X | P1 | Deployed | — | [Spec](a.md) |\n",
    )
    plan = build_feature_plan(proj, "PROJ-101")
    assert plan["items"] == []
    assert plan["warnings"]


# --- Abschlussbeleg-Prüfung (reine Logik) -----------------------------------


def test_validate_proof_requires_artifacts_and_checks():
    svc = FeatureCoordinatorService.__new__(FeatureCoordinatorService)
    pkg = {"package_id": "PROJ-101.2", "required_proof": "backend", "status": "läuft"}
    assert svc._validate_proof(pkg, {
        "package_id": "PROJ-101.2", "result_state": "success", "artifacts": [], "checks": [],
    }) is None
    ok = svc._validate_proof(pkg, {
        "package_id": "PROJ-101.2", "result_state": "success",
        "artifacts": ["backend/x.py"], "checks": [{"name": "pytest", "result": "ok"}],
    })
    assert ok is not None and ok["result_state"] == "success"
    assert svc._validate_proof(pkg, {
        "package_id": "PROJ-101.9", "result_state": "success",
        "artifacts": ["x"], "checks": [{"result": "ok"}],
    }) is None


# --- API: Dispatch + Lebenszyklus ------------------------------------------


def _dispatch(client: TestClient, proj: str, items=None) -> dict:
    if items is None:
        plan = client.post("/coordinator/feature-plan",
                           json={"project_path": proj, "feature_id": "PROJ-101"}).json()
        items = plan["items"]
    resp = client.post("/coordinator/feature-dispatch",
                       json={"project_path": proj, "feature_id": "PROJ-101", "items": items})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_feature_dispatch_starts_only_ready_packages(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    assert run["feature_id"] == "101"
    assert run["status"] == "läuft"
    coord = run["coordinator"]
    assert coord["is_feature_run"] is True and coord["feature_id"] == "101"
    by_id = {p["package_id"]: p for p in run["packages"]}
    assert by_id["PROJ-101.1"]["status"] == "läuft"
    assert by_id["PROJ-101.2"]["status"] == "wartet"
    assert by_id["PROJ-101.3"]["status"] == "wartet"


def test_feature_run_get_and_pause(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    r = client.get(f"/coordinator/features/{fid}")
    assert r.status_code == 200 and r.json()["feature_id"] == fid
    r = client.post(f"/coordinator/features/{fid}/pause", json={"paused": True})
    assert r.status_code == 200 and r.json()["paused"] is True
    assert client.get("/coordinator/features/999").status_code == 404


def test_feature_complete_proof_unlocks_dependents(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    proof = {
        "role": "architect", "result_state": "success",
        "artifacts": ["features/PROJ-101-x.md"],
        "checks": [{"name": "review", "result": "ok"}],
    }
    r = client.post(
        f"/coordinator/features/{fid}/packages/PROJ-101.1/complete", json=proof
    )
    assert r.status_code == 200, r.text
    by_id = {p["package_id"]: p for p in r.json()["packages"]}
    assert by_id["PROJ-101.1"]["status"] == "erfolgreich"
    assert by_id["PROJ-101.2"]["status"] == "läuft"
    assert by_id["PROJ-101.3"]["status"] == "läuft"


def test_feature_abort_sets_status(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    r = client.post(
        f"/coordinator/features/{fid}/decision",
        json={"action": "abort", "package_id": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "abgebrochen"


def test_feature_blocker_card_on_failed_proof(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    proof = {
        "role": "architect", "result_state": "failed",
        "artifacts": ["features/PROJ-101-x.md"], "checks": [{"name": "review", "result": "no"}],
        "open_limitations": "ungelöst",
    }
    r = client.post(
        f"/coordinator/features/{fid}/packages/PROJ-101.1/complete", json=proof
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "blockiert"
    assert body["blocker"] is not None
    # retry löst die Blockierung + startet das Paket neu.
    r = client.post(
        f"/coordinator/features/{fid}/decision",
        json={"action": "retry", "package_id": "PROJ-101.1"},
    )
    assert r.status_code == 200
    assert r.json()["blocker"] is None
    assert r.json()["status"] in ("läuft", "planung")
