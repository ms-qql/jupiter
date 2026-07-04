"""PROJ-55 — Session-Kondensierung (Wochen-Sweep): Worker + Vault-Archiv + API.

Deckt die backend-seitigen Akzeptanzkriterien ab:
- Auswahl nach Frontmatter-Alter (> 7 d); zu junge / kaputte Logs übersprungen.
- Trivial-Vorfilter (Slug-Blockliste bzw. zu kurz ohne Marker) → nur archivieren.
- Signal → headless Skill-Lauf; Ergebnis-Marker → Notiz-Pfade + Archivierung.
- Kein Datenverlust: Fehler/kein Marker → Roh-Log bleibt in Sessions/.
- Archiv + gzip (Recovery), Idempotenz (zweiter Scan fügt nichts hinzu), Retry.
- Wochenplan-Berechnung (DOW HH:MM, dependency-frei).
- Lauf-Protokoll (geprüft/kondensiert/trivial/archiviert/Fehler).
- API: Scan/Run/Queue/Runs/Settings (inkl. ungültiger Plan/Modell → 400).
"""
from __future__ import annotations

import gzip
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.session_condense_queue import SqliteSessionCondenseRepository
from app.engine.events import StreamEvent
from app.engine.manager import SessionManager
from app.engine.session_condense import (
    SessionCondenseWorker,
    _next_weekly_run_at,
    build_prompt,
    is_older_than,
    is_trivial,
    parse_result,
    project_from_filename,
)
from app.engine.vault import VaultService
from app.main import create_app

from .fakes import FakeDriver

# Innerhalb allowed_roots + existiert → gültiger Session-cwd für die FakeDriver-Läufe.
PROJECT = "/home/dev/projects/jupiter"


# --- Pure Helpers ----------------------------------------------------------

def test_project_from_filename():
    assert project_from_filename("2026-06-23--immo-crm-c874e3bc.md") == "immo-crm"
    assert project_from_filename("2026-06-23--jupiter-0a36f7c2.md") == "jupiter"
    assert project_from_filename("kaputt.md") == "unbekannt"


def test_is_older_than_uses_frontmatter_date():
    now = datetime(2026, 7, 4, tzinfo=timezone.utc)
    old = datetime(2026, 6, 1, tzinfo=timezone.utc)
    recent = datetime(2026, 7, 2, tzinfo=timezone.utc)
    assert is_older_than(old, 7, ref=now) is True
    assert is_older_than(recent, 7, ref=now) is False
    # Unbekanntes Datum → nie anfassen.
    assert is_older_than(None, 7, ref=now) is False


def test_is_trivial_blocklist_and_short():
    assert is_trivial("2026-06-23--test-83d77e02.md", "x" * 5000, 800) is True
    # Zu kurz UND kein Marker → trivial.
    assert is_trivial("2026-06-23--jupiter-aaaaaaaa.md", "nur ok", 800) is True
    # Zu kurz, ABER Marker („bug behoben") → NICHT trivial (geht zum Skill).
    assert is_trivial("2026-06-23--jupiter-aaaaaaaa.md", "bug behoben", 800) is False
    # Lang genug → nicht trivial.
    assert is_trivial("2026-06-23--jupiter-aaaaaaaa.md", "y" * 2000, 800) is False


def test_parse_result_condensed_trivial_and_missing():
    condensed = (
        "Fertig.\n\nJUPITER_CONDENSE_RESULT\noutcome: condensed\n"
        "note: /home/dev/tools/Hal/Agentic OS/Jupiter/Knowledge/bug-jupiter-aa.md\n"
        "note: <platzhalter>\n"
    )
    outcome, notes = parse_result(condensed)
    assert outcome == "condensed"
    assert notes == ["/home/dev/tools/Hal/Agentic OS/Jupiter/Knowledge/bug-jupiter-aa.md"]

    assert parse_result("JUPITER_CONDENSE_RESULT\noutcome: trivial\n") == ("trivial", [])
    assert parse_result("kein marker") == (None, [])


def test_build_prompt_invokes_skill_and_forbids_questions():
    p = build_prompt("/abs/log.md", "jupiter", "abcd1234")
    assert p.startswith("/hal-session-condense /abs/log.md")
    assert "AskUserQuestion" in p
    assert "JUPITER_CONDENSE_RESULT" in p
    assert "jupiter" in p and "abcd1234" in p
    assert "Secret" in p or "Secrets" in p


def test_next_weekly_run_at():
    # Mittwoch 2026-07-01 10:00.
    base = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    # Freitag 03:00 → gleiche Woche (in 2 Tagen).
    assert _next_weekly_run_at("FRI 03:00", base) == datetime(2026, 7, 3, 3, 0, tzinfo=timezone.utc)
    # Montag 03:00 → schon vorbei → nächste Woche.
    assert _next_weekly_run_at("MON 03:00", base) == datetime(2026, 7, 6, 3, 0, tzinfo=timezone.utc)
    # Leer/ungültig → None.
    assert _next_weekly_run_at("", base) is None
    assert _next_weekly_run_at("XYZ 03:00", base) is None
    assert _next_weekly_run_at("MON 25:00", base) is None


# --- Vault: Archiv + gzip + Enumeration ------------------------------------

def _vault(tmp_path) -> VaultService:
    return VaultService(vault_root=str(tmp_path / "vault"), jupiter_subdir="Agentic OS/Jupiter")


def _write_session(vault: VaultService, name: str, created_iso: str, body: str, sid: str = "sid-1") -> None:
    sdir = os.path.join(vault.write_root, "Sessions")
    os.makedirs(sdir, exist_ok=True)
    content = (
        "---\n"
        'owner: "dev"\n'
        f'session_id: "{sid}"\n'
        f'created: "{created_iso}"\n'
        'type: "session_log"\n'
        'title: "jupiter"\n'
        "---\n\n"
        f"{body}\n"
    )
    with open(os.path.join(sdir, name), "w", encoding="utf-8") as fh:
        fh.write(content)


def test_vault_archive_gzips_and_removes_source(tmp_path):
    v = _vault(tmp_path)
    _write_session(v, "2026-06-01--jupiter-aaaaaaaa.md", "2026-06-01T10:00:00+00:00", "Inhalt XYZ")
    rel = v.archive_session_log("2026-06-01--jupiter-aaaaaaaa.md")
    assert rel.endswith("Sessions/_archiv/2026-06-01--jupiter-aaaaaaaa.md.gz")
    # Quelle weg, Archiv da + Inhalt wiederherstellbar.
    assert not os.path.exists(os.path.join(v.write_root, "Sessions", "2026-06-01--jupiter-aaaaaaaa.md"))
    gz = os.path.join(v.write_root, "Sessions", "_archiv", "2026-06-01--jupiter-aaaaaaaa.md.gz")
    with gzip.open(gz, "rt", encoding="utf-8") as fh:
        assert "Inhalt XYZ" in fh.read()


def test_vault_list_session_logs_excludes_archiv(tmp_path):
    v = _vault(tmp_path)
    _write_session(v, "2026-06-01--jupiter-aaaaaaaa.md", "2026-06-01T10:00:00+00:00", "a", sid="s-a")
    v.archive_session_log("2026-06-01--jupiter-aaaaaaaa.md")
    _write_session(v, "2026-06-02--jupiter-bbbbbbbb.md", "2026-06-02T10:00:00+00:00", "b", sid="s-b")
    logs = v.list_session_logs()
    names = [l["filename"] for l in logs]
    assert names == ["2026-06-02--jupiter-bbbbbbbb.md"]  # archiviertes nicht dabei
    assert logs[0]["session_id"] == "s-b"
    assert logs[0]["created"] == "2026-06-02T10:00:00+00:00"


def test_vault_prune_archive_by_age(tmp_path):
    v = _vault(tmp_path)
    _write_session(v, "2026-06-01--jupiter-aaaaaaaa.md", "2026-06-01T10:00:00+00:00", "a")
    v.archive_session_log("2026-06-01--jupiter-aaaaaaaa.md")
    gz = os.path.join(v.write_root, "Sessions", "_archiv", "2026-06-01--jupiter-aaaaaaaa.md.gz")
    # mtime auf 40 Tage zurücksetzen → Pruning mit 30-Tage-Frist löscht.
    old = (datetime.now() - timedelta(days=40)).timestamp()
    os.utime(gz, (old, old))
    assert v.prune_archive(30) == 1
    assert not os.path.exists(gz)
    # Frischer Eintrag bleibt.
    _write_session(v, "2026-06-02--jupiter-bbbbbbbb.md", "2026-06-02T10:00:00+00:00", "b")
    v.archive_session_log("2026-06-02--jupiter-bbbbbbbb.md")
    assert v.prune_archive(30) == 0


# --- Worker (direkt, deterministisch) --------------------------------------

def _old_iso(days: int = 30) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _worker(tmp_path, monkeypatch, driver_factory=None) -> tuple[SessionCondenseWorker, VaultService]:
    monkeypatch.setattr(settings, "session_condense_project_path", PROJECT)
    v = _vault(tmp_path)
    repo = SqliteSessionCondenseRepository(str(tmp_path / "scq.db"))
    mgr = SessionManager(driver_factory=driver_factory or (lambda: FakeDriver()))
    return SessionCondenseWorker(mgr, repo, v), v


async def _drain(worker: SessionCondenseWorker, max_ticks: int = 60) -> None:
    for _ in range(max_ticks):
        await worker.tick()
        if not worker._draining and worker._current_id is None:
            return


class _CondenseMarkerDriver(FakeDriver):
    """Antwortet mit dem Kondensier-Ergebnis-Marker (outcome: condensed)."""

    async def start(self, spec, on_event):  # noqa: D401
        self._on = on_event
        self._spec = spec
        await on_event(StreamEvent("system", "init", {"session_id": spec.session_id}))
        await self._respond(
            "Erledigt.\n\nJUPITER_CONDENSE_RESULT\noutcome: condensed\n"
            "note: /home/dev/tools/Hal/Agentic OS/Jupiter/Knowledge/bug-geloest-jupiter-sid.md\n"
        )


async def test_scan_enqueues_only_old_sessions(tmp_path, monkeypatch):
    worker, v = _worker(tmp_path, monkeypatch)
    _write_session(v, "2026-01-01--jupiter-aaaaaaaa.md", _old_iso(30), "y" * 2000, sid="s-old")
    _write_session(v, "2026-07-04--jupiter-bbbbbbbb.md", _old_iso(0), "y" * 2000, sid="s-new")
    _write_session(v, "2026-01-01--jupiter-cccccccc.md", "kaputtes-datum", "y" * 2000, sid="s-bad")
    await worker.startup()  # ruft scan()
    q = await worker.list_queue()
    assert [r["session_filename"] for r in q] == ["2026-01-01--jupiter-aaaaaaaa.md"]
    assert q[0]["project"] == "jupiter"
    # Zweiter Scan ist idempotent (nichts Neues).
    res = await worker.scan()
    assert res["added"] == 0


async def test_trivial_is_archived_without_session(tmp_path, monkeypatch):
    worker, v = _worker(tmp_path, monkeypatch)
    _write_session(v, "2026-01-01--test-aaaaaaaa.md", _old_iso(30), "irrelevant", sid="s-t")
    await worker.startup()
    await worker.run_now()
    await _drain(worker)
    row = (await worker.list_queue())[0]
    assert row["status"] == "done"
    assert row["outcome"] == "trivial"
    # Roh-Log archiviert (aus Sessions/ verschwunden).
    assert not os.path.exists(os.path.join(v.write_root, "Sessions", "2026-01-01--test-aaaaaaaa.md"))
    assert os.path.exists(
        os.path.join(v.write_root, "Sessions", "_archiv", "2026-01-01--test-aaaaaaaa.md.gz")
    )
    runs = await worker.list_runs()
    assert runs[0]["trivial"] == 1 and runs[0]["archived"] == 1 and runs[0]["checked"] == 1


async def test_signal_condensed_records_notes_and_archives(tmp_path, monkeypatch):
    worker, v = _worker(tmp_path, monkeypatch, driver_factory=lambda: _CondenseMarkerDriver())
    _write_session(v, "2026-01-01--jupiter-aaaaaaaa.md", _old_iso(30), "Bug behoben: " + "z" * 2000, sid="sid")
    await worker.startup()
    await worker.run_now()
    await _drain(worker)
    row = (await worker.list_queue())[0]
    assert row["status"] == "done"
    assert row["outcome"] == "condensed"
    assert "bug-geloest-jupiter-sid.md" in row["knowledge_paths"]
    assert not os.path.exists(os.path.join(v.write_root, "Sessions", "2026-01-01--jupiter-aaaaaaaa.md"))
    runs = await worker.list_runs()
    assert runs[0]["condensed"] == 1 and runs[0]["archived"] == 1


async def test_missing_marker_keeps_raw_log(tmp_path, monkeypatch):
    """FakeDriver ohne Ergebnis-Marker → Fehler, Roh-Log bleibt für Retry liegen."""
    worker, v = _worker(tmp_path, monkeypatch)  # Default-FakeDriver = kein gültiger Marker
    _write_session(v, "2026-01-01--jupiter-aaaaaaaa.md", _old_iso(30), "Architektur-Entscheidung: " + "z" * 2000, sid="sid")
    await worker.startup()
    await worker.run_now()
    await _drain(worker)
    row = (await worker.list_queue())[0]
    assert row["status"] == "error"
    # Kein Datenverlust: Roh-Log NICHT archiviert.
    assert os.path.exists(os.path.join(v.write_root, "Sessions", "2026-01-01--jupiter-aaaaaaaa.md"))
    assert not os.path.isdir(os.path.join(v.write_root, "Sessions", "_archiv"))


async def test_retry_resets_error_to_pending(tmp_path, monkeypatch):
    worker, v = _worker(tmp_path, monkeypatch)
    _write_session(v, "2026-01-01--jupiter-aaaaaaaa.md", _old_iso(30), "z" * 2000, sid="sid")
    await worker.startup()
    item_id = (await worker.list_queue())[0]["id"]
    await worker._repo.update(item_id, status="error", error_message="kaputt")
    await worker.retry(item_id)
    assert (await worker.get_settings())  # smoke
    assert (await worker._repo.get(item_id))["status"] == "pending"


async def test_running_reset_to_pending_on_restart(tmp_path, monkeypatch):
    db = str(tmp_path / "scq.db")
    monkeypatch.setattr(settings, "session_condense_project_path", PROJECT)
    v = _vault(tmp_path)
    _write_session(v, "2026-01-01--jupiter-aaaaaaaa.md", _old_iso(30), "z" * 2000, sid="sid")
    repo = SqliteSessionCondenseRepository(db)
    await repo.init()
    row = await repo.add_candidate({"session_filename": "2026-01-01--jupiter-aaaaaaaa.md", "created_at": "x"})
    await repo.update(row["id"], status="running", worker_session_id="w-1")
    # „Neustart" auf derselben DB → startup setzt running→pending.
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    worker2 = SessionCondenseWorker(mgr, SqliteSessionCondenseRepository(db), v)
    await worker2.startup()
    q = await worker2.list_queue()
    assert q[0]["status"] == "pending"
    assert q[0]["worker_session_id"] is None


# --- API (TestClient) ------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "session_condense_db_path", str(tmp_path / "scq.db"))
    monkeypatch.setattr(settings, "session_condense_project_path", PROJECT)
    app = create_app(
        driver_factory=lambda: FakeDriver(),
        vault_service=VaultService(vault_root=str(tmp_path / "vault"), jupiter_subdir="Agentic OS/Jupiter"),
    )
    with TestClient(app) as c:
        yield c


def test_api_queue_scan_runs_settings(client):
    assert client.get("/session-condense/queue").status_code == 200
    assert client.post("/session-condense/scan").status_code == 200
    assert client.get("/session-condense/runs").status_code == 200
    s = client.get("/session-condense/settings")
    assert s.status_code == 200 and s.json()["age_days"] == 7


def test_api_settings_validation(client):
    # Ungültiger Wochenplan → 400.
    assert client.patch("/session-condense/settings", json={"schedule": "10:00"}).status_code == 400
    assert client.patch("/session-condense/settings", json={"schedule": "FUN 03:00"}).status_code == 400
    # Ungültiges Modell → 400.
    assert client.patch("/session-condense/settings", json={"model": "gpt-9"}).status_code == 400
    # Gültig → 200 + persistiert.
    r = client.patch("/session-condense/settings", json={"schedule": "MON 03:00", "model": "opus", "age_days": 14})
    assert r.status_code == 200
    body = r.json()
    assert body["schedule"] == "MON 03:00" and body["model"] == "opus" and body["age_days"] == 14
