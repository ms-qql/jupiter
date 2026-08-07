"""PROJ-76 — Textdateien im Fileexplorer bearbeiten (Backend).

Isoliert wie PROJ-11: ``allowed_roots`` auf tmp-Verzeichnis umgebogen.
Deckt Editierbarkeits-Flag, Lesen/Schreiben, Konflikterkennung (409),
Größen-/Typ-/UTF-8-Grenzen (400) und fehlende Datei (404) ab.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.files import FileService
from app.main import create_app

from .fakes import FakeDriver


@pytest.fixture
def root(tmp_path, monkeypatch) -> str:
    r = tmp_path / "roots"
    r.mkdir()
    monkeypatch.setattr(settings, "allowed_roots", [str(r)])
    monkeypatch.setattr(settings, "clipboard_dir", str(r / "clipboard"))
    return str(r)


@pytest.fixture
def client(root) -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


def _write(root: str, name: str, content: bytes) -> str:
    path = os.path.join(root, name)
    with open(path, "wb") as f:
        f.write(content)
    return path


# --- editable-Flag im Listing -----------------------------------------------

def test_list_marks_text_file_editable(client, root):
    _write(root, "notiz.md", b"# Hallo")
    res = client.get("/files/list", params={"path": root})
    entry = res.json()["entries"][0]
    assert entry["editable"] is True


def test_list_marks_binary_extension_not_editable(client, root):
    _write(root, "bild.png", b"\x89PNG\r\n\x1a\n")
    res = client.get("/files/list", params={"path": root})
    entry = res.json()["entries"][0]
    assert entry["editable"] is False


def test_list_marks_oversized_text_file_not_editable(client, root):
    _write(root, "gross.txt", b"x" * (2 * 1024 * 1024 + 1))
    res = client.get("/files/list", params={"path": root})
    entry = res.json()["entries"][0]
    assert entry["editable"] is False


# --- Lesen -------------------------------------------------------------------

def test_read_text_returns_content_size_hash(client, root):
    path = _write(root, "a.txt", b"hallo welt")
    res = client.get("/files/text", params={"path": path})
    assert res.status_code == 200
    body = res.json()
    assert body["content"] == "hallo welt"
    assert body["size"] == len(b"hallo welt")
    assert len(body["hash"]) == 64  # sha256 hex


def test_read_empty_file_ok(client, root):
    path = _write(root, "leer.txt", b"")
    res = client.get("/files/text", params={"path": path})
    assert res.status_code == 200
    assert res.json()["content"] == ""


def test_read_non_utf8_rejected_400(client, root):
    path = _write(root, "bin.txt", b"\xff\xfe\x00\x01")
    res = client.get("/files/text", params={"path": path})
    assert res.status_code == 400
    assert "UTF-8" in res.json()["detail"]


def test_read_oversized_rejected_400(client, root):
    path = _write(root, "gross.txt", b"x" * (2 * 1024 * 1024 + 1))
    res = client.get("/files/text", params={"path": path})
    assert res.status_code == 400


def test_read_disallowed_extension_rejected_400(client, root):
    path = _write(root, "bild.png", b"\x89PNG")
    res = client.get("/files/text", params={"path": path})
    assert res.status_code == 400


def test_read_missing_file_404(client, root):
    res = client.get("/files/text", params={"path": os.path.join(root, "nope.txt")})
    assert res.status_code == 404


def test_read_outside_roots_rejected_400(client):
    res = client.get("/files/text", params={"path": "/etc/passwd"})
    assert res.status_code == 400


# --- Schreiben -----------------------------------------------------------------

def test_write_text_roundtrip_updates_content_and_hash(client, root):
    path = _write(root, "a.txt", b"alt")
    read = client.get("/files/text", params={"path": path}).json()
    res = client.put("/files/text", json={
        "path": path, "content": "neu", "hash": read["hash"],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["content"] == "neu"
    assert body["hash"] != read["hash"]
    with open(path, "r") as f:
        assert f.read() == "neu"


def test_write_conflict_returns_409_when_externally_changed(client, root):
    path = _write(root, "a.txt", b"alt")
    read = client.get("/files/text", params={"path": path}).json()
    # externe Änderung, ohne den Editor zu benutzen
    with open(path, "w") as f:
        f.write("von außen geändert")
    res = client.put("/files/text", json={
        "path": path, "content": "mein entwurf", "hash": read["hash"],
    })
    assert res.status_code == 409
    with open(path, "r") as f:
        assert f.read() == "von außen geändert"  # nicht still überschrieben


def test_write_force_overwrites_despite_conflict(client, root):
    path = _write(root, "a.txt", b"alt")
    read = client.get("/files/text", params={"path": path}).json()
    with open(path, "w") as f:
        f.write("von außen geändert")
    res = client.put("/files/text", json={
        "path": path, "content": "mein entwurf", "hash": read["hash"], "force": True,
    })
    assert res.status_code == 200
    with open(path, "r") as f:
        assert f.read() == "mein entwurf"


def test_write_missing_file_404(client, root):
    res = client.put("/files/text", json={
        "path": os.path.join(root, "nope.txt"), "content": "x", "hash": "abc",
    })
    assert res.status_code == 404


def test_write_oversized_content_rejected_400(client, root):
    path = _write(root, "a.txt", b"alt")
    read = client.get("/files/text", params={"path": path}).json()
    res = client.put("/files/text", json={
        "path": path, "content": "x" * (2 * 1024 * 1024 + 1), "hash": read["hash"],
    })
    assert res.status_code == 400


def test_write_no_permission_returns_403(client, root):
    path = _write(root, "a.txt", b"alt")
    read = client.get("/files/text", params={"path": path}).json()
    os.chmod(root, 0o555)
    try:
        res = client.put("/files/text", json={
            "path": path, "content": "neu", "hash": read["hash"],
        })
        assert res.status_code == 403
    finally:
        os.chmod(root, 0o755)


def test_write_leaves_no_partial_file_on_failure(client, root, monkeypatch):
    """Schreibfehler mitten im Atomic-Write darf keine Teil-Datei hinterlassen."""
    path = _write(root, "a.txt", b"alt")
    read = client.get("/files/text", params={"path": path}).json()

    svc = FileService()
    real_replace = os.replace

    def boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        svc.write_text(path, "neu", read["hash"])
    monkeypatch.setattr(os, "replace", real_replace)

    with open(path, "r") as f:
        assert f.read() == "alt"  # ursprüngliche Datei unverändert
    assert not any(n.endswith(".tmp") for n in os.listdir(root))  # kein Leichnam


def test_write_symlink_escape_blocked(client, root):
    outside = os.path.join(os.path.dirname(root), "outside.txt")
    with open(outside, "w") as f:
        f.write("geheim")
    link = os.path.join(root, "escape.txt")
    os.symlink(outside, link)
    res = client.put("/files/text", json={"path": link, "content": "x", "hash": "abc"})
    assert res.status_code == 400
    with open(outside, "r") as f:
        assert f.read() == "geheim"
    os.remove(outside)
