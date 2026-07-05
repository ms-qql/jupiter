"""PROJ-21 — Pipeline-Dashboard & Assembler-UI (Backend-Vertrag).

Deckt die im QA-Bericht als fehlend markierten Endpunkte ab: Bilder fuellen,
Mockup-Export, Registry-Recycling, Registry-Katalog, Branding-Profile,
Portfolio-Assembler sowie die Pipeline-Kette (Audit -> Redesign -> Bilder ->
Mockup-Export) und die neuen Run-Detail-Felder (run_type, mockup_status,
registry_selection).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_REGISTRY_JSON = {
    "$schema": "https://ui.shadcn.com/schema/registry.json",
    "name": "ui-check-test-registry",
    "items": [
        {
            "name": "hero-x",
            "type": "registry:block",
            "title": "Hero X",
            "description": "Test-Hero.",
            "files": [{"path": "blocks/hero-x.jsx", "type": "registry:block"}],
            "meta": {"section": "hero", "style": "safe", "interactive": True, "industry": ["saas", "legal"], "source": "test", "image_slots": ["hero-x-1"]},
        },
        {
            "name": "trust-x",
            "type": "registry:block",
            "title": "Trust X",
            "files": [{"path": "blocks/trust-x.jsx", "type": "registry:block"}],
            "meta": {"section": "trust", "style": "safe", "industry": ["saas", "legal"], "source": "test"},
        },
        {
            "name": "features-x",
            "type": "registry:block",
            "title": "Features X",
            "files": [{"path": "blocks/features-x.jsx", "type": "registry:block"}],
            "meta": {"section": "services", "style": "bold", "industry": ["saas"], "source": "test"},
        },
        {
            "name": "pricing-x",
            "type": "registry:block",
            "title": "Pricing X",
            "files": [{"path": "blocks/pricing-x.jsx", "type": "registry:block"}],
            "meta": {"section": "pricing", "style": "safe", "industry": ["saas"], "source": "test"},
        },
        {
            "name": "cta-x",
            "type": "registry:block",
            "title": "CTA X",
            "files": [{"path": "blocks/cta-x.jsx", "type": "registry:block"}],
            "meta": {"section": "cta", "style": "safe", "industry": ["saas", "legal"], "source": "test"},
        },
    ],
}


def _fixture_project(tmp_path: Path) -> Path:
    root = tmp_path / "ui-check"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("ui-check.sh", "ui-check-auto.sh", "redesign.sh", "redesign-auto.sh", "images-fill.sh", "mockup-export.sh", "assemble.sh"):
        p = scripts / name
        p.write_text("#!/usr/bin/env bash\nsleep 60\n", encoding="utf-8")
        p.chmod(0o755)
    (scripts / "registry-recycle.mjs").write_text("#!/usr/bin/env node\n", encoding="utf-8")

    _write(root / "registry" / "registry.json", _REGISTRY_JSON)
    _write_text(root / "registry" / "VERSION", "0.2.0\n")

    for slug, complete in (("verdict", True), ("broken", False)):
        current = root / "branding" / slug / "current"
        _write(current / "tokens.json", {
            "color": {"accent": {"$value": "#c87f2c"}},
            "font": {"display": {"$value": ["Geist", "sans-serif"]}},
        })
        if complete:
            _write_text(current / "tailwind-theme.css", "@theme { --color-accent: #c87f2c; }\n")
            _write_text(current / "logo.svg", "<svg />")
        _write(root / "branding" / slug / "profile.json", {
            "slug": slug, "name": slug.title(), "industry": "legal", "tags": ["legal", "agency"], "active_version": "v1",
        })

    run = root / "runs" / "2026-07-05-example.com-001"
    _write(run / "status.json", {
        "run_id": run.name, "url": "https://example.com", "status": "done", "phase": "done",
        "started_at": "2026-07-05T08:00:00Z", "industry_tag": "saas",
    })
    _write(run / "ui-check.json", {
        "run_id": run.name, "url": "https://example.com", "rubric_version": "2026.07-1",
        "ai_provider": "claude", "ai_model": "Claude Sonnet", "mode": "landing", "depth": "redesign",
    })
    _write(run / "scores.json", {"total": 60, "rubric_version": "2026.07-1", "dimensions": {}, "findings": []})
    (run / "redesign" / "safe").mkdir(parents=True)
    (run / "redesign" / "bold").mkdir(parents=True)
    _write(run / "redesign" / "images-fill.json", {"counts": {"filled": 3, "placeholder": 1}})
    _write(run / "redesign" / "registry-selection.safe.json", {
        "sections": [{"id": "hero", "type": "hero", "decision": "registry", "block": "hero-x", "reason": "type-match"}],
    })
    _write(run / "redesign" / "registry-selection.bold.json", {"sections": []})
    _write(run / "after-score.json", {"total": 78})

    no_redesign_run = root / "runs" / "2026-07-05-nored.com-001"
    _write(no_redesign_run / "status.json", {"run_id": no_redesign_run.name, "url": "https://nored.com", "status": "done", "phase": "done"})
    _write(no_redesign_run / "ui-check.json", {"run_id": no_redesign_run.name, "url": "https://nored.com"})
    _write(no_redesign_run / "scores.json", {"total": 50})

    return root


class _FakeProc:
    def __init__(self, cmd, returncode=0, **kwargs):
        self.cmd = cmd
        self.pid = 9999
        self._returncode = returncode
        self._finished = returncode is not None

    def poll(self):
        return self._returncode if self._finished else None

    def wait(self):
        return self._returncode


def _capture_popen(captured: dict):
    """Popen-Stub, der das Kommando aufzeichnet und einen laufenden Fake-Prozess liefert."""
    def _popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc(cmd, returncode=None)
    return _popen


def test_start_images_requires_redesign_dir(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.post("/ui-check/runs/2026-07-05-nored.com-001/images")
    assert resp.status_code == 409
    assert "Redesign-Lauf" in resp.json()["detail"]


def test_start_images_happy_path_spawns_script(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}
    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _capture_popen(captured))

    svc = ui_check_mod.UiCheckService(str(root))
    detail = svc.start_images("2026-07-05-example.com-001", force=True, only="safe")

    cmd = captured["cmd"]
    assert cmd[0].endswith("scripts/images-fill.sh")
    assert "--force" in cmd
    assert "--only" in cmd and cmd[cmd.index("--only") + 1] == "safe"
    assert detail["run_id"] == "2026-07-05-example.com-001"


def test_start_mockup_export_conflicts_when_mockup_html_exists(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    run_dir = root / "runs" / "2026-07-05-example.com-001"
    (run_dir / "mockup.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.post("/ui-check/runs/2026-07-05-example.com-001/mockup-export")
    assert resp.status_code == 409
    assert "mockup.html" in resp.json()["detail"]

    # force=true erzwingt Re-Export laut Edge Case „mockup.html existiert bereits".
    from app.engine import ui_check as ui_check_mod
    captured = {}
    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _capture_popen(captured))
    resp2 = client.post("/ui-check/runs/2026-07-05-example.com-001/mockup-export", json={"force": True})
    assert resp2.status_code == 200
    assert "--force" in captured["cmd"]


def test_start_recycle_spawns_node_script(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}
    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _capture_popen(captured))

    svc = ui_check_mod.UiCheckService(str(root))
    svc.start_recycle("2026-07-05-example.com-001", min_total=65, force=True)

    cmd = captured["cmd"]
    assert cmd[0] == "node"
    assert cmd[1].endswith("scripts/registry-recycle.mjs")
    assert "--run" in cmd
    assert "--min-total" in cmd and cmd[cmd.index("--min-total") + 1] == "65"
    assert "--force" in cmd


def test_get_registry_returns_catalog(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.get("/ui-check/registry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "0.2.0"
    names = {item["name"] for item in body["items"]}
    assert "hero-x" in names
    hero = next(i for i in body["items"] if i["name"] == "hero-x")
    assert hero["section"] == "hero"
    assert hero["assembler_selectable"] is True


def test_get_registry_missing_file_returns_503_german_error(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    (root / "registry" / "registry.json").unlink()
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.get("/ui-check/registry")
    assert resp.status_code == 503
    assert "Registry-Katalog" in resp.json()["detail"]


def test_get_registry_invalid_json_returns_503(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    (root / "registry" / "registry.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.get("/ui-check/registry")
    assert resp.status_code == 503


def test_get_branding_profiles_flags_incomplete_profile(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.get("/ui-check/branding-profiles")
    assert resp.status_code == 200
    profiles = {p["slug"]: p for p in resp.json()["profiles"]}
    assert profiles["verdict"]["complete"] is True
    assert profiles["broken"]["complete"] is False
    assert "tailwind-theme.css" in profiles["broken"]["missing"]


def test_get_branding_profiles_empty_dir_returns_empty_list(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    import shutil
    shutil.rmtree(root / "branding")
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.get("/ui-check/branding-profiles")
    assert resp.status_code == 200
    assert resp.json()["profiles"] == []


def test_run_detail_includes_mockup_status_and_registry_selection(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    detail = client.get("/ui-check/runs/2026-07-05-example.com-001").json()
    assert detail["run_type"] == "audit_redesign"
    ms = detail["mockup_status"]
    assert ms["safe_ready"] is True
    assert ms["bold_ready"] is True
    assert ms["images"]["filled_slots"] == 3
    assert ms["images"]["placeholder_slots"] == 1
    assert ms["images"]["degraded"] is True
    assert ms["score_delta"] == 18  # after-score 78 - scores.total 60
    sel = detail["registry_selection"]
    assert sel["safe"][0]["block"] == "hero-x"
    assert sel["bold"] == []


def test_run_type_assemble_is_detected_and_mode_falls_back(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    assemble_run = root / "runs" / "2026-07-05-assemble-verdict-legal-001"
    _write(assemble_run / "status.json", {"run_id": assemble_run.name, "status": "done", "phase": "done"})
    _write(assemble_run / "ui-check.json", {"run_id": assemble_run.name, "mode": "assemble", "branding": "verdict", "industry_tag": "legal"})
    _write(assemble_run / "redesign" / "redesign-context.json", {"source": "assemble", "branding": "verdict"})
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    detail = client.get(f"/ui-check/runs/{assemble_run.name}").json()
    assert detail["run_type"] == "assemble"
    assert detail["mode"] == "auto"  # "assemble" ist kein gueltiger Mode-Wert -> Fallback


def test_start_assemble_happy_path_builds_expected_command(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}
    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _capture_popen(captured))
    client = TestClient(create_app())

    resp = client.post("/ui-check/assemble", json={
        "branding": "verdict",
        "industry": "legal",
        "sections": ["hero", "trust", "cta"],
        "prompt": "Kanzlei-Website",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["run_type"] == "assemble"
    assert body["run_id"].startswith("2026-") and "assemble-verdict-legal" in body["run_id"]

    cmd = captured["cmd"]
    assert cmd[0].endswith("scripts/assemble.sh")
    assert "--branding" in cmd and cmd[cmd.index("--branding") + 1] == "verdict"
    assert "--industry" in cmd and cmd[cmd.index("--industry") + 1] == "legal"
    assert "--sections" in cmd and cmd[cmd.index("--sections") + 1] == "hero,trust,cta"
    assert "--prompt" in cmd and cmd[cmd.index("--prompt") + 1] == "Kanzlei-Website"


def test_start_assemble_registry_only_reports_missing_sections(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    # "pricing-x" ist nur fuer industry=saas getaggt, nicht fuer "legal" -> Luecke.
    resp = client.post("/ui-check/assemble", json={
        "branding": "verdict",
        "industry": "legal",
        "sections": ["hero", "pricing"],
        "registry_only": True,
    })
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "pricing" in detail["missing_sections"]
    assert "hero" not in detail["missing_sections"]


def test_start_assemble_generate_override_excludes_matching_blocks(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}
    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _capture_popen(captured))
    client = TestClient(create_app())

    resp = client.post("/ui-check/assemble", json={
        "branding": "verdict",
        "industry": "legal",
        "sections": ["hero", "trust"],
        "overrides": [{"section": "hero", "decision": "generate"}],
    })
    assert resp.status_code == 201
    cmd = captured["cmd"]
    assert "--exclude" in cmd and cmd[cmd.index("--exclude") + 1] == "hero-x"


def test_start_assemble_block_override_pins_section(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}
    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _capture_popen(captured))
    client = TestClient(create_app())

    resp = client.post("/ui-check/assemble", json={
        "branding": "verdict",
        "industry": "legal",
        "sections": ["hero", "trust"],
        "overrides": [{"section": "hero", "decision": "block", "block": "hero-x"}],
    })
    assert resp.status_code == 201
    cmd = captured["cmd"]
    assert "--pin" in cmd and cmd[cmd.index("--pin") + 1] == "hero=hero-x"


def test_start_assemble_exclude_override_drops_section_from_plan(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    captured = {}
    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", _capture_popen(captured))
    client = TestClient(create_app())

    resp = client.post("/ui-check/assemble", json={
        "branding": "verdict",
        "industry": "legal",
        "sections": ["hero", "trust", "cta"],
        "overrides": [{"section": "trust", "decision": "exclude"}],
    })
    assert resp.status_code == 201
    cmd = captured["cmd"]
    assert cmd[cmd.index("--sections") + 1] == "hero,cta"


def test_start_assemble_missing_branding_profile_returns_404(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.post("/ui-check/assemble", json={"branding": "unknown-slug", "industry": "legal", "sections": ["hero"]})
    assert resp.status_code == 404


def test_start_assemble_incomplete_branding_profile_returns_409(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.post("/ui-check/assemble", json={"branding": "broken", "industry": "legal", "sections": ["hero"]})
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "tailwind-theme.css" in detail["missing_profile_parts"]


def test_start_assemble_invalid_branding_slug_is_rejected(tmp_path, monkeypatch):
    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    client = TestClient(create_app())

    resp = client.post("/ui-check/assemble", json={"branding": "Not_Valid", "industry": "legal", "sections": ["hero"]})
    assert resp.status_code == 409
    assert "Branding-Slug" in resp.json()["detail"]


def test_full_pipeline_chain_runs_redesign_images_mockup_in_sequence(tmp_path, monkeypatch):
    """AC-3: depth=redesign + full_pipeline haengt Redesign -> Bilder -> Mockup-Export
    automatisch an den Audit-Lauf an (Hintergrund-Thread beobachtet Popen.wait())."""
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    calls: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        return _FakeProc(cmd, returncode=0)  # jeder Schritt "beendet sich sofort" mit Exit 0.

    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", fake_popen)
    client = TestClient(create_app())

    resp = client.post("/ui-check/runs", json={
        "url": "https://chain.example",
        "depth": "redesign",
        "full_pipeline": True,
        "ai_provider": "claude",
        "ai_model": "sonnet",
    })
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    deadline = time.time() + 2
    while len(calls) < 4 and time.time() < deadline:
        time.sleep(0.02)

    assert len(calls) == 4
    assert calls[0][0].endswith("scripts/ui-check-auto.sh")
    assert calls[1][0].endswith("scripts/redesign-auto.sh")
    assert calls[2][0].endswith("scripts/images-fill.sh")
    assert calls[3][0].endswith("scripts/mockup-export.sh")

    run_dir = root / "runs" / run_id
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert "chain_error" not in status


def test_full_pipeline_chain_aborts_and_writes_chain_error_on_hard_failure(tmp_path, monkeypatch):
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    calls: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        # Audit-Schritt (erster Aufruf) schlaegt hart fehl (Exit 2) -> Kette bricht ab.
        returncode = 2 if len(calls) == 1 else 0
        return _FakeProc(cmd, returncode=returncode)

    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", fake_popen)
    client = TestClient(create_app())

    resp = client.post("/ui-check/runs", json={
        "url": "https://chain-fail.example",
        "depth": "redesign",
        "full_pipeline": True,
        "ai_provider": "claude",
        "ai_model": "sonnet",
    })
    run_id = resp.json()["run_id"]

    deadline = time.time() + 2
    run_dir = root / "runs" / run_id
    status = {}
    while time.time() < deadline:
        status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
        if "chain_error" in status:
            break
        time.sleep(0.02)

    assert len(calls) == 1  # nur der Audit-Schritt wurde gestartet.
    assert status["chain_error"]["step"] == "audit"
    assert status["chain_error"]["returncode"] == 2
    assert status["status"] == "error"


def test_cancel_during_chain_keeps_cancelled_status_instead_of_chain_error(tmp_path, monkeypatch):
    """Regression: SIGTERM auf den beobachteten Prozess liess den Chain-Worker
    frueher einen chain_error schreiben und "cancelled" ueberschreiben."""
    from app.engine import ui_check as ui_check_mod

    root = _fixture_project(tmp_path)
    monkeypatch.setattr(settings, "ui_check_project_path", str(root))
    procs: list["_BlockingProc"] = []

    class _BlockingProc:
        def __init__(self, cmd):
            self.cmd = cmd
            self.pid = 9999
            self._event = threading.Event()
            self._returncode = None

        def poll(self):
            return self._returncode

        def wait(self):
            self._event.wait(timeout=2)
            return self._returncode if self._returncode is not None else -15

    def fake_popen(cmd, **kwargs):
        proc = _BlockingProc(cmd)
        procs.append(proc)
        return proc

    def fake_killpg(pid, sig):
        procs[0]._returncode = -15
        procs[0]._event.set()

    monkeypatch.setattr(ui_check_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(ui_check_mod.os, "killpg", fake_killpg)
    client = TestClient(create_app())

    resp = client.post("/ui-check/runs", json={
        "url": "https://cancel-chain.example",
        "depth": "redesign",
        "full_pipeline": True,
        "ai_provider": "claude",
        "ai_model": "sonnet",
    })
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    deadline = time.time() + 1
    while not procs and time.time() < deadline:
        time.sleep(0.01)
    assert procs

    cancel_resp = client.post(f"/ui-check/runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    run_dir = root / "runs" / run_id
    deadline = time.time() + 2
    status: dict = {}
    while time.time() < deadline:
        status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
        if "chain_error" in status:
            break
        time.sleep(0.02)

    assert status.get("status") == "cancelled"
    assert "chain_error" not in status
