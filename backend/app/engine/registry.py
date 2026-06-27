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

import contextlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from urllib.parse import urlparse

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
    enabled: bool = True
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

    def to_settings(self) -> dict:
        """Bearbeitbarer Settings-Auszug. Enthält Config-Felder, aber nie Secret-Werte."""
        data = self.to_read()
        data.update(
            {
                "enabled": self.enabled,
                "context_window": self.context_window if self.kind == ENGINE else None,
                "auth_env": self.auth_env if self.kind == ENGINE else None,
                "api_base": self.api_base if self.kind == ENGINE and self.driver == DRIVER_OPENAI else None,
                "api_path": self.api_path if self.kind == ENGINE and self.driver == DRIVER_OPENAI else None,
                # CLI-Spezialfelder werden für bestehende Profile roundtrip-fähig gehalten;
                # das Frontend kann sie read-only anzeigen, ohne Secrets offenzulegen.
                "bin": self.bin if self.kind == ENGINE and self.driver == DRIVER_GENERIC_CLI else None,
                "argv_template": list(self.argv_template) if self.kind == ENGINE and self.driver == DRIVER_GENERIC_CLI else [],
                "resume_argv_template": (
                    list(self.resume_argv_template)
                    if self.kind == ENGINE and self.driver == DRIVER_GENERIC_CLI
                    else []
                ),
                "adapter": self.adapter if self.kind == ENGINE and self.driver == DRIVER_GENERIC_CLI else None,
                "prompt_via": self.prompt_via if self.kind == ENGINE and self.driver == DRIVER_GENERIC_CLI else None,
                "input_format": self.input_format if self.kind == ENGINE and self.driver == DRIVER_GENERIC_CLI else None,
                "oneshot": self.oneshot if self.kind == ENGINE and self.driver == DRIVER_GENERIC_CLI else None,
            }
        )
        return data


def _builtin_claude(default_model: str | None = None) -> EngineProfile:
    """Die immer vorhandene Claude-Engine (Default, PROJ-1)."""
    model = default_model or settings.default_model
    if model not in VALID_MODELS:
        model = settings.default_model
    return EngineProfile(
        key=CLAUDE_KEY,
        label="Claude Max",
        kind=ENGINE,
        driver=DRIVER_CLAUDE,
        models=sorted(VALID_MODELS),
        default_model=model,
        context_window=DEFAULT_CONTEXT_WINDOW,
        # PROJ-50: „abc" = Engine kann den abc-Workflow fahren. Claude über den
        # PreToolUse-Skill-Hook, Codex über Launcher-Seeding + file_change-Stream.
        capabilities=["usage", "resume", "multi_turn", "tools", "abc"],
    )


def _sandbox_from_argv(argv_template: list[str]) -> str | None:
    """Liest die Sandbox-Policy aus einem ``-s``/``--sandbox <wert>``-Flag im argv.

    Reine Funktion; ``None``, wenn kein Flag (oder kein Folge-Wert) vorhanden. So zeigt
    GET /engines bei generic_cli-Engines (z. B. Codex `-s workspace-write`) die Leitplanke
    an, ohne ein redundantes Config-Feld neben dem argv zu pflegen.
    """
    for i, tok in enumerate(argv_template):
        if tok in ("-s", "--sandbox") and i + 1 < len(argv_template):
            value = str(argv_template[i + 1]).strip()
            # Platzhalter (z. B. „{model}") sind keine Policy.
            if value and not value.startswith("{"):
                return value
    return None


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
    prof.enabled = bool(entry.get("enabled", True))

    if kind == ENGINE:
        driver = str(entry.get("driver") or DRIVER_GENERIC_CLI).strip()
        if driver not in VALID_DRIVERS:
            raise ValueError(f"Engine „{key}“: unbekannter driver „{driver}“.")
        prof.driver = driver
        prof.models = [str(m) for m in (entry.get("models") or [])]
        prof.default_model = entry.get("default_model") or (prof.models[0] if prof.models else None)
        prof.context_window = int(entry.get("context_window") or DEFAULT_CONTEXT_WINDOW)
        if prof.context_window <= 0:
            raise ValueError(f"Engine „{key}“: context_window muss > 0 sein.")
        prof.capabilities = [str(c) for c in (entry.get("capabilities") or [])]
        prof.auth_env = entry.get("auth_env")
        if prof.default_model and prof.models and prof.default_model not in prof.models:
            raise ValueError(
                f"Engine „{key}“: default_model muss in models enthalten sein."
            )
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
            # PROJ-48: Sandbox-Policy aus dem argv (`-s`/`--sandbox <wert>`) ableiten, damit
            # sie in `to_read()` (GET /engines) als Badge sichtbar wird — EINE Quelle der
            # Wahrheit bleibt das argv (was real läuft), kein zweites Config-Feld.
            prof.sandbox = _sandbox_from_argv(prof.argv_template)
        elif driver == DRIVER_OPENAI:
            prof.api_base = str(entry.get("api_base") or "https://api.openai.com").rstrip("/")
            prof.api_path = str(entry.get("api_path") or "/v1/chat/completions")
            prof.auth_env = entry.get("auth_env") or "OPENAI_API_KEY"
            _validate_openai_profile(prof)
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


def _looks_like_secret(value: str) -> bool:
    low = value.lower()
    return (
        value.startswith(("sk-", "sk_", "pat_", "eyJ"))
        or "api-key" in low
        or (len(value) > 48 and any(ch.isdigit() for ch in value))
    )


def _validate_auth_env(value: str | None, *, key: str) -> None:
    if not value:
        raise ValueError(f"Engine „{key}“: auth_env fehlt.")
    if _looks_like_secret(value):
        raise ValueError(
            f"Engine „{key}“: auth_env darf kein API-Key-Wert sein, nur der Name der Umgebungsvariable."
        )
    if not value.replace("_", "A").isalnum() or value[0].isdigit():
        raise ValueError(f"Engine „{key}“: auth_env muss ein Variablenname sein.")


def _validate_openai_profile(prof: EngineProfile) -> None:
    _validate_auth_env(prof.auth_env, key=prof.key)
    parsed = urlparse(prof.api_base)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"Engine „{prof.key}“: api_base muss eine https-URL sein.")
    if not prof.api_path.startswith("/"):
        raise ValueError(f"Engine „{prof.key}“: api_path muss mit / beginnen.")


def _profile_to_yaml(prof: EngineProfile) -> dict:
    """Serialisiert ein Profil stabil und menschenlesbar nach engines.yaml."""
    data: dict = {
        "key": prof.key,
        "label": prof.label,
        "kind": prof.kind,
    }
    if not prof.enabled:
        data["enabled"] = False
    if prof.kind == ENGINE:
        data["driver"] = prof.driver
        if prof.auth_env:
            data["auth_env"] = prof.auth_env
        if prof.models:
            data["models"] = list(prof.models)
        if prof.default_model:
            data["default_model"] = prof.default_model
        if prof.context_window != DEFAULT_CONTEXT_WINDOW:
            data["context_window"] = prof.context_window
        if prof.capabilities:
            data["capabilities"] = list(prof.capabilities)
        if prof.driver == DRIVER_OPENAI:
            data["api_base"] = prof.api_base
            data["api_path"] = prof.api_path
        elif prof.driver == DRIVER_GENERIC_CLI:
            if prof.bin:
                data["bin"] = prof.bin
            if prof.argv_template:
                data["argv_template"] = list(prof.argv_template)
            if prof.resume_argv_template:
                data["resume_argv_template"] = list(prof.resume_argv_template)
            data["adapter"] = prof.adapter
            data["prompt_via"] = prof.prompt_via
            data["input_format"] = prof.input_format
            if prof.oneshot:
                data["oneshot"] = True
    elif prof.kind == IFRAME:
        data["url"] = prof.url
        if prof.sandbox:
            data["sandbox"] = prof.sandbox
    elif prof.kind == LAUNCH:
        data["target"] = prof.target
    if prof.group:
        data["group"] = prof.group
    if prof.icon:
        data["icon"] = prof.icon
    return data


def _default_swisscom_profile() -> EngineProfile:
    return EngineProfile(
        key="swisscom",
        label="Swisscom",
        kind=ENGINE,
        driver=DRIVER_OPENAI,
        models=[],
        default_model=None,
        context_window=128_000,
        capabilities=["usage", "multi_turn"],
        auth_env="SWISSCOM_API_KEY",
        api_base="https://api.swisscom.com",
        api_path="/v1/chat/completions",
        enabled=False,
    )


class EngineRegistry:
    """Lädt die Engine-Profile aus YAML — live, mtime-gecacht; Claude immer dabei."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._mtime: float | None = None
        self._profiles: dict[str, EngineProfile] = {CLAUDE_KEY: _builtin_claude()}
        self._warning: str | None = None
        self._source: str = "default"
        self._loaded_once = False
        self._claude_default_model: str | None = None

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
                self._claude_default_model = None
            return
        if self._loaded_once and mtime == self._mtime:
            return
        self._parse_file(mtime)

    def _parse_file(self, mtime: float) -> None:
        self._loaded_once = True
        self._mtime = mtime
        profiles: dict[str, EngineProfile] = {}
        warnings: list[str] = []
        claude_default: str | None = None
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if isinstance(data, dict):
                raw_claude = data.get("claude") or {}
                if isinstance(raw_claude, dict):
                    raw_model = raw_claude.get("default_model")
                    if raw_model:
                        if str(raw_model) in VALID_MODELS:
                            claude_default = str(raw_model)
                        else:
                            warnings.append(
                                f"Claude: unbekanntes default_model „{raw_model}“."
                            )
            profiles[CLAUDE_KEY] = _builtin_claude(claude_default)
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
            profiles = {CLAUDE_KEY: _builtin_claude()}
            claude_default = None
        self._profiles = profiles
        self._claude_default_model = claude_default
        self._warning = "; ".join(warnings) or None

    def get(self, key: str | None, *, include_disabled: bool = False) -> EngineProfile | None:
        self._reload_if_changed()
        if not key:
            return self._profiles.get(CLAUDE_KEY)
        prof = self._profiles.get(key)
        if prof is not None and not prof.enabled and not include_disabled:
            return None
        return prof

    def require(self, key: str | None) -> EngineProfile:
        prof = self.get(key)
        if prof is None:
            raise KeyError(key or "")
        return prof

    def all(self) -> list[EngineProfile]:
        self._reload_if_changed()
        # Claude zuerst (Default), dann die konfigurierten in Einfügereihenfolge.
        rest = [
            p for k, p in self._profiles.items()
            if k != CLAUDE_KEY and p.enabled
        ]
        return [self._profiles[CLAUDE_KEY], *rest]

    def all_settings(self) -> list[EngineProfile]:
        self._reload_if_changed()
        profiles = [self._profiles[CLAUDE_KEY]]
        seen = {CLAUDE_KEY}
        for key in ("openai", "openrouter", "swisscom"):
            prof = self._profiles.get(key)
            if prof is None and key == "swisscom":
                prof = _default_swisscom_profile()
            if prof is not None:
                profiles.append(prof)
                seen.add(key)
        profiles.extend(p for k, p in self._profiles.items() if k not in seen)
        return profiles

    def snapshot(self) -> dict:
        return {
            "engines": [p.to_read() for p in self.all()],
            "source": self._source,
            "warning": self._warning,
        }

    def settings_snapshot(self) -> dict:
        return {
            "engines": [p.to_settings() for p in self.all_settings()],
            "source": self._source,
            "warning": self._warning,
        }

    def validate_settings(self, payload: dict) -> dict:
        profiles, claude_default = self._profiles_from_settings_payload(payload)
        warnings = self._settings_warnings(profiles)
        return {
            "valid": True,
            "warnings": warnings,
            "engines": [
                p.to_settings()
                for p in self._ordered_settings_profiles(profiles, claude_default)
            ],
        }

    def save_settings(self, payload: dict) -> dict:
        profiles, claude_default = self._profiles_from_settings_payload(payload)
        data: dict = {}
        if claude_default:
            data["claude"] = {"default_model": claude_default}
        data["engines"] = [
            _profile_to_yaml(p)
            for p in self._ordered_yaml_profiles(profiles)
        ]
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=".engines.", suffix=".yaml.tmp", dir=os.path.dirname(self._path)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
            os.replace(tmp, self._path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
        self._loaded_once = False
        return self.settings_snapshot()

    def _profiles_from_settings_payload(
        self, payload: dict
    ) -> tuple[dict[str, EngineProfile], str | None]:
        if not isinstance(payload, dict):
            raise ValueError("Engine-Einstellungen müssen ein Objekt sein.")
        raw_engines = payload.get("engines")
        if not isinstance(raw_engines, list):
            raise ValueError("engines muss eine Liste sein.")
        profiles: dict[str, EngineProfile] = {}
        claude_default: str | None = None
        for raw in raw_engines:
            if not isinstance(raw, dict):
                raise ValueError("Engine-Eintrag muss ein Objekt sein.")
            key = str(raw.get("key") or "").strip()
            if key == CLAUDE_KEY:
                model = str(raw.get("default_model") or settings.default_model).strip()
                if model not in VALID_MODELS:
                    raise ValueError(
                        f"Claude: Unbekanntes Modell '{model}'. Erlaubt: {sorted(VALID_MODELS)}."
                    )
                claude_default = model
                continue
            prof = _coerce_profile(raw)
            if prof.kind == ENGINE and prof.enabled and not prof.models:
                raise ValueError(f"Engine „{prof.key}“: aktive Engines brauchen mindestens ein Modell.")
            if prof.key in profiles:
                raise ValueError(f"Engine „{prof.key}“ ist doppelt vorhanden.")
            profiles[prof.key] = prof
        if "swisscom" not in profiles:
            profiles["swisscom"] = _default_swisscom_profile()
        return profiles, claude_default

    @staticmethod
    def _ordered_yaml_profiles(profiles: dict[str, EngineProfile]) -> list[EngineProfile]:
        priority = {"openai": 0, "openrouter": 1, "swisscom": 2, "codex": 10, "ollama": 11}
        return sorted(profiles.values(), key=lambda p: (priority.get(p.key, 50), p.key))

    def _ordered_settings_profiles(
        self, profiles: dict[str, EngineProfile], claude_default: str | None
    ) -> list[EngineProfile]:
        return [_builtin_claude(claude_default), *self._ordered_yaml_profiles(profiles)]

    @staticmethod
    def _settings_warnings(profiles: dict[str, EngineProfile]) -> list[str]:
        warnings: list[str] = []
        for prof in profiles.values():
            if prof.kind == ENGINE and prof.enabled:
                available, reason = prof.availability()
                if not available and reason:
                    warnings.append(f"{prof.label}: {reason}")
        return warnings


# Modul-Singleton — eine Registry pro Backend-Prozess (live aus der Datei).
engine_registry = EngineRegistry(settings.engines_config_path)
