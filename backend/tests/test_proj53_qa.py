"""PROJ-53 — QA-Ergänzungstests (Buch-Nuggets).

Ergänzt `test_proj53_book_nuggets.py` um Akzeptanz-/Sicherheits-Lücken:
- API: estimate-Validierung, run-now, library, unsupported Upload-Format.
- Worker: on_duplicate=overwrite, page_limit-Propagation, single-Modell-Persistenz.
- Sicherheit: Spalten-Whitelist in `update`/`add` (kein Schreiben fremder Spalten),
  SQL-Injection-Robustheit (parametrisiert), Default-Owner gestempelt.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.book_nuggets_queue import SqliteBookNuggetsRepository
from app.engine.manager import SessionManager
from app.engine.book_nuggets import BookNuggetsWorker, build_prompt
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "book_nuggets_project_path", PROJECT)
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as c:
        yield c


# --- API ----------------------------------------------------------------

def test_estimate_rejects_invalid_source(client):
    r = client.post("/book-nuggets/estimate", json={
        "source_type": "upload", "source_ref": "/x/b.mobi",
    })
    assert r.status_code == 400 and "mobi" in r.json()["detail"]


def test_estimate_url_unknown_size(client):
    r = client.post("/book-nuggets/estimate", json={
        "source_type": "url", "source_ref": "https://x.com/b.pdf", "model_mode": "single",
    })
    assert r.status_code == 200 and r.json()["est_cost"] is None


def test_run_now_and_library_endpoints(client):
    assert client.post("/book-nuggets/run-now").status_code == 200
    lib = client.get("/book-nuggets/library")
    assert lib.status_code == 200 and isinstance(lib.json(), list)


def test_unsupported_upload_format_rejected(client):
    r = client.post("/book-nuggets/queue", json={
        "source_type": "upload", "source_ref": "/tmp/archiv.zip",
    })
    assert r.status_code == 400 and "nicht unterstützt" in r.json()["detail"]


def test_invalid_model_rejected_by_schema(client):
    # Pydantic-Literal lehnt unbekanntes Modell ab (422), kein DB-Treffer.
    r = client.post("/book-nuggets/queue", json={
        "source_type": "url", "source_ref": "https://x.com/b.pdf",
        "model_consolidate": "gpt-9",
    })
    assert r.status_code == 422


# --- Worker -------------------------------------------------------------

async def _worker(tmp_path, monkeypatch) -> BookNuggetsWorker:
    monkeypatch.setattr(settings, "book_nuggets_project_path", PROJECT)
    repo = SqliteBookNuggetsRepository(str(tmp_path / "bnq.db"))
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    w = BookNuggetsWorker(mgr, repo)
    await w.startup()
    return w


async def test_on_duplicate_overwrite_accepts(tmp_path, monkeypatch):
    w = await _worker(tmp_path, monkeypatch)
    f = tmp_path / "b.pdf"
    f.write_bytes(b"same")
    await w.add_source("upload", str(f), "staged", "sonnet", "opus")
    # overwrite hebt die Duplikat-Blockade ebenso auf wie new_version.
    res = await w.add_source("upload", str(f), "staged", "sonnet", "opus", on_duplicate="overwrite")
    assert res["item"]["status"] == "pending"


async def test_page_limit_and_owner_persisted(tmp_path, monkeypatch):
    w = await _worker(tmp_path, monkeypatch)
    res = await w.add_source("url", "https://x.com/b.pdf", "single", "haiku", "opus", page_limit=120)
    item = res["item"]
    assert item["page_limit"] == 120
    assert item["owner"] == settings.default_owner
    assert item["model_extract"] == item["model_consolidate"] == "opus"  # single kollabiert


def test_build_prompt_omits_dup_line_when_none():
    p = build_prompt("url", "https://x.com/b.pdf", "sub", "staged", "sonnet", None, None)
    assert "ÜBERSCHREIBEN" not in p and "NEUE VERSION" not in p


# --- Sicherheit ---------------------------------------------------------

async def test_update_ignores_non_whitelisted_column(tmp_path):
    """Spalten-Whitelist: `update` darf keine fremde/sensible Spalte schreiben
    (Schutz vor Spalten-Injection über die Feldnamen)."""
    repo = SqliteBookNuggetsRepository(str(tmp_path / "bnq.db"))
    await repo.init()
    row = await repo.add({
        "owner": "dev", "source_type": "url", "source_ref": "https://x.com/b.pdf",
        "model_mode": "staged", "model_extract": "sonnet", "model_consolidate": "opus",
        "created_at": "2026-06-28T00:00:00",
    })
    # 'id' ist nicht in der Whitelist → darf NICHT überschrieben werden.
    await repo.update(row["id"], id=9999, status="done")
    got = await repo.get(row["id"])
    assert got is not None and got["id"] == row["id"] and got["status"] == "done"
    assert await repo.get(9999) is None


async def test_sql_injection_in_source_ref_is_inert(tmp_path):
    """Parametrisierte Queries: ein bösartiger source_ref bleibt reiner Text."""
    repo = SqliteBookNuggetsRepository(str(tmp_path / "bnq.db"))
    await repo.init()
    evil = "https://x.com/a.pdf'); DROP TABLE book_nuggets_queue;--"
    await repo.add({
        "owner": "dev", "source_type": "url", "source_ref": evil,
        "model_mode": "single", "model_extract": "opus", "model_consolidate": "opus",
        "created_at": "2026-06-28T00:00:00",
    })
    rows = await repo.list_queue()  # Tabelle existiert noch → kein DROP ausgeführt.
    assert len(rows) == 1 and rows[0]["source_ref"] == evil


async def test_add_ignores_non_insertable_fields(tmp_path):
    """`add` schreibt nur Insert-Whitelist-Spalten — injizierter Status wird ignoriert
    (jeder neue Eintrag startet zwingend als 'pending')."""
    repo = SqliteBookNuggetsRepository(str(tmp_path / "bnq.db"))
    await repo.init()
    row = await repo.add({
        "owner": "dev", "source_type": "url", "source_ref": "https://x.com/b.pdf",
        "model_mode": "single", "model_extract": "opus", "model_consolidate": "opus",
        "created_at": "2026-06-28T00:00:00",
        "status": "done",            # darf NICHT durchschlagen
        "result_note_path": "/etc/passwd",  # nicht insertable
    })
    assert row["status"] == "pending"
    assert row["result_note_path"] is None
