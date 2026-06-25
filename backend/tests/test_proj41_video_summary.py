"""PROJ-41 — Video Summary (native Micro-App): Queue-Worker + API.

Deckt die backend-seitigen Akzeptanzkriterien ab:
- URL-Paste-Zerlegung (Trenner), Trimmen, Dedup, Validierung (deutsche Fehler).
- Maschinenlesbares Pfad-Parsing aus dem Abschlussbericht (Pfade mit Leerzeichen).
- Tagesplan-Berechnung (HH:MM, dependency-frei).
- Drossel: nie mehr als ``batch_size`` Videos in Folge → Cooldown-Pause, dann weiter.
- Persistenz: Queue + Einstellungen überleben einen „Neustart"; running→pending.
- API: Queue-CRUD, Trigger, Einstellungen (inkl. ungültiger Zeitplan → 400).
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.video_summary_queue import SqliteVideoSummaryRepository
from app.engine.manager import SessionManager
from app.engine.video_summary import (
    VideoSummaryWorker,
    _next_run_at,
    build_prompt,
    parse_result_paths,
    parse_urls,
)
from app.main import create_app

from .fakes import FakeDriver

# Innerhalb allowed_roots + existiert → gültiger Session-cwd für die FakeDriver-Läufe.
PROJECT = "/home/dev/projects/jupiter"


# --- Pure Helpers ----------------------------------------------------------

def test_parse_urls_splits_trims_dedups():
    raw = "https://a.com/1\nhttps://b.com/2 , https://a.com/1;https://c.com/3"
    valid, rejected = parse_urls(raw)
    assert valid == ["https://a.com/1", "https://b.com/2", "https://c.com/3"]
    assert rejected == []


def test_parse_urls_rejects_invalid():
    valid, rejected = parse_urls("nicht-eine-url  ftp://x.y  https://ok.com/v")
    assert valid == ["https://ok.com/v"]
    assert set(rejected) == {"nicht-eine-url", "ftp://x.y"}


def test_parse_urls_accepts_list():
    valid, rejected = parse_urls(["https://a.com", "https://a.com", "  "])
    assert valid == ["https://a.com"]
    assert rejected == []


def test_parse_result_paths_handles_spaces_in_paths():
    text = (
        "Fertig.\n\nJUPITER_VIDEO_RESULT\n"
        "note: /home/dev/tools/Hal/04 Resources/AI & Claude/Mein Video.md\n"
        "pdf: /home/dev/tools/Hal/04 Resources/AI & Claude/Mein Video.pdf\n"
    )
    note, pdf = parse_result_paths(text)
    assert note == "/home/dev/tools/Hal/04 Resources/AI & Claude/Mein Video.md"
    assert pdf == "/home/dev/tools/Hal/04 Resources/AI & Claude/Mein Video.pdf"


def test_parse_result_paths_missing_marker():
    assert parse_result_paths("Kein Marker hier.") == (None, None)
    assert parse_result_paths("") == (None, None)


def test_build_prompt_invokes_skill_and_forbids_questions():
    p = build_prompt("https://youtu.be/x")
    assert p.startswith("/hal-video-summary https://youtu.be/x")
    assert "AskUserQuestion" in p
    assert "JUPITER_VIDEO_RESULT" in p


def test_next_run_at_today_and_tomorrow():
    from datetime import datetime

    base = datetime(2026, 6, 25, 10, 0, 0)
    # Später am selben Tag → heute.
    assert _next_run_at("14:30", base) == datetime(2026, 6, 25, 14, 30)
    # Bereits vorbei → morgen.
    assert _next_run_at("09:00", base) == datetime(2026, 6, 26, 9, 0)
    # Leer/ungültig → kein Plan.
    assert _next_run_at("", base) is None
    assert _next_run_at("25:00", base) is None
    assert _next_run_at("blah", base) is None


# --- Worker (direkt, deterministisch) --------------------------------------

def _worker(tmp_path, monkeypatch) -> VideoSummaryWorker:
    monkeypatch.setattr(settings, "video_summary_project_path", PROJECT)
    repo = SqliteVideoSummaryRepository(str(tmp_path / "vsq.db"))
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    return VideoSummaryWorker(mgr, repo)


async def _drain_to_idle(worker: VideoSummaryWorker, max_ticks: int = 50) -> None:
    """Tickt, bis der Worker idle ist oder pausiert (kein Fortschritt mehr)."""
    for _ in range(max_ticks):
        await worker.tick()
        st = worker.state()
        if st["status"] in ("idle", "paused") and worker._current_id is None:
            # Noch pending + nicht pausiert? weiterticken; sonst Stillstand.
            pending = [r for r in await worker.list_queue() if r["status"] == "pending"]
            if st["status"] == "paused" or not pending or not worker._draining:
                return


async def test_drossel_pauses_after_batch_size(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    await worker.save_settings(cooldown_minutes=30, batch_size=4, schedule="")
    await worker.add_urls([f"https://v.com/{i}" for i in range(5)])
    await worker.run_now()

    await _drain_to_idle(worker)

    queue = await worker.list_queue()
    done = [r for r in queue if r["status"] == "done"]
    pending = [r for r in queue if r["status"] == "pending"]
    # Nach genau 4 verarbeiteten Videos Cooldown → das 5. bleibt wartend.
    assert len(done) == 4
    assert len(pending) == 1
    assert worker.state()["status"] == "paused"
    assert worker._paused_until is not None

    # Cooldown künstlich beenden → das 5. Video läuft durch.
    worker._paused_until = None
    await _drain_to_idle(worker)
    queue = await worker.list_queue()
    assert len([r for r in queue if r["status"] == "done"]) == 5
    assert worker.state()["status"] == "idle"


async def test_idle_without_run_now_processes_nothing(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    await worker.add_urls(["https://v.com/a"])
    # Kein run_now / kein Zeitplan → bleibt pending.
    for _ in range(3):
        await worker.tick()
    queue = await worker.list_queue()
    assert queue[0]["status"] == "pending"
    assert worker.state()["status"] == "idle"


async def test_done_item_records_result_paths(tmp_path, monkeypatch):
    """FakeDriver, dessen Antwort den Ergebnis-Marker enthält → Pfade landen am Eintrag."""
    monkeypatch.setattr(settings, "video_summary_project_path", PROJECT)

    class MarkerDriver(FakeDriver):
        async def start(self, spec, on_event):  # noqa: D401
            self._on = on_event
            self._spec = spec
            from app.engine.events import StreamEvent

            await on_event(StreamEvent("system", "init", {"session_id": spec.session_id}))
            await self._respond(
                "JUPITER_VIDEO_RESULT\n"
                "note: /home/dev/tools/Hal/04 Resources/AI & Claude/X.md\n"
                "pdf: /home/dev/tools/Hal/04 Resources/AI & Claude/X.pdf\n"
            )

    repo = SqliteVideoSummaryRepository(str(tmp_path / "vsq.db"))
    mgr = SessionManager(driver_factory=lambda: MarkerDriver())
    worker = VideoSummaryWorker(mgr, repo)
    await worker.startup()
    await worker.add_urls(["https://v.com/a"])
    await worker.run_now()
    await _drain_to_idle(worker)

    row = (await worker.list_queue())[0]
    assert row["status"] == "done"
    assert row["result_note_path"].endswith("X.md")
    assert row["result_pdf_path"].endswith("X.pdf")


async def test_running_reset_to_pending_on_restart(tmp_path, monkeypatch):
    db = str(tmp_path / "vsq.db")
    monkeypatch.setattr(settings, "video_summary_project_path", PROJECT)
    repo = SqliteVideoSummaryRepository(db)
    await repo.init()
    row = await repo.add("https://v.com/a", "dev", "2026-06-25T00:00:00")
    await repo.update(row["id"], status="running", session_id="sess-x")

    # „Neustart": neuer Worker auf derselben DB → startup setzt running→pending.
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    worker2 = VideoSummaryWorker(mgr, SqliteVideoSummaryRepository(db))
    await worker2.startup()
    q = await worker2.list_queue()
    assert q[0]["status"] == "pending"
    assert q[0]["session_id"] is None


async def test_retry_resets_error_to_pending(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    row = await worker.add_urls(["https://v.com/a"])
    item_id = row["added"][0]["id"]
    await worker._repo.update(item_id, status="error", error_message="kaputt")
    await worker.retry(item_id)
    q = await worker.list_queue()
    assert q[0]["status"] == "pending"
    assert q[0]["error_message"] is None
    assert worker._draining is True


# --- API (TestClient) ------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "video_summary_project_path", PROJECT)
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as c:
        yield c


def test_api_add_mixed_and_persist(client):
    r = client.post("/video-summary/queue", json={"urls": "https://a.com/1, bad-url\nhttps://a.com/1"})
    assert r.status_code == 200
    body = r.json()
    assert [i["url"] for i in body["added"]] == ["https://a.com/1"]
    assert body["rejected"] == ["bad-url"]
    # zweite identische URL ist Duplikat innerhalb desselben Requests → nicht added.
    # (Dedup über seen-Set; nur einmal added, kein Duplicate-Vermerk nötig.)

    # GET zeigt den Eintrag + Worker-Zustand.
    q = client.get("/video-summary/queue").json()
    assert len(q["items"]) == 1
    assert q["state"]["status"] == "idle"

    # Erneutes Hinzufügen derselben URL → Duplikat.
    r2 = client.post("/video-summary/queue", json={"urls": "https://a.com/1"})
    assert r2.json()["duplicates"] == ["https://a.com/1"]


def test_api_add_all_invalid_returns_400(client):
    r = client.post("/video-summary/queue", json={"urls": "keine-url noch-eine"})
    assert r.status_code == 400
    assert "URL" in r.json()["detail"]


def test_api_delete_and_404(client):
    add = client.post("/video-summary/queue", json={"urls": "https://a.com/1"}).json()
    item_id = add["added"][0]["id"]
    assert client.delete(f"/video-summary/queue/{item_id}").status_code == 204
    assert client.delete(f"/video-summary/queue/{item_id}").status_code == 404


def test_api_settings_roundtrip_and_invalid_schedule(client):
    # Default.
    s = client.get("/video-summary/settings").json()
    assert s["batch_size"] == 4 and s["cooldown_minutes"] == 30

    # Gültige Änderung (persistiert).
    up = client.patch(
        "/video-summary/settings",
        json={"cooldown_minutes": 15, "schedule": "02:00"},
    ).json()
    assert up["cooldown_minutes"] == 15 and up["schedule"] == "02:00"
    assert client.get("/video-summary/settings").json()["schedule"] == "02:00"

    # Ungültiger Zeitplan → 400.
    bad = client.patch("/video-summary/settings", json={"schedule": "99:99"})
    assert bad.status_code == 400


def test_api_retry_non_error_conflict(client):
    add = client.post("/video-summary/queue", json={"urls": "https://a.com/1"}).json()
    item_id = add["added"][0]["id"]
    # pending → retry nicht erlaubt (409).
    r = client.post(f"/video-summary/queue/{item_id}/retry")
    assert r.status_code == 409
