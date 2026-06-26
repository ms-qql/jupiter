"""PROJ-50 — abc-Workflow auf der Codex-Engine (portierte Skills + Phasen-Signal).

Deckt die Akzeptanzkriterien ab, soweit unit-testbar:
- Spike-Korrektur: Codex liefert KEIN Skill-Event → Phase kommt aus dem Anstoß-Prompt
  (Launcher-Seeding), Feature/Fortschritt aus `file_change`-Items des Streams.
- codex-Adapter mappt `item.completed`/`file_change` → generisches `tool_use`-Event.
- `handle_event` speist dieses Event in die engine-agnostische `detect_phase_signal`
  (zweiter Einspeise-Punkt neben dem Claude-Gate) → Feature + Live-Ticker, ohne Regression.
- Launcher engine-bewusst: Codex bekommt Skill-benennende Anstoß-Prompts, Claude `/abc-…`.
- Capability `abc` an Codex und Claude.
- Generator: erzeugt gültige Codex-Skill-Frontmatter, idempotent, ohne tote .claude-Pfade.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.engine import abc_phases as ap
from app.engine.adapters import codex_parse_line
from app.engine.events import StreamEvent
from app.engine.registry import engine_registry

REPO = Path(__file__).resolve().parents[2]


# ===========================================================================
# Adapter: file_change → tool_use (PROJ-50)
# ===========================================================================

def test_file_change_add_becomes_write_tool_use():
    line = json.dumps({"type": "item.completed", "item": {
        "type": "file_change",
        "changes": [{"path": "features/PROJ-50-x.md", "kind": "add"}],
        "status": "failed",  # Pfad steht im Stream auch bei Fehlschlag
    }})
    ev = codex_parse_line(line)
    assert ev is not None and ev.type == "tool_use" and ev.subtype == "file_change"
    assert ev.raw["name"] == "Write"
    assert ev.raw["input"]["file_path"] == "features/PROJ-50-x.md"


def test_file_change_modify_becomes_edit():
    line = json.dumps({"type": "item.completed", "item": {
        "type": "file_change",
        "changes": [{"path": "backend/app/x.py", "kind": "update"}],
        "status": "completed",
    }})
    ev = codex_parse_line(line)
    assert ev.raw["name"] == "Edit"


def test_file_change_without_path_is_ignored():
    line = json.dumps({"type": "item.completed", "item": {
        "type": "file_change", "changes": [{}], "status": "completed"}})
    assert codex_parse_line(line) is None


def test_agent_message_still_visible_text():
    line = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "moin"}})
    ev = codex_parse_line(line)
    assert ev.type == "assistant"


# ===========================================================================
# Seeding-/Trigger-Helfer (Launcher kennt die Phase — Codex liefert sie nicht im Stream)
# ===========================================================================

@pytest.mark.parametrize("prompt,phase", [
    ("/abc-architecture 50", "architecture"),
    ("Nutze die Skill »abc-backend« für Feature 50", "backend"),
    ("/abc-qa-e2e 8", "qa"),
    ("abc-refactor 5", None),            # kein Phasen-Skill
    ("nur freitext ohne skill", None),
])
def test_phase_from_prompt(prompt, phase):
    assert ap.phase_from_prompt(prompt) == phase


def test_seed_triple_sets_phase_reached_and_feature():
    assert ap.seed_triple_from_prompt("/abc-qa 8") == ("qa", "qa", "8")
    assert ap.seed_triple_from_prompt("kein skill", reached="frontend") == (None, "frontend", None)


def test_phase_trigger_prompt_naming_vs_slash():
    assert ap.phase_trigger_prompt("abc-architecture", 50, naming=False) == "/abc-architecture 50"
    naming = ap.phase_trigger_prompt("abc-architecture", 50, naming=True)
    assert "»abc-architecture«" in naming and "50" in naming and not naming.startswith("/")


def test_rewrite_trigger_only_pure_slash_and_only_when_naming():
    # Reiner Slash-Trigger + naming → benannt
    assert ap.rewrite_trigger_for_engine("/abc-architecture 50", naming=True).startswith("Nutze die Skill")
    # naming=False → unverändert (Claude)
    assert ap.rewrite_trigger_for_engine("/abc-architecture 50", naming=False) == "/abc-architecture 50"
    # Freitext, der die Skill nur erwähnt → unangetastet (kein reiner Trigger)
    assert ap.rewrite_trigger_for_engine("bitte /abc-architecture 50 starten", naming=True) == "bitte /abc-architecture 50 starten"
    # Nicht-Phasen-Skill bleibt
    assert ap.rewrite_trigger_for_engine("/abc-refactor 5", naming=True) == "/abc-refactor 5"


# ===========================================================================
# handle_event: tool_use aus dem Stream → Feature + Phase-Apply + Ticker
# ===========================================================================

def _runtime(tmp_path, *, engine="codex"):
    from app.engine.base import DeadDriver
    from app.engine.manager import SessionRuntime, SessionState
    state = SessionState(
        session_id="s1", owner="dev", project_path=str(tmp_path),
        model="gpt-5.5", permission_mode="default",
    )
    state.engine = engine
    return SessionRuntime(state, DeadDriver()), state


@pytest.mark.asyncio
async def test_handle_tool_use_updates_feature_and_activity(tmp_path):
    runtime, state = _runtime(tmp_path)
    # Phase wie beim Launcher-Seeding vorbelegt (Codex liefert keine Phase im Stream).
    state.abc_phase, state.abc_phase_reached, state.abc_feature = ("architecture", "architecture", None)
    ev = StreamEvent("tool_use", "file_change",
                     {"name": "Write", "input": {"file_path": "features/PROJ-50-x.md"}})
    await runtime.handle_event(ev)
    # Feature aus dem Pfad gezogen; Phase bleibt (Pfad allein setzt keine Phase).
    assert state.abc_feature == "50"
    assert state.abc_phase == "architecture"
    # Live-Aktivitäts-Ticker (PROJ-46) gefüttert.
    assert runtime.last_activity is not None and runtime.last_activity["tool"] == "Write"


# ===========================================================================
# Capability + Launcher engine-awareness
# ===========================================================================

def test_codex_and_claude_have_abc_capability():
    assert engine_registry.get("claude").has_capability("abc")
    codex = engine_registry.get("codex")
    if codex is not None:  # nur wenn in der lokalen engines.yaml konfiguriert
        assert codex.has_capability("abc")


def test_launcher_naming_flag_resolution():
    from app.engine.launcher import _engine_uses_naming
    assert _engine_uses_naming("claude") is False      # Claude: Hook, kein Naming
    assert _engine_uses_naming(None) is False
    codex = engine_registry.get("codex")
    if codex is not None:
        assert _engine_uses_naming("codex") is True


def test_feature_suggestion_prompt_variants():
    from app.engine.launcher import _feature_suggestion
    f = {"id": "PROJ-50", "number": "50", "title": "x", "status": "Architected", "prio": "P1"}
    assert _feature_suggestion(f, naming=False)["initial_prompt"] == "/abc-frontend 50"
    assert "»abc-frontend«" in _feature_suggestion(f, naming=True)["initial_prompt"]


# ===========================================================================
# Generator (PROJ-50): reproduzierbar, gültige Frontmatter, keine toten .claude-Pfade
# ===========================================================================

def test_generator_check_passes_no_drift():
    """`--check` muss grün sein (Codex-Skills sind aktuell zu den Claude-Quellen)."""
    res = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "gen_codex_skills.py"), "--check"],
        capture_output=True, text=True,
    )
    # Exit 0 = aktuell; Exit 2 = Quelle fehlt (Umgebung ohne ~/.claude) → Test überspringen.
    if res.returncode == 2:
        pytest.skip("Keine ~/.claude/skills-Quelle in dieser Umgebung.")
    assert res.returncode == 0, f"Drift/Fehler:\n{res.stdout}\n{res.stderr}"


@pytest.mark.xfail(reason="QA-Bug #1 (Low): folded-scalar `description: >-` → leere short-description; Fix in backend-dev offen.", strict=False)
def test_generator_short_description_nonempty_for_folded_scalar(tmp_path):
    """QA-Regression: Skills mit YAML-folded-Scalar-Description (`>-`) müssen eine
    nicht-leere `metadata.short-description` bekommen. Aktuell greift die zeilenbasierte
    Extraktion den Indikator `>-` ab → leerer Wert. Flippt auf PASS, sobald der Generator
    Frontmatter YAML-bewusst parst."""
    import os
    import yaml
    src = Path(os.path.expanduser("~/.claude/skills"))
    if not (src / "abc-dokploy-data" / "SKILL.md").is_file():
        pytest.skip("Keine ~/.claude/skills-Quelle in dieser Umgebung.")
    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "gen_codex_skills.py"),
         "--src", str(src), "--dest", str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    out = (tmp_path / "abc-dokploy-data" / "SKILL.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(out[3:out.find("\n---", 3)])
    assert (fm.get("metadata") or {}).get("short-description"), "short-description ist leer (folded scalar)"


def test_generated_codex_skill_is_valid(tmp_path):
    """Generiert in ein tmp-Ziel und prüft Frontmatter + Claude-Ism-Bereinigung."""
    import os
    src = Path(os.path.expanduser("~/.claude/skills"))
    if not (src / "abc-architecture" / "SKILL.md").is_file():
        pytest.skip("Keine ~/.claude/skills-Quelle in dieser Umgebung.")
    res = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "gen_codex_skills.py"),
         "--src", str(src), "--dest", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    out = (tmp_path / "abc-architecture" / "SKILL.md").read_text(encoding="utf-8")
    assert out.startswith("---\nname: abc-architecture")
    assert "metadata:" in out and "short-description:" in out
    assert "user-invocable:" not in out and "argument-hint:" not in out
    assert "/home/dev/.claude/skills" not in out   # keine toten absoluten Pfade
    assert "Codex-Hinweis" in out                  # Präambel vorhanden
