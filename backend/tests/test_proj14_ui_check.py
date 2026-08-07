"""PROJ-14 — UI-Check Runner-API fuer die native Micro-App."""
from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

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
    (root / "scripts" / "ui-check-auto.sh").write_text("#!/usr/bin/env bash\nsleep 60\n", encoding="utf-8")
    (root / "scripts" / "ui-check-auto.sh").chmod(0o755)
    (root / "scripts" / "redesign.sh").write_text("#!/usr/bin/env bash\nsleep 60\n", encoding="utf-8")
    (root / "scripts" / "redesign.sh").chmod(0o755)
    (root / "scripts" / "redesign-auto.sh").write_text("#!/usr/bin/env bash\nsleep 60\n", encoding="utf-8")
    (root / "scripts" / "redesign-auto.sh").chmod(0o755)
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
        "ai_model": "Claude Sonnet",
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


def test_start_run_uses_auto_script_with_judge_model(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))

    captured = {}

    class _FakeProc:
        pid = 4242

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd

        def poll(self):
            return None

    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _FakeProc)

    class _Payload:
        url = "https://new.example"
        mode = "auto"
        depth = "audit"
        industry = None
        prompt = None
        desktop = False
        ai_provider = "claude"
        ai_model = "Claude Opus"

    service = ui_check_mod.UiCheckService(str(root))
    service.start_run(_Payload())

    cmd = captured["cmd"]
    assert cmd[0].endswith("scripts/ui-check-auto.sh")
    # UI-Label "Claude Opus" muss zum CLI-Alias "opus" werden (nicht wörtlich).
    assert "--judge-model" in cmd and cmd[cmd.index("--judge-model") + 1] == "opus"


def test_start_run_with_uploaded_screenshot_passes_png_to_runner(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}

    class _FakeProc:
        pid = 4245

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd

        def poll(self):
            return None

    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _FakeProc)
    client = TestClient(create_app())

    resp = client.post(
        "/ui-check/runs/with-screenshot",
        data={"url": "https://new.example", "ai_model": "Claude Sonnet"},
        files={"screenshot": ("website.png", io.BytesIO(b"\x89PNG\r\n\x1a\npixels"), "image/png")},
    )

    assert resp.status_code == 201
    screenshot = captured["cmd"][captured["cmd"].index("--screenshot") + 1]
    assert screenshot.endswith("uploaded-screenshot.png")
    assert Path(screenshot).read_bytes() == b"\x89PNG\r\n\x1a\npixels"


def test_start_run_with_jpeg_screenshot_converts_it_to_png(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}

    class _FakeProc:
        pid = 4246

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd

        def poll(self):
            return None

    image = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(image, "JPEG")
    image.seek(0)
    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _FakeProc)
    client = TestClient(create_app())

    resp = client.post(
        "/ui-check/runs/with-screenshot",
        data={"url": "https://new.example", "ai_model": "Claude Sonnet"},
        files={"screenshot": ("website.png", image, "image/png")},
    )

    assert resp.status_code == 201
    screenshot = captured["cmd"][captured["cmd"].index("--screenshot") + 1]
    assert Path(screenshot).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_start_run_omits_judge_model_for_unknown_label(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}

    class _FakeProc:
        pid = 4243

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd

        def poll(self):
            return None

    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _FakeProc)

    class _Payload:
        url = "https://new.example"
        mode = "auto"
        depth = "audit"
        industry = None
        prompt = None
        desktop = False
        ai_provider = "openrouter"
        ai_model = "OpenRouter Auto"

    ui_check_mod.UiCheckService(str(root)).start_run(_Payload())
    # Nicht-Claude-Provider: kein --judge-model → Skript nutzt seinen sonnet-Default.
    assert "--judge-model" not in captured["cmd"]


def test_start_redesign_uses_auto_script_with_gen_model(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}

    class _FakeProc:
        pid = 4244

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd

        def poll(self):
            return None

    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _FakeProc)

    ui_check_mod.UiCheckService(str(root)).start_redesign("2026-07-03-example.com-001")

    cmd = captured["cmd"]
    assert cmd[0].endswith("scripts/redesign-auto.sh")
    # ai_model "Claude Sonnet" (aus ui-check.json) → CLI-Alias "sonnet".
    assert "--gen-model" in cmd and cmd[cmd.index("--gen-model") + 1] == "sonnet"


def test_delete_run_removes_folder_and_404s_after(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    run_dir = root / "runs" / "2026-07-03-example.com-001"
    assert run_dir.exists()

    resp = client.delete("/ui-check/runs/2026-07-03-example.com-001")
    assert resp.status_code == 204
    assert not run_dir.exists()

    # Zweiter Aufruf: Ordner weg → 404.
    assert client.delete("/ui-check/runs/2026-07-03-example.com-001").status_code == 404
    # Path-Traversal bleibt verboten.
    assert client.delete("/ui-check/runs/../..").status_code == 404
    # Listing ist nach dem Loeschen leer.
    assert client.get("/ui-check/runs").json()["runs"] == []


def test_delete_run_refuses_running_process(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))

    service = ui_check_mod.UiCheckService(str(root))

    class _FakeProc:
        pid = 4245

        def poll(self):
            return None  # Prozess lebt noch.

    run_id = "2026-07-03-example.com-001"
    service._processes[run_id] = _FakeProc()  # noqa: SLF001 — internes Wiring im Test.

    try:
        service.delete_run(run_id)
    except ui_check_mod.UiCheckConflict as exc:
        assert "laeuft" in str(exc)
    else:
        raise AssertionError("Laufender Lauf haette nicht geloescht werden duerfen.")

    # Ordner ist unangetastet.
    assert (root / "runs" / run_id).exists()
