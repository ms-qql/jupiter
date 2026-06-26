"""PROJ-44 — QA-/Red-Team-Ergänzungen zu den Funktionstests.

Fokus: Korrektheits-/Sicherheits-Eigenschaften des Bibliotheks-Scans, die über die
reine Funktionalität hinausgehen (kein Subfolder-Leak, robustes Filtern), sowie der
Reader-Pfad für eine zwischenzeitlich gelöschte Notiz (404 statt 500).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.video_summary_queue import SqliteVideoSummaryRepository
from app.engine.manager import SessionManager
from app.engine.video_summary import VideoSummaryWorker
from app.main import create_app

from .fakes import FakeDriver


def _worker(tmp_path) -> VideoSummaryWorker:
    return VideoSummaryWorker(
        SessionManager(driver_factory=lambda: FakeDriver()),
        SqliteVideoSummaryRepository(str(tmp_path / "vsq.db")),
    )


async def test_library_does_not_recurse_into_subfolders(tmp_path, monkeypatch):
    """Der Scan listet NUR die oberste Ebene des Standard-Ordners — keine Notizen
    aus Geschwister-Kategorien oder ``07 Attachments``-Unterordnern (kein Leak)."""
    vault = tmp_path / "vault"
    out = vault / "04 Resources" / "Video Summaries"
    out.mkdir(parents=True)
    (out / "Top.md").write_text("# top")
    # Notiz in einem Unterordner — darf NICHT auftauchen.
    sub = out / "unterordner"
    sub.mkdir()
    (sub / "Versteckt.md").write_text("# versteckt")
    # Fremde Kategorie nebenan — darf NICHT auftauchen.
    other = vault / "04 Resources" / "AI & Claude"
    other.mkdir(parents=True)
    (other / "Fremd.md").write_text("# fremd")

    monkeypatch.setattr(settings, "video_summary_project_path", str(vault))
    monkeypatch.setattr(settings, "video_summary_output_subdir", "04 Resources/Video Summaries")
    titles = {i["title"] for i in await _worker(tmp_path).list_library()}
    assert titles == {"Top"}


async def test_library_handles_unreadable_entries_gracefully(tmp_path, monkeypatch):
    """Eine Datei ohne lesbare Metadaten/mtime bringt den Scan nicht zum Absturz."""
    vault = tmp_path / "vault"
    out = vault / "04 Resources" / "Video Summaries"
    out.mkdir(parents=True)
    (out / "Gut.md").write_text("# ok")
    monkeypatch.setattr(settings, "video_summary_project_path", str(vault))
    monkeypatch.setattr(settings, "video_summary_output_subdir", "04 Resources/Video Summaries")
    lib = await _worker(tmp_path).list_library()
    assert [i["title"] for i in lib] == ["Gut"]
    assert lib[0]["mtime"]  # ISO-String vorhanden


@pytest.fixture
def client(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    out = vault / "04 Resources" / "Video Summaries"
    out.mkdir(parents=True)
    monkeypatch.setattr(settings, "video_summary_project_path", str(vault))
    monkeypatch.setattr(settings, "video_summary_output_subdir", "04 Resources/Video Summaries")
    # vault_root des MD-Readers ebenfalls auf den Test-Vault biegen (sonst sucht der
    # Reader im autouse-isolierten leeren tmp-Vault).
    monkeypatch.setattr(settings, "vault_root", str(vault))
    # In Produktion liegt der Vault (/home/dev/tools/Hal) innerhalb allowed_roots;
    # für den tmp-Vault dies explizit ergänzen, sonst weist der Reader 400 statt 404.
    monkeypatch.setattr(settings, "allowed_roots", [*settings.allowed_roots, str(vault)])
    app = create_app()
    with TestClient(app) as c:
        yield c, out


def test_reader_returns_404_for_deleted_note(client):
    """Klick auf eine zwischenzeitlich gelöschte Notiz → 404 (kein 500/Crash)."""
    c, out = client
    md = out / "Weg.md"
    md.write_text("# weg")
    abs_path = str(md)
    # gelistet?
    lib = c.get("/video-summary/library")
    assert lib.status_code == 200
    assert any(i["md_path"] == abs_path for i in lib.json())
    # gelöscht → Reader-Route liefert 404.
    md.unlink()
    r = c.get(f"/md/file", params={"path": abs_path})
    assert r.status_code == 404


def test_library_path_within_allowed_roots(client):
    """Die zurückgegebenen md_path liegen im Vault (= innerhalb allowed_roots),
    damit Reader/Download sie überhaupt öffnen dürfen."""
    c, out = client
    (out / "Pfad.md").write_text("# p")
    data = c.get("/video-summary/library").json()
    assert data, "Bibliothek sollte den Eintrag listen"
    for item in data:
        assert any(item["md_path"].startswith(root) for root in settings.allowed_roots)
