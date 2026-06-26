"""PROJ-44 — Video Summary: Standard-Ordner, Bibliotheks-Kachel & Modellwahl.

Deckt die neuen backend-seitigen Akzeptanzkriterien ab (zusätzlich zu PROJ-41):
- Block A: ``build_prompt`` schreibt einen FESTEN Zielordner vor (keine Auto-Kategorie).
- Block B: ``GET /video-summary/library`` = Vault-Scan des Standard-Ordners
  (alle .md, neueste zuerst, pdf-Verweis, MOC/Nicht-.md gefiltert, fehlender Ordner → []).
- Block C: Modell ist persistiert (überlebt Neustart) + Whitelist-Validierung (400).
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.video_summary_queue import SqliteVideoSummaryRepository
from app.engine.manager import SessionManager
from app.engine.video_summary import VideoSummaryWorker, build_prompt
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


# --- Block A: fester Zielordner im Prompt ----------------------------------

def test_build_prompt_pins_fixed_folder_no_category():
    p = build_prompt("https://youtu.be/x", "04 Resources/Video Summaries")
    assert "04 Resources/Video Summaries/" in p
    assert "KEINE Kategorie" in p
    assert "AskUserQuestion" in p  # weiterhin nicht-interaktiv
    assert "JUPITER_VIDEO_RESULT" in p


def test_build_prompt_normalizes_subdir_slashes():
    p = build_prompt("https://youtu.be/x", "/04 Resources/Video Summaries/")
    # Kein doppelter/führender Slash im Ordner-Literal.
    assert '"04 Resources/Video Summaries/"' in p


# --- Block C: Modell persistiert (Worker-Ebene) ----------------------------

def _worker(tmp_path) -> VideoSummaryWorker:
    repo = SqliteVideoSummaryRepository(str(tmp_path / "vsq.db"))
    return VideoSummaryWorker(SessionManager(driver_factory=lambda: FakeDriver()), repo)


async def test_default_model_is_sonnet(tmp_path):
    w = _worker(tmp_path)
    await w.startup()
    s = await w.get_settings()
    assert s["model"] == "sonnet"


async def test_model_survives_restart(tmp_path):
    db = str(tmp_path / "vsq.db")
    w1 = VideoSummaryWorker(SessionManager(driver_factory=lambda: FakeDriver()), SqliteVideoSummaryRepository(db))
    await w1.startup()
    await w1.save_settings(cooldown_minutes=30, batch_size=4, schedule="", model="haiku")
    # „Neustart": frischer Worker, dieselbe DB.
    w2 = VideoSummaryWorker(SessionManager(driver_factory=lambda: FakeDriver()), SqliteVideoSummaryRepository(db))
    await w2.startup()
    assert (await w2.get_settings())["model"] == "haiku"
    assert w2._model == "haiku"


async def test_migration_adds_model_column_to_legacy_db(tmp_path):
    """Bestehende DB ohne ``model``-Spalte wird beim Start idempotent migriert."""
    import sqlite3

    db = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE video_summary_settings ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), cooldown_minutes INTEGER NOT NULL DEFAULT 30, "
        "batch_size INTEGER NOT NULL DEFAULT 4, schedule TEXT NOT NULL DEFAULT '');"
        "INSERT INTO video_summary_settings (id, cooldown_minutes, batch_size, schedule) "
        "VALUES (1, 30, 4, '');"
    )
    conn.commit()
    conn.close()

    w = VideoSummaryWorker(SessionManager(driver_factory=lambda: FakeDriver()), SqliteVideoSummaryRepository(db))
    await w.startup()  # darf nicht crashen
    assert (await w.get_settings())["model"] == "sonnet"


# --- Block B: Bibliotheks-Scan (Worker-Ebene) ------------------------------

async def test_library_scans_fixed_folder(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    out = vault / "04 Resources" / "Video Summaries"
    out.mkdir(parents=True)
    (out / "Erstes Video.md").write_text("# eins")
    (out / "Erstes Video.pdf").write_text("%PDF")  # gleichnamiges PDF
    (out / "Zweites Video.md").write_text("# zwei")  # ohne PDF
    (out / "Video Summaries.md").write_text("# MOC")  # MOC = ausgeblendet
    (out / "notiz.txt").write_text("kein md")  # Nicht-.md = ignoriert

    monkeypatch.setattr(settings, "video_summary_project_path", str(vault))
    monkeypatch.setattr(settings, "video_summary_output_subdir", "04 Resources/Video Summaries")

    w = _worker(tmp_path)
    lib = await w.list_library()
    titles = {i["title"] for i in lib}
    assert titles == {"Erstes Video", "Zweites Video"}  # MOC + .txt gefiltert
    by_title = {i["title"]: i for i in lib}
    assert by_title["Erstes Video"]["pdf_path"] is not None
    assert by_title["Zweites Video"]["pdf_path"] is None
    assert by_title["Erstes Video"]["md_path"].endswith("Erstes Video.md")


async def test_library_missing_folder_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "video_summary_project_path", str(tmp_path / "nope"))
    monkeypatch.setattr(settings, "video_summary_output_subdir", "04 Resources/Video Summaries")
    w = _worker(tmp_path)
    assert await w.list_library() == []


async def test_library_sorted_newest_first(tmp_path, monkeypatch):
    import os
    import time

    vault = tmp_path / "vault"
    out = vault / "04 Resources" / "Video Summaries"
    out.mkdir(parents=True)
    old = out / "Alt.md"
    new = out / "Neu.md"
    old.write_text("alt")
    new.write_text("neu")
    # mtimes deterministisch setzen (alt < neu).
    os.utime(old, (1_600_000_000, 1_600_000_000))
    os.utime(new, (1_700_000_000, 1_700_000_000))

    monkeypatch.setattr(settings, "video_summary_project_path", str(vault))
    monkeypatch.setattr(settings, "video_summary_output_subdir", "04 Resources/Video Summaries")
    w = _worker(tmp_path)
    lib = await w.list_library()
    assert [i["title"] for i in lib] == ["Neu", "Alt"]


# --- API-Ebene -------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "video_summary_db_path", str(tmp_path / "api.db"))
    vault = tmp_path / "vault"
    (vault / "04 Resources" / "Video Summaries").mkdir(parents=True)
    (vault / "04 Resources" / "Video Summaries" / "Demo.md").write_text("# demo")
    monkeypatch.setattr(settings, "video_summary_project_path", str(vault))
    monkeypatch.setattr(settings, "video_summary_output_subdir", "04 Resources/Video Summaries")
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_api_library_lists_notes(client):
    r = client.get("/video-summary/library")
    assert r.status_code == 200
    data = r.json()
    assert any(i["title"] == "Demo" for i in data)


def test_api_settings_exposes_model_default(client):
    r = client.get("/video-summary/settings")
    assert r.status_code == 200
    assert r.json()["model"] == "sonnet"


def test_api_patch_model_valid(client):
    r = client.patch("/video-summary/settings", json={"model": "haiku"})
    assert r.status_code == 200
    assert r.json()["model"] == "haiku"
    # persistiert (erneut lesen).
    assert client.get("/video-summary/settings").json()["model"] == "haiku"


def test_api_patch_model_invalid_rejected(client):
    r = client.patch("/video-summary/settings", json={"model": "gpt-4o"})
    assert r.status_code == 400
    assert "Modell" in r.json()["detail"]
    # unverändert geblieben.
    assert client.get("/video-summary/settings").json()["model"] == "sonnet"


def test_api_patch_other_field_keeps_model(client):
    client.patch("/video-summary/settings", json={"model": "opus"})
    client.patch("/video-summary/settings", json={"cooldown_minutes": 10})
    s = client.get("/video-summary/settings").json()
    assert s["model"] == "opus"
    assert s["cooldown_minutes"] == 10
