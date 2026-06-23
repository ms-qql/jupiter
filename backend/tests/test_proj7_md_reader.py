"""PROJ-7 MD-Reader — Tests (read-only Markdown über Vault + Projekt).

Sicherheits-Isolation: ``allowed_roots`` wird pro Test auf ein tmp-Verzeichnis
gebogen → kein Test liest je außerhalb des tmp-Baums.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.md_reader import MdReaderService
from app.main import create_app

from .fakes import FakeDriver

DOC = """---
owner: "dev"
type: "handover"
title: "Mein Doc"
---

# Überschrift

Inhalt mit [[Ziel]]-Wikilink.
"""


@pytest.fixture()
def tree(tmp_path, monkeypatch):
    """Legt einen Vault- und einen Projekt-Baum unter tmp an und biegt die Roots dorthin."""
    base = tmp_path
    vault = base / "vault"
    proj = base / "proj"
    # Vault: Jupiter-Artefakte
    (vault / "Agentic OS" / "Jupiter" / "Handovers").mkdir(parents=True)
    (vault / "Agentic OS" / "Jupiter" / "Handovers" / "h1.md").write_text(DOC, encoding="utf-8")
    (vault / "00 Context").mkdir(parents=True)
    (vault / "00 Context" / "note.md").write_text("# Private Notiz\n", encoding="utf-8")
    # Projekt: Feature-Specs + Rauschen, das übersprungen werden muss
    (proj / "features").mkdir(parents=True)
    (proj / "features" / "PROJ-7-md-reader.md").write_text("# Spec\n", encoding="utf-8")
    (proj / "README.md").write_text("# Readme\n", encoding="utf-8")
    (proj / "node_modules" / "pkg").mkdir(parents=True)
    (proj / "node_modules" / "pkg" / "junk.md").write_text("# nope\n", encoding="utf-8")
    (proj / ".git").mkdir()
    (proj / ".git" / "x.md").write_text("# nope\n", encoding="utf-8")
    (proj / "logo.png").write_text("notmd", encoding="utf-8")

    monkeypatch.setattr(settings, "allowed_roots", [str(base)])
    monkeypatch.setattr(settings, "vault_root", str(vault))
    monkeypatch.setattr(settings, "reader_default_project", str(proj))
    return base, vault, proj


@pytest.fixture()
def reader(tree) -> MdReaderService:
    return MdReaderService()


@pytest.fixture()
def client(tree) -> TestClient:
    app = create_app(driver_factory=lambda: FakeDriver())
    return TestClient(app)


# --- Acceptance Criteria ----------------------------------------------------

def test_ac_read_separates_frontmatter_and_body(reader, tree):
    """AC4: Frontmatter wird sauber (als Objekt) getrennt vom Body geliefert."""
    _base, vault, _proj = tree
    res = reader.read_file(str(vault / "Agentic OS" / "Jupiter" / "Handovers" / "h1.md"))
    assert res["frontmatter"]["title"] == "Mein Doc"
    assert res["frontmatter"]["type"] == "handover"
    assert res["body"].lstrip().startswith("# Überschrift")
    assert "---" not in res["body"]  # Frontmatter nicht im Body


def test_ac_index_builds_tree_and_wikilink_basis(reader):
    """AC1/AC3: flacher Index liefert path/rel/name für Baum + Wikilink-Auflösung."""
    root, files = reader.index("project")
    rels = {f["rel"] for f in files}
    assert "features/PROJ-7-md-reader.md" in rels
    assert "README.md" in rels
    # rel ist relativ zur Wurzel, name der Basisname, path absolut.
    spec = next(f for f in files if f["rel"].endswith("PROJ-7-md-reader.md"))
    assert spec["name"] == "PROJ-7-md-reader.md"
    assert os.path.isabs(spec["path"]) and spec["path"].startswith(root)


def test_index_excludes_noise_and_non_md(reader):
    """Index überspringt node_modules/.git und Nicht-MD (DoS-/Rausch-Schutz)."""
    _root, files = reader.index("project")
    paths = " ".join(f["rel"] for f in files)
    assert "node_modules" not in paths
    assert ".git" not in paths
    assert "logo.png" not in paths


def test_sources_lists_vault_and_project(reader):
    sources = reader.sources()
    ids = {s["id"] for s in sources}
    assert ids == {"vault", "project"}


def test_vault_source_sees_whole_vault(reader):
    """Browse-Scope: Vault-Quelle zeigt den ganzen Vault (inkl. PARA), read-only."""
    _root, files = reader.index("vault")
    rels = {f["rel"] for f in files}
    assert "00 Context/note.md" in rels
    assert "Agentic OS/Jupiter/Handovers/h1.md" in rels


# --- Edge Cases + Security --------------------------------------------------

def test_read_nonexistent_raises(reader, tree):
    _base, _vault, proj = tree
    with pytest.raises(FileNotFoundError):
        reader.read_file(str(proj / "features" / "fehlt.md"))


def test_read_non_md_rejected(reader, tree):
    """Nicht-MD-Datei → klarer Fehler statt Fehlversuch (Edge-Case)."""
    _base, _vault, proj = tree
    with pytest.raises(ValueError):
        reader.read_file(str(proj / "logo.png"))


def test_path_traversal_outside_roots_blocked(reader):
    """Absoluter Pfad außerhalb der allowed_roots → ValueError (kein Lesen von /etc/passwd)."""
    with pytest.raises(ValueError):
        reader.read_file("/etc/passwd")
    with pytest.raises(ValueError):
        reader.read_file("/etc/hosts")


def test_symlink_escape_skipped_in_index(reader, tree):
    """Symlink im Projekt, der aus der Wurzel zeigt → wird im Index übersprungen."""
    _base, _vault, proj = tree
    # Lege ein Ziel klar außerhalb der Wurzel an und linke darauf.
    target = os.path.join("/tmp", f"jupiter_secret_{os.getpid()}.md")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("# geheim\n")
    try:
        link = proj / "features" / "link.md"
        os.symlink(target, link)
        _root, files = reader.index("project")
        # Der Symlink, dessen realpath außerhalb der Wurzel liegt, darf NICHT auftauchen.
        assert all("/tmp/jupiter_secret_" not in f["path"] for f in files)
    finally:
        os.unlink(target)


def test_unknown_source_rejected(reader):
    with pytest.raises(ValueError):
        reader.index("bogus")


# --- API-Ebene --------------------------------------------------------------

def test_api_sources(client):
    r = client.get("/md/sources")
    assert r.status_code == 200
    assert {s["id"] for s in r.json()} == {"vault", "project"}


def test_api_index_and_file_roundtrip(client):
    idx = client.get("/md/index", params={"source": "project"})
    assert idx.status_code == 200
    spec = next(f for f in idx.json()["files"] if f["name"] == "PROJ-7-md-reader.md")
    r = client.get("/md/file", params={"path": spec["path"]})
    assert r.status_code == 200
    assert r.json()["body"].lstrip().startswith("# Spec")


def test_api_file_traversal_400(client):
    r = client.get("/md/file", params={"path": "/etc/passwd"})
    assert r.status_code == 400


def test_api_file_not_found_404(client, tree):
    _base, _vault, proj = tree
    r = client.get("/md/file", params={"path": str(proj / "features" / "nope.md")})
    assert r.status_code == 404


def test_api_index_unknown_source_400(client):
    r = client.get("/md/index", params={"source": "bogus"})
    assert r.status_code == 400
