"""PROJ-17 — Recovery über den Vault.

Testet die Recovery-Sicht gegen die Acceptance Criteria:
- wiederherstellbare Stränge aus verwaisten In-Memory-Sessions + aus reinem Vault;
- 3-stufige Quelle (Handover > Session-Log > nur Metadaten/„unvollständig");
- „Hier ging's weiter"-Vorschlag, restore (Kind + Staffelstab) idempotent,
- dismiss (ausblenden, Vault bleibt, überdauert Neustart), Projektpfad-Blockade.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.session_index import SqliteSessionIndexRepository
from app.engine.manager import ERROR, SessionManager
from app.engine.recovery import RecoveryService
from app.engine.vault import VaultService
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"
_ORPHAN_ERR = "Verwaist nach Backend-Neustart (Prozess beendet)."

_HANDOVER_BODY = (
    "# Handover — jupiter\n\n"
    "## Wo stehen wir?\n\n- Status: **arbeitet**\n\n"
    "## Offen\n\n- Tests schreiben\n\n"
    "## Pointer\n\n- Projektpfad: `%s`\n" % PROJECT
)


def _mgr(repo=None, vault=None) -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver(), vault=vault, repo=repo)


async def _drain(mgr: SessionManager) -> None:
    for _ in range(5):
        pending = list(mgr._persist_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


def _orphan(rt, project_path: str | None = None) -> None:
    """Macht aus einer (lebenden) Session einen verwaisten Recovery-Kandidaten."""
    rt.state.status = ERROR
    rt.state.error = _ORPHAN_ERR
    if project_path is not None:
        rt.state.project_path = project_path


async def _setup(monkeypatch, repo=None):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    vault = VaultService()
    mgr = _mgr(repo=repo, vault=vault)
    return mgr, vault, RecoveryService(mgr, vault)


# --- Kandidaten-Erkennung -------------------------------------------------

@pytest.mark.asyncio
async def test_inmemory_orphan_with_handover(monkeypatch):
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    vault.write(type="handover", session_id=sid, title="h", body=_HANDOVER_BODY)
    _orphan(rt)

    cands = svc.candidates()
    assert len(cands) == 1
    c = cands[0]
    assert c["session_id"] == sid
    assert c["source"] == "handover"
    assert "Tests schreiben" in c["suggestion"]
    assert c["restore_blocked"] is False
    assert c["last_handover_at"]  # Zeitpunkt vorhanden


@pytest.mark.asyncio
async def test_active_session_is_not_candidate(monkeypatch):
    """Nur verwaiste Stränge sind Kandidaten — laufende nicht (kein Doppel-Eintrag)."""
    mgr, vault, svc = await _setup(monkeypatch)
    await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    assert svc.candidates() == []


@pytest.mark.asyncio
async def test_restore_active_session_rejected(monkeypatch):
    """BUG-1: eine AKTIVE (nicht verwaiste) Session darf nicht restorebar sein —
    sonst entstünde ein Duplikat-Strang für einen lebenden Prozess."""
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    with pytest.raises(KeyError):  # kein Kandidat → Route übersetzt zu 404
        await svc.restore(rt.state.session_id)
    assert rt.state.child_session_id is None
    assert mgr.active_count() == 1  # kein zweiter Strang entstanden


def test_api_restore_active_session_404(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        sid = client.post(
            "/sessions", json={"project_path": PROJECT, "initial_prompt": "x", "model": "haiku"}
        ).json()["session_id"]
        assert client.post(f"/recovery/{sid}/restore", json={}).status_code == 404


@pytest.mark.asyncio
async def test_incomplete_without_handover_or_log(monkeypatch):
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    _orphan(rt)
    c = svc.candidates()[0]
    assert c["source"] == "incomplete"
    assert "unvollständig" in c["suggestion"].lower()
    assert c["restore_blocked"] is False  # Projektpfad existiert → wiederherstellbar


@pytest.mark.asyncio
async def test_newest_handover_wins(monkeypatch):
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    from datetime import datetime, timezone

    vault.write(
        type="handover", session_id=sid, title="alt",
        body="# H\n\n## Offen\n\n- ALT\n",
        created=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )
    vault.write(
        type="handover", session_id=sid, title="neu",
        body="# H\n\n## Offen\n\n- NEU\n",
        created=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )
    _orphan(rt)
    c = svc.candidates()[0]
    assert "NEU" in c["suggestion"] and "ALT" not in c["suggestion"]


@pytest.mark.asyncio
async def test_damaged_handover_warns(monkeypatch):
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    vault.write(type="handover", session_id=sid, title="kaputt", body="nur prosa, keine abschnitte")
    _orphan(rt)
    c = svc.candidates()[0]
    assert c["warning"] is not None


@pytest.mark.asyncio
async def test_blocked_when_project_path_gone(monkeypatch):
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    _orphan(rt, project_path="/does/not/exist/xyz")
    c = svc.candidates()[0]
    assert c["restore_blocked"] is True
    with pytest.raises(ValueError):
        await svc.restore(rt.state.session_id)


# --- Reiner Vault-Wiederaufbau (In-Memory komplett weg) -------------------

@pytest.mark.asyncio
async def test_pure_vault_candidate_handover(monkeypatch):
    mgr, vault, svc = await _setup(monkeypatch)
    vault.write(type="handover", session_id="ghost", title="g", body=_HANDOVER_BODY)
    cands = svc.candidates()
    c = next(x for x in cands if x["session_id"] == "ghost")
    assert c["source"] == "handover"
    assert c["project_path"] == PROJECT  # aus dem Pointer rekonstruiert
    assert c["restore_blocked"] is False
    child = await svc.restore("ghost")
    assert child.state.parent_session_id == "ghost"
    # idempotent: Strang hat nun einen Nachfolger → kein Kandidat mehr.
    assert not any(x["session_id"] == "ghost" for x in svc.candidates())


@pytest.mark.asyncio
async def test_pure_vault_log_only_blocked(monkeypatch):
    """Log ohne Frontmatter-Pfad und ohne auflösbaren Projektnamen → blockiert."""
    mgr, vault, svc = await _setup(monkeypatch)
    vault.write(
        type="session_log", session_id="ghost2", title="nicht-existentes-projekt-xyz",
        body="## Claude\n\nirgendwas\n",
    )
    c = next(x for x in svc.candidates() if x["session_id"] == "ghost2")
    assert c["source"] == "log"
    assert c["restore_blocked"] is True  # kein Projektpfad rekonstruierbar


@pytest.mark.asyncio
async def test_pure_vault_log_with_frontmatter_path(monkeypatch):
    """PROJ-17-Fix: Session-Log trägt ``project_path`` im Frontmatter → reiner
    Vault-Wiederaufbau (Live-Index weg) kann den Strang wiederherstellen."""
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    vault.write_session_log(rt.state, "## Claude\n\nweiter so\n")
    mgr._sessions.pop(sid)  # In-Memory komplett weg → nur noch Vault.

    c = next(x for x in svc.candidates() if x["session_id"] == sid)
    assert c["source"] == "log"
    assert c["project_path"] == PROJECT  # aus dem Frontmatter rekonstruiert
    assert c["restore_blocked"] is False
    child = await svc.restore(sid)
    assert child.state.parent_session_id == sid


@pytest.mark.asyncio
async def test_pure_vault_log_path_resolved_by_name(monkeypatch):
    """Altbestand ohne Frontmatter-Pfad: Projektname → existierendes Verzeichnis
    unter ``allowed_roots`` (Backfill). ``jupiter`` existiert unter /home/dev/projects."""
    mgr, vault, svc = await _setup(monkeypatch)
    vault.write(
        type="session_log", session_id="ghost-name", title="jupiter",
        body="## Claude\n\nirgendwas\n",
    )
    c = next(x for x in svc.candidates() if x["session_id"] == "ghost-name")
    assert c["source"] == "log"
    assert c["project_path"] == PROJECT
    assert c["restore_blocked"] is False


# --- Restore (Staffelstab) + Idempotenz -----------------------------------

@pytest.mark.asyncio
async def test_restore_links_child_idempotent(monkeypatch):
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    vault.write(type="handover", session_id=sid, title="h", body=_HANDOVER_BODY)
    _orphan(rt)

    child = await svc.restore(sid)
    assert child.state.parent_session_id == sid
    assert rt.state.child_session_id == child.state.session_id
    # Seed = Handover-Body als System-Prompt-Append der Kind-Session.
    assert "Tests schreiben" in child.state.effective_constitution
    # Nicht mehr als Kandidat sichtbar.
    assert svc.candidates() == []
    # Zweiter Restore desselben Strangs → abgelehnt (1 Strang = 1 Nachfolger).
    with pytest.raises(RuntimeError):
        await svc.restore(sid)


# --- Dismiss --------------------------------------------------------------

@pytest.mark.asyncio
async def test_dismiss_hides_but_keeps_vault(monkeypatch):
    mgr, vault, svc = await _setup(monkeypatch)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    vault.write(type="handover", session_id=sid, title="h", body=_HANDOVER_BODY)
    _orphan(rt)

    svc.dismiss(sid)
    assert svc.candidates() == []
    assert rt.state.recovery_dismissed is True
    assert vault.list_files("Handovers")  # Vault-Eintrag bleibt erhalten (Audit).


@pytest.mark.asyncio
async def test_dismiss_survives_rehydrate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    vault = VaultService()
    mgr = _mgr(repo=repo, vault=vault)
    svc = RecoveryService(mgr, vault)
    rt = await mgr.create(project_path=PROJECT, initial_prompt="x", model="haiku")
    sid = rt.state.session_id
    _orphan(rt)
    mgr._persist(rt)  # verwaisten Stand spiegeln
    await _drain(mgr)  # erst diesen Write abschließen (sonst Race auf dieselbe Zeile)
    svc.dismiss(sid)  # Flag setzen + spiegeln
    await _drain(mgr)

    # Frischer Manager (= Backend-Neustart) rehydriert aus dem Live-Index.
    mgr2 = _mgr(repo=repo, vault=vault)
    await mgr2.rehydrate()
    assert mgr2.get(sid).state.recovery_dismissed is True
    svc2 = RecoveryService(mgr2, vault)
    assert all(c["session_id"] != sid for c in svc2.candidates())


# --- API ------------------------------------------------------------------

def test_api_recovery_flow(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        sid = client.post(
            "/sessions", json={"project_path": PROJECT, "initial_prompt": "x", "model": "haiku"}
        ).json()["session_id"]
        st = app.state.manager.get(sid).state
        st.status, st.error = "error", _ORPHAN_ERR
        app.state.vault.write(type="handover", session_id=sid, title="h", body=_HANDOVER_BODY)

        lst = client.get("/recovery").json()
        assert [c["session_id"] for c in lst["candidates"]] == [sid]

        assert client.post(f"/recovery/{sid}/restore", json={}).status_code == 201
        # Zweiter Restore → 409.
        assert client.post(f"/recovery/{sid}/restore", json={}).status_code == 409


def test_api_dismiss_204(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 5)
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        sid = client.post(
            "/sessions", json={"project_path": PROJECT, "initial_prompt": "x", "model": "haiku"}
        ).json()["session_id"]
        st = app.state.manager.get(sid).state
        st.status, st.error = "error", _ORPHAN_ERR
        app.state.vault.write(type="handover", session_id=sid, title="h", body=_HANDOVER_BODY)

        assert client.post(f"/recovery/{sid}/dismiss").status_code == 204
        assert client.get("/recovery").json()["candidates"] == []


def test_api_restore_unknown_404(monkeypatch):
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        assert client.post("/recovery/nope/restore", json={}).status_code == 404
