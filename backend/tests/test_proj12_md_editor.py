"""PROJ-12 MD-Editor — Tests (Save atomar + Konflikt + Backlinks).

Baut auf der PROJ-7-Lese-Basis auf; ``allowed_roots`` wird pro Test auf ein
tmp-Verzeichnis gebogen → kein Test schreibt/liest je außerhalb des tmp-Baums.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.md_reader import MdConflictError, MdReaderService
from app.main import create_app

from .fakes import FakeDriver

DOC = """---
owner: "dev"
type: "note"
title: "Ziel"
---

# Ziel

Inhalt.
"""


@pytest.fixture()
def tree(tmp_path, monkeypatch):
    base = tmp_path
    vault = base / "vault"
    proj = base / "proj"
    (vault / "Agentic OS" / "Jupiter").mkdir(parents=True)
    (vault / "Agentic OS" / "Jupiter" / "vnote.md").write_text("# V\n", encoding="utf-8")
    (proj / "features").mkdir(parents=True)
    # Zielnotiz + Dateien, die (nicht) darauf verlinken.
    (proj / "Ziel.md").write_text(DOC, encoding="utf-8")
    (proj / "features" / "links.md").write_text("siehe [[Ziel]] dort\n", encoding="utf-8")
    (proj / "features" / "alias.md").write_text("siehe [[Ziel|der Plan]]\n", encoding="utf-8")
    (proj / "features" / "anchor.md").write_text("siehe [[Ziel#Abschnitt]]\n", encoding="utf-8")
    (proj / "features" / "none.md").write_text("kein link hier\n", encoding="utf-8")
    (proj / "node_modules").mkdir()
    (proj / "node_modules" / "junk.md").write_text("[[Ziel]]\n", encoding="utf-8")

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


# --- Read liefert jetzt mtime + hash (AC: Konfliktbasis) --------------------

def test_read_returns_mtime_and_hash(reader, tree):
    _b, _v, proj = tree
    res = reader.read_file(str(proj / "Ziel.md"))
    assert isinstance(res["mtime"], float)
    assert isinstance(res["hash"], str) and len(res["hash"]) == 64


# --- Save (AC1: laden → speichern, atomar) ----------------------------------

def test_save_writes_content_and_returns_meta(reader, tree):
    _b, _v, proj = tree
    target = str(proj / "Ziel.md")
    new = DOC + "\nNeue Zeile.\n"
    res = reader.save_file(target, new)
    assert res["path"] == target
    assert reader.read_file(target)["content"] == new
    assert res["hash"] == reader.read_file(target)["hash"]


def test_save_can_create_new_file(reader, tree):
    _b, _v, proj = tree
    target = str(proj / "features" / "neu.md")
    reader.save_file(target, "# Neu\n")
    assert reader.read_file(target)["body"].startswith("# Neu")


# --- Edge: ungültiges Frontmatter → kein Schreibvorgang ---------------------

def test_save_invalid_frontmatter_rejected(reader, tree):
    _b, _v, proj = tree
    target = str(proj / "Ziel.md")
    before = reader.read_file(target)["content"]
    with pytest.raises(ValueError):
        reader.save_file(target, "---\nowner: dev\ntitle: x\n\n# Frontmatter ohne Abschluss\n")
    # Datei unverändert (kein Datenverlust).
    assert reader.read_file(target)["content"] == before


# --- Edge: externe Änderung → Konflikt (mtime/Hash) -------------------------

def test_save_conflict_when_changed_externally(reader, tree):
    _b, _v, proj = tree
    target = str(proj / "Ziel.md")
    loaded = reader.read_file(target)
    # Externe Änderung simulieren.
    (proj / "Ziel.md").write_text(DOC + "\nFremd.\n", encoding="utf-8")
    with pytest.raises(MdConflictError):
        reader.save_file(
            target,
            DOC + "\nMeins.\n",
            expected_mtime=loaded["mtime"],
            expected_hash=loaded["hash"],
        )


def test_save_force_overwrites_conflict(reader, tree):
    _b, _v, proj = tree
    target = str(proj / "Ziel.md")
    loaded = reader.read_file(target)
    (proj / "Ziel.md").write_text(DOC + "\nFremd.\n", encoding="utf-8")
    reader.save_file(
        target,
        DOC + "\nMeins.\n",
        expected_mtime=loaded["mtime"],
        expected_hash=loaded["hash"],
        force=True,
    )
    assert "Meins." in reader.read_file(target)["content"]


def test_save_no_conflict_when_unchanged(reader, tree):
    _b, _v, proj = tree
    target = str(proj / "Ziel.md")
    loaded = reader.read_file(target)
    reader.save_file(
        target,
        DOC + "\nWeiter.\n",
        expected_mtime=loaded["mtime"],
        expected_hash=loaded["hash"],
    )
    assert "Weiter." in reader.read_file(target)["content"]


# --- Security: Schreiben außerhalb der Roots blockiert ----------------------

def test_save_traversal_blocked(reader):
    with pytest.raises(ValueError):
        reader.save_file("/tmp/evil.md", "# nope\n")
    with pytest.raises(ValueError):
        reader.save_file("/etc/passwd", "x")


def test_save_dotdot_escape_blocked(reader, tree):
    """Red-Team: ../ aus der Wurzel heraus → realpath landet außerhalb → ValueError."""
    _b, _v, proj = tree
    with pytest.raises(ValueError):
        reader.save_file(str(proj / ".." / ".." / "etc_evil.md"), "# nope\n")


def test_save_non_md_rejected(reader, tree):
    """Red-Team: Speichern in eine Nicht-.md (z. B. überschreiben einer Config) → ValueError."""
    _b, _v, proj = tree
    with pytest.raises(ValueError):
        reader.save_file(str(proj / "config.yaml"), "evil: true\n")


def test_save_symlink_escape_blocked(reader, tree):
    """Red-Team: .md-Symlink, der aus den Roots zeigt → realpath blockt das Schreiben."""
    import os

    _b, _v, proj = tree
    outside = os.path.join("/tmp", f"jupiter_qa_escape_{os.getpid()}.md")
    with open(outside, "w", encoding="utf-8") as fh:
        fh.write("# original außerhalb\n")
    link = proj / "features" / "escape.md"
    try:
        os.symlink(outside, link)
        with pytest.raises(ValueError):
            reader.save_file(str(link), "# überschrieben\n")
        # Ziel außerhalb der Roots blieb unangetastet.
        with open(outside, encoding="utf-8") as fh:
            assert "original außerhalb" in fh.read()
    finally:
        os.unlink(outside)


def test_backlinks_traversal_blocked(reader):
    with pytest.raises(ValueError):
        reader.backlinks("/etc/passwd")


# --- Backlinks (AC: wer verlinkt hierher) -----------------------------------

def test_backlinks_finds_linking_notes(reader, tree):
    _b, _v, proj = tree
    links = reader.backlinks(str(proj / "Ziel.md"))
    names = {e["name"] for e in links}
    # Plain, Alias und Anchor zählen; Datei ohne Link und node_modules nicht.
    assert {"links.md", "alias.md", "anchor.md"} <= names
    assert "none.md" not in names
    assert "junk.md" not in names
    assert "Ziel.md" not in names  # Selbstreferenz ausgeschlossen


def test_backlinks_empty_for_unlinked(reader, tree):
    _b, _v, proj = tree
    assert reader.backlinks(str(proj / "features" / "none.md")) == []


# --- API-Ebene --------------------------------------------------------------

def test_api_save_roundtrip(client, tree):
    _b, _v, proj = tree
    target = str(proj / "Ziel.md")
    r = client.post("/md/file", json={"path": target, "content": DOC + "\nAPI.\n"})
    assert r.status_code == 200
    assert set(r.json()) == {"path", "mtime", "hash"}
    got = client.get("/md/file", params={"path": target})
    assert "API." in got.json()["content"]


def test_api_save_conflict_409(client, tree):
    _b, _v, proj = tree
    target = str(proj / "Ziel.md")
    loaded = client.get("/md/file", params={"path": target}).json()
    (proj / "Ziel.md").write_text(DOC + "\nFremd.\n", encoding="utf-8")
    r = client.post(
        "/md/file",
        json={
            "path": target,
            "content": DOC + "\nMeins.\n",
            "expected_mtime": loaded["mtime"],
            "expected_hash": loaded["hash"],
        },
    )
    assert r.status_code == 409


def test_api_save_invalid_frontmatter_400(client, tree):
    _b, _v, proj = tree
    r = client.post(
        "/md/file",
        json={"path": str(proj / "Ziel.md"), "content": "---\nx: 1\ny: 2\n\n# offen\n"},
    )
    assert r.status_code == 400


def test_api_save_traversal_400(client):
    r = client.post("/md/file", json={"path": "/etc/passwd", "content": "x"})
    assert r.status_code == 400


def test_api_backlinks_200(client, tree):
    _b, _v, proj = tree
    r = client.get("/md/backlinks", params={"path": str(proj / "Ziel.md")})
    assert r.status_code == 200
    assert {e["name"] for e in r.json()["backlinks"]} >= {"links.md", "alias.md"}


def test_api_backlinks_not_found_404(client, tree):
    _b, _v, proj = tree
    r = client.get("/md/backlinks", params={"path": str(proj / "fehlt.md")})
    assert r.status_code == 404
