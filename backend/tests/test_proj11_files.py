"""PROJ-11 — Fileexplorer + Clipboard-Upload (Backend).

Isoliert: ``allowed_roots`` + ``clipboard_dir`` werden je Test auf ein tmp-
Verzeichnis umgebogen, damit kein echter Pfad berührt wird. Kein JWT/DB
(Jupiter-Override) — Sicherheit = ``realpath``-Scope + Größen-/Typ-Limits.
"""
from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.files import FileService
from app.main import create_app

from .fakes import FakeDriver

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture
def root(tmp_path, monkeypatch) -> str:
    """Erlaubte Wurzel + Clipboard-Ordner auf tmp umbiegen."""
    r = tmp_path / "roots"
    r.mkdir()
    monkeypatch.setattr(settings, "allowed_roots", [str(r)])
    monkeypatch.setattr(settings, "clipboard_dir", str(r / "clipboard"))
    return str(r)


@pytest.fixture
def client(root) -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


# --- Upload / Clipboard (Surface A + B teilen denselben Endpoint) ----------

def test_nameless_paste_gets_clip_timestamp_name(root):
    # Echter „kein Dateiname"-Fall (Service-Ebene; via TestClient nicht abbildbar).
    svc = FileService()
    entry = svc.save_upload(io.BytesIO(PNG), filename=None, content_type="image/png")
    assert entry["name"].startswith("clip-") and entry["name"].endswith(".png")
    assert entry["path"] == os.path.realpath(os.path.join(root, "clipboard", entry["name"]))
    assert os.path.isfile(entry["path"])


def test_clipboard_blob_without_extension_gets_one(client, root):
    # Browser-Paste eines Blobs: filename="blob", Endung aus content_type.
    res = client.post("/files/upload", files={"files": ("blob", PNG, "image/png")})
    assert res.status_code == 200
    entry = res.json()["files"][0]
    assert entry["name"] == "blob.png"
    assert entry["path"] == os.path.realpath(os.path.join(root, "clipboard", "blob.png"))


def test_named_upload_keeps_name(client, root):
    res = client.post("/files/upload", files={"files": ("shot.png", PNG, "image/png")})
    assert res.status_code == 200
    assert res.json()["files"][0]["name"] == "shot.png"


def test_upload_collision_gets_unique_suffix(client):
    client.post("/files/upload", files={"files": ("a.png", PNG, "image/png")})
    res = client.post("/files/upload", files={"files": ("a.png", PNG, "image/png")})
    assert res.json()["files"][0]["name"] == "a-1.png"


def test_upload_target_dir(client, root):
    sub = os.path.join(root, "ziel")
    os.makedirs(sub)
    res = client.post(
        "/files/upload",
        files={"files": ("d.png", PNG, "image/png")},
        data={"target_dir": sub},
    )
    assert res.status_code == 200
    assert res.json()["files"][0]["path"] == os.path.join(sub, "d.png")


def test_upload_too_large_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "upload_max_file_bytes", 8)
    res = client.post("/files/upload", files={"files": ("big.png", PNG, "image/png")})
    assert res.status_code == 400
    assert "zu groß" in res.json()["detail"]


def test_upload_disallowed_extension_rejected(client):
    res = client.post("/files/upload", files={"files": ("evil.exe", b"MZ", "application/octet-stream")})
    assert res.status_code == 400


def test_upload_outside_roots_rejected(client):
    res = client.post(
        "/files/upload",
        files={"files": ("x.png", PNG, "image/png")},
        data={"target_dir": "/etc"},
    )
    assert res.status_code == 400


# --- Listing / Download ----------------------------------------------------

def test_list_dir_dirs_first(client, root):
    os.makedirs(os.path.join(root, "subdir"))
    with open(os.path.join(root, "z.txt"), "w") as fh:
        fh.write("hi")
    res = client.get("/files/list", params={"path": root})
    assert res.status_code == 200
    names = [e["name"] for e in res.json()["entries"]]
    assert names == ["subdir", "z.txt"]  # Ordner zuerst
    kinds = {e["name"]: e["kind"] for e in res.json()["entries"]}
    assert kinds["subdir"] == "dir" and kinds["z.txt"] == "file"


def test_list_default_path_is_first_root(client, root):
    res = client.get("/files/list")
    assert res.status_code == 200
    assert res.json()["path"] == os.path.realpath(root)


def test_download_roundtrip(client):
    up = client.post("/files/upload", files={"files": ("dl.txt", b"hallo", "text/plain")})
    path = up.json()["files"][0]["path"]
    res = client.get("/files/download", params={"path": path})
    assert res.status_code == 200
    assert res.content == b"hallo"


def test_download_outside_roots_rejected(client):
    res = client.get("/files/download", params={"path": "/etc/passwd"})
    assert res.status_code == 400


def test_download_missing_404(client, root):
    res = client.get("/files/download", params={"path": os.path.join(root, "nope.txt")})
    assert res.status_code == 404


# --- Operationen -----------------------------------------------------------

def test_mkdir_rename_move_delete(client, root):
    # mkdir
    res = client.post("/files/mkdir", json={"parent": root, "name": "ordner"})
    assert res.status_code == 200
    folder = res.json()["path"]
    # Datei rein
    up = client.post("/files/upload", files={"files": ("f.txt", b"x", "text/plain")},
                     data={"target_dir": folder})
    f = up.json()["files"][0]["path"]
    # rename
    res = client.post("/files/rename", json={"path": f, "new_name": "g.txt"})
    assert res.status_code == 200 and res.json()["name"] == "g.txt"
    g = res.json()["path"]
    # move zurück in root
    res = client.post("/files/move", json={"path": g, "dest_dir": root})
    assert res.status_code == 200
    moved = res.json()["path"]
    assert moved == os.path.join(os.path.realpath(root), "g.txt")
    # delete (Datei + Ordner)
    res = client.post("/files/delete", json={"paths": [moved, folder]})
    body = res.json()
    assert sorted(body["deleted"]) == sorted([os.path.realpath(moved), os.path.realpath(folder)])
    assert body["failed"] == []


def test_mkdir_traversal_name_rejected(client, root):
    res = client.post("/files/mkdir", json={"parent": root, "name": "../escape"})
    assert res.status_code == 400


def test_rename_collision_409(client, root):
    client.post("/files/upload", files={"files": ("one.txt", b"1", "text/plain")},
                data={"target_dir": root})
    up = client.post("/files/upload", files={"files": ("two.txt", b"2", "text/plain")},
                     data={"target_dir": root})
    res = client.post("/files/rename", json={"path": up.json()["files"][0]["path"], "new_name": "one.txt"})
    assert res.status_code == 409


def test_delete_outside_roots_fails_softly(client):
    res = client.post("/files/delete", json={"paths": ["/etc/hosts"]})
    assert res.status_code == 200
    assert res.json()["deleted"] == [] and res.json()["failed"] == ["/etc/hosts"]


# --- Roots + Clipboard-Ordner-Einstellung ----------------------------------

def test_roots_endpoint(client, root):
    res = client.get("/files/roots")
    assert res.status_code == 200
    assert res.json() == [{"label": "roots", "path": os.path.realpath(root)}]


def test_clipboard_dir_get_creates_and_returns(client, root):
    res = client.get("/settings/clipboard-dir")
    assert res.status_code == 200
    assert res.json()["path"] == os.path.realpath(os.path.join(root, "clipboard"))
    assert os.path.isdir(res.json()["path"])


def test_clipboard_dir_patch_within_roots(client, root):
    new = os.path.join(root, "neuerclip")
    res = client.patch("/settings/clipboard-dir", json={"path": new})
    assert res.status_code == 200
    assert res.json()["path"] == os.path.realpath(new)
    # Folge-Paste landet im neuen Ordner.
    up = client.post("/files/upload", files={"files": ("p.png", PNG, "image/png")})
    assert up.json()["files"][0]["path"].startswith(os.path.realpath(new) + os.sep)


def test_clipboard_dir_patch_outside_roots_400(client):
    res = client.patch("/settings/clipboard-dir", json={"path": "/etc/clip"})
    assert res.status_code == 400


# --- Red-Team: Pfad-Härtung ------------------------------------------------

def test_list_outside_roots_rejected(client):
    assert client.get("/files/list", params={"path": "/etc"}).status_code == 400


@pytest.mark.parametrize("rel", ["../../../etc", "..", "sub/../../.."])
def test_list_traversal_rejected(client, root, rel):
    res = client.get("/files/list", params={"path": os.path.join(root, rel)})
    assert res.status_code == 400


def test_download_symlink_escape_blocked(client, root):
    # Symlink INNERHALB der Wurzel, der auf /etc/passwd ZEIGT → realpath bricht aus → 400.
    link = os.path.join(root, "escape")
    os.symlink("/etc/passwd", link)
    res = client.get("/files/download", params={"path": link})
    assert res.status_code == 400


def test_upload_symlink_target_dir_escape_blocked(client, root, tmp_path):
    # target_dir ist ein Symlink, der aus den Roots zeigt → abgelehnt, kein Schreiben außerhalb.
    outside = tmp_path / "outside"
    outside.mkdir()
    link = os.path.join(root, "outlink")
    os.symlink(str(outside), link)
    res = client.post(
        "/files/upload",
        files={"files": ("x.png", PNG, "image/png")},
        data={"target_dir": link},
    )
    assert res.status_code == 400
    assert not os.listdir(outside)  # nichts außerhalb geschrieben


def test_rename_traversal_name_rejected(client, root):
    up = client.post("/files/upload", files={"files": ("r.txt", b"1", "text/plain")},
                     data={"target_dir": root})
    res = client.post("/files/rename",
                      json={"path": up.json()["files"][0]["path"], "new_name": "../escaped.txt"})
    assert res.status_code == 400


def test_upload_no_write_permission_returns_403(client, root):
    # Low-2-Fix: kein 500 bei fehlender Schreibberechtigung, sondern 403.
    ro = os.path.join(root, "readonly")
    os.makedirs(ro)
    os.chmod(ro, 0o555)  # r-x: kein Schreiben
    try:
        res = client.post(
            "/files/upload",
            files={"files": ("x.png", PNG, "image/png")},
            data={"target_dir": ro},
        )
        assert res.status_code == 403
    finally:
        os.chmod(ro, 0o755)  # für tmp-Cleanup wiederherstellen
