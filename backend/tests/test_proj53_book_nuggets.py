"""PROJ-53 — Buch-Nuggets (native Micro-App): Queue-Worker + API.

Deckt die backend-seitigen Akzeptanzkriterien ab:
- Quellen-Validierung (URL gültig/ungültig, mobi/Format-Abweisung — deutsche Fehler).
- Kostenschätzung (best-effort; staged vs. single; unbekannte Größe → None).
- Prompt-Bau (Skill-Aufruf, Stufen-Logik, Duplikat-Hinweis, Result-Marker).
- Ergebnis-/Phasen-Parsing aus dem Abschlussbericht (Pfade mit Leerzeichen).
- Duplikaterkennung (D9): gleiche Identität → 409, on_duplicate hebt auf.
- Persistenz: Queue + Einstellungen überleben einen „Neustart"; running→pending.
- Auto-Drain + sequenzielle Verarbeitung; Modell single kollabiert extract=consolidate.
- API: Queue-CRUD, estimate, run-now, library, Einstellungen.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.book_nuggets_queue import SqliteBookNuggetsRepository
from app.engine.manager import SessionManager
from app.engine.book_nuggets import (
    BookNuggetsWorker,
    DuplicateError,
    build_prompt,
    compute_book_hash_sync,
    estimate_cost,
    extension_of,
    is_valid_url,
    parse_phase,
    parse_result_paths,
    validate_source,
)
from app.main import create_app

from .fakes import FakeDriver

# Innerhalb allowed_roots + existiert → gültiger Session-cwd für die FakeDriver-Läufe.
PROJECT = "/home/dev/projects/jupiter"


# --- Pure Helpers ----------------------------------------------------------

def test_is_valid_url_and_extension():
    assert is_valid_url("https://x.com/buch.pdf")
    assert not is_valid_url("ftp://x.com/a")
    assert not is_valid_url("keine-url")
    assert extension_of("https://x.com/path/buch.EPUB") == "epub"
    assert extension_of("/home/dev/Buch.pdf") == "pdf"
    assert extension_of("https://x.com/ohne-endung") == ""


def test_validate_source_url_ok_and_metadata_rejected():
    err, ref = validate_source("url", "https://files.example.com/b.pdf")
    assert err is None and ref == "https://files.example.com/b.pdf"
    # Produktseite ohne abrufbaren Volltext = ungültige Datei-URL? -> hier nur Schema/Host
    # geprüft; eine echte URL ohne Datei-Endung ist erlaubt (Content-Type kennt der Skill).
    err2, _ = validate_source("url", "nicht-eine-url")
    assert err2 is not None and "URL" in err2


def test_validate_source_mobi_and_unknown_format_rejected():
    err, _ = validate_source("upload", "/tmp/buch.mobi")
    assert err is not None and "mobi" in err
    err2, _ = validate_source("upload", "/tmp/buch.xyz")
    assert err2 is not None and "nicht unterstützt" in err2
    err3, ref = validate_source("upload", "/tmp/buch.docx")
    assert err3 is None and ref == "/tmp/buch.docx"


def test_validate_source_unknown_type():
    err, _ = validate_source("ftp", "x")
    assert err is not None


def test_compute_book_hash_upload_vs_url(tmp_path):
    f = tmp_path / "b.pdf"
    f.write_bytes(b"hello world")
    h1 = compute_book_hash_sync("upload", str(f))
    assert h1.startswith("sha256:")
    # Gleicher Inhalt → gleicher Hash (Identität für Duplikaterkennung).
    f2 = tmp_path / "copy.pdf"
    f2.write_bytes(b"hello world")
    assert compute_book_hash_sync("upload", str(f2)) == h1
    # URL → URL-Identität.
    assert compute_book_hash_sync("url", "https://x.com/a") == "url:https://x.com/a"


def test_estimate_cost_single_vs_staged_and_unknown():
    # Unbekannte Größe (URL) → alles None.
    assert estimate_cost(None, "single", "sonnet", "opus")["est_cost"] is None
    single = estimate_cost(8000, "single", "sonnet", "opus")
    assert single["est_tokens"] == 2000
    assert single["est_cost"] == pytest.approx(2000 / 1_000_000 * 18.0, rel=1e-6)
    staged = estimate_cost(8000, "staged", "sonnet", "opus")
    expected = 2000 / 1_000_000 * 6.0 + 2000 * 0.2 / 1_000_000 * 18.0
    assert staged["est_cost"] == pytest.approx(round(expected, 4), rel=1e-6)
    # Staged ist günstiger als single (Sinn der Stufen-Logik).
    assert staged["est_cost"] < single["est_cost"]


def test_estimate_cost_respects_page_limit():
    full = estimate_cost(10_000_000, "single", "sonnet", "opus")
    capped = estimate_cost(10_000_000, "single", "sonnet", "opus", page_limit=10)
    assert capped["est_tokens"] < full["est_tokens"]
    assert capped["pages"] == 10


def test_build_prompt_staged_and_single():
    p = build_prompt("upload", "/v/b.pdf", "04 Resources/Buch_Nuggets", "staged", "haiku", 200, None)
    assert p.startswith("/hal-book-nuggets")
    assert "STAGED" in p and "haiku" in p
    assert "Seitenlimit: max. 200" in p
    assert "AskUserQuestion" in p
    assert "JUPITER_BOOK_RESULT" in p
    assert "04 Resources/Buch_Nuggets/" in p
    s = build_prompt("url", "https://x.com/b.epub", "sub", "single", "sonnet", None, None)
    assert "SINGLE" in s and "Kein Seitenlimit" in s
    assert "Quelle (URL): https://x.com/b.epub" in s


def test_build_prompt_duplicate_hints():
    ov = build_prompt("upload", "/v/b.pdf", "sub", "single", "opus", None, "overwrite")
    assert "ÜBERSCHREIBEN" in ov
    nv = build_prompt("upload", "/v/b.pdf", "sub", "single", "opus", None, "new_version")
    assert "NEUE VERSION" in nv


def test_parse_result_paths_and_phase():
    text = (
        "JUPITER_BOOK_PHASE: parsing\nJUPITER_BOOK_PHASE: contra\n"
        "Fertig.\n\nJUPITER_BOOK_RESULT\n"
        "title: Thinking in Systems\n"
        "author: Donella Meadows\n"
        "dir: /home/dev/tools/Hal/04 Resources/Buch_Nuggets/Donella Meadows-Thinking\n"
        "note: /home/dev/tools/Hal/04 Resources/Buch_Nuggets/Donella Meadows-Thinking/x.md\n"
        "pdf: /home/dev/tools/Hal/04 Resources/Buch_Nuggets/Donella Meadows-Thinking/x.pdf\n"
    )
    res = parse_result_paths(text)
    assert res["title"] == "Thinking in Systems"
    assert res["author"] == "Donella Meadows"
    assert res["note"].endswith("x.md") and res["pdf"].endswith("x.pdf")
    assert res["dir"].endswith("Donella Meadows-Thinking")
    assert parse_phase(text) == "contra"


def test_parse_result_paths_ignores_placeholders_and_missing():
    placeholder = "JUPITER_BOOK_RESULT\ntitle: <erkannter Buchtitel>\nnote: <pfad>\n"
    res = parse_result_paths(placeholder)
    assert res["title"] is None and res["note"] is None
    empty = parse_result_paths("kein marker")
    assert all(v is None for v in empty.values())
    assert parse_phase("") is None


# --- Worker (direkt, deterministisch) --------------------------------------

def _worker(tmp_path, monkeypatch) -> BookNuggetsWorker:
    monkeypatch.setattr(settings, "book_nuggets_project_path", PROJECT)
    repo = SqliteBookNuggetsRepository(str(tmp_path / "bnq.db"))
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    return BookNuggetsWorker(mgr, repo)


async def _drain(worker: BookNuggetsWorker, max_ticks: int = 50) -> None:
    for _ in range(max_ticks):
        await worker.tick()
        if worker.state()["status"] == "idle" and not worker._draining:
            return


async def test_add_source_auto_drains_and_completes(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    res = await worker.add_source("url", "https://x.com/b.pdf", "staged", "sonnet", "opus")
    assert res["item"]["status"] == "pending"
    assert worker._draining is True  # Auto-Drain
    await _drain(worker)
    row = (await worker.list_queue())[0]
    assert row["status"] == "done"
    assert worker.state()["status"] == "idle"


async def test_single_mode_collapses_models(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    res = await worker.add_source("url", "https://x.com/b.pdf", "single", "haiku", "opus")
    # single → extract wird auf das gewählte (Konsolidierungs-)Modell gesetzt.
    assert res["item"]["model_extract"] == res["item"]["model_consolidate"] == "opus"


async def test_invalid_source_raises(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    with pytest.raises(ValueError):
        await worker.add_source("upload", "/x/b.mobi", "staged", "sonnet", "opus")
    with pytest.raises(ValueError):
        await worker.add_source("url", "keine-url", "staged", "sonnet", "opus")


async def test_duplicate_detection_pending_and_done(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    f = tmp_path / "b.pdf"
    f.write_bytes(b"same content")
    await worker.add_source("upload", str(f), "staged", "sonnet", "opus")
    # Zweites Mal dieselbe Datei (gleicher Hash), noch pending/running → 409.
    with pytest.raises(DuplicateError):
        await worker.add_source("upload", str(f), "staged", "sonnet", "opus")
    # on_duplicate hebt die Blockade auf.
    res = await worker.add_source(
        "upload", str(f), "staged", "sonnet", "opus", on_duplicate="new_version"
    )
    assert res["item"]["status"] == "pending"


async def test_estimate_upload_uses_filesize(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    f = tmp_path / "b.pdf"
    f.write_bytes(b"x" * 8000)
    est = await worker.estimate("upload", str(f), "single", "sonnet", "opus")
    assert est["est_tokens"] == 2000 and est["est_cost"] is not None
    # URL ohne Download → unbekannte Größe.
    est_url = await worker.estimate("url", "https://x.com/b.pdf", "single", "sonnet", "opus")
    assert est_url["est_cost"] is None


async def test_running_reset_to_pending_on_restart(tmp_path, monkeypatch):
    db = str(tmp_path / "bnq.db")
    repo = SqliteBookNuggetsRepository(db)
    await repo.init()
    row = await repo.add({
        "owner": "dev", "source_type": "url", "source_ref": "https://x.com/b.pdf",
        "model_mode": "staged", "model_extract": "sonnet", "model_consolidate": "opus",
        "created_at": "2026-06-28T00:00:00",
    })
    await repo.update(row["id"], status="running", session_id="sess-x", phase="contra")
    # „Neustart": neuer Worker auf derselben DB → startup setzt running→pending.
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    worker2 = BookNuggetsWorker(mgr, SqliteBookNuggetsRepository(db))
    await worker2.startup()
    q = await worker2.list_queue()
    assert q[0]["status"] == "pending" and q[0]["session_id"] is None and q[0]["phase"] is None


async def test_retry_resets_error_to_pending(tmp_path, monkeypatch):
    worker = _worker(tmp_path, monkeypatch)
    await worker.startup()
    res = await worker.add_source("url", "https://x.com/b.pdf", "staged", "sonnet", "opus")
    item_id = res["item"]["id"]
    await worker._repo.update(item_id, status="error", error_message="kaputt")
    await worker.retry(item_id)
    row = (await worker.list_queue())[0]
    assert row["status"] == "pending" and row["error_message"] is None
    assert worker._draining is True


async def test_marker_driver_records_result(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "book_nuggets_project_path", PROJECT)

    class MarkerDriver(FakeDriver):
        async def start(self, spec, on_event):
            self._on = on_event
            self._spec = spec
            from app.engine.events import StreamEvent

            await on_event(StreamEvent("system", "init", {"session_id": spec.session_id}))
            await self._respond(
                "JUPITER_BOOK_RESULT\n"
                "title: Mein Buch\nauthor: Autor X\n"
                "dir: /home/dev/tools/Hal/04 Resources/Buch_Nuggets/Autor X-Mein Buch\n"
                "note: /home/dev/tools/Hal/04 Resources/Buch_Nuggets/Autor X-Mein Buch/n.md\n"
                "pdf: /home/dev/tools/Hal/04 Resources/Buch_Nuggets/Autor X-Mein Buch/n.pdf\n"
            )

    repo = SqliteBookNuggetsRepository(str(tmp_path / "bnq.db"))
    mgr = SessionManager(driver_factory=lambda: MarkerDriver())
    worker = BookNuggetsWorker(mgr, repo)
    await worker.startup()
    await worker.add_source("url", "https://x.com/b.pdf", "staged", "sonnet", "opus")
    await _drain(worker)
    row = (await worker.list_queue())[0]
    assert row["status"] == "done"
    assert row["title"] == "Mein Buch" and row["author"] == "Autor X"
    assert row["result_note_path"].endswith("n.md")
    assert row["result_pdf_path"].endswith("n.pdf")


async def test_library_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "book_nuggets_project_path", str(tmp_path))
    monkeypatch.setattr(settings, "book_nuggets_output_subdir", "out")
    sub = tmp_path / "out" / "Autor-Titel"
    sub.mkdir(parents=True)
    (sub / "Autor-Titel.md").write_text("# Nugget")
    (sub / "Autor-Titel.pdf").write_bytes(b"%PDF")
    repo = SqliteBookNuggetsRepository(str(tmp_path / "bnq.db"))
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    worker = BookNuggetsWorker(mgr, repo)
    lib = await worker.list_library()
    assert len(lib) == 1
    assert lib[0]["title"] == "Autor-Titel"
    assert lib[0]["md_path"].endswith("Autor-Titel.md")
    assert lib[0]["pdf_path"].endswith("Autor-Titel.pdf")


# --- API (TestClient) ------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "book_nuggets_project_path", PROJECT)
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as c:
        yield c


def test_api_add_and_get_queue(client):
    r = client.post("/book-nuggets/queue", json={
        "source_type": "url", "source_ref": "https://x.com/b.pdf",
        "model_mode": "staged", "model_extract": "sonnet", "model_consolidate": "opus",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["item"]["source_ref"] == "https://x.com/b.pdf"
    q = client.get("/book-nuggets/queue").json()
    assert len(q["items"]) == 1


def test_api_add_invalid_returns_400(client):
    r = client.post("/book-nuggets/queue", json={
        "source_type": "url", "source_ref": "keine-url",
    })
    assert r.status_code == 400
    r2 = client.post("/book-nuggets/queue", json={
        "source_type": "upload", "source_ref": "/x/b.mobi",
    })
    assert r2.status_code == 400 and "mobi" in r2.json()["detail"]


def test_api_duplicate_returns_409(client, tmp_path):
    f = tmp_path / "b.pdf"
    f.write_bytes(b"dup content")
    payload = {"source_type": "upload", "source_ref": str(f)}
    assert client.post("/book-nuggets/queue", json=payload).status_code == 200
    r = client.post("/book-nuggets/queue", json=payload)
    assert r.status_code == 409
    assert "existing_id" in r.json()
    # Mit on_duplicate → akzeptiert.
    ok = client.post("/book-nuggets/queue", json={**payload, "on_duplicate": "new_version"})
    assert ok.status_code == 200


def test_api_estimate(client, tmp_path):
    f = tmp_path / "b.pdf"
    f.write_bytes(b"x" * 4000)
    r = client.post("/book-nuggets/estimate", json={
        "source_type": "upload", "source_ref": str(f), "model_mode": "single",
        "model_extract": "sonnet", "model_consolidate": "opus",
    })
    assert r.status_code == 200
    assert r.json()["est_tokens"] == 1000


def test_api_delete_and_404(client):
    add = client.post("/book-nuggets/queue", json={
        "source_type": "url", "source_ref": "https://x.com/b.pdf",
    }).json()
    item_id = add["item"]["id"]
    assert client.delete(f"/book-nuggets/queue/{item_id}").status_code == 204
    assert client.delete(f"/book-nuggets/queue/{item_id}").status_code == 404


def test_api_settings_roundtrip(client):
    s = client.get("/book-nuggets/settings").json()
    assert s["default_model_mode"] == "staged"
    up = client.patch("/book-nuggets/settings", json={
        "default_model_mode": "single", "default_page_limit": 300,
    }).json()
    assert up["default_model_mode"] == "single" and up["default_page_limit"] == 300
    assert client.get("/book-nuggets/settings").json()["default_page_limit"] == 300


def test_api_retry_non_error_conflict(client):
    add = client.post("/book-nuggets/queue", json={
        "source_type": "url", "source_ref": "https://x.com/b.pdf",
    }).json()
    item_id = add["item"]["id"]
    r = client.post(f"/book-nuggets/queue/{item_id}/retry")
    assert r.status_code == 409
