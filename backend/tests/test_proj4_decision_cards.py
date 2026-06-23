"""PROJ-4 — Decision Cards / Freigabe-Flow.

Deckt die zentrale Trigger-Policy, die Ausschnitt-Destillation, den Hook-Settings-Bau,
den blockierenden Freigabe-Flow im Manager sowie den REST-Vertrag (inkl. internem
Hook-Endpoint) ab — alles mit FakeDriver, ohne echte Claude-Session.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

from app.config import settings
from app.engine import policy
from app.engine.claude_driver import build_argv
from app.engine.decisions import OBSOLETE, OPEN, DecisionOutcome
from app.engine.hooks import build_hook_settings
from app.engine.base import LaunchSpec
from app.engine.manager import AWAITING_APPROVAL, RUNNING, SessionManager
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


# --- Policy: der EINE zentrale Trigger -------------------------------------

@pytest.mark.parametrize("tool", ["Read", "Glob", "Grep", "WebFetch", "TodoWrite"])
def test_read_tools_need_no_card(tool):
    assert policy.requires_card(tool, {}) is False


@pytest.mark.parametrize("tool", ["Bash", "Edit", "Write", "NotebookEdit", "Task", "Unbekannt"])
def test_write_and_unknown_tools_need_card(tool):
    """Konservativ: alles außer bekannten Lese-Tools → Card."""
    assert policy.requires_card(tool, {}) is True


def test_excerpt_bash_is_command_not_log():
    ex = policy.extract_excerpt("Bash", {"command": "rm -rf /tmp/x", "description": "Aufräumen"})
    assert "rm -rf /tmp/x" in ex
    assert "Aufräumen" in ex


def test_excerpt_edit_is_diff():
    ex = policy.extract_excerpt("Edit", {"file_path": "a.py", "old_string": "alt", "new_string": "neu"})
    assert "- alt" in ex and "+ neu" in ex


def test_excerpt_is_clipped():
    big = "x" * 10_000
    ex = policy.extract_excerpt("Write", {"file_path": "a.py", "content": big})
    assert len(ex) < 6_000 and "gekürzt" in ex


def test_clip_rationale_limits_length():
    assert policy.clip_rationale("") == ""
    long = "wort " * 500
    clipped = policy.clip_rationale(long)
    assert len(clipped) < 1_000 and "gekürzt" in clipped


def test_summarize_action_is_human_readable():
    assert "a.py" in policy.summarize_action("Edit", {"file_path": "a.py"})
    assert "Shell" in policy.summarize_action("Bash", {"command": "ls"})


# --- Hook-Settings + build_argv --------------------------------------------

def test_build_hook_settings_shape():
    import json

    js = build_hook_settings("http://127.0.0.1:8000", "tok", 1234, hook_script="/x/hook.py", python_bin="/py")
    obj = json.loads(js)
    hook = obj["hooks"]["PreToolUse"][0]
    assert hook["matcher"] == "*"
    cmd = hook["hooks"][0]
    assert cmd["timeout"] == 1234
    assert "/py /x/hook.py --url http://127.0.0.1:8000 --token tok" == cmd["command"]


def test_build_argv_adds_settings_only_when_present():
    base = dict(session_id="s1", project_path=PROJECT, model="haiku", permission_mode="default", initial_prompt="x")
    assert "--settings" not in build_argv(LaunchSpec(**base))
    argv = build_argv(LaunchSpec(**base, settings_json='{"hooks":{}}'))
    assert "--settings" in argv and '{"hooks":{}}' in argv


def test_hook_response_contract():
    allow = DecisionOutcome(behavior="allow").to_hook_response()["hookSpecificOutput"]
    assert allow["permissionDecision"] == "allow"
    deny = DecisionOutcome(behavior="deny", reason="weil").to_hook_response()["hookSpecificOutput"]
    assert deny["permissionDecision"] == "deny" and deny["permissionDecisionReason"] == "weil"


# --- Manager: blockierender Freigabe-Flow ----------------------------------

def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


@pytest.mark.asyncio
async def test_read_tool_auto_allows_without_card():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hallo", model="haiku")
    out = await mgr.request_decision(rt.state.session_id, "tu1", "Read", {"file_path": "a.py"})
    assert out.behavior == "allow" and out.auto is True
    assert rt.pending == {} and rt.state.status != AWAITING_APPROVAL


@pytest.mark.asyncio
async def test_write_tool_opens_card_and_approve_unblocks():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hallo", model="haiku")
    rt._last_assistant_text = "Ich räume auf."  # „Warum"-Quelle

    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "rm -rf x"})
    )
    await asyncio.sleep(0)  # Card entstehen lassen
    assert rt.state.status == AWAITING_APPROVAL
    card = rt.pending["tu1"]
    assert card.tool_name == "Bash" and card.state == OPEN
    assert card.rationale == "Ich räume auf."
    assert card.context["project_path"] == PROJECT

    mgr.resolve_decision(rt.state.session_id, "tu1", approve=True)
    out = await task
    assert out.behavior == "allow"
    assert rt.pending == {} and rt.state.status == RUNNING


@pytest.mark.asyncio
async def test_deny_with_comment_returns_reason():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "rm -rf /"})
    )
    await asyncio.sleep(0)
    mgr.resolve_decision(rt.state.session_id, "tu1", approve=False, comment="Nutze git rm")
    out = await task
    assert out.behavior == "deny" and out.reason == "Nutze git rm"
    assert "tu1" not in rt.pending  # aufgelöste Card verlässt die offene Liste


@pytest.mark.asyncio
async def test_multiple_cards_resolved_independently():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    t1 = asyncio.create_task(mgr.request_decision(rt.state.session_id, "a", "Bash", {"command": "x"}))
    t2 = asyncio.create_task(mgr.request_decision(rt.state.session_id, "b", "Write", {"file_path": "f", "content": "c"}))
    await asyncio.sleep(0)
    assert len(rt.pending) == 2 and rt.state.status == AWAITING_APPROVAL
    mgr.resolve_decision(rt.state.session_id, "a", approve=True)
    out1 = await t1
    # Eine Card noch offen → bleibt awaiting_approval.
    assert out1.behavior == "allow" and rt.state.status == AWAITING_APPROVAL
    mgr.resolve_decision(rt.state.session_id, "b", approve=False)
    out2 = await t2
    assert out2.behavior == "deny" and rt.state.status == RUNNING


@pytest.mark.asyncio
async def test_stop_marks_open_cards_obsolete():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    task = asyncio.create_task(mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "x"}))
    await asyncio.sleep(0)
    card = rt.pending["tu1"]
    await mgr.stop(rt.state.session_id)
    out = await task
    assert out.behavior == "deny"           # wartender Hook wird entsperrt (deny)
    assert card.state == OBSOLETE
    assert rt.pending == {}


@pytest.mark.asyncio
async def test_double_resolve_raises():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    task = asyncio.create_task(mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "x"}))
    await asyncio.sleep(0)
    mgr.resolve_decision(rt.state.session_id, "tu1", approve=True)
    await task
    with pytest.raises(KeyError):
        mgr.resolve_decision(rt.state.session_id, "tu1", approve=True)


# --- REST-Vertrag -----------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


def _create(client: TestClient) -> str:
    r = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "Hi", "model": "haiku"})
    return r.json()["session_id"]


def test_session_read_has_pending_decisions_field(client: TestClient):
    sid = _create(client)
    data = client.get(f"/sessions/{sid}").json()
    assert data["pending_decisions"] == []


def test_ws_initial_snapshot_carries_pending_decisions(client: TestClient):
    """Der erste WS-Snapshot muss pending_decisions enthalten (sonst rendert die
    Detailseite eine bereits offene Card nicht — per Screenshot gefunden)."""
    sid = _create(client)
    with client.websocket_connect(f"/sessions/{sid}/stream") as ws:
        msg = ws.receive_json()
        assert msg["kind"] == "state"
        assert "pending_decisions" in msg


def test_resolve_unknown_session_404(client: TestClient):
    r = client.post("/sessions/nope/decisions/x", json={"decision": "approve"})
    assert r.status_code == 404


def test_resolve_unknown_decision_404(client: TestClient):
    sid = _create(client)
    r = client.post(f"/sessions/{sid}/decisions/ghost", json={"decision": "approve"})
    assert r.status_code == 404


def test_resolve_invalid_decision_422(client: TestClient):
    sid = _create(client)
    r = client.post(f"/sessions/{sid}/decisions/x", json={"decision": "maybe"})
    assert r.status_code == 422


def test_internal_permission_wrong_token_403(client: TestClient):
    sid = _create(client)
    r = client.post(
        "/internal/permission",
        json={"session_id": sid, "tool_name": "Read", "tool_input": {}, "tool_use_id": "t"},
        headers={"X-Jupiter-Hook-Token": "falsch"},
    )
    assert r.status_code == 403


def test_internal_permission_read_tool_auto_allows(client: TestClient):
    sid = _create(client)
    r = client.post(
        "/internal/permission",
        json={"session_id": sid, "tool_name": "Read", "tool_input": {"file_path": "a"}, "tool_use_id": "t"},
        headers={"X-Jupiter-Hook-Token": settings.hook_token},
    )
    assert r.json()["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_internal_permission_unknown_session_denies(client: TestClient):
    r = client.post(
        "/internal/permission",
        json={"session_id": "geist", "tool_name": "Bash", "tool_input": {}, "tool_use_id": "t"},
        headers={"X-Jupiter-Hook-Token": settings.hook_token},
    )
    assert r.json()["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.asyncio
async def test_end_to_end_hook_blocks_until_resolved():
    """Hook-POST blockiert → Card im Board → REST-Freigabe entsperrt → allow."""
    app = create_app(driver_factory=lambda: FakeDriver())
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        sid = (await ac.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "Hi", "model": "haiku"})).json()["session_id"]

        hook = asyncio.create_task(
            ac.post(
                "/internal/permission",
                json={"session_id": sid, "tool_name": "Bash", "tool_input": {"command": "rm -rf x"}, "tool_use_id": "tu1"},
                headers={"X-Jupiter-Hook-Token": settings.hook_token},
            )
        )

        # Warten bis die Card im Board erscheint.
        lst = []
        for _ in range(100):
            await asyncio.sleep(0.01)
            lst = (await ac.get("/sessions")).json()
            if lst and lst[0]["pending_decisions"]:
                break
        assert lst[0]["status"] == "awaiting_approval"
        card = lst[0]["pending_decisions"][0]
        assert card["tool_name"] == "Bash" and "rm -rf x" in card["excerpt"]

        res = await ac.post(f"/sessions/{sid}/decisions/{card['decision_id']}", json={"decision": "approve"})
        assert res.status_code == 202

        hook_resp = await hook
        assert hook_resp.json()["hookSpecificOutput"]["permissionDecision"] == "allow"
        # Board zeigt die Card nicht mehr.
        assert (await ac.get(f"/sessions/{sid}")).json()["pending_decisions"] == []
