"""PROJ-5 — Context-Management & Handover.

Deckt ab: Schwellen-Klemmung + Settings-API, pro-Session-Override, „unbekannt"-
Gauge bei fehlenden Token-Daten, der einmalige Schwellen-Auto-Vorschlag, der
Hybrid-Handover-Generator (Gerüst), das Schreiben in den Vault sowie der Reset-
Staffelstab (alt archiviert, Kind-Session mit Handover-Seed + parent-Verweis).
Alles mit FakeDriver — ohne echte Claude-Session.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import THRESHOLD_MAX_PCT, THRESHOLD_MIN_PCT, clamp_threshold, settings
from app.engine.handover import build_handover_md
from app.engine.manager import DONE, SessionManager
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


# --- Schwellen-Klemmung (Edge-Case 4) --------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [(0, THRESHOLD_MIN_PCT), (100, THRESHOLD_MAX_PCT), (-50, THRESHOLD_MIN_PCT),
     (999, THRESHOLD_MAX_PCT), (70, 70)],
)
def test_clamp_threshold(value, expected):
    assert clamp_threshold(value) == expected


# --- Manager-Fixtures -------------------------------------------------------


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


async def _session(mgr: SessionManager):
    return await mgr.create(project_path=PROJECT, initial_prompt="Hallo", model="haiku")


# --- Gauge „unbekannt" + Füllstand ------------------------------------------


@pytest.mark.asyncio
async def test_context_known_true_after_usage():
    mgr = _mgr()
    rt = await _session(mgr)
    # FakeDriver liefert usage → context_known True, Füllstand > 0.
    assert rt.state.context_known is True
    assert rt.to_read()["context_fill_pct"] > 0


def test_fresh_state_is_unknown():
    from app.engine.manager import SessionState

    s = SessionState(session_id="x", owner="dev", project_path=PROJECT, model="haiku", permission_mode="default")
    data = s.to_read()
    assert data["context_known"] is False
    assert data["context_fill_pct"] == 0.0  # Frontend zeigt bei context_known=False „unbekannt"


# --- wirksame Schwelle + Warn-Flag ------------------------------------------


@pytest.mark.asyncio
async def test_effective_threshold_override_beats_global():
    mgr = _mgr()
    rt = await _session(mgr)
    assert rt.state.effective_threshold_pct == clamp_threshold(settings.context_fill_threshold_pct)
    rt.state.context_threshold_override_pct = 60
    assert rt.state.effective_threshold_pct == 60


@pytest.mark.asyncio
async def test_threshold_warning_and_one_shot_notice():
    mgr = _mgr()
    rt = await _session(mgr)
    q = rt.subscribe()
    # Füllstand künstlich über eine niedrige Session-Schwelle heben.
    rt.state.context_threshold_override_pct = THRESHOLD_MIN_PCT  # 50
    rt.state.context_fill_pct = 90.0
    rt.state.context_known = True
    assert rt.state.threshold_warning is True

    rt._maybe_warn_threshold()
    rt._maybe_warn_threshold()  # zweiter Aufruf darf NICHT erneut feuern
    notices = []
    while not q.empty():
        msg = q.get_nowait()
        if msg.get("kind") == "notice":
            notices.append(msg)
    assert len(notices) == 1
    assert notices[0]["event"] == "threshold_reached"
    assert notices[0]["threshold_pct"] == THRESHOLD_MIN_PCT
    assert rt.state.threshold_warned is True


# --- Handover-Generator (Gerüst) --------------------------------------------


@pytest.mark.asyncio
async def test_generate_handover_has_all_sections():
    mgr = _mgr()
    rt = await _session(mgr)
    out = mgr.generate_handover(rt.state.session_id)
    assert out["title"].startswith("handover-")
    body = out["body"]
    for heading in ("Wo stehen wir?", "Erledigt", "Offen", "Fallstricke", "Pointer"):
        assert f"## {heading}" in body
    # Pointer statt Volltext: Projektpfad referenziert, kein Frontmatter im Body.
    assert PROJECT in body
    assert not body.startswith("---")


def test_build_handover_enrichment_overrides_prose():
    from app.engine.manager import SessionState

    s = SessionState(session_id="abcd1234", owner="dev", project_path=PROJECT, model="haiku", permission_mode="default")
    body = build_handover_md(s, [], [], enrichment={"offen": "LLM: noch Tests offen"})
    assert "LLM: noch Tests offen" in body


# --- REST: Settings-Schwelle ------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


@pytest.fixture(autouse=True)
def _reset_global_threshold():
    original = settings.context_fill_threshold_pct
    yield
    settings.context_fill_threshold_pct = original


def _create(client: TestClient) -> str:
    r = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "Hi", "model": "haiku"})
    return r.json()["session_id"]


def test_get_threshold_default(client: TestClient):
    data = client.get("/settings/threshold").json()
    assert data["min_pct"] == THRESHOLD_MIN_PCT and data["max_pct"] == THRESHOLD_MAX_PCT
    assert THRESHOLD_MIN_PCT <= data["threshold_pct"] <= THRESHOLD_MAX_PCT


def test_patch_threshold_clamps(client: TestClient):
    assert client.patch("/settings/threshold", json={"threshold_pct": 100}).json()["threshold_pct"] == THRESHOLD_MAX_PCT
    assert client.patch("/settings/threshold", json={"threshold_pct": 0}).json()["threshold_pct"] == THRESHOLD_MIN_PCT
    assert client.patch("/settings/threshold", json={"threshold_pct": 75}).json()["threshold_pct"] == 75


def test_patch_session_threshold_override(client: TestClient):
    sid = _create(client)
    data = client.patch(f"/sessions/{sid}/threshold", json={"threshold_pct": 200}).json()
    assert data["context_fill_threshold_pct"] == THRESHOLD_MAX_PCT  # geklemmt
    # None setzt zurück auf global.
    back = client.patch(f"/sessions/{sid}/threshold", json={"threshold_pct": None}).json()
    assert back["context_fill_threshold_pct"] == clamp_threshold(settings.context_fill_threshold_pct)


def test_session_threshold_unknown_404(client: TestClient):
    assert client.patch("/sessions/nope/threshold", json={"threshold_pct": 80}).status_code == 404


# --- REST: Handover generate → write ---------------------------------------


def test_generate_then_write_handover(client: TestClient):
    sid = _create(client)
    gen = client.post(f"/sessions/{sid}/handover/generate")
    assert gen.status_code == 200
    body = gen.json()["body"]
    # Generierten Body in den Vault schreiben (vorhandener Endpoint).
    written = client.post(f"/sessions/{sid}/handover", json={"body": body, "title": "ho-test"})
    assert written.status_code == 201
    assert written.json()["type"] == "handover"
    assert written.json()["path"].endswith(".md")


def test_generate_handover_unknown_404(client: TestClient):
    assert client.post("/sessions/nope/handover/generate").status_code == 404


# --- REST: Reset (Staffelstab) ---------------------------------------------


def test_reset_archives_old_and_seeds_child(client: TestClient):
    sid = _create(client)
    seed = "# Handover\n\n## Offen\n\n- Weiterarbeiten an X"
    resp = client.post(f"/sessions/{sid}/reset", json={"seed_context": seed})
    assert resp.status_code == 201
    child = resp.json()
    assert child["session_id"] != sid
    assert child["parent_session_id"] == sid

    # Alte Session ist archiviert (abgeschlossen).
    old = client.get(f"/sessions/{sid}").json()
    assert old["status"] == "done"

    # Kind-Session trägt den Handover als Seed in ihrer effektiven Konstitution.
    detail = client.get(f"/sessions/{child['session_id']}/constitution").json()
    assert "Weiterarbeiten an X" in detail["text"]


def test_reset_unknown_404(client: TestClient):
    assert client.post("/sessions/nope/reset", json={"seed_context": "x"}).status_code == 404


def test_double_reset_conflicts_409(client: TestClient):
    """QA5-1: zweiter Reset desselben Strangs wird abgelehnt (kein verwaistes Kind)."""
    sid = _create(client)
    first = client.post(f"/sessions/{sid}/reset", json={"seed_context": "seed"})
    assert first.status_code == 201
    child_id = first.json()["session_id"]
    # Der Vorgänger zeigt nun auf seinen Nachfolger.
    assert client.get(f"/sessions/{sid}").json()["child_session_id"] == child_id
    # Zweiter Reset → 409, kein weiteres Kind.
    second = client.post(f"/sessions/{sid}/reset", json={"seed_context": "seed2"})
    assert second.status_code == 409
    sessions = client.get("/sessions").json()
    children = [s for s in sessions if s["parent_session_id"] == sid]
    assert len(children) == 1  # genau EIN Nachfolger pro Strang


def test_reset_requires_seed_422(client: TestClient):
    sid = _create(client)
    assert client.post(f"/sessions/{sid}/reset", json={}).status_code == 422


@pytest.mark.asyncio
async def test_reset_manager_level_links_parent():
    mgr = _mgr()
    rt = await _session(mgr)
    child = await mgr.reset(rt.state.session_id, seed_context="Seed-Kontext-XYZ")
    assert child.state.parent_session_id == rt.state.session_id
    assert rt.state.child_session_id == child.state.session_id  # Strang verkettet
    assert rt.state.status == DONE  # alt archiviert
    assert "Seed-Kontext-XYZ" in child.state.effective_constitution


@pytest.mark.asyncio
async def test_double_reset_raises_and_leaves_no_orphan():
    """QA5-1 (Manager-Ebene): zweiter Reset wirft, Registry behält genau ein Kind."""
    mgr = _mgr()
    rt = await _session(mgr)
    child = await mgr.reset(rt.state.session_id, seed_context="s1")
    before = len(mgr.list())
    with pytest.raises(RuntimeError):
        await mgr.reset(rt.state.session_id, seed_context="s2")
    assert len(mgr.list()) == before  # keine zweite (verwaiste) Kind-Session entstanden
    assert rt.state.child_session_id == child.state.session_id


# --- Red-Team / Edge-Cases (QA PROJ-5) -------------------------------------


@pytest.mark.asyncio
async def test_reset_while_awaiting_approval_does_not_hang():
    """Reset einer Session mit offener Decision Card darf NICHT hängen — der blockierte
    Hook-Aufruf wird entsperrt (deny), alt wird archiviert, Kind verweist auf Vorgänger."""
    from app.engine.manager import AWAITING_APPROVAL

    mgr = _mgr()
    rt = await _session(mgr)
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "x"})
    )
    await asyncio.sleep(0)
    assert rt.state.status == AWAITING_APPROVAL
    child = await asyncio.wait_for(
        mgr.reset(rt.state.session_id, seed_context="seed"), timeout=3.0
    )
    out = await asyncio.wait_for(task, timeout=3.0)
    assert out.behavior == "deny"  # wartender Hook entsperrt
    assert rt.state.status == DONE
    assert child.state.parent_session_id == rt.state.session_id


@pytest.mark.asyncio
async def test_generate_handover_on_empty_transcript():
    """Generieren ohne jegliche Treiber-Daten: gültiges Gerüst, Füllstand „unbekannt"."""
    from app.engine.manager import SessionRuntime, SessionState

    mgr = _mgr()
    st = SessionState(
        session_id="empty123", owner="dev", project_path=PROJECT,
        model="haiku", permission_mode="default",
    )
    mgr._sessions["empty123"] = SessionRuntime(st, FakeDriver())
    out = mgr.generate_handover("empty123")
    assert all(f"## {s}" in out["body"] for s in ("Wo stehen wir?", "Offen", "Pointer"))
    assert "unbekannt" in out["body"]


@pytest.mark.asyncio
async def test_generate_handover_lists_open_decision_in_offen():
    """Offene Freigabe (PROJ-4) erscheint im Handover unter „Offen" — kein verlorener Kontext."""
    mgr = _mgr()
    rt = await _session(mgr)
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "rm x"})
    )
    await asyncio.sleep(0)
    out = mgr.generate_handover(rt.state.session_id)
    offen = out["body"].split("## Offen")[1].split("##")[0]
    assert "Freigabe ausstehend" in offen
    # Aufräumen: blockierten Hook entsperren.
    mgr.resolve_decision(rt.state.session_id, "tu1", approve=False)
    await task
