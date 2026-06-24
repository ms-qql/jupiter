"""Amok-Watchdog — die Reißleine gegen durchdrehende Sessions (PROJ-16).

Zwei Teile, beide ohne DB (In-Memory + Datei-Config, konsistent mit PROJ-10):

1. ``WatchdogStore`` — lädt die **vier konfigurierbaren Limits** aus einer YAML-Datei
   (live, mtime-gecacht; fehlt/defekt → eingebaute konservative Defaults, **nie**
   „kein Watchdog"). Gleiches Muster wie ``policy.PolicyStore``.

2. ``WatchdogMonitor`` — pro Session ein In-Memory-Monitor mit **Schiebefenstern**
   (Sliding Windows) für Tokens, Laufzeit-ohne-Fortschritt, Schreibrate und identische
   Tool-Wiederholungen. ``evaluate`` ist eine reine Lese-Prüfung am Tool-Gate
   (``request_decision``); ``record`` schreibt den erlaubten Aufruf in die Fenster;
   ``reset`` setzt nach „Fortsetzen" das ausgelöste Limit zurück (+ Cooldown gegen
   Card-Flut).

Die eigentliche „Pause statt Kill"-Mechanik lebt im Manager: bei Alarm wird der
nächste Tool-Aufruf in eine Watchdog-Decision-Card umgelenkt (PROJ-4-Future), die
die Session blockiert, ohne den Prozess zu töten — und das **vor** dem Bypass-Auto-
Allow, sodass die Reißleine selbst autonom erlaubte Aktionen sticht.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass

import yaml

from ..config import settings

log = logging.getLogger(__name__)

# Eingebaute, konservative Defaults — greifen, wenn keine/eine defekte Datei da ist
# (Edge-Case „Limit-Konfig fehlt" → nie „kein Watchdog").
DEFAULTS: dict = {
    "enabled": True,
    "token_limit": 200_000,        # abgerechnete Tokens je Zeitfenster
    "token_window_seconds": 60,
    "max_idle_seconds": 180,       # max. Laufzeit ohne Fortschritt
    "max_repeated_calls": 5,       # identische Tool-Calls in Folge → Schleife
    "write_limit": 30,             # Writes je Zeitfenster
    "write_window_seconds": 60,
}

# Positive-Integer-Felder (alles außer ``enabled``).
_INT_FIELDS: tuple[str, ...] = (
    "token_limit",
    "token_window_seconds",
    "max_idle_seconds",
    "max_repeated_calls",
    "write_limit",
    "write_window_seconds",
)

# Schreibende Tool-Klassen (zählen gegen die Schreibrate).
WRITE_TOOLS: frozenset[str] = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

# Cooldown nach „Fortsetzen"/„Korrigieren": kein sofortiges Re-Trigger, keine
# Card-Flut (Edge-Case „Mehrfach-Alarm in Folge").
COOLDOWN_SECONDS: float = 30.0

# Obergrenze der Fingerprint-Länge (Token-Disziplin; lange Inputs nicht voll halten).
_FP_MAX_CHARS: int = 2_000


# --- Store: Limits aus YAML, live (mtime), Default-Fallback ----------------


class WatchdogStore:
    """Liest die Watchdog-Limits aus einer YAML-Datei — live, mtime-gecacht.

    Fehlende Schlüssel werden mit ``DEFAULTS`` aufgefüllt; eine strukturell kaputte
    Datei fällt komplett auf ``DEFAULTS`` zurück (+ sichtbare Warnung, kein Crash).
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._mtime: float | None = None
        self._limits: dict = dict(DEFAULTS)
        self._source: str = "default"
        self._warning: str | None = None
        self._loaded_once = False

    def _reload_if_changed(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            if self._source != "default" or not self._loaded_once:
                self._limits = dict(DEFAULTS)
                self._source = "default"
                self._warning = None
                self._mtime = None
                self._loaded_once = True
            return
        if self._loaded_once and mtime == self._mtime:
            return
        self._parse_file(mtime)

    def _parse_file(self, mtime: float) -> None:
        self._loaded_once = True
        self._mtime = mtime
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            self._limits = _validate(data)
            self._source = self._path
            self._warning = None
        except (OSError, ValueError, yaml.YAMLError) as exc:
            log.warning("Watchdog-Config %s ungültig: %s — Fallback auf Defaults.", self._path, exc)
            self._limits = dict(DEFAULTS)
            self._source = "default"
            self._warning = f"Watchdog-Config ungültig ({exc})"

    def limits(self) -> dict:
        """Aktuelle Limits (live aus der Datei)."""
        self._reload_if_changed()
        return dict(self._limits)

    def snapshot(self) -> dict:
        """Limits + Herkunft/Warnung für die Settings-API (GET /settings/watchdog)."""
        self._reload_if_changed()
        return {**self._limits, "source": self._source, "warning": self._warning}

    def save(self, payload: dict) -> dict:
        """Limits validieren + nach YAML schreiben → beim nächsten Zugriff live aktiv.

        Wirft ``ValueError`` bei nicht-positiven/ungültigen Werten (Route → HTTP 400/422).
        """
        validated = _validate(payload, strict=True)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(validated, fh, allow_unicode=True, sort_keys=False)
        self._loaded_once = False  # nächster Zugriff lädt frisch (Live-Reload).
        return self.snapshot()


def _validate(data: object, *, strict: bool = False) -> dict:
    """Mischt ``data`` über ``DEFAULTS`` und prüft Typen/Positivität.

    ``strict=True`` (Save-Pfad): jedes Int-Feld muss > 0 sein, sonst ``ValueError``.
    Nicht-strict (Lade-Pfad): unsinnige Werte werden auf den Default geklemmt.
    """
    if not isinstance(data, dict):
        raise ValueError("Watchdog-Config muss ein Objekt sein.")
    out: dict = {"enabled": bool(data.get("enabled", DEFAULTS["enabled"]))}
    for key in _INT_FIELDS:
        raw = data.get(key, DEFAULTS[key])
        try:
            val = int(raw)
        except (TypeError, ValueError) as exc:
            if strict:
                raise ValueError(f"{key} muss eine Ganzzahl sein.") from exc
            val = DEFAULTS[key]
        if val <= 0:
            if strict:
                raise ValueError(f"{key} muss > 0 sein (war {val}).")
            val = DEFAULTS[key]
        out[key] = val
    return out


# Modul-Singleton — eine Watchdog-Config pro Backend-Prozess (live aus der Datei).
watchdog_store = WatchdogStore(settings.watchdog_config_path)


# --- Monitor: Sliding-Window-Metriken pro Session --------------------------


@dataclass(frozen=True)
class WatchdogAlarm:
    """Ein gerissenes Limit: Metrik-Schlüssel + menschenlesbarer Klartext-Grund."""

    metric: str  # "tokens" | "idle" | "repeat" | "writes"
    reason: str


class WatchdogMonitor:
    """Pro-Session-Monitor. Misst im Event-Pfad, prüft am Tool-Gate.

    Zeit kommt aus ``clock`` (Default ``time.monotonic``) — injizierbar für Tests.
    """

    def __init__(self, store: WatchdogStore, clock=time.monotonic) -> None:
        self._store = store
        self._clock = clock
        self._tokens: deque[tuple[float, int]] = deque()  # (ts, billed_tokens)
        self._writes: deque[float] = deque()              # ts je Write
        self._last_progress: float = clock()
        self._last_fp: str | None = None
        self._repeat: int = 0
        self._cooldown_until: float = 0.0

    # --- Füttern aus dem Event-Pfad (handle_event/_apply_usage) -----------

    def feed_usage(self, billed_tokens: int) -> None:
        """Abgerechnete Tokens eines result-Events ins Fenster + zählt als Fortschritt."""
        now = self._clock()
        if billed_tokens and billed_tokens > 0:
            self._tokens.append((now, int(billed_tokens)))
        self._last_progress = now

    def note_progress(self) -> None:
        """Echte Aktivität (Assistenten-Output/Result) → Fortschritts-Uhr zurücksetzen."""
        self._last_progress = self._clock()

    # --- Prüfen + Aufzeichnen am Tool-Gate (request_decision) -------------

    def evaluate(self, tool_name: str, tool_input: dict | None) -> WatchdogAlarm | None:
        """Reine Lese-Prüfung: würde dieser Tool-Aufruf ein Limit reißen?

        Gibt einen ``WatchdogAlarm`` zurück (→ Manager pausiert) oder ``None``.
        Im Cooldown oder bei abgeschaltetem Watchdog immer ``None``.
        """
        now = self._clock()
        lim = self._store.limits()
        if not lim["enabled"] or now < self._cooldown_until:
            return None

        # 1) Tokens je Zeitfenster.
        _trim_pairs(self._tokens, now - lim["token_window_seconds"])
        tok = sum(t for _, t in self._tokens)
        if tok > lim["token_limit"]:
            return WatchdogAlarm(
                "tokens",
                f"Token-Limit: {tok} Tokens in {lim['token_window_seconds']} s "
                f"überschreiten {lim['token_limit']}.",
            )

        # 2) Laufzeit ohne Fortschritt.
        idle = now - self._last_progress
        if idle > lim["max_idle_seconds"]:
            return WatchdogAlarm(
                "idle",
                f"Stillstand: {int(idle)} s ohne Fortschritt überschreiten "
                f"{lim['max_idle_seconds']} s.",
            )

        # 3) Identische Tool-Calls in Folge (Schleife ≠ Iteration).
        fp = _fingerprint(tool_name, tool_input)
        prospective = self._repeat + 1 if fp == self._last_fp else 1
        if prospective >= lim["max_repeated_calls"]:
            return WatchdogAlarm(
                "repeat",
                f"Schleife: {prospective}x identischer Aufruf {tool_name} "
                f"(Limit {lim['max_repeated_calls']}).",
            )

        # 4) Schreibrate (prospektiv inkl. dieses Writes).
        if tool_name in WRITE_TOOLS:
            _trim(self._writes, now - lim["write_window_seconds"])
            if len(self._writes) + 1 > lim["write_limit"]:
                return WatchdogAlarm(
                    "writes",
                    f"Schreibrate: {len(self._writes) + 1} Writes in "
                    f"{lim['write_window_seconds']} s überschreiten {lim['write_limit']}.",
                )
        return None

    def record(self, tool_name: str, tool_input: dict | None) -> None:
        """Erlaubten (nicht pausierten) Tool-Aufruf in die Fenster aufnehmen."""
        now = self._clock()
        fp = _fingerprint(tool_name, tool_input)
        self._repeat = self._repeat + 1 if fp == self._last_fp else 1
        self._last_fp = fp
        if tool_name in WRITE_TOOLS:
            self._writes.append(now)

    def reset(self, metric: str) -> None:
        """Nach „Fortsetzen"/„Korrigieren": ausgelöstes Limit-Fenster leeren + Cooldown.

        Verhindert sofortiges Re-Trigger desselben Limits (AC) und Card-Flut.
        """
        now = self._clock()
        if metric == "tokens":
            self._tokens.clear()
        elif metric == "idle":
            self._last_progress = now
        elif metric == "repeat":
            self._repeat = 0
            self._last_fp = None
        elif metric == "writes":
            self._writes.clear()
        self._cooldown_until = now + COOLDOWN_SECONDS


def _fingerprint(tool_name: str, tool_input: dict | None) -> str:
    try:
        payload = json.dumps(tool_input or {}, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        payload = str(tool_input)
    return f"{tool_name}:{payload[:_FP_MAX_CHARS]}"


def _trim(dq: deque[float], cutoff: float) -> None:
    while dq and dq[0] < cutoff:
        dq.popleft()


def _trim_pairs(dq: deque[tuple[float, int]], cutoff: float) -> None:
    while dq and dq[0][0] < cutoff:
        dq.popleft()
