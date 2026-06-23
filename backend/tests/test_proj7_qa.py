"""PROJ-7 QA — AC-Mapping + Red-Team über die MD-Reader-API.

Ergänzt test_proj7_md_reader.py um die in der QA live verifizierten Angriffe
(project-Param-Missbrauch, .md-Escape, relativer-Pfad-Guard) als permanente
Regression. allowed_roots wird pro Test auf tmp gebogen.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.md_reader import MdReaderService
from app.main import create_app

from .fakes import FakeDriver


@pytest.fixture()
def env(tmp_path, monkeypatch):
    base = tmp_path
    vault = base / "vault"
    proj = base / "proj"
    other = base / "other"  # zweite erlaubte Wurzel (wie /home/dev/tools)
    (vault / "Agentic OS" / "Jupiter" / "Handovers").mkdir(parents=True)
    (vault / "Agentic OS" / "Jupiter" / "Handovers" / "h.md").write_text("# H\n", encoding="utf-8")
    (proj / "features").mkdir(parents=True)
    (proj / "features" / "PROJ-7-md-reader.md").write_text("# Spec\n", encoding="utf-8")
    other.mkdir(parents=True)
    (other / "notiz.md").write_text("# Other\n", encoding="utf-8")
    (base / "secret_outside.md").write_text("# außerhalb der Quellen, aber in base\n", encoding="utf-8")

    # allowed_roots = base (umfasst vault, proj, other); Default-Projekt = proj.
    monkeypatch.setattr(settings, "allowed_roots", [str(base)])
    monkeypatch.setattr(settings, "vault_root", str(vault))
    monkeypatch.setattr(settings, "reader_default_project", str(proj))
    return base, vault, proj, other


@pytest.fixture()
def reader(env) -> MdReaderService:
    return MdReaderService()


@pytest.fixture()
def client(env) -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


# --- Akzeptanzkriterien (API-Ebene) ----------------------------------------

def test_ac1_render_source_returns_raw_md_and_frontmatter(client, env):
    """AC1/AC4: Datei wird mit getrenntem Frontmatter + Body geliefert (Render-Basis)."""
    _b, vault, _p, _o = env
    path = os.path.join(str(vault), "Agentic OS", "Jupiter", "Handovers", "h.md")
    r = client.get("/md/file", params={"path": path})
    assert r.status_code == 200
    body = r.json()
    assert "frontmatter" in body and "body" in body

def test_ac3_tree_navigation_index(client):
    """AC3: Datei-Navigation/Baum — Index liefert die durchstöberbaren .md."""
    r = client.get("/md/index", params={"source": "project"})
    assert r.status_code == 200
    assert any(f["name"] == "PROJ-7-md-reader.md" for f in r.json()["files"])

def test_ac5_read_only_no_write_route(client):
    """AC5 (durch PROJ-12 abgelöst): /md/index bleibt rein lesend (POST → 405).

    Der Schreib-Endpoint POST /md/file kam mit PROJ-12 (MD-Editor) bewusst hinzu;
    die ursprüngliche read-only-Invariante für /md/file gilt daher nicht mehr —
    ein leerer POST liefert jetzt 422 (Validierung), keine 405. Die Lese-Pfade
    (/md/index) bleiben unverändert ohne Schreibmethode.
    """
    assert client.post("/md/index", json={}).status_code == 405
    # /md/file akzeptiert jetzt POST (PROJ-12) → leerer Body = 422, nicht 405.
    assert client.post("/md/file", json={}).status_code == 422


# --- Red-Team ---------------------------------------------------------------

def test_qa_project_param_can_target_other_allowed_root(reader, env):
    """Beobachtung (by design): project= darf auf JEDE erlaubte Wurzel zeigen."""
    _b, _v, _p, other = env
    root, files = reader.index("project", project=str(other))
    assert root == os.path.realpath(str(other))
    assert any(f["name"] == "notiz.md" for f in files)

def test_qa_project_param_traversal_blocked(client, env):
    """project= mit ../-Ausbruch aus allowed_roots → 400."""
    _b, _v, _p, _o = env
    r = client.get("/md/index", params={"source": "project", "project": "/home/dev/projects/../../etc"})
    assert r.status_code == 400

def test_qa_md_file_outside_roots_blocked(reader, env):
    """Absolute .md außerhalb allowed_roots → ValueError (nicht nur Nicht-.md)."""
    with pytest.raises(ValueError):
        reader.read_file("/tmp/definitely-outside-roots-xyz.md")

def test_qa71_relative_path_cannot_escape_roots(reader):
    """QA-7.1: relative Pfade werden gegen CWD aufgelöst (Contract = absolut), ABER
    der allowed_roots-Guard hält — ein ../-Ausbruch bleibt blockiert."""
    with pytest.raises((ValueError, FileNotFoundError)):
        reader.read_file("../../../../../../etc/passwd")

def test_qa_file_in_base_but_outside_listed_sources_is_reachable(reader, env):
    """Beobachtung (by design): jede .md innerhalb allowed_roots ist per absolutem
    Pfad lesbar — auch wenn sie in keinem der angezeigten Quell-Bäume liegt."""
    base, _v, _p, _o = env
    res = reader.read_file(os.path.join(str(base), "secret_outside.md"))
    assert res["body"].startswith("#")
