"""PROJ-57 — OpenCode als Harness-Engine (generic_cli + opencode-Adapter).

Deckt die Akzeptanzkriterien ab:
- opencode-Adapter: OpenCodes ``--format json``-Events → Jupiter-StreamEvents
  (Live-Text, sessionID→resume_token, tool_use sichtbar, step_finish→result inkl. Usage
  UND echter USD-Kosten, unbekannte Events defensiv ignoriert).
- Usage-Mapping gegen ein **real verifiziertes** OpenCode-Sample (opencode v1.17.13):
  ``total = input + output + reasoning + cache.read`` → ``input`` enthält den Cache NICHT.
- Multi-Turn via Resume: Folge-Turn spawnt einen neuen Prozess mit ``-s <sessionID>``;
  Kontext-Erhalt nachgewiesen; Turn-Ende → „wartet" statt „done".
- Registrierung: opencode in der Engine-Registry (adapter opencode, resume_argv_template,
  kein auth_env). OpenRouter-HTTP-Direkteintrag ist abgelöst.
- Kosten: engine_shows_cost(opencode) → echte USD (Novum), fließt in state.total_cost_usd.
- PROJ-56-Auslöser (Restart · Reanimierung · _resume) über den self-resume-Pfad.
"""
from __future__ import annotations

import sys

import pytest

from app.engine.adapters import (
    VALID_ADAPTERS,
    get_adapter,
    opencode_parse_line,
)
from app.engine.base import LaunchSpec
from app.engine.events import extract_text, extract_usage
from app.engine.generic_cli_driver import GenericCliDriver, build_generic_argv
from app.engine.registry import EngineProfile, EngineRegistry
from app.engine.usage import engine_shows_cost

# Real am Live-System aufgezeichnet (opencode v1.17.13, openrouter/minimax-m3) — der Vertrag.
SID = "ses_0ce6d7aabffeu2rPx17SHg4XwP"
REAL_SAMPLE = [
    '{"type":"step_start","timestamp":1783243117069,"sessionID":"%s",'
    '"part":{"id":"prt_a","messageID":"msg_a","sessionID":"%s","type":"step-start"}}' % (SID, SID),
    '{"type":"text","timestamp":1783243117284,"sessionID":"%s",'
    '"part":{"id":"prt_b","messageID":"msg_a","sessionID":"%s","type":"text",'
    '"text":"Hallo","time":{"start":1,"end":2}}}' % (SID, SID),
    '{"type":"step_finish","timestamp":1783243117337,"sessionID":"%s",'
    '"part":{"id":"prt_c","reason":"stop","messageID":"msg_a","sessionID":"%s","type":"step-finish",'
    '"tokens":{"total":16047,"input":14102,"output":2,"reasoning":37,'
    '"cache":{"write":0,"read":1906}},"cost":0.00439176}}' % (SID, SID),
]
# Ein tool_use-Event (bash) — real aufgezeichnet.
TOOL_LINE = (
    '{"type":"tool_use","timestamp":1,"sessionID":"%s","part":{"type":"tool","tool":"bash",'
    '"callID":"call_1","state":{"status":"completed","input":{"command":"echo hi"},'
    '"output":"hi\\n","title":"echo hi"}}}' % SID
)


def _collector():
    events: list = []

    async def on_event(e):
        events.append(e)

    return events, on_event


# ===========================================================================
# Adapter-Mapping
# ===========================================================================

def test_opencode_adapter_registered():
    assert "opencode" in VALID_ADAPTERS
    assert get_adapter("opencode") is opencode_parse_line


def test_step_start_becomes_resume_token_not_visible():
    ev = opencode_parse_line(REAL_SAMPLE[0])
    assert ev is not None and ev.type == "system" and ev.subtype == "resume_token"
    assert ev.raw["resume_token"] == SID
    assert extract_text(ev) is None  # kein Anzeige-Event → Treiber fängt es ab


def test_text_becomes_visible_assistant_text():
    ev = opencode_parse_line(REAL_SAMPLE[1])
    assert ev is not None and ev.type == "assistant"
    assert extract_text(ev) == "Hallo"


def test_unknown_and_empty_ignored():
    assert opencode_parse_line('{"type":"reasoning","part":{}}') is None
    assert opencode_parse_line('{"type":"directory","x":1}') is None
    assert opencode_parse_line("kein json") is None
    assert opencode_parse_line("") is None
    # text ohne Inhalt → nichts:
    assert opencode_parse_line('{"type":"text","part":{"text":"  "}}') is None


def test_tool_use_visible_activity():
    ev = opencode_parse_line(TOOL_LINE)
    assert ev is not None and ev.type == "tool_use"
    assert ev.raw["name"] == "bash"
    assert ev.raw["input"]["command"] == "echo hi"


def test_file_tool_carries_path_for_phase_detection():
    line = (
        '{"type":"tool_use","sessionID":"%s","part":{"type":"tool","tool":"write",'
        '"state":{"status":"completed","input":{"filePath":"/p/app/x.py","content":"..."}}}}' % SID
    )
    ev = opencode_parse_line(line)
    assert ev is not None and ev.type == "tool_use"
    assert ev.raw["name"] == "Write"                 # write → Write (feature_from_path-Fallback)
    assert ev.raw["input"]["file_path"] == "/p/app/x.py"


def test_step_finish_maps_usage_and_real_cost():
    ev = opencode_parse_line(REAL_SAMPLE[2])
    assert ev is not None and ev.type == "result" and ev.subtype == "success"
    assert ev.raw.get("context_is_per_turn") is True
    assert ev.raw.get("is_error") is False
    # Echte USD-Kosten durchgereicht (Novum):
    assert ev.raw.get("total_cost_usd") == pytest.approx(0.00439176)

    usage = extract_usage(ev)
    assert usage is not None
    # input enthält den Cache NICHT (total = input+output+reasoning+cache.read):
    assert usage.input_tokens == 14102
    assert usage.cache_read_input_tokens == 1906
    assert usage.cache_creation_input_tokens == 0
    # Reasoning zählt zur Output-Last:
    assert usage.output_tokens == 2 + 37             # 39
    # Kontext-Füllstand = echter Prompt-Umfang (input + cache_read), kein Doppelzählen:
    assert usage.context_used_tokens == 14102 + 1906  # 16008
    # total aus dem Sample bestätigt die Zerlegung:
    assert 14102 + 2 + 37 + 1906 == 16047
    assert usage.total_cost_usd == pytest.approx(0.00439176)


def test_step_finish_without_tokens_is_safe():
    ev = opencode_parse_line('{"type":"step_finish","part":{"reason":"stop"}}')
    assert ev is not None and ev.type == "result"
    usage = extract_usage(ev)
    assert usage is not None and usage.billed_tokens == 0
    assert usage.total_cost_usd is None              # keine Kosten → sauber None


def test_intermediate_tool_step_still_emits_usage():
    # Zwischen-Schritt eines Tool-Turns (reason tool-calls) → ebenfalls result mit Usage,
    # damit Tokens/Kosten über den ganzen Turn akkumulieren.
    line = (
        '{"type":"step_finish","part":{"reason":"tool-calls",'
        '"tokens":{"total":100,"input":80,"output":5,"reasoning":0,"cache":{"write":0,"read":15}},'
        '"cost":0.001}}'
    )
    ev = opencode_parse_line(line)
    assert ev is not None and ev.type == "result"
    assert extract_usage(ev).billed_tokens == 80 + 5


# ===========================================================================
# Kosten-Anzeige (PROJ-19/PROJ-57)
# ===========================================================================

def test_engine_shows_cost_opencode():
    assert engine_shows_cost("opencode") is True     # echte USD (Novum)
    assert engine_shows_cost("claude") is True
    assert engine_shows_cost("codex") is False       # Subscription → „n/v"
    assert engine_shows_cost("swisscom") is False


# ===========================================================================
# argv-Bau (Resume-Pfad)
# ===========================================================================

def _opencode_profile() -> EngineProfile:
    return EngineProfile(
        key="opencode",
        label="OpenCode",
        driver="generic_cli",
        bin="/home/dev/.opencode/bin/opencode",
        argv_template=["run", "--format", "json", "-m", "{model}", "--auto"],
        resume_argv_template=["run", "--format", "json", "-s", "{resume_id}", "--auto"],
        adapter="opencode",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )


def test_build_argv_initial_and_resume():
    prof = _opencode_profile()
    spec = LaunchSpec(
        session_id="s1", project_path="/p", model="openrouter/minimax/minimax-m3",
        permission_mode="default", initial_prompt="hi",
    )
    initial = build_generic_argv(prof, spec)
    assert initial == [
        "/home/dev/.opencode/bin/opencode", "run", "--format", "json",
        "-m", "openrouter/minimax/minimax-m3", "--auto",
    ]
    resumed = build_generic_argv(prof, spec, resume=True, resume_id=SID)
    assert resumed == [
        "/home/dev/.opencode/bin/opencode", "run", "--format", "json",
        "-s", SID, "--auto",
    ]


# ===========================================================================
# Registry
# ===========================================================================

OPENCODE_YAML = """
engines:
  - key: opencode
    label: "OpenCode"
    kind: engine
    driver: generic_cli
    bin: /home/dev/.opencode/bin/opencode
    argv_template: ["run", "--format", "json", "-m", "{model}", "--auto"]
    resume_argv_template: ["run", "--format", "json", "-s", "{resume_id}", "--auto"]
    adapter: opencode
    prompt_via: stdin
    input_format: text
    oneshot: true
    models: [openrouter/z-ai/glm-5.2, openrouter/minimax/minimax-m3]
    default_model: openrouter/minimax/minimax-m3
    context_window: 128000
    capabilities: [usage, resume, multi_turn]
"""


def test_registry_loads_opencode(tmp_path):
    p = tmp_path / "engines.yaml"
    p.write_text(OPENCODE_YAML, encoding="utf-8")
    reg = EngineRegistry(str(p))
    prof = reg.get("opencode")
    assert prof is not None
    assert prof.adapter == "opencode"
    assert prof.oneshot is True
    assert prof.default_model == "openrouter/minimax/minimax-m3"
    assert "resume" in prof.capabilities
    assert prof.resume_argv_template[:5] == ["run", "--format", "json", "-s", "{resume_id}"]
    # KEIN auth_env — Auth über OpenCodes eigenen Store (geerbtes HOME).
    assert prof.auth_env is None
    # to_read()/to_settings() dürfen keinerlei Secret/argv-Leak in GET /engines geben:
    read = prof.to_read()
    assert "bin" not in read and "argv_template" not in read and "auth_env" not in read


def test_openrouter_http_entry_removed_but_swisscom_kept(tmp_path):
    """Ablösung: der rohe OpenRouter-HTTP-Eintrag ist weg; Swisscom-HTTP bleibt bestehen."""
    from pathlib import Path
    live = Path(__file__).resolve().parents[1] / "config" / "engines.yaml"
    if not live.exists():
        pytest.skip("keine Live-engines.yaml im Testlauf")
    reg = EngineRegistry(str(live))
    assert reg.get("openrouter", include_disabled=True) is None
    assert reg.get("opencode") is not None
    swisscom = reg.get("swisscom", include_disabled=True)
    assert swisscom is not None and swisscom.driver == "openai"


# ===========================================================================
# Treiber-Integration: Multi-Turn-Resume gegen eine Fake-OpenCode-CLI
# ===========================================================================

# Winzige Fake-„opencode"-CLI: spricht OpenCode-JSON, erkennt `-s <id>` und echot
# Prompt + empfangene sessionID zurück → Kontext-Übergang nachweisbar.
FAKE_OPENCODE = r'''
import sys, json
args = sys.argv[1:]
prompt = sys.stdin.read().strip()
sid = "ses_NEW"
if "-s" in args:
    i = args.index("-s")
    sid = args[i + 1] if i + 1 < len(args) else ""
    text = "resumed:%s:%s" % (prompt, sid)
else:
    text = "hi:%s" % prompt
print(json.dumps({"type": "step_start", "sessionID": sid, "part": {"type": "step-start"}}))
print(json.dumps({"type": "text", "sessionID": sid, "part": {"type": "text", "text": text}}))
print(json.dumps({"type": "step_finish", "sessionID": sid, "part": {"reason": "stop",
    "tokens": {"total": 130, "input": 100, "output": 10, "reasoning": 5, "cache": {"write": 0, "read": 15}},
    "cost": 0.002}}))
'''


def _fake_profile(tmp_path, *, resumable: bool) -> EngineProfile:
    script = tmp_path / "fake_opencode.py"
    script.write_text(FAKE_OPENCODE, encoding="utf-8")
    prof = EngineProfile(
        key="opencode",
        label="Fake OpenCode",
        driver="generic_cli",
        bin=sys.executable,
        argv_template=[str(script), "run", "--format", "json", "-m", "{model}", "--auto"],
        adapter="opencode",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )
    if resumable:
        prof.resume_argv_template = [
            str(script), "run", "--format", "json", "-s", "{resume_id}", "--auto"
        ]
    return prof


def _texts(events) -> list[str]:
    return [t for e in events if e.type == "assistant" and (t := extract_text(e))]


def _kinds(events) -> list[tuple[str, str | None]]:
    return [(e.type, e.subtype) for e in events]


@pytest.mark.asyncio
async def test_empty_chat_start_waits_until_first_input(tmp_path):
    """PROJ-34: OpenCode darf nicht ohne Nachricht gestartet werden; die erste echte
    Chat-Eingabe ist ein Frischstart und liefert erst dann die Resume-ID."""
    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s-empty", project_path=str(tmp_path), model="opencode-go/minimax-m3",
        permission_mode="default", initial_prompt="",
    )

    await drv.start(spec, on)

    assert _kinds(events) == [("system", "init"), ("system", "waiting")]
    assert drv.is_alive is False
    assert drv._reader_task is None
    assert drv._resume_id is None

    await drv.send_input("erste echte Frage")
    await drv._reader_task

    assert "hi:erste echte Frage" in _texts(events)
    assert drv._resume_id == "ses_NEW"
    assert ("result", "success") in _kinds(events)


@pytest.mark.asyncio
async def test_empty_chat_start_manager_state_is_waiting(tmp_path):
    from app.engine.manager import RUNNING, WAITING, SessionRuntime, SessionState

    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    state = SessionState(
        session_id="s-empty-state", owner="dev", project_path=str(tmp_path),
        model="opencode-go/minimax-m3", permission_mode="default", engine="opencode",
    )
    runtime = SessionRuntime(state, drv)
    spec = LaunchSpec(
        session_id=state.session_id, project_path=str(tmp_path), model=state.model,
        permission_mode="default", initial_prompt="",
    )

    await drv.start(spec, runtime.handle_event)
    assert state.status == WAITING

    await drv.send_input("erste")
    state.status = RUNNING  # entspricht SessionManager.send_input nach erfolgreichem Spawn
    await drv._reader_task
    assert state.status == WAITING


@pytest.mark.asyncio
async def test_empty_chat_start_over_tmux_creates_prompt_only_on_first_input(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tmux_data_dir", str(tmp_path / "tmuxdata"))
    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s-empty-tmux", project_path=str(tmp_path), model="opencode-go/minimax-m3",
        permission_mode="default", initial_prompt="", transport="tmux",
    )
    try:
        await drv.start(spec, on)
        assert drv._transport_obj is None

        await drv.send_input("tmux erste Frage")
        await drv._reader_task

        assert "hi:tmux erste Frage" in _texts(events)
        assert drv._transport_obj is not None
        assert list(drv._transport_obj._dir.glob("prompt-*.txt"))
    finally:
        await drv.stop()


@pytest.mark.asyncio
async def test_opencode_multi_turn_resume_keeps_context(tmp_path):
    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    assert drv.supports_self_resume is True
    events, on = _collector()

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="openrouter/minimax/minimax-m3",
        permission_mode="default", initial_prompt="erste Frage",
    )
    await drv.start(spec, on)
    await drv._reader_task

    assert "hi:erste Frage" in _texts(events)
    assert ("result", "success") in _kinds(events)
    assert ("system", "closed") not in _kinds(events)   # Session bleibt fortsetzbar
    assert drv.is_alive is False
    assert drv._resume_id == "ses_NEW"                   # sessionID gemerkt
    assert ("system", "resume_token") not in _kinds(events)  # nicht als Anzeige-Event geleakt

    events.clear()
    await drv.send_input("zweite Frage")
    await drv._reader_task
    # Kontext (sessionID) erhalten → Fake-CLI echot sie zurück:
    assert "resumed:zweite Frage:ses_NEW" in _texts(events)
    assert ("result", "success") in _kinds(events)


@pytest.mark.asyncio
async def test_manager_integration_status_usage_cost(tmp_path):
    """Manager-Ebene: nach step_finish steht der Status auf WAITING (nicht DONE), Usage
    akkumuliert, echte Kosten fließen, Kontext-Gauge gefüllt, Live-Text im Transkript.
    Folge-Turn (Resume) erhält den Kontext und bleibt WAITING (PROJ-56 self-resume)."""
    from app.engine.manager import DONE, RUNNING, WAITING, SessionRuntime, SessionState

    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    done_calls: list = []
    state = SessionState(
        session_id="s1", owner="dev", project_path=str(tmp_path),
        model="openrouter/minimax/minimax-m3", permission_mode="default",
    )
    state.engine = "opencode"
    runtime = SessionRuntime(state, drv, on_done=lambda r: done_calls.append(r))

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="openrouter/minimax/minimax-m3",
        permission_mode="default", initial_prompt="erste",
    )
    await drv.start(spec, runtime.handle_event)
    await drv._reader_task

    assert state.status == WAITING, f"erwartet WAITING, war {state.status}"
    assert done_calls == []
    assert any(e.text == "hi:erste" for e in runtime.transcript if e.kind == "text")
    assert state.tokens_used > 0
    assert state.context_known is True
    assert state.context_fill_pct > 0
    assert state.cache_read_tokens == 15
    # Echte USD-Kosten akkumuliert (Novum gegenüber Codex/Hermes):
    assert state.total_cost_usd == pytest.approx(0.002)
    tokens_t1, cost_t1 = state.tokens_used, state.total_cost_usd

    # Folge-Turn (self-resume, kein kontextloser Neustart).
    assert drv.supports_self_resume is True and drv.is_alive is False
    state.status = RUNNING
    await drv.send_input("zweite")
    await drv._reader_task

    assert any(e.text.startswith("resumed:zweite:") for e in runtime.transcript if e.kind == "text")
    assert state.status == WAITING
    assert state.tokens_used > tokens_t1
    assert state.total_cost_usd > cost_t1               # Kosten akkumulieren über Turns
    assert done_calls == []


@pytest.mark.asyncio
async def test_proj56_restart_resume_keeps_context(tmp_path):
    """PROJ-56-Auslöser (Backend-Restart / _resume bei totem Treiber): ein NEUER Treiber
    mit persistierter resume_id nimmt den serverseitigen Kontext wieder auf, ohne einen
    kontextlosen Frischstart — der erste send_input re-spawnt mit `-s <id>`."""
    prof = _fake_profile(tmp_path, resumable=True)

    # Turn 1 auf Treiber A → resume_id fangen (das persistierte der Manager).
    drvA = GenericCliDriver(prof)
    eventsA, onA = _collector()
    specA = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="m",
        permission_mode="default", initial_prompt="erste",
    )
    await drvA.start(specA, onA)
    await drvA._reader_task
    persisted_id = drvA.resume_id
    assert persisted_id == "ses_NEW"

    # „Restart": frischer Treiber B, start() mit resume=True + persistierter ID → KEIN
    # Frischstart-Prozess, nur ID vormerken; der nächste send_input nimmt den Kontext auf.
    drvB = GenericCliDriver(prof)
    eventsB, onB = _collector()
    specB = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="m",
        permission_mode="default", initial_prompt="", resume=True, resume_id=persisted_id,
    )
    await drvB.start(specB, onB)
    assert drvB.is_alive is False              # kein Prozess gespawnt (kontext-erhaltend)
    assert not eventsB                          # kein init/Text vor der nächsten Eingabe

    await drvB.send_input("nach dem Restart")
    await drvB._reader_task
    assert "resumed:nach dem Restart:ses_NEW" in _texts(eventsB)  # Kontext überlebte „Restart"


@pytest.mark.asyncio
async def test_resume_without_id_raises_clear_error(tmp_path):
    # Fehlende Resume-ID → klare deutsche Meldung statt kaputtem `-s <leer>`-Aufruf.
    prof = _fake_profile(tmp_path, resumable=True)
    drv = GenericCliDriver(prof)
    drv._spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="m",
        permission_mode="default", initial_prompt="",
    )
    with pytest.raises(RuntimeError, match="Resume-ID"):
        await drv.send_input("frage")
