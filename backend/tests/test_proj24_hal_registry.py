"""PROJ-24 — Hal↔Registry-Dashboard: Backend-Unit-Tests fuer die kritischen QA-Fixes.

Deckt die BUG-24-* Fixes ab:
- BUG-24-1: hal_queue_select validiert IDs gegen die gescannte Hal-Bibliothek
  (kein Uebernehmen client-kontrollierter rel_path-Werte).
- BUG-24-2: hal_start_ingest startet eine echte Session ueber den (gemockten)
  SessionManager statt einen Fake-Erfolg vorzutaeuschen; done wird erst aus
  dem echten Session-Status abgeleitet.
- BUG-24-3: revision-Mismatch auf Schreib-Endpunkten wird abgelehnt.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.engine.ui_check import UiCheckConflict, UiCheckNotFound, UiCheckService


@dataclass
class _FakeSessionState:
    session_id: str
    status: str = "running"
    error: str | None = None


class _FakeRuntime:
    def __init__(self, session_id: str) -> None:
        self.state = _FakeSessionState(session_id=session_id)


class _FakeManager:
    """Stub fuer SessionManager: zeichnet create()-Aufrufe auf, keine echten Prozesse."""

    def __init__(self) -> None:
        self.created: list[dict] = []
        self._runtimes: dict[str, _FakeRuntime] = {}
        self._next_id = 0

    async def create(self, **kwargs) -> _FakeRuntime:
        self._next_id += 1
        session_id = f"fake-session-{self._next_id}"
        runtime = _FakeRuntime(session_id)
        self._runtimes[session_id] = runtime
        self.created.append(kwargs)
        return runtime

    def get(self, session_id: str) -> _FakeRuntime | None:
        return self._runtimes.get(session_id)


def _make_service(tmp_path: Path, hal_root: Path, manager: _FakeManager | None = None) -> UiCheckService:
    project = tmp_path / "ui-check"
    project.mkdir()
    return UiCheckService(project_path=str(project), manager=manager)


def _seed_hal_entry(hal_root: Path, category: str, name: str) -> None:
    d = hal_root / category / name
    d.mkdir(parents=True)


def test_queue_select_rejects_unknown_id(tmp_path, monkeypatch):
    hal_root = tmp_path / "hal"
    _seed_hal_entry(hal_root, "Websites", "acme")
    monkeypatch.setenv("HAL_WEB_ROOT", str(hal_root))
    svc = _make_service(tmp_path, hal_root)

    with pytest.raises(UiCheckNotFound):
        svc.hal_queue_select(["Websites--../../../../etc"])

    assert svc._load_queue() == []


def test_queue_select_derives_rel_path_from_scan_not_client(tmp_path, monkeypatch):
    hal_root = tmp_path / "hal"
    _seed_hal_entry(hal_root, "Websites", "acme")
    monkeypatch.setenv("HAL_WEB_ROOT", str(hal_root))
    svc = _make_service(tmp_path, hal_root)

    result = svc.hal_queue_select(["Websites--acme"])
    entry = result["queue"][0]
    assert entry["rel_path"] == "Websites/acme"
    assert entry["category"] == "Websites"
    assert entry["status"] == "selected"


def test_queue_select_stale_revision_conflict(tmp_path, monkeypatch):
    hal_root = tmp_path / "hal"
    _seed_hal_entry(hal_root, "Websites", "acme")
    _seed_hal_entry(hal_root, "Websites", "beta")
    monkeypatch.setenv("HAL_WEB_ROOT", str(hal_root))
    svc = _make_service(tmp_path, hal_root)

    stale_revision = svc.hal_queue_select(["Websites--acme"])["revision"]
    svc.hal_queue_cancel("Websites--acme")  # changes the queue file → revision moves on

    with pytest.raises(UiCheckConflict):
        svc.hal_queue_select(["Websites--beta"], revision=stale_revision)


def test_start_ingest_rejects_path_outside_hal_root(tmp_path, monkeypatch):
    hal_root = tmp_path / "hal"
    _seed_hal_entry(hal_root, "Websites", "acme")
    monkeypatch.setenv("HAL_WEB_ROOT", str(hal_root))
    manager = _FakeManager()
    svc = _make_service(tmp_path, hal_root, manager=manager)

    # Queue-Datei extern manipuliert (z.B. durch alten Bug oder direkten Dateizugriff).
    svc._save_queue([{
        "id": "Websites--acme", "name": "acme", "category": "Websites",
        "rel_path": "../../../../etc", "status": "selected",
    }])

    import asyncio
    with pytest.raises(UiCheckConflict):
        asyncio.run(svc.hal_start_ingest("Websites--acme"))
    assert manager.created == []


def test_start_ingest_uses_real_session_manager(tmp_path, monkeypatch):
    hal_root = tmp_path / "hal"
    _seed_hal_entry(hal_root, "Websites", "acme")
    monkeypatch.setenv("HAL_WEB_ROOT", str(hal_root))
    manager = _FakeManager()
    svc = _make_service(tmp_path, hal_root, manager=manager)
    svc.hal_queue_select(["Websites--acme"])

    import asyncio
    result = asyncio.run(svc.hal_start_ingest("Websites--acme"))

    assert result["session_id"] == "fake-session-1"
    assert len(manager.created) == 1
    assert "/ui-template-ingest" in manager.created[0]["initial_prompt"]

    queue = svc._load_queue()
    assert queue[0]["ingest_session_id"] == "fake-session-1"
    assert queue[0]["status"] == "selected"  # erst done nach echtem Session-Erfolg


def test_queue_flips_to_done_only_after_session_succeeds(tmp_path, monkeypatch):
    hal_root = tmp_path / "hal"
    _seed_hal_entry(hal_root, "Websites", "acme")
    monkeypatch.setenv("HAL_WEB_ROOT", str(hal_root))
    manager = _FakeManager()
    svc = _make_service(tmp_path, hal_root, manager=manager)
    svc.hal_queue_select(["Websites--acme"])

    import asyncio
    asyncio.run(svc.hal_start_ingest("Websites--acme"))

    # Session laeuft noch → Queue bleibt selected.
    assert svc.hal_registry()["queue"][0]["status"] == "selected"

    # Session erfolgreich beendet → naechstes Lesen leitet done ab.
    runtime = manager.get("fake-session-1")
    runtime.state.status = "done"
    assert svc.hal_registry()["queue"][0]["status"] == "done"


def test_queue_stays_selected_after_failed_session(tmp_path, monkeypatch):
    hal_root = tmp_path / "hal"
    _seed_hal_entry(hal_root, "Websites", "acme")
    monkeypatch.setenv("HAL_WEB_ROOT", str(hal_root))
    manager = _FakeManager()
    svc = _make_service(tmp_path, hal_root, manager=manager)
    svc.hal_queue_select(["Websites--acme"])

    import asyncio
    asyncio.run(svc.hal_start_ingest("Websites--acme"))

    runtime = manager.get("fake-session-1")
    runtime.state.status = "error"
    runtime.state.error = "Ingest abgebrochen"

    assert svc.hal_registry()["queue"][0]["status"] == "selected"
