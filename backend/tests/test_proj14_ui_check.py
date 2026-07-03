"""PROJ-14 — UI-Check Runner-API fuer die native Micro-App."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _fixture_project(tmp_path: Path) -> Path:
    root = tmp_path / "ui-check"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "ui-check.sh").write_text("#!/usr/bin/env bash\nsleep 60\n", encoding="utf-8")
    (root / "scripts" / "ui-check.sh").chmod(0o755)
    (root / "scripts" / "redesign.sh").write_text("#!/usr/bin/env bash\nsleep 60\n", encoding="utf-8")
    (root / "scripts" / "redesign.sh").chmod(0o755)
    run = root / "runs" / "2026-07-03-example.com-001"
    _write(run / "status.json", {
        "run_id": run.name,
        "url": "https://example.com",
        "status": "done",
        "phase": "done",
        "started_at": "2026-07-03T08:00:00Z",
        "industry_tag": "saas",
    })
    _write(run / "ui-check.json", {
        "run_id": run.name,
        "url": "https://example.com",
        "rubric_version": "2026.07-1",
        "ai_provider": "claude",
        "ai_model": "sonnet",
        "mode": "landing",
        "depth": "audit",
    })
    _write(run / "scores.json", {
        "total": 72,
        "rubric_version": "2026.07-1",
        "dimensions": {"visuell": {"score": 76, "source": "judge"}},
        "findings": [{
            "severity": "hoch",
            "title": "CTA unklar",
            "evidence": "Primaerer CTA ist nicht eindeutig.",
            "location": "Hero",
        }],
    })
    _write(run / "meta.json", {
        "url": "https://example.com",
        "screenshots": [{"path": "capture/shot-1440.png"}],
    })
    (run / "capture").mkdir()
    (run / "capture" / "shot-1440.png").write_bytes(b"png")
    (run / "report.md").write_text("# Report\n", encoding="utf-8")
    _write(run / "branding" / "tokens.json", {
        "color": {"primary": {"$value": "#0d9488"}},
        "font": {"display": {"$value": "Inter, sans-serif"}},
    })
    _write(run / "branding" / "branding-meta.json", {"logo": {"file": "logo.svg"}})
    (run / "branding" / "logo.svg").write_text("<svg />", encoding="utf-8")
    return root


def test_ui_check_lists_and_reads_existing_runs(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    listing = client.get("/ui-check/runs").json()
    assert listing["runs"][0]["run_id"] == "2026-07-03-example.com-001"
    assert listing["runs"][0]["score_total"] == 72

    detail = client.get("/ui-check/runs/2026-07-03-example.com-001").json()
    assert detail["status"] == "done"
    assert detail["dimensions"][0]["label"] == "Visuell"
    assert detail["findings"][0]["severity"] == "high"
    assert detail["branding"]["colors"] == ["#0d9488"]
    assert detail["artifacts"]["report"] == "report"
    assert detail["artifacts"]["screenshots"] == ["screenshot-0"]


def test_ui_check_serves_artifacts_and_404s_path_traversal(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.get("/ui-check/runs/2026-07-03-example.com-001/artifacts/report")
    assert resp.status_code == 200
    assert "# Report" in resp.text

    assert client.get("/ui-check/runs/../secret").status_code == 404


def test_ui_check_start_and_cancel_run(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    started = client.post("/ui-check/runs", json={
        "url": "https://new.example",
        "mode": "auto",
        "depth": "audit",
        "ai_provider": "claude",
        "ai_model": "sonnet",
        "desktop": True,
    })
    assert started.status_code == 201
    run_id = started.json()["run_id"]
    assert run_id.startswith("2026-")

    cancelled = client.post(f"/ui-check/runs/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
