"""Provider-Budget-Quoten — UI-editierbare Schnappschüsse für PROJ-52.

Die providerseitigen 5h-/Wochen-Kontingente von Claude/Codex sind nicht stabil und
maschinenlesbar abrufbar (Claudes ``/usage`` zählt z. B. **alle** Geräte + claude.ai,
nicht nur die lokalen Jupiter-Sessions). Eine lokale Token-Schätzung kann diese Zahlen
darum nicht reproduzieren. Stattdessen pflegt der Nutzer pro Provider/Fenster einen
**Schnappschuss** (Prozent + Reset-Zeitpunkt) in den Einstellungen; die Sidebar zeigt
genau diese Werte und markiert sie automatisch als *veraltet*, sobald der Reset-Zeitpunkt
überschritten ist (Prompt zum Nachtragen).

Die Konfiguration lebt — analog ``WatchdogStore`` / ``LivenessStore`` — in einer YAML-
Datei, die **live** (mtime-gecacht) gelesen und über ``GET/PUT /settings/provider-budgets``
gepflegt wird. Ein leeres Feld (``None``) bedeutet bewusst „unbekannt" → die Sidebar zeigt
für dieses Fenster ``n/v`` statt eines erfundenen Werts (keine falsche Präzision).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import yaml

from ..config import settings

log = logging.getLogger(__name__)

# Provider × Fenster → zwei Felder je Kombination: Prozent + Reset-Zeitpunkt (ISO 8601).
_PCT_FIELDS: tuple[str, ...] = (
    "claude_5h_pct",
    "claude_week_pct",
    "codex_5h_pct",
    "codex_week_pct",
)
_RESET_FIELDS: tuple[str, ...] = (
    "claude_5h_reset_at",
    "claude_week_reset_at",
    "codex_5h_reset_at",
    "codex_week_reset_at",
)

# Eingebauter Default: alles leer → ehrliches „n/v", bis der Nutzer reale Zahlen einträgt.
DEFAULTS: dict = {k: None for k in (*_PCT_FIELDS, *_RESET_FIELDS)}


def _parse_iso(value: object) -> datetime:
    """ISO-8601 strikt parsen (``Z`` erlaubt). Wirft ``ValueError`` bei Unsinn."""
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _validate(data: object, *, strict: bool = False) -> dict:
    """Mischt ``data`` über ``DEFAULTS`` und prüft Typen.

    ``strict=True`` (Save-Pfad): Prozente müssen Zahl ≥ 0 oder leer sein; Reset-Zeiten
    gültiges ISO 8601 oder leer — sonst ``ValueError`` (Route → 400/422). Nicht-strict
    (Lade-Pfad): unbrauchbare Werte fallen still auf ``None`` (eine teildefekte Datei
    killt nie die ganze Anzeige).
    """
    if not isinstance(data, dict):
        raise ValueError("Provider-Budget-Config muss ein Objekt sein.")
    out: dict = {}
    for key in _PCT_FIELDS:
        raw = data.get(key)
        if raw is None or raw == "":
            out[key] = None
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError) as exc:
            if strict:
                raise ValueError(f"{key} muss eine Zahl oder leer sein.") from exc
            out[key] = None
            continue
        if val < 0:
            if strict:
                raise ValueError(f"{key} muss ≥ 0 sein (war {val}).")
            out[key] = None
            continue
        out[key] = val
    for key in _RESET_FIELDS:
        raw = data.get(key)
        if raw is None or raw == "":
            out[key] = None
            continue
        try:
            _parse_iso(raw)
        except (TypeError, ValueError) as exc:
            if strict:
                raise ValueError(f"{key} ist kein gültiger Zeitpunkt (ISO 8601).") from exc
            out[key] = None
            continue
        out[key] = str(raw)
    return out


class ProviderBudgetStore:
    """Liest die Budget-Schnappschüsse aus einer YAML-Datei — live, mtime-gecacht.

    Fehlende Schlüssel werden mit ``DEFAULTS`` (leer) aufgefüllt; eine strukturell
    kaputte Datei fällt komplett auf ``DEFAULTS`` zurück (+ sichtbare Warnung, kein Crash).
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._mtime: float | None = None
        self._values: dict = dict(DEFAULTS)
        self._source: str = "default"
        self._warning: str | None = None
        self._loaded_once = False

    def _reload_if_changed(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            if self._source != "default" or not self._loaded_once:
                self._values = dict(DEFAULTS)
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
            self._values = _validate(data)
            self._source = self._path
            self._warning = None
        except (OSError, ValueError, yaml.YAMLError) as exc:
            log.warning(
                "Provider-Budget-Config %s ungültig: %s — Fallback auf leer (n/v).",
                self._path,
                exc,
            )
            self._values = dict(DEFAULTS)
            self._source = "default"
            self._warning = f"Provider-Budget-Config ungültig ({exc})"

    def values(self) -> dict:
        """Aktuelle Schnappschüsse (live aus der Datei)."""
        self._reload_if_changed()
        return dict(self._values)

    def snapshot(self) -> dict:
        """Werte + Herkunft/Warnung für die Settings-API (GET /settings/provider-budgets)."""
        self._reload_if_changed()
        return {
            **self._values,
            "source": self._source,
            "warning": self._warning,
            "refresh_minutes": max(1, int(settings.provider_budget_refresh_minutes)),
        }

    def save(self, payload: dict) -> dict:
        """Werte validieren + nach YAML schreiben → beim nächsten Zugriff live aktiv."""
        validated = _validate(payload, strict=True)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(validated, fh, allow_unicode=True, sort_keys=False)
        self._loaded_once = False  # nächster Zugriff lädt frisch (Live-Reload).
        return self.snapshot()


# Modul-Singleton — eine Budget-Config pro Backend-Prozess (live aus der Datei).
provider_budget_store = ProviderBudgetStore(settings.provider_budgets_config_path)
