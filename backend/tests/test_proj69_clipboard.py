"""PROJ-69 — Clipboard-Micro-App Backend."""
from __future__ import annotations

import os
import signal
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.clipboard_items import REMOVED, SqliteClipboardRepository
from app.engine.clipboard import ClipboardService
from app.main import create_app

from .fakes import FakeDriver


def _scope(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    inbox = vault / "00 Inbox" / "Clipboard"
    monkeypatch.setattr(settings, "vault_root", str(vault))
    monkeypatch.setattr(settings, "clipboard_inbox_dir", str(inbox))
    monkeypatch.setattr(settings, "clipboard_db_path", str(tmp_path / "clipboard.db"))
    monkeypatch.setattr(settings, "allowed_roots", ["/home/dev/projects", "/home/dev", str(tmp_path)])
    return vault, inbox


async def test_service_add_upload_writes_hal_file_sidecar_and_db(tmp_path, monkeypatch):
    _vault, inbox = _scope(monkeypatch, tmp_path)
    repo = SqliteClipboardRepository(str(tmp_path / "clipboard.db"))
    svc = ClipboardService(repo)
    await svc.startup()

    row = await svc.add_upload(
        BytesIO(b"image-bytes"),
        "Screenshot 1.png",
        "image/png",
        source_method="paste",
        source_device="ipad",
        notes="Testnotiz",
    )

    assert row["status"] == "active"
    assert row["source_method"] == "paste"
    assert row["source_device"] == "ipad"
    assert row["display_name"] == "Screenshot 1.png"
    assert row["size_bytes"] == len(b"image-bytes")
    assert row["hal_inbox_path"].startswith(str(inbox))
    assert row["metadata_path"].startswith(str(inbox))
    assert row["hal_inbox_path"].endswith(".png")
    assert row["metadata_path"].endswith(".md")
    assert (inbox / row["hal_inbox_path"].split("/")[-1]).read_bytes() == b"image-bytes"
    sidecar = (inbox / row["metadata_path"].split("/")[-1]).read_text()
    assert "type: clipboard-item" in sidecar
    assert "source_method: paste" in sidecar
    assert "Testnotiz" in sidecar

    listed = await svc.list_items()
    assert [x["id"] for x in listed] == [row["id"]]


async def test_service_remove_hides_item_but_keeps_hal_file(tmp_path, monkeypatch):
    _vault, _inbox = _scope(monkeypatch, tmp_path)
    repo = SqliteClipboardRepository(str(tmp_path / "clipboard.db"))
    svc = ClipboardService(repo)
    await svc.startup()
    row = await svc.add_upload(BytesIO(b"pdf"), "a.pdf", "application/pdf")
    path = row["hal_inbox_path"]

    await svc.remove_item(row["id"])

    assert await svc.list_items() == []
    stored = await repo.get(row["id"])
    assert stored["status"] == REMOVED
    assert stored["removed_at"] is not None
    assert (tmp_path / "vault" / "00 Inbox" / "Clipboard").exists()
    assert path and os.path.exists(path)


async def test_service_rejects_too_large_without_leaving_active_item(tmp_path, monkeypatch):
    _vault, inbox = _scope(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "upload_max_file_bytes", 4)
    repo = SqliteClipboardRepository(str(tmp_path / "clipboard.db"))
    svc = ClipboardService(repo)
    await svc.startup()

    with pytest.raises(ValueError):
        await svc.add_upload(BytesIO(b"too-large"), "big.pdf", "application/pdf")

    assert await svc.list_items() == []
    assert [p.name for p in inbox.iterdir()] == []


async def test_service_duplicate_filename_within_same_second_creates_distinct_items(
    tmp_path, monkeypatch
):
    """Regression für BUG-1: Namenskollision durfte _target_paths NIE in eine
    Endlosschleife schicken (stale `stem` statt Kandidaten-Stem im .md-Check).
    SIGALRM sorgt dafür, dass ein Rückfall den Test hart fehlschlagen laesst,
    statt die ganze Suite aufzuhängen."""
    _vault, inbox = _scope(monkeypatch, tmp_path)
    repo = SqliteClipboardRepository(str(tmp_path / "clipboard.db"))
    svc = ClipboardService(repo)
    await svc.startup()

    def _on_alarm(signum, frame):
        raise TimeoutError("_target_paths haengt vermutlich in einer Endlosschleife (BUG-1)")

    previous = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(5)
    try:
        first = await svc.add_upload(
            BytesIO(b"a"), "dup.png", "image/png",
            source_method="drag_drop", source_device="pc",
        )
        second = await svc.add_upload(
            BytesIO(b"b"), "dup.png", "image/png",
            source_method="drag_drop", source_device="pc",
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)

    assert first["id"] != second["id"]
    assert first["hal_inbox_path"] != second["hal_inbox_path"]
    assert first["display_name"] == second["display_name"] == "dup.png"
    assert os.path.exists(first["hal_inbox_path"])
    assert os.path.exists(second["hal_inbox_path"])

    listed = await svc.list_items()
    assert {row["id"] for row in listed} == {first["id"], second["id"]}


async def test_repository_persists_across_service_restart(tmp_path, monkeypatch):
    _scope(monkeypatch, tmp_path)
    db = str(tmp_path / "clipboard.db")
    svc1 = ClipboardService(SqliteClipboardRepository(db))
    await svc1.startup()
    await svc1.add_upload(BytesIO(b"hello"), "hello.txt", "text/plain")

    svc2 = ClipboardService(SqliteClipboardRepository(db))
    await svc2.startup()
    rows = await svc2.list_items()
    assert len(rows) == 1
    assert rows[0]["display_name"] == "hello.txt"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    _scope(monkeypatch, tmp_path)
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as c:
        yield c


def test_api_upload_list_download_patch_and_remove(client):
    upload = client.post(
        "/clipboard/items",
        files={"file": ("shot.png", b"PNGDATA", "image/png")},
        data={"source_method": "drag_drop", "source_device": "pc", "notes": "Quelle"},
    )
    assert upload.status_code == 200
    item = upload.json()
    assert item["display_name"] == "shot.png"
    assert item["source_method"] == "drag_drop"
    assert item["source_device"] == "pc"
    assert item["size_bytes"] == len(b"PNGDATA")

    listed = client.get("/clipboard/items").json()["items"]
    assert len(listed) == 1 and listed[0]["id"] == item["id"]

    downloaded = client.get(f"/clipboard/items/{item['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"PNGDATA"

    preview = client.get(f"/clipboard/items/{item['id']}/preview")
    assert preview.status_code == 200
    assert preview.content == b"PNGDATA"

    patched = client.patch(
        f"/clipboard/items/{item['id']}",
        json={"display_name": "Neuer Name.png", "notes": "Neue Notiz"},
    )
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Neuer Name.png"
    assert patched.json()["notes"] == "Neue Notiz"

    removed = client.delete(f"/clipboard/items/{item['id']}")
    assert removed.status_code == 204
    assert client.get("/clipboard/items").json()["items"] == []
    # Datei bleibt auch nach Entfernen downloadbar, weil nur die aktive Liste bereinigt wird.
    assert client.get(f"/clipboard/items/{item['id']}/download").content == b"PNGDATA"


def test_api_rejects_bad_source_method_and_unknown_item(client):
    bad = client.post(
        "/clipboard/items",
        files={"file": ("x.pdf", b"x", "application/pdf")},
        data={"source_method": "bad"},
    )
    assert bad.status_code == 400
    assert "Quelle" in bad.json()["detail"]

    missing = client.get("/clipboard/items/999")
    assert missing.status_code == 404
    assert client.delete("/clipboard/items/999").status_code == 404


def test_api_settings(client):
    r = client.get("/clipboard/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["max_file_bytes"] == settings.upload_max_file_bytes
    assert body["inbox_dir"].endswith("00 Inbox/Clipboard")
    assert "png" in body["allowed_extensions"]
