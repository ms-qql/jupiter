"""Verifizierter Liveness-Indikator + Auto-Reanimierung (PROJ-27).

Zwei Bausteine, beide ohne zweite Buchhaltung:

* ``LivenessStore`` — die Schwellen (Fortschritts-Timeout, Poll-Frequenz, Auto-
  Versuche, Backoff, globaler An/Aus-Schalter) aus einer YAML-Datei, **live**
  mtime-gecacht mit eingebautem Default-Fallback — exakt das Muster des
  Watchdog-Stores (PROJ-16).
* ``LivenessMonitor`` — die pro-Session-Buchhaltung der Auto-Reanimierung
  (Versuchszähler, Backoff-Gate, letztes Ergebnis). Den *Fortschritt* selbst
  misst weiterhin der Watchdog-Monitor (``seconds_since_progress``); hier wird
  nur entschieden, *wann* ein Auto-Versuch erlaubt ist.

Die eigentliche Zustands-Ableitung (aktiv/hängt/tot) lebt am ``SessionRuntime``
(``derive_liveness``), weil sie Prozess (PID), Status und Fortschritts-Uhr
zusammenführt — alles vorhandene Signale.
"""
from __future__ import annotations

import logging
import os
import time

import yaml

from ..config import settings

log = logging.getLogger(__name__)

# Die drei verifizierten Liveness-Zustände (deutsche UI-Labels, direkt durchgereicht).
LIVENESS_ACTIVE = "aktiv"    # Prozess lebt + Fortschritt ODER legitime Wartestellung.
LIVENESS_HANGING = "hängt"   # Prozess lebt, aber kein Fortschritt über Schwelle / Stream tot.
LIVENESS_DEAD = "tot"        # beendet / verwaist / nicht (mehr) steuerbar.

# Eingebaute, konservative Defaults — greifen, wenn keine/eine defekte Datei da ist
# (nie „kein Liveness"; Auto-Reanimierung mit hartem Limit + Backoff).
DEFAULTS: dict = {
    "enabled_auto_reanimation": True,  # globaler Schalter; aus → nur Indikator + Knopf.
    "progress_timeout_seconds": 180,   # kein Fortschritt > X → „hängt" (analog max_idle_seconds).
    # PROJ-32: höhere Geduld, SOLANGE ein Tool läuft (langer Build/Test/Explore ist kein
    # Hänger). Greift erst, wenn auch diese überschritten wird (echter Tool-Hänger).
    "tool_in_flight_timeout_seconds": 600,
    "poll_interval_seconds": 15,       # Frequenz des Hintergrund-Auswerters.
    "max_auto_attempts": 2,            # danach nur noch der manuelle Knopf.
    "backoff_seconds": 30,             # Wartezeit zwischen Auto-Versuchen.
}

# Positive-Integer-Felder (> 0). ``backoff_seconds`` darf 0 sein (kein Backoff).
_POSITIVE_FIELDS: tuple[str, ...] = (
    "progress_timeout_seconds",
    "tool_in_flight_timeout_seconds",
    "poll_interval_seconds",
    "max_auto_attempts",
)
_NON_NEGATIVE_FIELDS: tuple[str, ...] = ("backoff_seconds",)


def _validate(data: object, *, strict: bool = False) -> dict:
    """Mischt ``data`` über ``DEFAULTS`` und prüft Typen/Wertebereiche.

    ``strict=True`` (Save-Pfad): Verstöße werfen ``ValueError`` (Route → 400/422).
    Nicht-strict (Lade-Pfad): unsinnige Werte werden auf den Default geklemmt.
    """
    if not isinstance(data, dict):
        raise ValueError("Liveness-Config muss ein Objekt sein.")
    out: dict = {
        "enabled_auto_reanimation": bool(
            data.get("enabled_auto_reanimation", DEFAULTS["enabled_auto_reanimation"])
        )
    }
    for key in (*_POSITIVE_FIELDS, *_NON_NEGATIVE_FIELDS):
        raw = data.get(key, DEFAULTS[key])
        try:
            val = int(raw)
        except (TypeError, ValueError) as exc:
            if strict:
                raise ValueError(f"{key} muss eine Ganzzahl sein.") from exc
            val = DEFAULTS[key]
        floor = 1 if key in _POSITIVE_FIELDS else 0
        if val < floor:
            if strict:
                raise ValueError(f"{key} muss >= {floor} sein (war {val}).")
            val = DEFAULTS[key]
        out[key] = val
    return out


class LivenessStore:
    """Liest die Liveness-Schwellen aus einer YAML-Datei — live, mtime-gecacht.

    Fehlende Schlüssel werden mit ``DEFAULTS`` aufgefüllt; eine strukturell kaputte
    Datei fällt komplett auf ``DEFAULTS`` zurück (+ sichtbare Warnung, kein Crash).
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._mtime: float | None = None
        self._config: dict = dict(DEFAULTS)
        self._source: str = "default"
        self._warning: str | None = None
        self._loaded_once = False

    def _reload_if_changed(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            if self._source != "default" or not self._loaded_once:
                self._config = dict(DEFAULTS)
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
            self._config = _validate(data)
            self._source = self._path
            self._warning = None
        except (OSError, ValueError, yaml.YAMLError) as exc:
            log.warning("Liveness-Config %s ungültig: %s — Fallback auf Defaults.", self._path, exc)
            self._config = dict(DEFAULTS)
            self._source = "default"
            self._warning = f"Liveness-Config ungültig ({exc})"

    def config(self) -> dict:
        """Aktuelle Schwellen (live aus der Datei)."""
        self._reload_if_changed()
        return dict(self._config)

    def snapshot(self) -> dict:
        """Schwellen + Herkunft/Warnung für die Settings-API (GET /settings/liveness)."""
        self._reload_if_changed()
        return {**self._config, "source": self._source, "warning": self._warning}

    def save(self, payload: dict) -> dict:
        """Schwellen validieren + nach YAML schreiben → beim nächsten Zugriff live aktiv."""
        validated = _validate(payload, strict=True)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(validated, fh, allow_unicode=True, sort_keys=False)
        self._loaded_once = False  # nächster Zugriff lädt frisch (Live-Reload).
        return self.snapshot()


# Modul-Singleton — eine Liveness-Config pro Backend-Prozess (live aus der Datei).
liveness_store = LivenessStore(settings.liveness_config_path)


class LivenessMonitor:
    """Pro-Session-Buchhaltung der Auto-Reanimierung (Versuche + Backoff + Ergebnis).

    Misst KEINEN Fortschritt (das tut der Watchdog-Monitor) — entscheidet nur, ob
    ein weiterer automatischer Reanimations-Versuch erlaubt ist, und merkt sich das
    letzte Ergebnis für die UI. Zeit kommt aus ``clock`` (injizierbar für Tests).
    """

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self.auto_attempts: int = 0
        self.next_attempt_at: float = 0.0
        self.last_result: str | None = None  # "läuft_wieder" | "fehlgeschlagen"
        # PROJ-45: Turn-Wasserstand (``state.num_turns``) zum Zeitpunkt des letzten
        # Auto-Versuchs. Das Budget wird erst zurückgesetzt, wenn num_turns DIESEN Stand
        # übersteigt — also ein echter neuer Turn NACH dem Resume-Transkript-Abspiel fertig
        # wurde. So zählt nur substanzieller neuer Fortschritt, nicht das kurze Replay.
        self.progress_watermark: int = 0
        # Letzter an die UI gestreamter Zustand — damit der Hintergrund-Poll NUR bei
        # echter Änderung broadcastet (kein Dauer-Strom für stille Sessions).
        self.last_broadcast_state: str | None = None

    def may_auto_attempt(self, max_attempts: int) -> bool:
        """Darf jetzt ein automatischer Versuch laufen? (Budget übrig + Backoff offen)."""
        return self.auto_attempts < max_attempts and self._clock() >= self.next_attempt_at

    def record_attempt(self, backoff_seconds: float, *, success: bool) -> None:
        """Einen Auto-Versuch verbuchen: Zähler hoch, Backoff setzen, Ergebnis merken."""
        self.auto_attempts += 1
        self.next_attempt_at = self._clock() + max(0.0, backoff_seconds)
        self.mark_result(success=success)

    def mark_result(self, *, success: bool) -> None:
        self.last_result = "läuft_wieder" if success else "fehlgeschlagen"

    def note_reanimation_baseline(self, turns: int) -> None:
        """PROJ-45: Turn-Wasserstand zum Reanimations-Zeitpunkt merken.

        Das Budget gilt erst dann als „durch echten Fortschritt verdient zurückzusetzen",
        wenn ``num_turns`` diesen Stand übersteigt (neuer Turn nach dem Replay), nicht
        schon durch das kurzzeitige Assistenten-Output des Transkript-Abspiels."""
        self.progress_watermark = turns

    def reset(self) -> None:
        """Echter Fortschritt nach einem Hänger / manueller Eingriff → frisches Budget.

        Lässt ``last_result`` bewusst stehen (die UI zeigt „läuft wieder" weiter, bis
        ein neuer Versuch es überschreibt)."""
        self.auto_attempts = 0
        self.next_attempt_at = 0.0
        self.progress_watermark = 0  # PROJ-45: stale Wasserstand verwerfen (Budget frisch).
