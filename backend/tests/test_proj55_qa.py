"""PROJ-55 — QA + Security-Red-Team für die Session-Kondensierung.

Fokus (ergänzend zu test_proj55_session_condense.py):
- **Pfad-Sandbox / Traversal:** Roh-Log-Zugriff + Archivierung dürfen den
  Sessions-Bereich nie verlassen (kein `../`-Ausbruch, keine absoluten Pfade).
- **Kein Datenverlust:** Schlägt das Archivieren fehl, bleibt das Roh-Log liegen
  und der Eintrag wird Fehler (Retry möglich).
- **Wochenplan-Fire:** ein fälliger Plan stößt genau einen Drain an (kein Doppelfeuern).
- **Idempotenz:** wiederholter Scan/Lauf ohne neue Alt-Sessions ändert nichts.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.db.session_condense_queue import SqliteSessionCondenseRepository
from app.engine.manager import SessionManager
from app.engine.session_condense import SessionCondenseWorker, _next_weekly_run_at
from app.engine.vault import VaultService

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _vault(tmp_path) -> VaultService:
    return VaultService(vault_root=str(tmp_path / "vault"), jupiter_subdir="Agentic OS/Jupiter")


def _write_session(vault: VaultService, name: str, created_iso: str, body: str, sid: str = "sid") -> None:
    sdir = os.path.join(vault.write_root, "Sessions")
    os.makedirs(sdir, exist_ok=True)
    content = (
        f'---\nowner: "dev"\nsession_id: "{sid}"\ncreated: "{created_iso}"\n'
        f'type: "session_log"\ntitle: "jupiter"\n---\n\n{body}\n'
    )
    with open(os.path.join(sdir, name), "w", encoding="utf-8") as fh:
        fh.write(content)


def _old_iso(days: int = 30) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# --- Security: Pfad-Sandbox / Traversal ------------------------------------

def test_bare_name_rejects_dotfiles_and_empty(tmp_path):
    v = _vault(tmp_path)
    for bad in ("", "   ", ".", ".hidden", "..", "/"):
        with pytest.raises(ValueError):
            v._bare_name(bad)


def test_session_log_abspath_stays_in_sandbox(tmp_path):
    v = _vault(tmp_path)
    sessions_root = os.path.realpath(os.path.join(v.write_root, "Sessions"))
    # Traversal-Versuche werden auf den Basisnamen reduziert → bleiben in Sessions/.
    for name in ("../../../etc/passwd", "a/b/../../evil.md", "....//x.md"):
        p = v.session_log_abspath(name)
        assert p.startswith(sessions_root + os.sep)


def test_archive_traversal_cannot_escape(tmp_path):
    v = _vault(tmp_path)
    # Datei existiert nicht (Basisname passwd) → FileNotFoundError, KEIN Schreibausbruch.
    with pytest.raises(OSError):
        v.archive_session_log("../../../etc/passwd")
    # Nichts außerhalb des Vaults angelegt.
    assert not os.path.exists("/etc/_archiv")


def test_archive_absolute_path_rejected(tmp_path):
    v = _vault(tmp_path)
    # Absoluter „Dateiname" → Basisname greift; kein Ausbruch, nur FileNotFound.
    with pytest.raises(OSError):
        v.archive_session_log("/etc/shadow")


# --- Kein Datenverlust bei Archiv-Fehler -----------------------------------

async def test_archive_failure_keeps_raw_log(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "session_condense_project_path", PROJECT)
    v = _vault(tmp_path)
    _write_session(v, "2026-01-01--test-aaaaaaaa.md", _old_iso(30), "irrelevant")
    repo = SqliteSessionCondenseRepository(str(tmp_path / "scq.db"))
    worker = SessionCondenseWorker(SessionManager(driver_factory=lambda: FakeDriver()), repo, v)

    def _boom(_name):
        raise OSError("Platte voll")

    monkeypatch.setattr(v, "archive_session_log", _boom)
    await worker.startup()
    await worker.run_now()
    for _ in range(20):
        await worker.tick()
        if not worker._draining and worker._current_id is None:
            break

    row = (await worker.list_queue())[0]
    assert row["status"] == "error"
    assert "Archivierung fehlgeschlagen" in (row["error_message"] or "")
    # Roh-Log NICHT verloren.
    assert os.path.exists(os.path.join(v.write_root, "Sessions", "2026-01-01--test-aaaaaaaa.md"))
    runs = await worker.list_runs()
    assert runs[0]["errors"] == 1 and runs[0]["archived"] == 0


# --- Wochenplan-Fire (genau einmal) ----------------------------------------

async def test_schedule_fires_once_and_advances(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "session_condense_project_path", PROJECT)
    v = _vault(tmp_path)
    repo = SqliteSessionCondenseRepository(str(tmp_path / "scq.db"))
    worker = SessionCondenseWorker(SessionManager(driver_factory=lambda: FakeDriver()), repo, v)
    await worker.startup()
    # Plan künstlich in die Vergangenheit → beim nächsten Tick fällig.
    worker._schedule = "MON 03:00"
    worker._next_scheduled_run = datetime.now(timezone.utc) - timedelta(minutes=1)
    await worker._maybe_fire_schedule()
    assert worker._draining is True
    # Nächster Lauf ist neu vorgemerkt (in der Zukunft) → kein Doppelfeuern.
    assert worker._next_scheduled_run is not None
    assert worker._next_scheduled_run > datetime.now(timezone.utc)


def test_next_weekly_run_at_is_dependency_free():
    base = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)  # Mittwoch
    # Groß-/Kleinschreibung egal.
    assert _next_weekly_run_at("wed 09:00", base) == datetime(2026, 7, 8, 9, 0, tzinfo=timezone.utc)
    assert _next_weekly_run_at("WED 11:00", base) == datetime(2026, 7, 1, 11, 0, tzinfo=timezone.utc)


# --- Idempotenz -------------------------------------------------------------

async def test_repeated_run_without_new_sessions_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "session_condense_project_path", PROJECT)
    v = _vault(tmp_path)
    _write_session(v, "2026-01-01--test-aaaaaaaa.md", _old_iso(30), "irrelevant")  # trivial
    repo = SqliteSessionCondenseRepository(str(tmp_path / "scq.db"))
    worker = SessionCondenseWorker(SessionManager(driver_factory=lambda: FakeDriver()), repo, v)
    await worker.startup()
    await worker.run_now()
    for _ in range(20):
        await worker.tick()
        if not worker._draining and worker._current_id is None:
            break
    q1 = await worker.list_queue()
    assert len(q1) == 1 and q1[0]["status"] == "done"
    # Zweiter Lauf: Roh-Log ist archiviert (weg aus Sessions/) → Scan findet nichts Neues.
    res = await worker.scan()
    assert res["added"] == 0
    assert len(await worker.list_queue()) == 1
