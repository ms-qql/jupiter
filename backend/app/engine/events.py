"""Parser für den `claude --output-format stream-json`-Event-Strom.

Gegen den **real verifizierten** Event-Vertrag von Claude Code v2.1.185 gebaut
(Live-Spike, PROJ-1). Beobachtete Event-Typen pro Zeile (je ein JSON-Objekt):

- ``{"type":"system","subtype":"init", "session_id":..., "model":..., "permissionMode":..., "apiKeySource":"none", ...}``
- ``{"type":"system","subtype":"hook_started"|"hook_response", ...}``        → ignorierbar
- ``{"type":"system","subtype":"thinking_tokens","estimated_tokens":N, ...}`` → Live-Denk-Zähler
- ``{"type":"assistant","message":{"content":[{"type":"thinking"|"text",...}], "usage":{...}}}``
- ``{"type":"rate_limit_event","rate_limit_info":{"status":...,"resetsAt":...,"rateLimitType":...}}``
- ``{"type":"result","subtype":"success","is_error":false,"result":"...","num_turns":1,
      "total_cost_usd":..., "usage":{...}, "modelUsage":{"<model>":{"contextWindow":200000,...}}}``

Der Default-Kontextfenster-Fallback ist 200000 (aus ``modelUsage[...].contextWindow``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

DEFAULT_CONTEXT_WINDOW = 200_000


@dataclass
class StreamEvent:
    """Eine geparste Zeile des Event-Stroms."""

    type: str
    subtype: str | None
    raw: dict

    @property
    def session_id(self) -> str | None:
        return self.raw.get("session_id")


@dataclass
class UsageSnapshot:
    """Token-/Kontext-Verbrauch eines Turns — Datenquelle für #25 (PROJ-5)."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    context_window: int = DEFAULT_CONTEXT_WINDOW
    total_cost_usd: float | None = None

    @property
    def context_used_tokens(self) -> int:
        # Was im aktuellen Turn als Prompt-Kontext gesendet wurde.
        return (
            self.input_tokens
            + self.cache_read_input_tokens
            + self.cache_creation_input_tokens
        )

    @property
    def context_fill_pct(self) -> float:
        if self.context_window <= 0:
            return 0.0
        return min(100.0, round(self.context_used_tokens / self.context_window * 100, 1))

    @property
    def billed_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def parse_line(line: str) -> StreamEvent | None:
    """Parst eine einzelne stdout-Zeile. Gibt ``None`` bei Leerzeile/unparsebar.

    Unparsebare Zeilen brechen die Session NICHT ab (Edge-Case der Spec).
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict) or "type" not in obj:
        return None
    return StreamEvent(type=obj.get("type", ""), subtype=obj.get("subtype"), raw=obj)


def extract_text(event: StreamEvent) -> str | None:
    """Liefert den zusammengesetzten Text der ``text``-Blöcke einer Assistant-Message."""
    if event.type != "assistant":
        return None
    blocks = event.raw.get("message", {}).get("content", []) or []
    parts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    text = "".join(parts)
    return text or None


def extract_thinking(event: StreamEvent) -> str | None:
    """Liefert den Text der ``thinking``-Blöcke einer Assistant-Message (falls vorhanden)."""
    if event.type != "assistant":
        return None
    blocks = event.raw.get("message", {}).get("content", []) or []
    parts = [b.get("thinking", "") for b in blocks if isinstance(b, dict) and b.get("type") == "thinking"]
    text = "".join(parts)
    return text or None


def extract_usage(event: StreamEvent) -> UsageSnapshot | None:
    """Extrahiert Verbrauch aus ``assistant``- oder ``result``-Events."""
    if event.type == "assistant":
        usage = event.raw.get("message", {}).get("usage")
        cost = None
    elif event.type == "result":
        usage = event.raw.get("usage")
        cost = event.raw.get("total_cost_usd")
    else:
        return None
    if not isinstance(usage, dict):
        return None

    # Kontextfenster bevorzugt aus modelUsage des result-Events lesen.
    ctx_window = DEFAULT_CONTEXT_WINDOW
    model_usage = event.raw.get("modelUsage")
    if isinstance(model_usage, dict) and model_usage:
        first = next(iter(model_usage.values()))
        if isinstance(first, dict):
            ctx_window = int(first.get("contextWindow") or DEFAULT_CONTEXT_WINDOW)

    return UsageSnapshot(
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        cache_read_input_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
        cache_creation_input_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
        context_window=ctx_window,
        total_cost_usd=cost,
    )


def extract_result_text(event: StreamEvent) -> str | None:
    if event.type != "result":
        return None
    return event.raw.get("result")


def is_error_result(event: StreamEvent) -> bool:
    return event.type == "result" and bool(event.raw.get("is_error"))


def extract_rate_limit(event: StreamEvent) -> dict | None:
    if event.type != "rate_limit_event":
        return None
    info = event.raw.get("rate_limit_info")
    return info if isinstance(info, dict) else None
