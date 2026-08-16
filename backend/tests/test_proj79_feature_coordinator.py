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
        "PROJ-101.1", "PROJ-101.2", "PROJ-101.3", "PROJ-101.4", "PROJ-101.5", "PROJ-101.6", "PROJ-101.7",
    ]
    by_id = {p["package_id"]: p for p in plan["items"]}
    assert by_id["PROJ-101.1"]["required_proof"] == "architecture"
    assert by_id["PROJ-101.2"]["skill"] == "abc-review-architecture"
    assert by_id["PROJ-101.2"]["model"] == "sonnet"
    assert by_id["PROJ-101.2"]["dependencies"] == ["PROJ-101.1"]
    assert by_id["PROJ-101.3"]["dependencies"] == ["PROJ-101.2"]
    assert by_id["PROJ-101.4"]["dependencies"] == ["PROJ-101.2"]
    assert set(by_id["PROJ-101.5"]["dependencies"]) == {"PROJ-101.3", "PROJ-101.4"}
    assert by_id["PROJ-101.5"]["required_proof"] == "qa"
    assert by_id["PROJ-101.3"]["write_scope"] == ["backend/"]


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
    assert by_id["PROJ-101.1"]["permission_mode"] == "bypassPermissions"
    assert by_id["PROJ-101.1"]["token_savings"] == "on"


def test_feature_dispatch_is_idempotent(client, tmp_path):
    proj = _write_project(tmp_path)
    first = _dispatch(client, proj)
    second = _dispatch(client, proj)
    assert second["coordinator"]["session_id"] == first["coordinator"]["session_id"]
    assert len([r for r in client.app.state.manager.list() if r.state.is_feature_run]) == 1


def test_feature_delete_stops_and_removes_packages(client, tmp_path):
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    coordinator_id = run["coordinator"]["session_id"]
    response = client.delete(f"/coordinator/features/runs/{coordinator_id}")
    assert response.status_code == 204, response.text
    assert client.app.state.manager.list() == []


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
    assert by_id["PROJ-101.3"]["status"] == "wartet"


def test_feature_dispatch_rejects_mismatched_engine_model_before_creating_run(client, tmp_path):
    proj = _write_project(tmp_path)
    plan = client.post("/coordinator/feature-plan", json={"project_path": proj, "feature_id": "PROJ-101"}).json()
    plan["items"][0].update({"engine": "claude", "model": "not-a-claude-model"})
    response = client.post("/coordinator/feature-dispatch", json={"project_path": proj, "feature_id": "PROJ-101", "items": plan["items"]})
    assert response.status_code == 400
    assert client.app.state.manager.list() == []


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


# --- QA-Bugfixes -------------------------------------------------------------


def test_started_package_prompt_contains_completion_curl(client, tmp_path):
    """BUG-1: Kind-Session muss den Abschlussbeleg-Vertrag im Prompt kennen — sonst
    endet sie regulär, ohne dass der Scheduler sie je als erfolgreich zählt."""
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    pkg = next(p for p in run["packages"] if p["package_id"] == "PROJ-101.1")
    runtime = client.app.state.manager.get(pkg["session_id"])
    prompt = runtime.driver._spec.initial_prompt
    assert "/coordinator/features/101/packages/PROJ-101.1/complete" in prompt
    assert "result_state" in prompt


def test_ui_shaped_success_proof_with_check_is_accepted(client, tmp_path):
    """BUG-2: Payload wie das gefixte Formular (ein Check mit Ergebnis) muss
    akzeptiert werden — vorher scheiterte selbst das UI-eigene Formular (checks=[])."""
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    fid = run["feature_id"]
    proof = {
        "package_id": "PROJ-101.1", "role": "architect", "result_state": "success",
        "artifacts": ["features/PROJ-101-x.md"],
        "checks": [{"name": "Abschlussprüfung", "result": "manuell verifiziert"}],
        "open_limitations": None,
    }
    r = client.post(f"/coordinator/features/{fid}/packages/PROJ-101.1/complete", json=proof)
    assert r.status_code == 200, r.text
    by_id = {p["package_id"]: p for p in r.json()["packages"]}
    assert by_id["PROJ-101.1"]["status"] == "erfolgreich"


def test_resume_attempts_include_automatic_watchdog_reanimation(client, tmp_path):
    """BUG-3: automatische Watchdog-Reanimation (PROJ-27/45) muss in resume_attempts
    sichtbar sein, nicht nur manuelle „erneut versuchen"-Klicks."""
    proj = _write_project(tmp_path)
    run = _dispatch(client, proj)
    pkg = next(p for p in run["packages"] if p["package_id"] == "PROJ-101.1")
    runtime = client.app.state.manager.get(pkg["session_id"])
    runtime.liveness.auto_attempts = 2  # simuliert zwei automatische Reanimationen
    fid = run["feature_id"]
    r = client.get(f"/coordinator/features/{fid}")
    by_id = {p["package_id"]: p for p in r.json()["packages"]}
    assert by_id["PROJ-101.1"]["resume_attempts"] == 2


def test_feature_plan_warns_on_overlapping_parallel_write_scope(tmp_path, monkeypatch):
    """BUG-5: Backend + Frontend laufen ohne Abhängigkeit zueinander parallel — bei
    überlappendem write_scope muss der Plan warnen statt die Kollision zu verschweigen."""
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_project(tmp_path)
    plan = build_feature_plan(proj, "PROJ-101")
    by_id = {p["package_id"]: p for p in plan["items"]}
    backend_pkg = next(p for p in by_id.values() if p["role"] == "backend")
    frontend_pkg = next(p for p in by_id.values() if p["role"] == "frontend")
    backend_pkg["write_scope"] = ["shared/"]
    frontend_pkg["write_scope"] = ["shared/x.py"]
    from app.engine.coordinator import _collision_warnings
    warnings = _collision_warnings(list(by_id.values()))
    assert any(backend_pkg["package_id"] in w and frontend_pkg["package_id"] in w for w in warnings)


def test_feature_plan_unrecognized_status_gets_distinct_warning(tmp_path, monkeypatch):
    """BUG-4: ein nicht erkannter Status darf nicht wie „fertig" (deployed) aussehen —
    unklare Spezifikation braucht eine eindeutige Klärungs-Warnung."""
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])
    proj = _write_project(
        tmp_path, _HEADER + "| PROJ-101 | X | P1 | Frobnicated | — | [Spec](a.md) |\n",
    )
    plan = build_feature_plan(proj, "PROJ-101")
    assert plan["items"] == []
    assert any("nicht erkannten Status" in w for w in plan["warnings"])
