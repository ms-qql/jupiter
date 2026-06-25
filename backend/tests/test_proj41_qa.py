"""PROJ-41 — QA: gezielte Edge-Case-Abdeckung (ergänzt test_proj41_video_summary.py).

Prüft die in der Spec dokumentierten Edge Cases, die der Haupt-Testfile noch nicht
explizit nachstellt:
- „Jetzt ausführen" während bereits eine Verarbeitung läuft → kein Doppelstart.
- Cron-Lauf fällig → Drain idempotent, nächster Lauf vorgemerkt (keine Doppelfeuerung).
- Ungültige URL blockiert die übrigen nicht (gelangt gar nicht erst in die Queue).
- Einstellungen überleben einen „Neustart" (eigener Worker auf derselben DB).
- Entfernen eines LAUFENDEN Eintrags stoppt die zugehörige Session.
- Session-Limit erreicht → Eintrag bleibt pending (kein harter Fehler).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.config import settings
from app.db.video_summary_queue import SqliteVideoSummaryRepository
from app.engine.manager import ACTIVE_STATES, SessionLimitError, SessionManager
from app.engine.video_summary import VideoSummaryWorker, _next_run_at

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _worker(tmp_path, monkeypatch, *, manager: SessionManager | None = None) -> VideoSummaryWorker:
    monkeypatch.setattr(settings, "video_summary_project_path", PROJECT)
    repo = SqliteVideoSummaryRepository(str(tmp_path / "vsq.db"))
    mgr = manager or SessionManager(driver_factory=lambda: FakeDriver())
    return VideoSummaryWorker(mgr, repo)


def _active_sessions(mgr: SessionManager) -> int:
    return sum(1 for r in mgr.list() if r.state.status in ACTIVE_STATES)


async def test_run_now_while_running_no_double_start(tmp_path, monkeypatch):
    """„Jetzt ausführen" doppelt + Tick → nie zwei Sessions gleichzeitig, item2 wartet."""
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    worker = _worker(tmp_path, monkeypatch, manager=mgr)
    await worker.startup()
    await worker.add_urls(["https://v.com/1", "https://v.com/2"])
    await worker.run_now()

    await worker.tick()  # startet item1 (FakeDriver → sofort waiting)
    assert worker._current_id is not None
    # Idempotenter Zweitauslöser ändert nichts am laufenden Stand.
    await worker.run_now()
    await worker.run_now()
    running = [r for r in await worker.list_queue() if r["status"] == "running"]
    assert len(running) == 1  # genau eine läuft
    pending = [r for r in await worker.list_queue() if r["status"] == "pending"]
    assert len(pending) == 1  # die zweite wartet noch


async def test_schedule_due_sets_draining_and_advances(tmp_path, monkeypatch):
    """Fälliger Tagesplan → Drain an + nächster Lauf am Folgetag (kein Doppelfeuern)."""
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    # Plan auf eine längst vergangene Uhrzeit → beim nächsten Tick sofort fällig.
    worker._schedule = "00:00"
    worker._next_scheduled_run = datetime.now() - timedelta(seconds=1)
    before = worker._next_scheduled_run
    worker._check_schedule()
    assert worker._draining is True
    # Nächster Lauf wurde nach vorn verschoben (in die Zukunft) → feuert nicht erneut.
    assert worker._next_scheduled_run is not None
    assert worker._next_scheduled_run > before
    assert worker._next_scheduled_run > datetime.now()


async def test_invalid_url_does_not_enter_queue(tmp_path, monkeypatch):
    """Gemischte Eingabe: nur gültige URLs landen in der Queue, ungültige werden abgewiesen."""
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    res = await worker.add_urls("https://ok.com/v  kaputt  ftp://x.y  https://ok2.com/v")
    assert {i["url"] for i in res["added"]} == {"https://ok.com/v", "https://ok2.com/v"}
    assert set(res["rejected"]) == {"kaputt", "ftp://x.y"}
    queue_urls = {r["url"] for r in await worker.list_queue()}
    assert queue_urls == {"https://ok.com/v", "https://ok2.com/v"}


async def test_settings_survive_restart(tmp_path, monkeypatch):
    """Einstellungen sind persistent: ein frischer Worker auf derselben DB liest sie."""
    monkeypatch.setattr(settings, "video_summary_project_path", PROJECT)
    db = str(tmp_path / "vsq.db")
    w1 = VideoSummaryWorker(
        SessionManager(driver_factory=lambda: FakeDriver()), SqliteVideoSummaryRepository(db)
    )
    await w1.startup()
    await w1.save_settings(cooldown_minutes=15, batch_size=2, schedule="03:00")

    # „Neustart": neuer Worker, dieselbe DB.
    w2 = VideoSummaryWorker(
        SessionManager(driver_factory=lambda: FakeDriver()), SqliteVideoSummaryRepository(db)
    )
    await w2.startup()
    s = await w2.get_settings()
    assert s == {"cooldown_minutes": 15, "batch_size": 2, "schedule": "03:00"}
    # Zeitplan ist nach dem Neustart aktiv (nächster Lauf berechnet).
    assert w2._next_scheduled_run is not None


async def test_remove_running_stops_session(tmp_path, monkeypatch):
    """Entfernen eines laufenden Eintrags stoppt die zugehörige Session (kein Geister-Prozess)."""
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    worker = _worker(tmp_path, monkeypatch, manager=mgr)
    await worker.startup()
    add = await worker.add_urls(["https://v.com/1"])
    item_id = add["added"][0]["id"]
    await worker.run_now()
    await worker.tick()  # startet die Session
    sid = worker._current_session_id
    assert sid is not None and mgr.get(sid).driver.is_alive

    await worker.remove(item_id)
    assert mgr.get(sid).driver.is_alive is False  # gestoppt
    assert worker._current_id is None
    assert await worker.list_queue() == []  # Eintrag entfernt


async def test_session_limit_keeps_item_pending(tmp_path, monkeypatch):
    """Sind alle Session-Slots belegt, bleibt der Eintrag pending (nächster Tick erneut)."""

    class LimitedManager(SessionManager):
        async def create(self, **kwargs):  # noqa: D401 — erzwingt das Limit
            raise SessionLimitError("Limit erreicht.")

    mgr = LimitedManager(driver_factory=lambda: FakeDriver())
    worker = _worker(tmp_path, monkeypatch, manager=mgr)
    await worker.startup()
    await worker.add_urls(["https://v.com/1"])
    await worker.run_now()
    await worker.tick()
    q = await worker.list_queue()
    assert q[0]["status"] == "pending"  # NICHT error — wird später erneut versucht
    assert worker._current_id is None
