"""Persistenter Einstellungen-Speicher für Hermes-Kanban (PROJ-82).

Einziges neues persistiertes Stück der nativen Hermes-Kanban-Ansicht: das
Board-Polling-Intervall (Sekunden, 5–60, Default 10). Gleiches Muster wie
``watchdog.WatchdogStore`` — YAML-Datei, live (mtime-gecacht), Default-Fallback,
übersteht Backend-Neustarts.
"""
from __future__ import annotations

import logging
import os
import time

import yaml

from ..config import settings

log = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 10
_MIN_INTERVAL = 5
_MAX_INTERVAL = 60


class HermesKanbanStore:
    """Liest/schreibt das Polling-Intervall aus ``hermes_kanban.yaml`` (live)."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._mtime: float | None = None
        self._value: int = DEFAULT_POLL_INTERVAL
        self._source: str = "default"
        self._warning: str | None = None
        self._loaded_once = False

    def _reload_if_changed(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            if self._source != "default" or not self._loaded_once:
                self._value = DEFAULT_POLL_INTERVAL
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
            raw = int(data.get("poll_interval_seconds", DEFAULT_POLL_INTERVAL))
        except (OSError, ValueError, yaml.YAMLError) as exc:
            log.warning("hermes_kanban.yaml ungültig: %s — Fallback auf Default.", exc)
            self._value = DEFAULT_POLL_INTERVAL
            self._source = "default"
            self._warning = f"hermes_kanban.yaml ungültig ({exc})"
            return
        self._value = min(max(raw, _MIN_INTERVAL), _MAX_INTERVAL)
        self._source = self._path
        self._warning = None

    def snapshot(self) -> dict:
        self._reload_if_changed()
        return {
            "poll_interval_seconds": self._value,
            "source": self._source,
            "warning": self._warning,
        }

    def save(self, value: int) -> dict:
        if not _MIN_INTERVAL <= value <= _MAX_INTERVAL:
            raise ValueError(f"Intervall muss zwischen {_MIN_INTERVAL} und {_MAX_INTERVAL} Sekunden liegen.")
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            yaml.safe_dump({"poll_interval_seconds": value}, fh, allow_unicode=True, sort_keys=False)
        self._loaded_once = False  # nächster Zugriff lädt frisch (Live-Reload).
        time.sleep(0)  # Vorbereitet für späteren Cache-Invalidate.
        return self.snapshot()


hermes_kanban_store = HermesKanbanStore(settings.hermes_kanban_config_path)
