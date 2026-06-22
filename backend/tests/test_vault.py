"""Tests für PROJ-2 (Vault-Anbindung): VaultService-Unit + API-Integration + Autolog."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.engine.vault import VaultService, _parse_frontmatter, slugify
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


# --- Unit: Helfer -----------------------------------------------------------

def test_slugify_umlaut():
    assert slugify("Übergabe für Café & Stuff") == "uebergabe-fuer-cafe-stuff"
    assert slugify("") == "untitled"


def test_frontmatter_roundtrip():
    fm, body = _parse_frontmatter('---\nowner: "dev"\ntype: "handover"\n---\nHallo Welt\n')
    assert fm == {"owner": "dev", "type": "handover"}
    assert body == "Hallo Welt\n"


# --- Unit: VaultService -----------------------------------------------------

@pytest.fixture()
def vault(tmp_path) -> VaultService:
    return VaultService(vault_root=str(tmp_path / "vault"))


def test_write_creates_valid_md_with_frontmatter(vault):
    res = vault.write(type="handover", body="Inhalt", title="Mein Doc", session_id="abcd1234ef", owner="dev")
    full = os.path.join(vault.vault_root, res.path)
    assert os.path.exists(full)
    assert res.path.startswith("Agentic OS/Jupiter/Handovers/")
    fm, body = _parse_frontmatter(open(full, encoding="utf-8").read())
    for key in ("owner", "session_id", "created", "type"):
        assert key in fm  # AC: Pflicht-Frontmatter
    assert fm["type"] == "handover"
    assert "Inhalt" in body


def test_write_session_log_lands_in_sessions(vault):
    res = vault.write(type="session_log", body="Log", title="jupiter", session_id="11112222")
    assert res.path.startswith("Agentic OS/Jupiter/Sessions/")


def test_read_and_list_roundtrip(vault):
    res = vault.write(type="handover", body="ABC", title="Doc")
    read = vault.read_file(res.path)
    assert read["frontmatter"]["type"] == "handover"
    assert "ABC" in read["body"]
    listed = [f["path"] for f in vault.list_files()]
    assert res.path in listed


def test_search_finds_match_with_excerpt(vault):
    vault.write(type="handover", body="Der geheime Schatz liegt im Keller.", title="Karte")
    hits = vault.search("geheime schatz")
    assert len(hits) == 1
    assert "Schatz" in hits[0]["excerpt"]
    assert hits[0]["path"].endswith(".md")


def test_search_scans_whole_vault_not_only_jupiter(vault, tmp_path):
    # Datei außerhalb des Jupiter-Bereichs (z. B. bestehendes PARA-Wissen).
    other = os.path.join(vault.vault_root, "02 Projects", "Fremd.md")
    os.makedirs(os.path.dirname(other), exist_ok=True)
    open(other, "w", encoding="utf-8").write("Apfelkuchen Rezept")
    hits = vault.search("apfelkuchen")
    assert len(hits) == 1
    assert hits[0]["path"] == "02 Projects/Fremd.md"


def test_on_exists_append_default(vault):
    a = vault.write(type="handover", body="erste", title="Tag", session_id="ses", created=_fixed())
    b = vault.write(type="handover", body="zweite", title="Tag", session_id="ses", created=_fixed())
    assert a.path == b.path  # gleiche Datei
    content = open(os.path.join(vault.vault_root, a.path), encoding="utf-8").read()
    assert "erste" in content and "zweite" in content
    assert content.count("---\n") <= 2  # kein zweites Frontmatter beim Append


def test_on_exists_version_creates_new_file(vault):
    a = vault.write(type="handover", body="x", title="Tag", session_id="ses", created=_fixed())
    b = vault.write(type="handover", body="y", title="Tag", session_id="ses", created=_fixed(), on_exists="version")
    assert a.path != b.path
    assert b.path.endswith("-2.md")


def test_on_exists_error_raises(vault):
    vault.write(type="handover", body="x", title="Tag", session_id="ses", created=_fixed())
    with pytest.raises(FileExistsError):
        vault.write(type="handover", body="y", title="Tag", session_id="ses", created=_fixed(), on_exists="error")


def test_unknown_type_rejected(vault):
    with pytest.raises(ValueError):
        vault.write(type="evil", body="x")


# --- Security: Pfad-Traversal ----------------------------------------------

@pytest.mark.parametrize("bad", ["../../etc/passwd", "..", "a/../../b", "/etc/passwd", ""])
def test_read_path_traversal_rejected(vault, bad):
    with pytest.raises((ValueError, FileNotFoundError, IsADirectoryError)):
        vault.read_file(bad)


def test_write_stays_in_jupiter_subtree(vault):
    # Es gibt keinen API-Weg, den Zielordner frei zu wählen — der subdir kommt aus `type`.
    # Direkte Härtung: _resolve_write lehnt Ausbruch ab.
    with pytest.raises(ValueError):
        vault._resolve_write("../../../etc/passwd")


def test_atomic_write_leaves_no_tmp(vault):
    res = vault.write(type="handover", body="x", title="Doc")
    d = os.path.dirname(os.path.join(vault.vault_root, res.path))
    assert not any(f.endswith(".tmp") for f in os.listdir(d))


# --- API-Integration --------------------------------------------------------

@pytest.fixture()
def client(tmp_path) -> TestClient:
    app = create_app(
        driver_factory=lambda: FakeDriver(),
        vault_service=VaultService(vault_root=str(tmp_path / "vault")),
    )
    return TestClient(app)


def test_api_write_read_list_search(client: TestClient):
    w = client.post("/vault/files", json={"type": "handover", "body": "Notiz mit Suchwort Drache", "title": "API Doc"})
    assert w.status_code == 201
    path = w.json()["path"]

    r = client.get("/vault/file", params={"path": path})
    assert r.status_code == 200
    assert r.json()["frontmatter"]["type"] == "handover"

    lst = client.get("/vault/files")
    assert path in [f["path"] for f in lst.json()]

    s = client.get("/vault/search", params={"q": "drache"})
    assert s.status_code == 200
    assert len(s.json()["hits"]) == 1


def test_api_read_missing_404(client: TestClient):
    assert client.get("/vault/file", params={"path": "Agentic OS/Jupiter/Sessions/nope.md"}).status_code == 404


def test_api_read_traversal_400(client: TestClient):
    assert client.get("/vault/file", params={"path": "../../etc/passwd"}).status_code == 400


def test_api_write_conflict_409(client: TestClient):
    body = {"type": "handover", "body": "x", "title": "Konflikt", "session_id": "ses", "on_exists": "error"}
    assert client.post("/vault/files", json=body).status_code == 201
    assert client.post("/vault/files", json=body).status_code == 409


def test_api_invalid_type_422(client: TestClient):
    assert client.post("/vault/files", json={"type": "session", "body": "x"}).status_code == 422


def test_handover_endpoint_writes_curated_doc(client: TestClient):
    sid = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "Hi", "model": "haiku"}).json()["session_id"]
    h = client.post(f"/sessions/{sid}/handover", json={"body": "Übergabe-Stand: fertig.", "title": "Stand"})
    assert h.status_code == 201
    assert h.json()["path"].startswith("Agentic OS/Jupiter/Handovers/")


def test_handover_unknown_session_404(client: TestClient):
    assert client.post("/sessions/nope/handover", json={"body": "x"}).status_code == 404


def test_autolog_writes_session_log_on_stop(client: TestClient):
    sid = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "Hi", "model": "haiku"}).json()["session_id"]
    # FakeDriver.stop() emittiert ``closed`` → Session DONE → Auto-Log-Hook.
    assert client.post(f"/sessions/{sid}/stop").status_code == 200
    logs = client.get("/vault/files", params={"dir": "Sessions"}).json()
    assert len(logs) == 1
    assert logs[0]["path"].startswith("Agentic OS/Jupiter/Sessions/")


# --- helpers ----------------------------------------------------------------

def _fixed():
    from datetime import datetime, timezone

    return datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
