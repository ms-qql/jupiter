"""PROJ-8 — ABC-Workflow-Gantt (Backend).

Deckt die zentrale Phasen-Konstante + Skill→Phase-Detektor, die monotone „weiteste
Phase", die Feature-Erkennung (Skill-Arg + berührtes Spec-File), die Verdrahtung im
Freigabe-Hook (Seiteneffekt, ohne die Card-Logik zu stören) sowie den REST-Vertrag
(neue Felder + ``project_name``) ab — alles mit FakeDriver, ohne echte Claude-Session.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.engine import abc_phases, policy
from app.engine.manager import AWAITING_APPROVAL, SessionManager
from app.engine.policy import PolicyStore
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


# --- Phasen-Konstante + Mapping --------------------------------------------

def test_canonical_phase_order():
    assert abc_phases.ABC_PHASES == (
        "brainstorm", "requirements", "architecture", "frontend",
        "backend", "qa", "deploy", "document",
    )


@pytest.mark.parametrize(
    "skill,phase",
    [
        ("abc-brainstorm", "brainstorm"),
        ("abc-requirements", "requirements"),
        ("abc-architecture", "architecture"),
        ("abc-frontend", "frontend"),
        ("abc-backend", "backend"),
        ("abc-qa", "qa"),
        ("abc-qa-e2e", "qa"),          # E2E zählt zur QA-Phase
        ("abc-deploy", "deploy"),
        ("abc-document", "document"),
        ("  abc-backend  ", "backend"),  # tolerant gegenüber Whitespace
    ],
)
def test_phase_for_workflow_skills(skill, phase):
    assert abc_phases.phase_for_skill(skill) == phase


@pytest.mark.parametrize("skill", ["abc-refactor", "abc-challenge", "abc-clarification",
                                   "abc-fullstack", "codegraph", "", None, "frontend"])
def test_non_phase_skills_map_to_none(skill):
    assert abc_phases.phase_for_skill(skill) is None


# --- max_phase: monotone „weiteste erreichte Phase" -------------------------

def test_max_phase_keeps_furthest():
    assert abc_phases.max_phase("backend", "qa") == "qa"
    assert abc_phases.max_phase("document", "deploy") == "document"  # nicht-linear
    assert abc_phases.max_phase("frontend", "frontend") == "frontend"


def test_max_phase_handles_none_and_unknown():
    assert abc_phases.max_phase(None, "qa") == "qa"
    assert abc_phases.max_phase("qa", None) == "qa"
    assert abc_phases.max_phase(None, None) is None
    assert abc_phases.max_phase("quatsch", "qa") == "qa"  # unbekannt → ignoriert


# --- Feature-Erkennung ------------------------------------------------------

@pytest.mark.parametrize(
    "args,feat",
    [("8", "8"), ("PROJ-8", "8"), ("proj-12", "12"), ("6 mit Zusatz", "6"),
     (8, "8"), ("", None), (None, None), ("kein-feature", None)],
)
def test_feature_from_args(args, feat):
    assert abc_phases.feature_from_args(args) == feat


@pytest.mark.parametrize(
    "path,feat",
    [("features/PROJ-8-abc-workflow-gantt.md", "8"),
     ("/abs/features/PROJ-11-x.md", "11"),
     ("features/INDEX.md", None),
     ("backend/app/main.py", None),
     ("", None), (None, None)],
)
def test_feature_from_path(path, feat):
    assert abc_phases.feature_from_path(path) == feat


# --- detect_phase_signal: reiner Detektor -----------------------------------

def test_detect_skill_sets_phase_reached_and_feature():
    out = abc_phases.detect_phase_signal(
        "Skill", {"skill": "abc-backend", "args": "8"},
        phase=None, reached=None, feature=None,
    )
    assert out == ("backend", "backend", "8")


def test_detect_keeps_reached_on_backward_jump():
    """Nach 'document' zurück zu 'frontend': aktuelle Phase wandert, reached bleibt."""
    out = abc_phases.detect_phase_signal(
        "Skill", {"skill": "abc-frontend", "args": "8"},
        phase="document", reached="document", feature="8",
    )
    assert out == ("frontend", "document", "8")


def test_detect_skill_without_arg_keeps_known_feature():
    out = abc_phases.detect_phase_signal(
        "Skill", {"skill": "abc-document"},
        phase="qa", reached="qa", feature="8",
    )
    assert out == ("document", "document", "8")


def test_detect_non_phase_skill_changes_nothing():
    state = ("backend", "backend", "8")
    out = abc_phases.detect_phase_signal(
        "Skill", {"skill": "abc-refactor"},
        phase=state[0], reached=state[1], feature=state[2],
    )
    assert out == state


def test_detect_touched_spec_file_sets_fallback_feature():
    out = abc_phases.detect_phase_signal(
        "Write", {"file_path": "features/PROJ-13-x.md", "content": "…"},
        phase="backend", reached="backend", feature=None,
    )
    assert out == ("backend", "backend", "13")


def test_detect_unrelated_tool_changes_nothing():
    state = ("backend", "backend", "8")
    out = abc_phases.detect_phase_signal(
        "Bash", {"command": "ls"}, phase=state[0], reached=state[1], feature=state[2],
    )
    assert out == state


# --- Verdrahtung im Manager (Hook-Seiteneffekt) -----------------------------

def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


@pytest.mark.asyncio
async def test_read_tool_detects_nothing_but_runs_detector():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    out = await mgr.request_decision(rt.state.session_id, "tu1", "Read", {"file_path": "a.py"})
    assert out.behavior == "allow" and out.auto is True
    assert rt.state.abc_phase is None  # Read ist kein abc-Skill


@pytest.mark.asyncio
async def test_skill_invocation_sets_phase_via_hook():
    """Der Skill-Aufruf läuft durch den Freigabe-Hook: der Detektor setzt die Phase
    als Seiteneffekt, die Card-Logik bleibt unberührt (Skill ist genehmigungspflichtig)."""
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    task = asyncio.create_task(
        mgr.request_decision(
            rt.state.session_id, "tu1", "Skill", {"skill": "abc-backend", "args": "8"}
        )
    )
    await asyncio.sleep(0)  # Detektor + Card entstehen lassen
    assert rt.state.abc_phase == "backend"
    assert rt.state.abc_phase_reached == "backend"
    assert rt.state.abc_feature == "8"
    assert rt.state.status == AWAITING_APPROVAL  # Skill öffnet weiterhin eine Card
    # aufräumen: entscheiden → Hook entsperren
    mgr.resolve_decision(rt.state.session_id, "tu1", approve=True)
    await task


@pytest.mark.asyncio
async def test_spec_edit_provides_fallback_feature_via_hook():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    task = asyncio.create_task(
        mgr.request_decision(
            rt.state.session_id, "tu1", "Write",
            {"file_path": f"{PROJECT}/features/PROJ-8-abc-workflow-gantt.md", "content": "x"},
        )
    )
    await asyncio.sleep(0)
    assert rt.state.abc_feature == "8"
    mgr.resolve_decision(rt.state.session_id, "tu1", approve=True)
    await task


# --- PROJ-30: Phasen-Erkennung im bypassPermissions-Modus -------------------

# Kanonische Skill-Kette über ALLE 8 Phasen (Schwerpunkt der Regression: qa, deploy).
_PHASE_SKILLS = [
    ("abc-brainstorm", "brainstorm"),
    ("abc-requirements", "requirements"),
    ("abc-architecture", "architecture"),
    ("abc-frontend", "frontend"),
    ("abc-backend", "backend"),
    ("abc-qa", "qa"),
    ("abc-deploy", "deploy"),
    ("abc-document", "document"),
]


@pytest.mark.asyncio
async def test_bypass_recognizes_all_phases_without_cards(tmp_path, monkeypatch):
    """PROJ-30: Im bypassPermissions-Modus mit deaktiviertem Phasen-Gate laufen Skill-
    Aufrufe ohne Decision Card durch — die Phase MUSS trotzdem erkannt werden (alle 8
    Phasen, inkl. qa/deploy). Beobachtung ist von der Card-Kontrolle entkoppelt."""
    p = tmp_path / "policy.yaml"
    p.write_text("phase_gate:\n  enabled: false\n  transitions: []\n", encoding="utf-8")
    monkeypatch.setattr(policy, "policy_store", PolicyStore(str(p)))

    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku",
                          permission_mode="bypassPermissions")
    for i, (skill, phase) in enumerate(_PHASE_SKILLS):
        out = await mgr.request_decision(
            rt.state.session_id, f"tu{i}", "Skill", {"skill": skill, "args": "30"}
        )
        assert out.behavior == "allow"  # keine blockierende Card im Bypass
        assert rt.pending == {}, f"{skill}: es darf keine Card entstehen"
        assert rt.state.abc_phase == phase, f"{skill}: aktuelle Phase falsch"
        assert rt.state.abc_phase_reached == phase, f"{skill}: erreichte Phase falsch"
    # Schwerpunkt: qa UND deploy wurden unterwegs korrekt erkannt.
    assert rt.state.abc_feature == "30"
    assert rt.state.abc_phase_reached == "document"  # monoton bis ans Ende


@pytest.mark.asyncio
async def test_bypass_qa_deploy_recognized_even_while_gate_blocks(tmp_path, monkeypatch):
    """PROJ-30: Bei aktivem Phasen-Gate (Default) pausiert die qa/deploy-Card im Bypass die
    Tool-Ausführung — die Phase im Gantt rückt aber SOFORT vor (entkoppelte Erkennung),
    statt einzufrieren, bis jemand die Card auflöst."""
    p = tmp_path / "policy.yaml"
    p.write_text("phase_gate:\n  enabled: true\n  transitions: []\n", encoding="utf-8")
    monkeypatch.setattr(policy, "policy_store", PolicyStore(str(p)))

    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku",
                          permission_mode="bypassPermissions")
    rt.state.abc_phase = "backend"
    rt.state.abc_phase_reached = "backend"

    # backend→qa: Gate feuert (bypass-fest), aber qa ist sofort erkannt.
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "qa", "Skill", {"skill": "abc-qa", "args": "30"})
    )
    await asyncio.sleep(0)
    assert rt.pending["qa"].card_type == "phase_transition"
    assert rt.state.abc_phase == "qa" and rt.state.abc_phase_reached == "qa"
    mgr.resolve_decision(rt.state.session_id, "qa", approve=True)
    await task

    # qa→deploy: dito, deploy sofort sichtbar.
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "dep", "Skill", {"skill": "abc-deploy", "args": "30"})
    )
    await asyncio.sleep(0)
    assert rt.pending["dep"].card_type == "phase_transition"
    assert rt.state.abc_phase == "deploy" and rt.state.abc_phase_reached == "deploy"
    mgr.resolve_decision(rt.state.session_id, "dep", approve=True)
    await task


# --- project_name -----------------------------------------------------------

@pytest.mark.asyncio
async def test_project_name_defaults_to_basename():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    assert rt.state.project_name == "jupiter"


@pytest.mark.asyncio
async def test_project_name_explicit_wins():
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hi", model="haiku", project_name="Apollo"
    )
    assert rt.state.project_name == "Apollo"


# --- REST-Vertrag -----------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


def _create(client: TestClient, **extra) -> dict:
    body = {"project_path": PROJECT, "initial_prompt": "Hi", "model": "haiku", **extra}
    return client.post("/sessions", json=body).json()


def test_session_read_carries_abc_fields(client: TestClient):
    data = _create(client)
    assert data["project_name"] == "jupiter"
    assert data["abc_phase"] is None
    assert data["abc_phase_reached"] is None
    assert data["abc_feature"] is None


def test_create_accepts_project_name(client: TestClient):
    r = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "Hi", "model": "haiku",
              "project_name": "Apollo"},
    )
    assert r.status_code == 201
    assert r.json()["project_name"] == "Apollo"


def test_list_sessions_carries_abc_fields(client: TestClient):
    _create(client)
    row = client.get("/sessions").json()[0]
    for key in ("project_name", "abc_phase", "abc_phase_reached", "abc_feature"):
        assert key in row


@pytest.mark.asyncio
async def test_end_to_end_skill_hook_updates_gantt_fields():
    """Echter REST+Hook-Pfad: ein abc-Skill-Aufruf des Permission-Hooks setzt die
    Gantt-Felder, die ``GET /sessions`` live mitträgt (gleiche Polling-Mechanik wie
    Board/Rail → Live-Aktualisierung gratis)."""
    import httpx
    from httpx import ASGITransport

    from app.config import settings

    app = create_app(driver_factory=lambda: FakeDriver())
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        sid = (
            await ac.post(
                "/sessions",
                json={"project_path": PROJECT, "initial_prompt": "Hi", "model": "haiku",
                      "project_name": "Jupiter"},
            )
        ).json()["session_id"]

        # Hook meldet einen Skill-Aufruf (genehmigungspflichtig → blockiert).
        hook = asyncio.create_task(
            ac.post(
                "/internal/permission",
                json={"session_id": sid, "tool_name": "Skill",
                      "tool_input": {"skill": "abc-backend", "args": "8"}, "tool_use_id": "tu1"},
                headers={"X-Jupiter-Hook-Token": settings.hook_token},
            )
        )
        # Warten, bis der Detektor die Phase über die Liste sichtbar macht.
        row = {}
        for _ in range(100):
            await asyncio.sleep(0.01)
            rows = (await ac.get("/sessions")).json()
            if rows and rows[0]["abc_phase"]:
                row = rows[0]
                break
        assert row["project_name"] == "Jupiter"
        assert row["abc_phase"] == "backend"
        assert row["abc_phase_reached"] == "backend"
        assert row["abc_feature"] == "8"

        # Card auflösen → Hook entsperren (sauberes Teardown).
        await ac.post(f"/sessions/{sid}/decisions/tu1", json={"decision": "approve"})
        await hook
