"""PROJ-23 — Cross-Agent-Review / Challenge (engine-übergreifend).

Deckt die Acceptance Criteria ab:
- Challenge startet eine Reviewer-Session über die Dispatch-/Treiber-Schicht mit dem
  Artefakt als Pointer-Prüfobjekt.
- Reviewer nutzt standardmäßig eine ANDERE Engine; ist keine andere verfügbar, läuft die
  Challenge mit Warnhinweis (``same_engine``) auf derselben Engine.
- Review-Ergebnis strukturiert (Befund + Schweregrad + Fundstelle + Gegenvorschlag) als
  ``review_finding``-Card + Vault-Notiz.
- Pro Befund übernehmen/verwerfen/mit Kommentar zurück; übernehmen/zurück reichen an die
  Autor-Session.
- Jeder Review nennt Autor- und Reviewer-Engine/-Modell.
- Edge Cases: nur eine Engine, keine Befunde, Rundenlimit, Versions-Drift.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.challenge import (
    MAX_ROUNDS,
    ChallengeService,
    Finding,
)
from app.engine.base import EngineDriver, EventHandler, LaunchSpec
from app.engine.events import StreamEvent
from app.engine.manager import SessionManager
from app.engine.registry import CLAUDE_KEY, _builtin_claude, engine_registry
from app.engine.vault import VaultService
from app.main import create_app

PROJECT = "/home/dev/projects/jupiter"

# Reviewer-Output, den der Fake-Treiber als „Assistenten-Antwort" emittiert. Tests
# überschreiben ihn über das gemeinsame STATE-Dict (eine Factory bedient Autor + Reviewer).
_DEFAULT_FINDINGS = (
    "Hier meine Befunde:\n"
    "```json\n"
    '{"findings": ['
    '{"severity": "hoch", "location": "Abschnitt C", "title": "Fehlende RLS", '
    '"suggestion": "RLS-Policy ergaenzen"},'
    '{"severity": "QUATSCH", "location": "Abschnitt A", "title": "Unklarer Vertrag", '
    '"suggestion": "Feldtypen praezisieren"}'
    "]}\n"
    "```\n"
)


class _ChallengeFake(EngineDriver):
    """Wie FakeDriver, aber die Reviewer-Session (Prompt enthält „Cross-Agent-Reviewer")
    antwortet mit einem konfigurierbaren Befund-JSON statt mit einem Echo."""

    def __init__(self, state: dict) -> None:
        self._on: EventHandler | None = None
        self._alive = True
        self._paused = False
        self._spec: LaunchSpec | None = None
        self.sent: list[str] = []
        self._state = state

    @property
    def is_alive(self) -> bool:
        return self._alive

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._on = on_event
        self._spec = spec
        await on_event(
            StreamEvent("system", "init", {
                "session_id": spec.session_id,
                "model": "claude-haiku-4-5-20251001",
                "permissionMode": spec.permission_mode,
                "apiKeySource": "none",
            })
        )
        prompt = spec.initial_prompt or ""
        if "Cross-Agent-Reviewer" in prompt:
            await self._respond(self._state["reviewer_output"])
        elif prompt:
            await self._respond(f"Antwort auf: {prompt}")

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert.")
        if not self._alive:
            raise RuntimeError("Session läuft nicht.")
        self.sent.append(text)
        await self._respond(f"Echo: {text}")

    async def pause(self) -> None:
        self._paused = True

    async def stop(self) -> None:
        self._alive = False
        if self._on is not None:
            await self._on(StreamEvent("system", "closed", {}))

    async def _respond(self, text: str) -> None:
        usage = {"input_tokens": 100, "output_tokens": 10,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        await self._on(StreamEvent(
            "assistant", None,
            {"message": {"content": [{"type": "text", "text": text}], "usage": usage}},
        ))
        await self._on(StreamEvent("result", "success", {
            "is_error": False, "result": text, "num_turns": 1, "total_cost_usd": 0.01,
            "usage": usage,
            "modelUsage": {"claude-haiku-4-5-20251001": {"contextWindow": 200000}},
            "session_id": self._spec.session_id,
        }))


@pytest.fixture(autouse=True)
def _claude_only(monkeypatch):
    """Deterministisch: nur die eingebaute Claude-Engine sichtbar (der VPS hat reale
    Engines in engines.yaml → Reviewer würde sonst an einen echten Nicht-Claude-Treiber
    dispatchen). So fährt der Reviewer den Fake-Treiber; same_engine=True ist erwartbar.
    Den Cross-Engine-Fall deckt ``test_pick_reviewer_engine_prefers_other`` ab."""
    monkeypatch.setattr(engine_registry, "_reload_if_changed", lambda: None)
    monkeypatch.setattr(engine_registry, "_profiles", {CLAUDE_KEY: _builtin_claude()})


@pytest.fixture()
def state() -> dict:
    return {"reviewer_output": _DEFAULT_FINDINGS}


@pytest.fixture()
def client(state) -> TestClient:
    app = create_app(driver_factory=lambda: _ChallengeFake(state))
    return TestClient(app)


def _author(client: TestClient) -> str:
    return client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "baue X", "model": "haiku"},
    ).json()["session_id"]


# --- Parser (reine Logik) --------------------------------------------------

def test_parse_findings_block():
    findings = ChallengeService._parse_findings(_DEFAULT_FINDINGS)
    assert len(findings) == 2
    assert findings[0].severity == "hoch"
    assert findings[0].location == "Abschnitt C"
    # ungültiger Schweregrad → Default „mittel".
    assert findings[1].severity == "mittel"


def test_parse_findings_no_block_returns_none():
    assert ChallengeService._parse_findings("nur Fließtext, kein JSON") is None
    assert ChallengeService._parse_findings("") is None


def test_parse_findings_empty_list():
    assert ChallengeService._parse_findings('```json\n{"findings": []}\n```') == []


# --- Engine-Auswahl --------------------------------------------------------

def test_pick_reviewer_engine_same_when_only_one(monkeypatch):
    """Nur Claude verfügbar → gleiche Engine + same_engine=True (kein Block)."""
    svc = ChallengeService(SessionManager(driver_factory=lambda: _ChallengeFake({})), VaultService())
    eng, same = svc.pick_reviewer_engine("claude", None)
    assert eng == "claude" and same is True


def test_pick_reviewer_engine_prefers_other(monkeypatch):
    """Gibt es eine andere verfügbare Session-Engine, wird sie bevorzugt (echte Diversität)."""
    class _Prof:
        def __init__(self, key):
            self.key = key
            self.is_session_engine = True
        def availability(self):
            return True, None
    class _Reg:
        def all(self):
            return [_Prof("claude"), _Prof("codex")]
        def get(self, k):
            return _Prof(k)
    monkeypatch.setattr("app.engine.challenge.engine_registry", _Reg())
    svc = ChallengeService(SessionManager(driver_factory=lambda: _ChallengeFake({})), VaultService())
    eng, same = svc.pick_reviewer_engine("claude", None)
    assert eng == "codex" and same is False


# --- Challenge starten -----------------------------------------------------

def test_challenge_starts_reviewer_session(client: TestClient):
    author = _author(client)
    r = client.post(f"/sessions/{author}/challenge",
                    json={"artifact_pointer": "Agentic OS/Jupiter/Knowledge/foo.md"})
    assert r.status_code == 201, r.text
    review = r.json()
    assert review["author_session_id"] == author
    assert review["round"] == 1
    # Attribution: Autor- UND Reviewer-Engine/-Modell genannt (AC).
    assert review["author_engine"] == "claude" and review["author_model"]
    assert review["reviewer_engine"] == "claude" and review["reviewer_model"]
    assert review["same_engine"] is True  # nur Claude verfügbar
    # Reviewer-Session existiert mit role=reviewer.
    sessions = {s["session_id"]: s for s in client.get("/sessions").json()}
    assert sessions[review["review_id"]]["role"] == "reviewer"


def test_challenge_author_not_found_404(client: TestClient):
    r = client.post("/sessions/nope/challenge", json={"artifact_pointer": "x.md"})
    assert r.status_code == 404


def test_reviews_collect_structured_findings(client: TestClient):
    author = _author(client)
    review_id = client.post(
        f"/sessions/{author}/challenge", json={"artifact_pointer": "x.md"}
    ).json()["review_id"]
    reviews = client.get(f"/sessions/{author}/reviews").json()
    assert len(reviews) == 1
    rv = reviews[0]
    assert rv["collected"] is True and rv["incomplete"] is False
    findings = rv["findings"]
    assert len(findings) == 2
    f0 = findings[0]
    assert {"severity", "location", "title", "suggestion"} <= set(f0)
    assert f0["severity"] == "hoch"
    # Befunde erscheinen auch als nicht-blockierende Cards auf der Reviewer-Session.
    detail = client.get(f"/sessions/{review_id}").json()
    types = {c["card_type"] for c in detail["pending_decisions"]}
    assert "review_finding" in types


def test_resolve_uebernehmen_routes_to_author(client: TestClient):
    author = _author(client)
    review_id = client.post(
        f"/sessions/{author}/challenge", json={"artifact_pointer": "x.md"}
    ).json()["review_id"]
    fid = client.get(f"/sessions/{author}/reviews").json()[0]["findings"][0]["finding_id"]
    r = client.post(f"/reviews/{review_id}/findings/{fid}", json={"action": "übernehmen"})
    assert r.status_code == 200, r.text
    assert r.json()["resolution"] == "übernehmen"
    # Der Gegenvorschlag ist als Eingabe an die Autor-Session gereist.
    author_driver = client.app.state.manager.get(author).driver
    assert any("RLS-Policy ergaenzen" in t for t in author_driver.sent)
    # Befund-Card auf der Reviewer-Session ist entfernt.
    detail = client.get(f"/sessions/{review_id}").json()
    assert all(c["decision_id"] != fid for c in detail["pending_decisions"])


def test_resolve_verwerfen_does_not_touch_author(client: TestClient):
    author = _author(client)
    review_id = client.post(
        f"/sessions/{author}/challenge", json={"artifact_pointer": "x.md"}
    ).json()["review_id"]
    fid = client.get(f"/sessions/{author}/reviews").json()[0]["findings"][0]["finding_id"]
    r = client.post(f"/reviews/{review_id}/findings/{fid}", json={"action": "verwerfen"})
    assert r.status_code == 200 and r.json()["resolution"] == "verwerfen"
    author_driver = client.app.state.manager.get(author).driver
    assert author_driver.sent == []  # Artefakt/Autor bleibt unberührt


def test_resolve_zurueck_sends_comment(client: TestClient):
    author = _author(client)
    review_id = client.post(
        f"/sessions/{author}/challenge", json={"artifact_pointer": "x.md"}
    ).json()["review_id"]
    fid = client.get(f"/sessions/{author}/reviews").json()[0]["findings"][0]["finding_id"]
    r = client.post(f"/reviews/{review_id}/findings/{fid}",
                    json={"action": "zurück", "comment": "Das ist beabsichtigt, weil…"})
    assert r.status_code == 200
    author_driver = client.app.state.manager.get(author).driver
    assert any("Das ist beabsichtigt" in t for t in author_driver.sent)


def test_resolve_finding_twice_404(client: TestClient):
    author = _author(client)
    review_id = client.post(
        f"/sessions/{author}/challenge", json={"artifact_pointer": "x.md"}
    ).json()["review_id"]
    fid = client.get(f"/sessions/{author}/reviews").json()[0]["findings"][0]["finding_id"]
    client.post(f"/reviews/{review_id}/findings/{fid}", json={"action": "verwerfen"})
    again = client.post(f"/reviews/{review_id}/findings/{fid}", json={"action": "verwerfen"})
    assert again.status_code == 404


def test_no_findings_explicit_note(client: TestClient, state):
    state["reviewer_output"] = 'Alles gut.\n```json\n{"findings": []}\n```'
    author = _author(client)
    client.post(f"/sessions/{author}/challenge", json={"artifact_pointer": "x.md"})
    rv = client.get(f"/sessions/{author}/reviews").json()[0]
    assert rv["collected"] is True
    assert rv["findings"] == []  # explizit „keine Befunde", nicht stilles Verschwinden


def test_round_limit_escalates(client: TestClient):
    author = _author(client)
    for n in range(MAX_ROUNDS):
        r = client.post(f"/sessions/{author}/challenge", json={"artifact_pointer": "x.md"})
        assert r.status_code == 201
        assert r.json()["round"] == n + 1
    # Über dem Limit → 409 (an den Menschen eskalieren).
    over = client.post(f"/sessions/{author}/challenge", json={"artifact_pointer": "x.md"})
    assert over.status_code == 409
    assert "Rundenlimit" in over.json()["detail"]


def test_version_and_stale_detection(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [PROJECT])
    vault: VaultService = client.app.state.vault
    written = vault.write(type="curated", body="# Vertrag v1\nGET /x", title="art23", dated=False)
    pointer = written.path
    author = _author(client)
    review_id = client.post(
        f"/sessions/{author}/challenge", json={"artifact_pointer": pointer}
    ).json()["review_id"]
    rv = client.get(f"/reviews/{review_id}").json()
    assert rv["artifact_version"] is not None and rv["stale"] is False
    # Artefakt nach dem Review ändern → Versions-Drift erkannt.
    vault.write(type="curated", body="# Vertrag v2 geaendert", title="art23",
                dated=False, on_exists="append")
    rv2 = client.get(f"/reviews/{review_id}").json()
    assert rv2["stale"] is True


def test_finding_dataclass_roundtrip():
    f = Finding("finding-1", "hoch", "loc", "titel", "vorschlag")
    d = f.to_read()
    assert d["finding_id"] == "finding-1" and d["state"] == "open" and d["resolution"] is None
