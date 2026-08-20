"""Hermes-Profil-Modellwahl (PROJ-83) — Erkennung + atomares Schreiben.

Liest zur Laufzeit die auf dem Jupiter-Server verfügbaren Hermes-Profile
(Präfix ``jupiter-`` mit lesbarer ``config.yaml``) und schreibt pro Profil
atomar das gewählte Modell nach ``model.default`` (bzw. ``model.provider``).
Kein Cache, keine DB — jeder Zugriff liest die Profile-Verzeichnisse frisch,
damit zwischen Laden und Speichern angelegte/entfernte Profile korrekt
behandelt werden (Edge Case „Profil zwischen Laden und Speichern gelöscht").

Es werden bewusst NUR die Felder ``model.default``/``model.provider``
geschrieben; alle übrigen Profilwerte (Secrets, Skills, Tools …) bleiben
unangetastet. Secrets/Tokens/Credentials werden nie in die API-Antwort
gespiegelt (Acceptance C).
"""
from __future__ import annotations

import contextlib
import logging
import os
import re
import tempfile

import yaml

from ..config import VALID_MODELS, settings

log = logging.getLogger(__name__)

# Ein Profil gilt als abc-Profil, wenn es mit diesem Präfix beginnt.
ABC_PREFIX = "jupiter-"
# Von der Profilerkennung ausgeschlossen (nicht-abc, siehe Spec PROJ-83).
_EXCLUDE = {"jupiter"}
# `default` ist explizit KEIN abc-Profil.
_DEFAULT_PROFILE = "default"

# Striktes Format für Profilnamen aus Client-Input: nur `jupiter-` + Kleinbuch-
# staben/Ziffern/`_`/`-`. Schließt `/`, `..`, Absolutpfade und Steuerzeichen aus
# (Verteidigung gegen Path-Traversal im `profile`-Parameter, PROJ-83 BUG-1).
_PROFILE_RE = re.compile(r"^jupiter-[a-z0-9_-]+$")

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
    return _ROLE_LABELS.get(name, name[len(ABC_PREFIX):].capitalize() if name.startswith(ABC_PREFIX) else name)


def discover_profiles(profiles_dir: str | None = None) -> tuple[list[dict], str | None]:
    """Erkennt alle abc-Profile im Verzeichnis.

    Liefert ``(profile_eintraege, warnung)``. Jeder Eintrag hat die Felder
    ``profile``, ``label``, ``current_model``, ``provider``, ``error``. Ein
    einzeln nicht lesbares Profil wird mit ``error`` markiert, aber nicht den
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

    for name in names:
        cfg_path = _profile_path(base, name)
        entry = {
            "profile": name,
            "label": _role_label(name),
            "current_model": None,
            "provider": None,
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
            entry["current_model"] = model_block.get("default")
            entry["provider"] = model_block.get("provider")
        entries.append(entry)
    return entries, warning


def available_models() -> list[str]:
    """Die aus Jupiters bestehender Modellverwaltung wählbaren Modelle (PROJ-51)."""
    return sorted(VALID_MODELS)


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
    profile: str, model: str, profiles_dir: str | None = None
) -> dict:
    """Schreibt ``model.default`` (atomar) in die ``config.yaml`` des Profils.

    Validiert gegen ``VALID_MODELS`` (Acceptance B: ungültige Auswahl serverseitig
    abgewiesen). Verändert ausschließlich die ``model``-Sektion — alle anderen
    Profilwerte bleiben erhalten (Acceptance C). Schreibt über eine temporäre
    Datei + ``os.replace``, damit kein teilweise geschriebenes YAML entsteht
    (Tech Design: atomares Speichern).

    Der ``profile``-Parameter wird strikt validiert (PROJ-83 BUG-1, Path-Traversal):
    nur das Format ``jupiter-[a-z0-9_-]+`` ist erlaubt, der Name muss zusätzlich
    in den von ``discover_profiles()`` erkannten Profilen enthalten sein, und der
    daraus gebaute Pfad muss (realpath) innerhalb von ``profiles_dir`` bleiben.

    Liefert ``{"profile", "ok", "error", "saved_model"}`` — bewusst pro Profil,
    damit Teilfehler klar benannt werden (Edge Case „ein Profil ungültig").
    """
    base = profiles_dir or settings.hermes_profiles_dir

    # 1) Format-Validierung gegen Path-Traversal (kein `/`, `..`, Absolutpfad).
    if not isinstance(profile, str) or not _PROFILE_RE.match(profile):
        return {"profile": profile, "ok": False, "error": "Kein abc-Profil.", "saved_model": None}
    # 2) Whitelist: nur tatsächlich erkannte Profile sind beschreibbar.
    known = {e["profile"] for e in discover_profiles(base)[0]}
    if profile not in known:
        return {"profile": profile, "ok": False, "error": "Kein abc-Profil.", "saved_model": None}

    model_str = str(model).strip()
    if model_str not in VALID_MODELS:
        return {
            "profile": profile,
            "ok": False,
            "error": f"Modell '{model_str}' ist nicht auswählbar.",
            "saved_model": None,
        }

    cfg_path = _profile_path(base, profile)
    # 3) Scope-Check: aufgelöster Pfad muss im Profilverzeichnis bleiben.
    if not _is_within(cfg_path, base):
        return {"profile": profile, "ok": False, "error": "Kein abc-Profil.", "saved_model": None}
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {
            "profile": profile,
            "ok": False,
            "error": f"Profil-Konfiguration nicht lesbar/schreibbar: {exc}",
            "saved_model": None,
        }
    if not isinstance(data, dict):
        return {
            "profile": profile,
            "ok": False,
            "error": "Profil-Konfiguration ist kein gültiges Mapping.",
            "saved_model": None,
        }

    # Nur die `model`-Sektion überschreiben — den Rest unverändert lassen.
    model_block = data.get("model")
    if not isinstance(model_block, dict):
        model_block = {}
    model_block["default"] = model_str
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
        return {
            "profile": profile,
            "ok": False,
            "error": f"Speichern fehlgeschlagen: {exc}",
            "saved_model": None,
        }

    return {"profile": profile, "ok": True, "error": None, "saved_model": model_str}
