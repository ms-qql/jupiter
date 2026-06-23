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

from app.engine import abc_phases
from app.engine.manager import AWAITING_APPROVAL, SessionManager
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
