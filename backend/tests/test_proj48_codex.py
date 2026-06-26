"""PROJ-48 — OpenAI Codex CLI als Jupiter-Engine (generic_cli + codex-Adapter).

Deckt die Akzeptanzkriterien ab:
- codex-Adapter: verschachteltes Codex-JSONL → Jupiter-StreamEvents (Live-Text, Turn-Ende
  inkl. echter Usage, thread_id→resume_token, unbekannte Events defensiv ignoriert).
- Usage-Mapping (Reasoning in die Output-Last, cached separat, kein Doppelzählen) — gegen
  ein **real verifiziertes** Codex-Sample (codex-cli 0.142.2).
- Multi-Turn via Resume: Folge-Turn spawnt einen neuen Prozess mit `resume <thread_id>`;
  Kontext-Erhalt nachgewiesen; Turn-Ende → „wartet" statt „done" (kein closed).
- Registrierung: codex in der Engine-Registry (adapter codex, resume_argv_template).
- Keine Regression: nicht-resumefähige oneshot-CLIs (hermes/ollama) emittieren weiter closed.
"""
from __future__ import annotations

import json
import sys

import pytest

from app.engine.adapters import (
    VALID_ADAPTERS,
    codex_parse_line,
    get_adapter,
)
from app.engine.base import LaunchSpec
from app.engine.events import extract_text, extract_usage
from app.engine.generic_cli_driver import GenericCliDriver, build_generic_argv
from app.engine.registry import EngineProfile, EngineRegistry

# Real am Live-System aufgezeichnet (codex-cli 0.142.2) — nicht erfinden, das ist der Vertrag.
REAL_SAMPLE = [
    '{"type":"thread.started","thread_id":"019f054d-e588-7963-851a-fdf8b2eba6b4"}',
    '{"type":"turn.started"}',
    '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hallo"}}',
    '{"type":"turn.completed","usage":{"input_tokens":11418,"cached_input_tokens":9600,'
    '"output_tokens":68,"reasoning_output_tokens":59}}',
]


def _collector():
    events: list = []

    async def on_event(e):
        events.append(e)

    return events, on_event


# ===========================================================================
# Adapter-Mapping
# ===========================================================================

def test_codex_adapter_registered():
    assert "codex" in VALID_ADAPTERS
    assert get_adapter("codex") is codex_parse_line


def test_thread_started_becomes_resume_token_not_visible():
    ev = codex_parse_line(REAL_SAMPLE[0])
    assert ev is not None and ev.type == "system" and ev.subtype == "resume_token"
    assert ev.raw["resume_token"] == "019f054d-e588-7963-851a-fdf8b2eba6b4"
    # kein Anzeige-Event (kein assistant/result) → Treiber fängt es ab.
    assert extract_text(ev) is None


def test_turn_started_and_unknown_ignored():
    assert codex_parse_line(REAL_SAMPLE[1]) is None  # turn.started
    assert codex_parse_line('{"type":"völlig.unbekannt","x":1}') is None
    assert codex_parse_line("kein json") is None
    assert codex_parse_line("") is None


def test_agent_message_becomes_visible_assistant_text():
    ev = codex_parse_line(REAL_SAMPLE[2])
    assert ev is not None and ev.type == "assistant"
    assert extract_text(ev) == "Hallo"


def test_turn_completed_maps_usage_claude_style():
    ev = codex_parse_line(REAL_SAMPLE[3])
    assert ev is not None and ev.type == "result" and ev.subtype == "success"
    assert ev.raw.get("context_is_per_turn") is True
    assert ev.raw.get("is_error") is False

    usage = extract_usage(ev)
    assert usage is not None
    # input - cached (nicht-gecachter neuer Prompt), Cache separat (analog Claude):
    assert usage.input_tokens == 11418 - 9600       # 1818
    assert usage.cache_read_input_tokens == 9600
    # Reasoning zählt zur Output-Last:
    assert usage.output_tokens == 68 + 59           # 127
    # Abgerechnete Tokens konsistent zur Claude-Engine (input + output):
    assert usage.billed_tokens == 1818 + 127        # 1945
    # Kontext-Füllstand = echter Prompt-Umfang, KEIN Doppelzählen des Cache:
    assert usage.context_used_tokens == 11418


def test_turn_completed_without_usage_is_safe():
    ev = codex_parse_line('{"type":"turn.completed"}')
    assert ev is not None and ev.type == "result"
    usage = extract_usage(ev)
    assert usage is not None and usage.billed_tokens == 0


def test_non_agent_item_is_ignored():
    # item.completed ohne Text (z. B. reine Tool-/Reasoning-Items) → kein Anzeige-Event.
    assert codex_parse_line('{"type":"item.completed","item":{"type":"reasoning"}}') is None


# ===========================================================================
# argv-Bau (Resume-Pfad)
# ===========================================================================

def _codex_profile() -> EngineProfile:
    return EngineProfile(
        key="codex",
        label="OpenAI Codex",
        driver="generic_cli",
        bin="/home/dev/.local/bin/codex",
        argv_template=["exec", "-m", "{model}", "-s", "workspace-write", "--json", "-"],
        resume_argv_template=[
            "exec", "-m", "{model}", "-s", "workspace-write", "--json", "resume", "{resume_id}", "-"
        ],
        adapter="codex",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )


def test_build_argv_initial_and_resume():
    prof = _codex_profile()
    spec = LaunchSpec(
        session_id="s1", project_path="/p", model="gpt-5.5",
        permission_mode="default", initial_prompt="hi",
    )
    initial = build_generic_argv(prof, spec)
    assert initial == [
        "/home/dev/.local/bin/codex", "exec", "-m", "gpt-5.5",
        "-s", "workspace-write", "--json", "-",
    ]
    resumed = build_generic_argv(prof, spec, resume=True, resume_id="TID-9")
    assert resumed == [
        "/home/dev/.local/bin/codex", "exec", "-m", "gpt-5.5",
        "-s", "workspace-write", "--json", "resume", "TID-9", "-",
    ]


# ===========================================================================
# Registry
# ===========================================================================

CODEX_YAML = """
engines:
  - key: codex
    label: "OpenAI Codex"
    kind: engine
    driver: generic_cli
    bin: /home/dev/.local/bin/codex
    argv_template: ["exec", "-m", "{model}", "-s", "workspace-write", "--json", "-"]
    resume_argv_template: ["exec", "-m", "{model}", "-s", "workspace-write", "--json", "resume", "{resume_id}", "-"]
    adapter: codex
    prompt_via: stdin
    input_format: text
    oneshot: true
    models: [gpt-5.5]
    default_model: gpt-5.5
    capabilities: [usage, resume, multi_turn]
"""


def test_registry_loads_codex(tmp_path):
    p = tmp_path / "engines.yaml"
    p.write_text(CODEX_YAML, encoding="utf-8")
    reg = EngineRegistry(str(p))
    prof = reg.get("codex")
    assert prof is not None
    assert prof.adapter == "codex"
    assert prof.oneshot is True
    assert prof.default_model == "gpt-5.5"
    assert "resume" in prof.capabilities
    assert prof.resume_argv_template[-3:] == ["resume", "{resume_id}", "-"]
    # KEIN auth_env (Subscription-Auth über geerbtes HOME).
    assert prof.auth_env is None


# ===========================================================================
# Treiber-Integration: Multi-Turn-Resume gegen eine Fake-Codex-CLI
# ===========================================================================

# Eine winzige Fake-„codex"-CLI: spricht Codex-JSONL, erkennt `resume <id>` und echot
# Prompt + empfangene resume_id zurück → der Test kann den Kontext-Übergang nachweisen.
FAKE_CODEX = r'''
import sys, json
args = sys.argv[1:]
prompt = sys.stdin.read().strip()
if "resume" in args:
    i = args.index("resume")
    rid = args[i + 1] if i + 1 < len(args) else ""
    print(json.dumps({"type": "thread.started", "thread_id": rid}))
    print(json.dumps({"type": "turn.started"}))
    print(json.dumps({"type": "item.completed",
                      "item": {"type": "agent_message", "text": "resumed:%s:%s" % (prompt, rid)}}))
    print(json.dumps({"type": "turn.completed",
                      "usage": {"input_tokens": 200, "cached_input_tokens": 50,
                                "output_tokens": 10, "reasoning_output_tokens": 5}}))
else:
    print(json.dumps({"type": "thread.started", "thread_id": "TID-123"}))
    print(json.dumps({"type": "turn.started"}))
    print(json.dumps({"type": "item.completed",
                      "item": {"type": "agent_message", "text": "hi:%s" % prompt}}))
    print(json.dumps({"type": "turn.completed",
                      "usage": {"input_tokens": 100, "cached_input_tokens": 20,
                                "output_tokens": 5, "reasoning_output_tokens": 0}}))
'''


def _fake_profile(tmp_path, *, resumable: bool) -> EngineProfile:
    script = tmp_path / "fake_codex.py"
    script.write_text(FAKE_CODEX, encoding="utf-8")
    prof = EngineProfile(
        key="codex",
        label="Fake Codex",
        driver="generic_cli",
        bin=sys.executable,  # python führt das Skript aus → kein Exec-Bit nötig
        argv_template=[str(script), "exec", "--json", "-"],
        adapter="codex",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )
    if resumable:
        prof.resume_argv_template = [str(script), "exec", "--json", "resume", "{resume_id}", "-"]
    return prof


def _texts(events) -> list[str]:
    return [t for e in events if e.type == "assistant" and (t := extract_text(e))]


def _kinds(events) -> list[tuple[str, str | None]]:
    return [(e.type, e.subtype) for e in events]


@pytest.mark.asyncio
async def test_codex_multi_turn_resume_keeps_context(tmp_path):
    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    assert drv.supports_self_resume is True
    events, on = _collector()

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="gpt-5.5",
        permission_mode="default", initial_prompt="erste Frage",
    )
    await drv.start(spec, on)
    await drv._reader_task  # Turn 1 fertig

    # Live-Text sichtbar, Turn-Ende vorhanden — aber KEIN closed (Session bleibt fortsetzbar).
    assert "hi:erste Frage" in _texts(events)
    assert ("result", "success") in _kinds(events)
    assert ("system", "closed") not in _kinds(events)
    assert drv.is_alive is False  # oneshot: Prozess ist nach dem Turn weg
    # thread_id aus thread.started gemerkt (resume_token), nicht als Anzeige-Event geleakt.
    assert drv._resume_id == "TID-123"
    assert ("system", "resume_token") not in _kinds(events)

    # Folge-Turn: re-spawnt mit `resume <thread_id>` → die Fake-CLI echot die resume_id zurück.
    events.clear()
    await drv.send_input("zweite Frage")
    await drv._reader_task  # Turn 2 fertig

    assert "resumed:zweite Frage:TID-123" in _texts(events)  # Kontext (thread_id) erhalten
    assert ("result", "success") in _kinds(events)
    assert ("system", "closed") not in _kinds(events)


@pytest.mark.asyncio
async def test_non_resumable_oneshot_still_closes(tmp_path):
    # Regression: ohne resume_argv_template (wie hermes/ollama) endet ein oneshot-Turn
    # weiterhin mit closed → die Session geht regulär nach „done".
    prof = _fake_profile(tmp_path, resumable=False)
    drv = GenericCliDriver(prof)
    assert drv.supports_self_resume is False
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="x",
        permission_mode="default", initial_prompt="frage",
    )
    await drv.start(spec, on)
    await drv._reader_task
    assert ("system", "closed") in _kinds(events)


# Fake-„codex", das KEIN turn.completed liefert (Prozess endet sauber, aber ohne Turn-Ende).
FAKE_CODEX_NO_RESULT = r'''
import sys, json
sys.stdin.read()
print(json.dumps({"type": "thread.started", "thread_id": "TID-X"}))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "halb"}}))
'''


@pytest.mark.asyncio
async def test_manager_integration_status_and_usage_through_handle_event(tmp_path):
    """Manager-Ebene (echter Treiber + handle_event): nach turn.completed steht der Status
    auf WAITING (nicht DONE — Race-Sicherheit), Usage akkumuliert, Kontext-Gauge gefüllt,
    Live-Text im Transkript. Folge-Turn (Resume) erhält den Kontext und bleibt WAITING."""
    from app.engine.manager import DONE, RUNNING, WAITING, SessionRuntime, SessionState

    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    done_calls: list = []
    state = SessionState(
        session_id="s1", owner="dev", project_path=str(tmp_path),
        model="gpt-5.5", permission_mode="default",
    )
    state.engine = "codex"
    runtime = SessionRuntime(state, drv, on_done=lambda r: done_calls.append(r))

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="gpt-5.5",
        permission_mode="default", initial_prompt="erste",
    )
    await drv.start(spec, runtime.handle_event)
    await drv._reader_task

    # Turn-Ende → wartet (NICHT done); kein Vault-Log (on_done) ausgelöst.
    assert state.status == WAITING, f"erwartet WAITING, war {state.status}"
    assert done_calls == []
    # Live-Text im Transkript.
    assert any(e.text == "hi:erste" for e in runtime.transcript if e.kind == "text")
    # Echte Usage: tokens_used > 0, Kontext-Gauge gefüllt (per-turn-Usage).
    assert state.tokens_used > 0
    assert state.context_known is True
    assert state.context_fill_pct > 0
    assert state.cache_read_tokens == 20  # cached_input aus Turn 1
    tokens_after_t1 = state.tokens_used

    # Folge-Turn wie der Manager: supports_self_resume → kein _resume, Treiber re-spawnt selbst.
    assert drv.supports_self_resume is True and drv.is_alive is False
    state.status = RUNNING
    await drv.send_input("zweite")
    await drv._reader_task

    assert any(e.text == "resumed:zweite:TID-123" for e in runtime.transcript if e.kind == "text")
    assert state.status == WAITING
    assert state.tokens_used > tokens_after_t1  # Usage akkumuliert über Turns
    assert done_calls == []  # weiterhin kein „done"


@pytest.mark.asyncio
async def test_clean_exit_without_turn_end_falls_back_to_done(tmp_path):
    """Sicherheitskante: endet ein resumefähiger oneshot-Prozess sauber (rc 0), OHNE ein
    Turn-Ende geliefert zu haben, darf die Session nicht ewig „arbeitet" bleiben → closed
    (→ DONE), kein Steckenbleiben."""
    from app.engine.manager import DONE, RUNNING, SessionRuntime, SessionState

    script = tmp_path / "fake_codex_noresult.py"
    script.write_text(FAKE_CODEX_NO_RESULT, encoding="utf-8")
    prof = EngineProfile(
        key="codex", label="Fake", driver="generic_cli", bin=sys.executable,
        argv_template=[str(script), "exec", "--json", "-"],
        resume_argv_template=[str(script), "exec", "--json", "resume", "{resume_id}", "-"],
        adapter="codex", prompt_via="stdin", input_format="text", oneshot=True,
    )
    drv = GenericCliDriver(prof)
    state = SessionState(
        session_id="s1", owner="dev", project_path=str(tmp_path),
        model="x", permission_mode="default",
    )
    runtime = SessionRuntime(state, drv)
    state.status = RUNNING
    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="x",
        permission_mode="default", initial_prompt="frage",
    )
    await drv.start(spec, runtime.handle_event)
    await drv._reader_task
    assert state.status == DONE


# ===========================================================================
# QA-Fixes: Liveness zwischen Turns (Fix 1/2) + Sandbox-Badge (Fix 3)
# ===========================================================================

class _StubDriver:
    """Minimaler Treiber-Stub: steuert is_alive + supports_self_resume für derive_liveness."""

    def __init__(self, *, alive: bool, self_resume: bool) -> None:
        self._alive = alive
        self._self_resume = self_resume

    @property
    def is_alive(self) -> bool:
        return self._alive

    @property
    def supports_self_resume(self) -> bool:
        return self._self_resume

    @property
    def pid(self):
        return None


def _runtime_with(driver, status):
    from app.engine.manager import SessionRuntime, SessionState
    state = SessionState(
        session_id="s", owner="dev", project_path="/tmp", model="gpt-5.5", permission_mode="default"
    )
    rt = SessionRuntime(state, driver)
    state.status = status
    return rt


def test_liveness_resumable_between_turns_is_active_not_dead():
    """Fix 1/2: oneshot-CLI mit Resume, WAITING + toter Prozess → aktiv (nicht tot).
    So zeigt das Badge nicht „tot" und reanimate() lehnt die gesunde Session ab."""
    from app.engine import liveness
    from app.engine.manager import WAITING
    rt = _runtime_with(_StubDriver(alive=False, self_resume=True), WAITING)
    assert rt.derive_liveness() == liveness.LIVENESS_ACTIVE


def test_liveness_non_resumable_dead_process_still_dead():
    """Gegenprobe: ohne Self-Resume (hermes/ollama/claude) bleibt ein toter Prozess tot."""
    from app.engine import liveness
    from app.engine.manager import WAITING
    rt = _runtime_with(_StubDriver(alive=False, self_resume=False), WAITING)
    assert rt.derive_liveness() == liveness.LIVENESS_DEAD


def test_registry_exposes_sandbox_badge(tmp_path):
    """Fix 3: GET /engines (to_read) zeigt die Sandbox-Policy aus dem argv als Badge."""
    from app.engine.registry import EngineRegistry
    p = tmp_path / "engines.yaml"
    p.write_text(CODEX_YAML, encoding="utf-8")
    prof = EngineRegistry(str(p)).get("codex")
    assert prof.sandbox == "workspace-write"
    assert prof.to_read()["sandbox"] == "workspace-write"


def test_sandbox_from_argv_helper_edge_cases():
    from app.engine.registry import _sandbox_from_argv
    assert _sandbox_from_argv(["exec", "-s", "workspace-write", "--json"]) == "workspace-write"
    assert _sandbox_from_argv(["exec", "--sandbox", "read-only"]) == "read-only"
    assert _sandbox_from_argv(["exec", "--json"]) is None          # kein Flag
    assert _sandbox_from_argv(["exec", "-s"]) is None               # Flag ohne Wert
    assert _sandbox_from_argv(["-s", "{model}"]) is None            # Platzhalter ≠ Policy


@pytest.mark.asyncio
async def test_resume_without_id_raises_clear_error(tmp_path):
    # Schutz: Resume-Template braucht eine resume_id; fehlt sie, klare deutsche Meldung
    # (statt eines kaputten `resume <leer>`-Aufrufs).
    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    drv._spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="gpt-5.5",
        permission_mode="default", initial_prompt="",
    )
    # kein Prozess gestartet, keine resume_id empfangen
    with pytest.raises(RuntimeError, match="Resume-ID"):
        await drv.send_input("frage")
