"""Strom-Adapter (PROJ-18) — normalisieren fremde Engine-Ausgaben auf den EINEN
internen Event-Vertrag (Claude-förmige :class:`StreamEvent`s).

Nach oben sehen alle Engines gleich aus (#6): der ``SessionRuntime.handle_event``
versteht nur die Claude-Form (``system/assistant/result/rate_limit_event``). Ein
Adapter ist daher genau eine Funktion ``parse_line(line) -> StreamEvent | None``,
die eine Roh-Zeile der Fremd-Engine in diese Form übersetzt. So bleibt der gesamte
Manager-/Cockpit-Code engine-agnostisch — die Kopplung steckt allein hier.

Drei Adapter decken das Spektrum:

- ``claude``    — Claudes ``stream-json`` (die bestehende :func:`events.parse_line`).
- ``jsonl``     — generisch: ein JSON-Objekt je Zeile; bekannte Text-/Done-Felder
                  werden auf assistant-Text bzw. ein result-Event gemappt.
- ``plaintext`` — Fallback: jede nicht-leere Zeile = assistant-Text. Keine Usage →
                  Token-/Kontext-Anzeige degradiert sichtbar zu „n/v" (Edge-Case
                  „Engine liefert kein Stream-JSON").
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


# Registry der bekannten Adapter. ``claude`` = die bestehende, real verifizierte Logik.
_ADAPTERS: dict[str, Adapter] = {
    "claude": _claude_parse_line,
    "jsonl": jsonl_parse_line,
    "plaintext": plaintext_parse_line,
}

VALID_ADAPTERS: frozenset[str] = frozenset(_ADAPTERS)


def get_adapter(name: str) -> Adapter:
    """Liefert die Parse-Funktion für ``name``; unbekannt → ``plaintext`` (sicherer Fallback)."""
    return _ADAPTERS.get(name, plaintext_parse_line)
