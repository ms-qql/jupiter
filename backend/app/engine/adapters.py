"""Strom-Adapter (PROJ-18) — normalisieren fremde Engine-Ausgaben auf den EINEN
internen Event-Vertrag (Claude-förmige :class:`StreamEvent`s).

Nach oben sehen alle Engines gleich aus (#6): der ``SessionRuntime.handle_event``
versteht nur die Claude-Form (``system/assistant/result/rate_limit_event``). Ein
Adapter ist daher genau eine Funktion ``parse_line(line) -> StreamEvent | None``,
die eine Roh-Zeile der Fremd-Engine in diese Form übersetzt. So bleibt der gesamte
Manager-/Cockpit-Code engine-agnostisch — die Kopplung steckt allein hier.

Vier Adapter decken das Spektrum:

- ``claude``    — Claudes ``stream-json`` (die bestehende :func:`events.parse_line`).
- ``jsonl``     — generisch: ein JSON-Objekt je Zeile; bekannte Text-/Done-Felder
                  werden auf assistant-Text bzw. ein result-Event gemappt.
- ``plaintext`` — Fallback: jede nicht-leere Zeile = assistant-Text. Keine Usage →
                  Token-/Kontext-Anzeige degradiert sichtbar zu „n/v" (Edge-Case
                  „Engine liefert kein Stream-JSON").
- ``codex``     — OpenAI-Codex-CLI (PROJ-48): ``codex exec --json`` liefert die Events
                  **verschachtelt** (Text unter ``item.text``, Usage unter
                  ``turn.completed.usage``). Der Adapter mappt sie auf die Claude-Form
                  und reicht die ``thread_id`` (für ``resume``) als ``system/resume_token``
                  an den Treiber durch.
- ``opencode``  — OpenCode-CLI (PROJ-57): ``opencode run --format json`` liefert je Zeile
                  ein Event mit top-level ``type`` + ``sessionID`` + ``part``. Der Adapter
                  reicht die ``sessionID`` (für ``-s <id>``-Resume) als ``system/resume_token``
                  durch, mappt ``text``→assistant, ``tool_use``→tool_use und **jedes**
                  ``step_finish`` (auch die Zwischen-Schritte eines Tool-Turns, reason
                  ``tool-calls``) auf ein result-Event inkl. Usage **und echter USD-Kosten**
                  (``part.cost``). Referenz: opencode v1.17.13, real am Live-System verifiziert.
"""
from __future__ import annotations

import json
from collections.abc import Callable

from .events import StreamEvent, parse_line as _claude_parse_line

# Ein Adapter ist eine reine Funktion: Roh-Zeile → StreamEvent (oder None = ignorieren).
Adapter = Callable[[str], StreamEvent | None]

# Bekannte Schlüssel, unter denen JSONL-Engines ihren Text-Delta ablegen (best effort).
_TEXT_KEYS: tuple[str, ...] = ("response", "text", "content", "delta", "output", "token")
# Schlüssel, die ein abgeschlossenes Ergebnis signalisieren.
_DONE_KEYS: tuple[str, ...] = ("done", "stop", "completed", "final")


def _assistant_event(text: str) -> StreamEvent:
    """Baut ein Claude-förmiges assistant-Text-Event (ohne Usage → Gauge bleibt „unbekannt")."""
    return StreamEvent(
        type="assistant",
        subtype=None,
        raw={"message": {"content": [{"type": "text", "text": text}]}},
    )


def _result_event(text: str = "") -> StreamEvent:
    """Baut ein Claude-förmiges result-Event OHNE Usage (Engine ohne Token-Routing)."""
    return StreamEvent(
        type="result",
        subtype="success",
        raw={"is_error": False, "result": text, "num_turns": 1},
    )


def plaintext_parse_line(line: str) -> StreamEvent | None:
    """Jede nicht-leere Zeile → assistant-Text. Kein Turn-Ende-Signal (das liefert
    das EOF/Prozessende des Treibers → ``closed`` → DONE)."""
    text = line.rstrip("\n")
    if not text.strip():
        return None
    return _assistant_event(text)


def jsonl_parse_line(line: str) -> StreamEvent | None:
    """Ein JSON-Objekt je Zeile → assistant-Text bzw. result.

    Unparsebare oder textlose Zeilen werden ignoriert (kein Hard-Fail, wie bei Claude).
    Ein ``done``-Marker (true) erzeugt ein result-Event und schließt damit den Turn.
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        # Keine JSON-Zeile → defensiv als Klartext behandeln (degradiert, kein Crash).
        return plaintext_parse_line(line)
    if not isinstance(obj, dict):
        return None

    text = _extract_text(obj)
    done = any(bool(obj.get(k)) for k in _DONE_KEYS)
    if done:
        return _result_event(text or "")
    if text:
        return _assistant_event(text)
    return None


def _extract_text(obj: dict) -> str:
    """Holt den Text-Delta aus den bekannten Schlüsseln (oder ``message.content``)."""
    for key in _TEXT_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val:
            return val
    msg = obj.get("message")
    if isinstance(msg, str):
        return msg
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, str):
            return content
    return ""


def _codex_result_event(usage: dict | None) -> StreamEvent:
    """Baut aus Codex' ``turn.completed.usage`` ein Claude-förmiges result-Event.

    Mapping (PROJ-48, real verifiziert mit codex-cli 0.142.2) — Codex liefert je Turn
    ``{input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}``;
    ``cached_input_tokens`` ist eine **Teilmenge** von ``input_tokens`` (real geprüft:
    9600 ≤ 11562). Wir spiegeln Claudes Semantik (``cache_read`` separat, **nicht** in
    ``input_tokens`` enthalten):

    - ``input_tokens``            = ``input - cached``  (neuer, nicht-gecachter Prompt)
    - ``cache_read_input_tokens`` = ``cached``          (Cache-Sicht, analog Claude)
    - ``output_tokens``           = ``output + reasoning`` (Reasoning zählt zur Output-Last)

    Daraus folgt: Kontext-Füllstand (= ``input - cached`` + ``cache_read``) = echter
    Prompt-Umfang (kein Doppelzählen des Cache); abgerechnete Tokens
    (``input_tokens + output_tokens``) konsistent zur Claude-Engine. ``context_is_per_turn``
    signalisiert dem Manager, dass diese Usage den **aktuellen** Turn-Prompt abbildet
    (anders als Claudes kumulative result-Usage) → sie darf den Kontext-Gauge füllen.
    """
    u = usage if isinstance(usage, dict) else {}

    def _int(key: str) -> int:
        try:
            return max(0, int(u.get(key, 0) or 0))
        except (TypeError, ValueError):
            return 0

    inp, cached = _int("input_tokens"), _int("cached_input_tokens")
    out, reasoning = _int("output_tokens"), _int("reasoning_output_tokens")
    return StreamEvent(
        type="result",
        subtype="success",
        raw={
            "is_error": False,
            "result": "",
            "num_turns": 1,
            "context_is_per_turn": True,
            "usage": {
                "input_tokens": max(0, inp - cached),
                "cache_read_input_tokens": cached,
                "output_tokens": out + reasoning,
            },
        },
    )


def codex_parse_line(line: str) -> StreamEvent | None:
    """Codex-CLI-JSONL (``codex exec --json``) → Claude-förmige StreamEvents.

    - ``thread.started``  → ``system/resume_token`` (``thread_id`` für ``exec resume``;
      kein Anzeige-Event — der Treiber fängt es ab und unterdrückt es).
    - ``item.completed`` mit ``item.text`` (z. B. ``agent_message``, Fehler-/Sandbox-Text)
      → assistant-Text (sichtbar; kein stiller Stillstand).
    - ``turn.completed`` → result-Event **inkl. gemappter Usage** (Turn-Ende).
    - ``turn.started`` / unbekannte ``type`` → ``None`` (defensiv ignoriert, kein Hard-Fail).
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None

    etype = obj.get("type")
    if etype == "thread.started":
        tid = obj.get("thread_id")
        if not tid:
            return None
        return StreamEvent("system", "resume_token", {"resume_token": str(tid)})
    if etype == "item.completed":
        item = obj.get("item")
        if isinstance(item, dict):
            # PROJ-50: Datei-Änderungen tragen den berührten Pfad — Codex liefert KEIN
            # Skill-Event (Spike), daher ist `file_change` die Stream-Quelle für die
            # Feature-/Fortschritts-Erkennung. Auf ein generisches `tool_use`-Event
            # mappen (Write/Edit), das `handle_event` an `detect_phase_signal` reicht.
            if item.get("type") == "file_change":
                ev = _codex_file_change_event(item)
                if ev is not None:
                    return ev
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return _assistant_event(text)
        return None
    if etype == "turn.completed":
        return _codex_result_event(obj.get("usage"))
    return None


def _codex_file_change_event(item: dict) -> StreamEvent | None:
    """Codex' ``file_change``-Item → Claude-förmiges ``tool_use``-Event (PROJ-50).

    Trägt den ersten berührten Pfad als ``input.file_path`` (auch bei ``status:failed`` —
    der Pfad steht im Stream); ``name`` = ``Write`` (neu) bzw. ``Edit`` (Änderung), damit
    der engine-agnostische ``detect_phase_signal``-Fallback (``feature_from_path``) greift.
    """
    changes = item.get("changes")
    if not isinstance(changes, list) or not changes:
        return None
    first = changes[0] if isinstance(changes[0], dict) else {}
    path = first.get("path")
    if not path:
        return None
    name = "Write" if first.get("kind") == "add" else "Edit"
    return StreamEvent("tool_use", "file_change", {"name": name, "input": {"file_path": str(path)}})


# ---------------------------------------------------------------------------
# OpenCode-Adapter (PROJ-57)
# ---------------------------------------------------------------------------

# OpenCode-Tool-Namen, die eine Datei berühren → auf Claude-Namen (Write/Edit) mappen,
# damit der engine-agnostische `detect_phase_signal`-Fallback (feature_from_path) und der
# Aktivitäts-Ticker den Pfad sehen (analog codex file_change → PROJ-50).
_OPENCODE_FILE_TOOLS: dict[str, str] = {"write": "Write", "edit": "Edit"}
# Schlüssel, unter denen OpenCode-Tools ihren Datei-Pfad ablegen (defensiv mehrere prüfen).
_OPENCODE_PATH_KEYS: tuple[str, ...] = ("filePath", "file_path", "path")


def _opencode_tool_event(part: dict) -> StreamEvent | None:
    """OpenCodes ``tool_use``-Part → Claude-förmiges ``tool_use``-Event (sichtbare Aktivität).

    Datei-Tools (write/edit) tragen den berührten Pfad als ``input.file_path``; sonstige
    Tools (bash/read/grep …) reichen ihren Roh-Input durch. Ohne Tool-Namen → ``None``.
    """
    tool = part.get("tool")
    if not isinstance(tool, str) or not tool:
        return None
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    inp = state.get("input") if isinstance(state.get("input"), dict) else {}
    mapped = _OPENCODE_FILE_TOOLS.get(tool.lower())
    if mapped is not None:
        path = next((str(inp[k]) for k in _OPENCODE_PATH_KEYS if inp.get(k)), None)
        return StreamEvent("tool_use", "tool", {"name": mapped, "input": {"file_path": path or ""}})
    return StreamEvent("tool_use", "tool", {"name": tool, "input": dict(inp)})


def _opencode_result_event(part: dict) -> StreamEvent:
    """OpenCodes ``step_finish``-Part → Claude-förmiges result-Event inkl. Usage + Kosten.

    Token-Mapping (real verifiziert, opencode v1.17.13): ``tokens`` liefert
    ``{total, input, output, reasoning, cache:{write, read}}``, wobei
    ``total = input + output + reasoning + cache.read`` — d. h. ``input`` **enthält den Cache
    NICHT** (anders als Codex, wo cached eine Teilmenge von input war). Wir spiegeln Claudes
    Semantik direkt:

    - ``input_tokens``            = ``tokens.input``        (neuer, nicht-gecachter Prompt)
    - ``cache_read_input_tokens`` = ``tokens.cache.read``   (Cache-Sicht, separat)
    - ``cache_creation_input_tokens`` = ``tokens.cache.write``
    - ``output_tokens``           = ``tokens.output + tokens.reasoning`` (Reasoning = Output-Last)

    Kontext-Füllstand (= input + cache_read + cache_write) = echter Prompt-Umfang;
    abgerechnete Tokens (input + output) konsistent zur Claude-Engine. ``context_is_per_turn``
    markiert die Usage als aktuellen Turn-Prompt (füllt den Gauge). ``part.cost`` ist die
    **echte USD-Summe** dieses Schritts → als ``total_cost_usd`` durchgereicht (Novum: diese
    Engine zeigt echte Kosten statt „n/v"). Zwischen-Schritte (reason ``tool-calls``) liefern
    ebenfalls Usage/Kosten → sie akkumulieren korrekt über den Turn.
    """
    tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
    cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}

    def _int(d: dict, key: str) -> int:
        try:
            return max(0, int(d.get(key, 0) or 0))
        except (TypeError, ValueError):
            return 0

    raw: dict = {
        "is_error": False,
        "result": "",
        "num_turns": 1,
        "context_is_per_turn": True,
        "usage": {
            "input_tokens": _int(tokens, "input"),
            "cache_read_input_tokens": _int(cache, "read"),
            "cache_creation_input_tokens": _int(cache, "write"),
            "output_tokens": _int(tokens, "output") + _int(tokens, "reasoning"),
        },
    }
    cost = part.get("cost")
    if isinstance(cost, (int, float)):
        raw["total_cost_usd"] = float(cost)
    return StreamEvent("result", "success", raw)


def opencode_parse_line(line: str) -> StreamEvent | None:
    """OpenCode-CLI (``opencode run --format json``) → Claude-förmige StreamEvents.

    - ``step_start``  → ``system/resume_token`` (top-level ``sessionID`` für ``-s``-Resume;
      kein Anzeige-Event — der Treiber fängt es ab und merkt sich die ``resume_id``).
    - ``text``        → assistant-Text aus ``part.text`` (sichtbar; kein stiller Stillstand).
    - ``tool_use``    → Claude-``tool_use`` (sichtbare Aktivität; Datei-Pfad bei write/edit).
    - ``step_finish`` → result-Event **inkl. gemappter Usage + Kosten** (Turn-/Schritt-Ende).
    - unbekannte ``type`` (``reasoning``/``directory``/…) → ``None`` (defensiv, kein Hard-Fail).
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None

    etype = obj.get("type")
    if etype == "step_start":
        sid = obj.get("sessionID")
        if not sid:
            return None
        return StreamEvent("system", "resume_token", {"resume_token": str(sid)})
    part = obj.get("part") if isinstance(obj.get("part"), dict) else {}
    if etype == "text":
        txt = part.get("text")
        if isinstance(txt, str) and txt.strip():
            return _assistant_event(txt)
        return None
    if etype == "tool_use":
        return _opencode_tool_event(part)
    if etype == "step_finish":
        return _opencode_result_event(part)
    return None


# Registry der bekannten Adapter. ``claude`` = die bestehende, real verifizierte Logik.
_ADAPTERS: dict[str, Adapter] = {
    "claude": _claude_parse_line,
    "jsonl": jsonl_parse_line,
    "plaintext": plaintext_parse_line,
    "codex": codex_parse_line,
    "opencode": opencode_parse_line,
}

VALID_ADAPTERS: frozenset[str] = frozenset(_ADAPTERS)


def get_adapter(name: str) -> Adapter:
    """Liefert die Parse-Funktion für ``name``; unbekannt → ``plaintext`` (sicherer Fallback)."""
    return _ADAPTERS.get(name, plaintext_parse_line)
