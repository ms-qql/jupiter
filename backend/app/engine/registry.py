"""Engine-Registry (PROJ-18) — zentrale, codefreie Konfiguration weiterer Engines.

Drei Integrations-Tiefen, eine Registry (vgl. Tech-Design PROJ-18):

- ``kind: engine``  — eine **steuerbare Session** (Treiber-Tiefe). Welcher Treiber sie
  fährt, sagt ``driver``: ``claude`` (eingebaut), ``generic_cli`` (fremde CLI per
  ``argv_template`` + Strom-``adapter``) oder ``openai`` (HTTP-API, Key aus ``auth_env``).
- ``kind: iframe``  — eine fremde Web-App, eingebettet (``url``). Kein Session-Lifecycle.
- ``kind: launch``  — ein externer Startknopf (``target``). Kein Session-Lifecycle.

Geladen wird aus ``engines.yaml`` (live, mtime-gecacht — gleiches Muster wie
``WatchdogStore``/``PolicyStore``). Die eingebaute **Claude-Engine ist IMMER da**,
auch ohne Datei → rückwärtskompatibel zu PROJ-1. Eine fehlende/kaputte Datei
degradiert auf „nur Claude" (+ Warnung), statt zu crashen.

Secrets (API-Keys) stehen NIE in dieser Datei — nur der **Name** der Env-Variable
(``auth_env``); den Wert liest der Treiber serverseitig aus der Umgebung.
"""
from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field

import yaml

from ..config import VALID_MODELS, settings
from .adapters import VALID_ADAPTERS

log = logging.getLogger(__name__)

ENGINE, IFRAME, LAUNCH = "engine", "iframe", "launch"
# PROJ-40: ``kind: native`` — eine nativ in Jupiter programmierte Micro-App. Kein
# Session-Lifecycle, keine url/target: der Code lebt im Frontend (microapps-registry.ts),
# verknüpft per ``key``; die Registry trägt nur die Metadaten (label/icon/group).
NATIVE = "native"
VALID_KINDS: frozenset[str] = frozenset({ENGINE, IFRAME, LAUNCH, NATIVE})

# Treiber-Arten für ``kind: engine``.
DRIVER_CLAUDE, DRIVER_GENERIC_CLI, DRIVER_OPENAI = "claude", "generic_cli", "openai"
VALID_DRIVERS: frozenset[str] = frozenset({DRIVER_CLAUDE, DRIVER_GENERIC_CLI, DRIVER_OPENAI})

# Schlüssel der eingebauten Claude-Engine (Default; bleibt ohne Config bestehen).
CLAUDE_KEY = "claude"

DEFAULT_CONTEXT_WINDOW = 200_000


@dataclass
class EngineProfile:
    """Ein Registry-Eintrag. Je nach ``kind``/``driver`` sind andere Felder relevant."""

    key: str
    label: str
    kind: str = ENGINE
    # kind == engine:
    driver: str = DRIVER_CLAUDE
    models: list[str] = field(default_factory=list)
    default_model: str | None = None
    context_window: int = DEFAULT_CONTEXT_WINDOW
    capabilities: list[str] = field(default_factory=list)
    auth_env: str | None = None
    # driver == generic_cli:
    bin: str | None = None
    argv_template: list[str] = field(default_factory=list)
    # PROJ-48: optionales argv für Folge-Turns einer oneshot-CLI (Resume-Pfad). Leer =
    # keine Fortsetzung möglich (Verhalten wie bisher: Re-Spawn ohne Kontext). Generisch
    # für jede oneshot-CLI mit Resume — Platzhalter zusätzlich: {resume_id}.
    resume_argv_template: list[str] = field(default_factory=list)
    adapter: str = "plaintext"
    prompt_via: str = "stdin"        # "stdin" | "arg"
    input_format: str = "text"       # "stream_json" | "text"
    oneshot: bool = False            # stdin nach Eingabe schließen (Single-Turn-CLIs)
    # driver == openai:
    api_base: str = "https://api.openai.com"
    api_path: str = "/v1/chat/completions"
    # kind == iframe:
    url: str | None = None
    sandbox: str | None = None
    # kind == launch:
    target: str | None = None
    # PROJ-39: Gruppierung (z. B. "orchestration" | "micro") + optionales Sidebar-Icon
    # (lucide-Name). Trennt Orchestration-Apps (PROJ-39) von Micro-Apps (PROJ-40);
    # das Frontend filtert die Engine-Liste clientseitig auf `group`.
    group: str | None = None
    icon: str | None = None

    @property
    def is_claude(self) -> bool:
        return self.kind == ENGINE and self.driver == DRIVER_CLAUDE

    @property
    def is_session_engine(self) -> bool:
        """Treiber-Tiefe: erzeugt eine steuerbare Session (≠ iframe/launch)."""
        return self.kind == ENGINE

    def has_capability(self, cap: str) -> bool:
        return cap in self.capabilities

    # --- Verfügbarkeit (für GET /engines + Start-Vorprüfung) ----------------

    def availability(self) -> tuple[bool, str | None]:
        """``(verfügbar, grund_wenn_nicht)`` — Frontend graut aus statt zu crashen."""
        if self.kind in (IFRAME, LAUNCH, NATIVE):
            return True, None
        if self.driver == DRIVER_CLAUDE:
            if shutil.which(settings.claude_bin) is None:
                return False, "Claude-CLI nicht gefunden (`claude` installiert/eingeloggt?)."
            return True, None
        if self.driver == DRIVER_GENERIC_CLI:
            # Binary = explizites `bin` ODER (fehlt es) das erste argv_template-Element —
            # konsistent mit ``_coerce_profile`` (bin ODER argv_template genügt) und
            # ``build_generic_argv`` (nimmt argv_template[0] als Programm, wenn kein bin).
            cli = self.bin or (self.argv_template[0] if self.argv_template else None)
            if not cli or shutil.which(cli) is None:
                return False, f"CLI „{cli or '?'}“ nicht im PATH gefunden."
            if self.auth_env and not os.environ.get(self.auth_env):
                return False, f"Umgebungsvariable {self.auth_env} fehlt (Key/Login)."
            return True, None
        if self.driver == DRIVER_OPENAI:
            if not self.auth_env or not os.environ.get(self.auth_env):
                env = self.auth_env or "OPENAI_API_KEY"
                return False, f"API-Key fehlt — {env} in der Server-Umgebung setzen."
            return True, None
        return False, "Unbekannter Treiber."

    def valid_model(self, model: str) -> bool:
        """Akzeptiert das Profil dieses Modell? Leere ``models`` = alles erlauben."""
        if not self.models:
            return True
        return model in self.models

    def to_read(self) -> dict:
        """Engine-agnostischer Auszug für GET /engines (keine Secrets, kein argv)."""
        available, reason = self.availability()
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "driver": self.driver if self.kind == ENGINE else None,
            "available": available,
            "unavailable_reason": reason,
            "models": list(self.models),
            "default_model": self.default_model,
            "capabilities": list(self.capabilities),
            "url": self.url,
            "sandbox": self.sandbox,
            "target": self.target,
            "group": self.group,
            "icon": self.icon,
        }


def _builtin_claude() -> EngineProfile:
    """Die immer vorhandene Claude-Engine (Default, PROJ-1)."""
    return EngineProfile(
        key=CLAUDE_KEY,
        label="Claude Max",
        kind=ENGINE,
        driver=DRIVER_CLAUDE,
        models=sorted(VALID_MODELS),
        default_model=settings.default_model,
        context_window=DEFAULT_CONTEXT_WINDOW,
        capabilities=["usage", "resume", "multi_turn", "tools"],
    )


def _coerce_profile(entry: dict) -> EngineProfile:
    """Baut ein ``EngineProfile`` aus einem YAML-Eintrag; wirft ``ValueError`` bei Unsinn."""
    if not isinstance(entry, dict):
        raise ValueError("Engine-Eintrag muss ein Objekt sein.")
    key = str(entry.get("key") or "").strip()
    if not key:
        raise ValueError("Engine-Eintrag ohne `key`.")
    if key == CLAUDE_KEY:
        raise ValueError("Schlüssel `claude` ist reserviert (eingebaute Engine).")
    kind = str(entry.get("kind") or ENGINE).strip()
    if kind not in VALID_KINDS:
        raise ValueError(f"Engine „{key}“: unbekanntes kind „{kind}“.")

    prof = EngineProfile(key=key, label=str(entry.get("label") or key), kind=kind)

    if kind == ENGINE:
        driver = str(entry.get("driver") or DRIVER_GENERIC_CLI).strip()
        if driver not in VALID_DRIVERS:
            raise ValueError(f"Engine „{key}“: unbekannter driver „{driver}“.")
        prof.driver = driver
        prof.models = [str(m) for m in (entry.get("models") or [])]
        prof.default_model = entry.get("default_model") or (prof.models[0] if prof.models else None)
        prof.context_window = int(entry.get("context_window") or DEFAULT_CONTEXT_WINDOW)
        prof.capabilities = [str(c) for c in (entry.get("capabilities") or [])]
        prof.auth_env = entry.get("auth_env")
        if driver == DRIVER_GENERIC_CLI:
            prof.bin = entry.get("bin")
            prof.argv_template = [str(a) for a in (entry.get("argv_template") or [])]
            prof.resume_argv_template = [
                str(a) for a in (entry.get("resume_argv_template") or [])
            ]
            adapter = str(entry.get("adapter") or "plaintext")
            if adapter not in VALID_ADAPTERS:
                raise ValueError(f"Engine „{key}“: unbekannter adapter „{adapter}“.")
            prof.adapter = adapter
            prof.prompt_via = str(entry.get("prompt_via") or "stdin")
            prof.input_format = str(entry.get("input_format") or "text")
            prof.oneshot = bool(entry.get("oneshot", False))
            if not prof.bin and not prof.argv_template:
                raise ValueError(f"Engine „{key}“: generic_cli braucht `bin` oder `argv_template`.")
        elif driver == DRIVER_OPENAI:
            prof.api_base = str(entry.get("api_base") or "https://api.openai.com").rstrip("/")
            prof.api_path = str(entry.get("api_path") or "/v1/chat/completions")
            prof.auth_env = entry.get("auth_env") or "OPENAI_API_KEY"
            if "usage" not in prof.capabilities:
                prof.capabilities.append("usage")
    elif kind == IFRAME:
        prof.url = entry.get("url")
        prof.sandbox = entry.get("sandbox")
        if not prof.url:
            raise ValueError(f"iFrame-Engine „{key}“: `url` fehlt.")
    elif kind == LAUNCH:
        prof.target = entry.get("target")
        if not prof.target:
            raise ValueError(f"Launch-Engine „{key}“: `target` fehlt.")
    elif kind == NATIVE:
        # PROJ-40: keine Backend-Pflichtfelder — der Code liegt im Frontend
        # (microapps-registry.ts), verknüpft per `key`. Nur Metadaten (group/icon).
        pass

    # PROJ-39: optionale Gruppierung + Sidebar-Icon (kind-unabhängig, v. a. für iframe).
    group = entry.get("group")
    prof.group = str(group).strip() if group else None
    icon = entry.get("icon")
    prof.icon = str(icon).strip() if icon else None
    return prof


class EngineRegistry:
    """Lädt die Engine-Profile aus YAML — live, mtime-gecacht; Claude immer dabei."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._mtime: float | None = None
        self._profiles: dict[str, EngineProfile] = {CLAUDE_KEY: _builtin_claude()}
        self._warning: str | None = None
        self._source: str = "default"
        self._loaded_once = False

    def _reload_if_changed(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            if self._source != "default" or not self._loaded_once:
                self._profiles = {CLAUDE_KEY: _builtin_claude()}
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
        profiles: dict[str, EngineProfile] = {CLAUDE_KEY: _builtin_claude()}
        warnings: list[str] = []
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            entries = data.get("engines") if isinstance(data, dict) else None
            for entry in entries or []:
                try:
                    prof = _coerce_profile(entry)
                except ValueError as exc:  # einzelner Eintrag defekt → überspringen, Rest lädt.
                    warnings.append(str(exc))
                    log.warning("Engine-Registry: Eintrag übersprungen — %s", exc)
                    continue
                profiles[prof.key] = prof
            self._source = self._path
        except (OSError, yaml.YAMLError) as exc:
            log.warning("Engine-Registry %s ungültig: %s — nur Claude.", self._path, exc)
            warnings.append(f"engines.yaml ungültig ({exc})")
            self._source = "default"
        self._profiles = profiles
        self._warning = "; ".join(warnings) or None

    def get(self, key: str | None) -> EngineProfile | None:
        self._reload_if_changed()
        if not key:
            return self._profiles.get(CLAUDE_KEY)
        return self._profiles.get(key)

    def require(self, key: str | None) -> EngineProfile:
        prof = self.get(key)
        if prof is None:
            raise KeyError(key or "")
        return prof

    def all(self) -> list[EngineProfile]:
        self._reload_if_changed()
        # Claude zuerst (Default), dann die konfigurierten in Einfügereihenfolge.
        rest = [p for k, p in self._profiles.items() if k != CLAUDE_KEY]
        return [self._profiles[CLAUDE_KEY], *rest]

    def snapshot(self) -> dict:
        return {
            "engines": [p.to_read() for p in self.all()],
            "source": self._source,
            "warning": self._warning,
        }


# Modul-Singleton — eine Registry pro Backend-Prozess (live aus der Datei).
engine_registry = EngineRegistry(settings.engines_config_path)
