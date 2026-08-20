"""Hermes-Profil-Modellwahl (PROJ-83 Rework) — Erkennung + atomares Schreiben.

Liest zur Laufzeit die auf dem Jupiter-Server verfügbaren Hermes-Profile
(Präfix ``jupiter-`` mit lesbarer ``config.yaml``) und schreibt pro Profil
atomar die gewählte Engine+Modell-Kombination nach ``model.provider`` +
``model.default``.

Die Engine-/Modellwerte stammen ausschließlich aus der bestehenden
Engine-Registry (``GET /engines`` / ``engines.yaml``, PROJ-18/51) — keine
eigene, zweite Modellliste. Die Hin-/Rückübersetzung zwischen dem
Registry-Vokabular (``engine`` + ``model``) und dem ``config.yaml``-Format
(``model.provider`` + ``model.default``) erfolgt zentral hier
(siehe Tech-Design-Nachtrag in ``features/PROJ-83-*.md``).

Es werden bewusst NUR die Felder ``model.provider``/``model.default``
geschrieben; alle übrigen Profilwerte (Secrets, Skills, Tools, ``base_url`` …)
bleiben unangetastet. Secrets/Tokens/Credentials werden nie in die API-Antwort
gespiegelt (Acceptance C).
"""
from __future__ import annotations

import contextlib
import logging
import os
import re
import tempfile

import yaml

from ..config import settings
from .registry import engine_registry

log = logging.getLogger(__name__)

# Ein Profil gilt als abc-Profil, wenn es mit diesem Präfix beginnt.
ABC_PREFIX = "jupiter-"
# Von der Profilerkennung ausgeschlossen (nicht-abc, siehe Spec PROJ-83).
_EXCLUDE = {"jupiter"}
# `default` ist explizit KEIN abc-Profil.
_DEFAULT_PROFILE = "default"

# Erlaubte Engine-Keys für Hermes (Tech-Design-Nachtrag). openai/swisscom/ollama
# und spätere Registry-Engines bleiben ausgeschlossen, bis ein eigener Rework
# ihre Hermes-Abbildung festlegt.
ALLOWED_ENGINES: tuple[str, ...] = ("claude", "codex", "opencode")

# Striktes Format für Profilnamen aus Client-Input: nur `jupiter-` + Kleinbuch-
# staben/Ziffern/`_`/`-`. Schließt `/`, `..`, Absolutpfade und Steuerzeichen aus
# (Verteidigung gegen Path-Traversal im `profile`-Parameter, PROJ-83 BUG-1).
_PROFILE_RE = re.compile(r"^jupiter-[a-z0-9_-]+$")

# Claude-Alias (Registry-Modellwert) → Hermes-`config.yaml`-Modell (provider=anthropic).
CLAUDE_ALIAS_TO_MODEL = {
    "sonnet": "claude-sonnet-5",
    "haiku": "claude-haiku-4.5",
    "opus": "claude-opus-5",
    "fable": "claude-fable-5",
}
CLAUDE_MODEL_TO_ALIAS = {v: k for k, v in CLAUDE_ALIAS_TO_MODEL.items()}
CLAUDE_PROVIDER = "anthropic"
CODEX_PROVIDER = "openai-codex"

# Lesbare, menschennahe Rollenbezeichnung je bekannter abc-Phase (Best-Effort).
_ROLE_LABELS: dict[str, str] = {
    "jupiter-requirements": "Requirements",
    "jupiter-architecture": "Architecture",
    "jupiter-frontend": "Frontend",
    "jupiter-backend": "Backend",
    "jupiter-qa": "QA",
    "jupiter-coordinator": "Koordinator",
    "jupiter-backoffice": "Backoffice",
    "jupiter-document": "Document",
    "jupiter-deploy": "Deploy",
    "jupiter-review": "Review",
}


def _profile_path(profiles_dir: str, name: str) -> str:
    return os.path.join(profiles_dir, name, "config.yaml")


def _role_label(name: str) -> str:
    if name in _ROLE_LABELS:
        return _ROLE_LABELS[name]
    if name.startswith(ABC_PREFIX):
        return name[len(ABC_PREFIX):].capitalize()
    return name


def allowed_engine_models() -> dict[str, list[str]]:
    """Die zur Laufzeit verfügbaren Modelle je erlaubter Engine (aus der Registry).

    Nur Engines mit ``kind == "engine"`` UND ``available == true`` und einem
    erlaubten Key landen hier — exakt die Menge, die das Frontend anbietet.
    """
    out: dict[str, list[str]] = {}
    for key in ALLOWED_ENGINES:
        prof = engine_registry.get(key)
        if prof is None or prof.kind != "engine":
            continue
        available, _ = prof.availability()
        if not available:
            continue
        out[key] = list(prof.models)
    return out


def _forward(engine: str, model: str, allowed: dict[str, list[str]]) -> tuple[str, str]:
    """Engine+Modell (Registry-Vokabular) → (provider, default) für config.yaml.

    Wirft ``ValueError``, wenn die Kombination nicht auswählbar ist.
    """
    models = allowed.get(engine)
    if not models:
        raise ValueError("Unbekannte oder nicht verfügbare Engine.")
    if model not in models:
        raise ValueError(f"Modell '{model}' ist für diese Engine nicht auswählbar.")
    if engine == "claude":
        mapped = CLAUDE_ALIAS_TO_MODEL.get(model)
        if not mapped:
            raise ValueError(f"Modell '{model}' ist für Claude nicht auswählbar.")
        return CLAUDE_PROVIDER, mapped
    if engine == "codex":
        return CODEX_PROVIDER, model
    # opencode: Modellwert ist "anbieter/modell" → provider=Präfix, default=Rest.
    prefix, sep, suffix = model.partition("/")
    if not sep:
        raise ValueError("OpenCode-Modell erwartet das Format 'anbieter/modell'.")
    return prefix, suffix


def _reverse(
    provider: str | None, default: str | None, allowed: dict[str, list[str]]
) -> tuple[str | None, str | None]:
    """config.yaml (provider, default) → (engine, model) aus der Registry.

    Liefert ``(None, None)``, wenn die Kombination keiner bekannten Engine
    zugeordnet werden kann (z. B. außerhalb Jupiters gesetzt → „nicht verfügbar").
    """
    if not provider or not default:
        return None, None
    if provider == CLAUDE_PROVIDER:
        alias = CLAUDE_MODEL_TO_ALIAS.get(default)
        if alias and alias in allowed.get("claude", []):
            return "claude", alias
        return None, None
    if provider == CODEX_PROVIDER:
        if default in allowed.get("codex", []):
            return "codex", default
        return None, None
    # opencode-Stil: provider ist der Präfix-Teil des Modellwerts.
    candidate = f"{provider}/{default}"
    if candidate in allowed.get("opencode", []):
        return "opencode", candidate
    return None, None


def discover_profiles(profiles_dir: str | None = None) -> tuple[list[dict], str | None]:
    """Erkennt alle abc-Profile im Verzeichnis.

    Liefert ``(profile_eintraege, warnung)``. Jeder Eintrag hat die Felder
    ``profile``, ``label``, ``engine``, ``model``, ``provider``, ``default``,
    ``error``. Die Felder ``engine``/``model`` sind die aus der Registry
    rückübersetzte Engine/Modell-Kombination (``None``, wenn nicht auflösbar).
    ``provider``/``default`` sind die Rohwerte aus der ``config.yaml``.

    Ein einzeln nicht lesbares Profil wird mit ``error`` markiert, aber nicht den
    Gesamtabbruch bewirkt (Acceptance C). Ein nicht erreichbares Verzeichnis
    liefert ``warning`` + leere Liste (statt Crash).
    """
    base = profiles_dir or settings.hermes_profiles_dir
    entries: list[dict] = []
    warning: str | None = None
    try:
        names = sorted(
            n
            for n in os.listdir(base)
            if n.startswith(ABC_PREFIX)
            and n not in _EXCLUDE
            and n != _DEFAULT_PROFILE
            and os.path.isdir(os.path.join(base, n))
        )
    except OSError as exc:
        warning = f"Profilverzeichnis nicht erreichbar ({base}): {exc}"
        return entries, warning

    allowed = allowed_engine_models()
    for name in names:
        cfg_path = _profile_path(base, name)
        entry = {
            "profile": name,
            "label": _role_label(name),
            "engine": None,
            "model": None,
            "provider": None,
            "default": None,
            "error": None,
        }
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError) as exc:
            entry["error"] = f"Profil-Konfiguration nicht lesbar: {exc}"
            entries.append(entry)
            continue
        if not isinstance(data, dict):
            entry["error"] = "Profil-Konfiguration ist kein gültiges Mapping."
            entries.append(entry)
            continue
        model_block = data.get("model")
        if isinstance(model_block, dict):
            provider = model_block.get("provider")
            default = model_block.get("default")
            entry["provider"] = provider
            entry["default"] = default
            engine, model = _reverse(provider, default, allowed)
            entry["engine"] = engine
            entry["model"] = model
        entries.append(entry)
    return entries, warning


def _is_within(path: str, base: str) -> bool:
    """True, wenn ``path`` (realpath) innerhalb des Verzeichnisses ``base`` liegt.

    Verteidigung gegen Path-Traversal: auch wenn ein Profilname die
    Format-Regex übersteht, darf der aufgelöste Pfad niemals das
    Profilverzeichnis verlassen.
    """
    try:
        real = os.path.realpath(path)
        base_real = os.path.realpath(base)
    except OSError:
        return False
    try:
        return os.path.commonpath([real, base_real]) == base_real
    except ValueError:
        return False


def save_profile_model(
    profile: str, engine: str, model: str, profiles_dir: str | None = None
) -> dict:
    """Übersetzt Engine+Modell und schreibt atomar ``model.provider`` +
    ``model.default`` in die ``config.yaml`` des Profils.

    Validiert ausschließlich gegen den zur Laufzeit geladenen
    ``engine_registry``-Snapshot (Acceptance D): nur die drei erlaubten
    Engine-Keys und deren angebotene Modelle sind zulässig. Verändert
    ausschließlich ``model.provider``/``model.default`` — alle anderen
    Profilwerte (inkl. ``model.base_url``) bleiben erhalten (Acceptance C).
    Schreibt über eine temporäre Datei + ``os.replace`` (atomar, kein
    teilweise geschriebenes YAML).

    Der ``profile``-Parameter wird strikt validiert (PROJ-83 BUG-1,
    Path-Traversal): nur Format ``jupiter-[a-z0-9_-]+``, muss zusätzlich in den
    von ``discover_profiles()`` erkannten Profilen enthalten sein, und der
    daraus gebaute Pfad muss (realpath) innerhalb von ``profiles_dir`` bleiben.

    Liefert ``{profile, ok, error, entry}`` — bei Erfolg ist ``entry`` der
    vollständig zurückübersetzte Profileintrag, sonst ``None`` (Edge Case
    „ein Profil ungültig": Teilfehler klar benennbar).
    """
    base = profiles_dir or settings.hermes_profiles_dir
    fail = lambda error: {  # noqa: E731
        "profile": profile,
        "ok": False,
        "error": error,
        "entry": None,
    }

    # 1) Format-Validierung gegen Path-Traversal (kein `/`, `..`, Absolutpfad).
    if not isinstance(profile, str) or not _PROFILE_RE.match(profile):
        return fail("Kein abc-Profil.")
    # 2) Whitelist: nur tatsächlich erkannte Profile sind beschreibbar.
    known = {e["profile"] for e in discover_profiles(base)[0]}
    if profile not in known:
        return fail("Kein abc-Profil.")

    allowed = allowed_engine_models()
    try:
        provider, default = _forward(engine, model, allowed)
    except ValueError as exc:
        return fail(str(exc))

    cfg_path = _profile_path(base, profile)
    # 3) Scope-Check: aufgelöster Pfad muss im Profilverzeichnis bleiben.
    if not _is_within(cfg_path, base):
        return fail("Kein abc-Profil.")

    try:
        with open(cfg_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        return fail(f"Profil-Konfiguration nicht lesbar/schreibbar: {exc}")
    if not isinstance(data, dict):
        return fail("Profil-Konfiguration ist kein gültiges Mapping.")

    # Nur die `model`-Sektion überschreiben — den Rest (provider, base_url,
    # toolsets …) unverändert lassen.
    model_block = data.get("model")
    if not isinstance(model_block, dict):
        model_block = {}
    model_block["provider"] = provider
    model_block["default"] = default
    data["model"] = model_block

    try:
        parent = os.path.dirname(cfg_path)
        os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=f".{profile}.", suffix=".yaml.tmp", dir=parent
        )
        with contextlib.suppress(OSError):
            os.chmod(tmp, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
        os.replace(tmp, cfg_path)
    except (OSError, yaml.YAMLError) as exc:
        return fail(f"Speichern fehlgeschlagen: {exc}")

    return {
        "profile": profile,
        "ok": True,
        "error": None,
        "entry": {
            "profile": profile,
            "label": _role_label(profile),
            "engine": engine,
            "model": model,
            "provider": provider,
            "default": default,
            "error": None,
        },
    }
