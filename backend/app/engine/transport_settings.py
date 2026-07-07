"""Transport-Konfiguration (PROJ-63) — globaler Default `direct`/`tmux` + optionale
Engine-Overrides, YAML-backed und live mtime-geprüft — dasselbe Muster wie
``liveness.py``/``watchdog.py`` (siehe dort für die Begründung: Datei-first, kein
DB-Zwang, sofort wirksam ohne Neustart).

Bewusst konservativ: der eingebaute Default ist immer ``direct`` (Spec-Vorgabe —
"Default bleibt bis nach erfolgreichem Spike konservativ direct"), auch wenn die
Konfigurationsdatei fehlt oder kaputt ist.
"""
from __future__ import annotations

import logging
import os

import yaml

from ..config import settings
from .transport import tmux_available

log = logging.getLogger(__name__)

VALID_TRANSPORTS: tuple[str, ...] = ("direct", "tmux")

DEFAULTS: dict = {
    "default_transport": "direct",
    "engine_overrides": {},  # z. B. {"codex": "tmux"}
}


def _validate(data: object, *, strict: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Transport-Config muss ein Objekt sein.")

    default_transport = data.get("default_transport", DEFAULTS["default_transport"])
    if default_transport not in VALID_TRANSPORTS:
        if strict:
            raise ValueError(
                f"default_transport muss einer von {VALID_TRANSPORTS} sein (war '{default_transport}')."
            )
        default_transport = DEFAULTS["default_transport"]

    raw_overrides = data.get("engine_overrides", {})
    if not isinstance(raw_overrides, dict):
        if strict:
            raise ValueError("engine_overrides muss ein Objekt (Engine-Key -> Transport) sein.")
        raw_overrides = {}

    overrides: dict[str, str] = {}
    for key, value in raw_overrides.items():
        if value not in VALID_TRANSPORTS:
            if strict:
                raise ValueError(
                    f"engine_overrides['{key}'] muss einer von {VALID_TRANSPORTS} sein (war '{value}')."
                )
            continue  # nicht-strict (Lade-Pfad): ungültigen Eintrag stillschweigend verwerfen
        overrides[str(key)] = value

    return {"default_transport": default_transport, "engine_overrides": overrides}


class TransportStore:
    """Liest die Transport-Konfiguration aus einer YAML-Datei — live, mtime-gecacht."""

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
            log.warning("Transport-Config %s ungültig: %s — Fallback auf Default 'direct'.", self._path, exc)
            self._config = dict(DEFAULTS)
            self._source = "default"
            self._warning = f"Transport-Config ungültig ({exc})"

    def config(self) -> dict:
        """Aktuelle Config (live aus der Datei): ``default_transport`` + ``engine_overrides``."""
        self._reload_if_changed()
        return dict(self._config)

    def resolve(self, engine_key: str | None) -> str:
        """Effektiver Transport für eine Engine: Override, sonst globaler Default.

        Liefert IMMER ``"direct"``, wenn tmux auf diesem Host nicht verfügbar ist —
        eine konfigurierte "tmux"-Wahl darf niemals zu einem Startfehler führen,
        solange der Betreiber das Binary nicht installiert hat (klarer Fallback
        statt Crash, siehe Akzeptanzkriterium "fehlendes tmux -> klare Meldung")."""
        cfg = self.config()
        wanted = cfg["engine_overrides"].get(engine_key, cfg["default_transport"]) if engine_key else cfg["default_transport"]
        if wanted == "tmux" and not tmux_available(settings.tmux_bin):
            return "direct"
        return wanted

    def snapshot(self) -> dict:
        """Für GET /settings/transports: Config + Herkunft/Warnung + tmux-Verfügbarkeit."""
        self._reload_if_changed()
        return {
            **self._config,
            "source": self._source,
            "warning": self._warning,
            "tmux_available": tmux_available(settings.tmux_bin),
        }

    def save(self, payload: dict) -> dict:
        """Config validieren + nach YAML schreiben → beim nächsten Zugriff live aktiv."""
        validated = _validate(payload, strict=True)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(validated, fh, allow_unicode=True, sort_keys=False)
        self._loaded_once = False
        return self.snapshot()


# Modul-Singleton — eine Transport-Config pro Backend-Prozess (live aus der Datei).
transport_store = TransportStore(settings.transport_config_path)
