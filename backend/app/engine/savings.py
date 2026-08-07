"""PROJ-73 — engine-übergreifendes Token-Savings-Profil.

Dateibasierter globaler Default, read-only Modul-Discovery und deterministische
Prompt-Komposition. Fremdtools werden hier bewusst weder installiert noch konfiguriert.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from ..config import settings

PROFILE_ID = "balanced-v1"
MODULES = ("caveman", "ponytail", "codegraph")
ENGINES = ("claude", "codex", "opencode")
DEFAULTS = {
    "enabled": False,
    "profile_id": PROFILE_ID,
    "module_enabled": {name: True for name in MODULES},
}

SavingsChoice = Literal["standard", "on", "off"]


def _validate(data: object, *, strict: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Token-Savings-Konfiguration muss ein Objekt sein.")
    enabled = data.get("enabled", False)
    if not isinstance(enabled, bool):
        if strict:
            raise ValueError("enabled muss true oder false sein.")
        enabled = False
    profile_id = data.get("profile_id", PROFILE_ID)
    if profile_id != PROFILE_ID:
        if strict:
            raise ValueError(f"Unbekanntes Savings-Profil '{profile_id}'.")
        profile_id = PROFILE_ID
    raw_modules = data.get("module_enabled", {})
    if not isinstance(raw_modules, dict):
        if strict:
            raise ValueError("module_enabled muss ein Objekt sein.")
        raw_modules = {}
    module_enabled = {
        name: raw_modules.get(name, DEFAULTS["module_enabled"][name]) is True
        for name in MODULES
    }
    return {
        "enabled": enabled,
        "profile_id": profile_id,
        "module_enabled": module_enabled,
    }


class SavingsStore:
    """YAML-backed Settings-Store mit atomarem Save und konservativem Default Aus."""

    def __init__(self, path: str) -> None:
        self.path = path

    def config(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                return _validate(yaml.safe_load(fh) or {})
        except FileNotFoundError:
            return _validate(DEFAULTS)
        except (OSError, ValueError, yaml.YAMLError):
            return _validate(DEFAULTS)

    def snapshot(self) -> dict:
        cfg = self.config()
        warning = None
        source = self.path if os.path.isfile(self.path) else "default"
        if source != "default":
            try:
                with open(self.path, encoding="utf-8") as fh:
                    _validate(yaml.safe_load(fh) or {}, strict=True)
            except (OSError, ValueError, yaml.YAMLError) as exc:
                source = "default"
                warning = f"Token-Savings-Konfiguration ungültig ({exc})"
        return {**cfg, "source": source, "warning": warning}

    def save(self, payload: dict) -> dict:
        cfg = _validate(payload, strict=True)
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)
        os.replace(tmp, target)
        return self.snapshot()


def _first_existing(paths: list[Path]) -> Path | None:
    return next((p for p in paths if p.is_file()), None)


def _skill_path(name: str, engine: str) -> Path | None:
    home = Path.home()
    candidates: dict[str, list[Path]] = {
        "claude": [
            home / ".claude" / "skills" / name / "SKILL.md",
            home / ".claude" / "plugins" / name / "skills" / name / "SKILL.md",
        ],
        "codex": [home / ".codex" / "skills" / name / "SKILL.md"],
        "opencode": [
            home / ".config" / "opencode" / "skills" / name / "SKILL.md",
            home / ".config" / "opencode" / "plugins" / name / "SKILL.md",
        ],
    }
    direct = _first_existing(candidates.get(engine, []))
    if direct:
        return direct

    # Claude and Codex install native plugins in versioned cache directories;
    # these paths are the authoritative runtime source, not a copied skill.
    cache_root = home / f".{engine}" / "plugins" / "cache" / name
    cached = sorted(cache_root.glob(f"**/skills/{name}/SKILL.md"), reverse=True)
    return _first_existing(cached)


def _opencode_plugin_configured(name: str) -> bool:
    if name != "ponytail":
        return False
    config = Path.home() / ".config" / "opencode" / "opencode.json"
    try:
        return "@dietrichgebert/ponytail" in config.read_text(encoding="utf-8")
    except OSError:
        return False


def _codegraph_binary() -> Path | None:
    configured = str(getattr(settings, "codegraph_bin", "") or "").strip()
    if configured:
        p = Path(configured).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return p
    found = shutil.which("codegraph")
    if found:
        return Path(found)
    # Service-Prozesse laden NVM-Shellprofile nicht. Kontrollierter Fallback auf
    # installierte Node-Versionen, neueste zuerst; keine Shell-Ausführung.
    roots = sorted(
        (Path.home() / ".nvm" / "versions" / "node").glob("*/bin/codegraph"),
        reverse=True,
    )
    return _first_existing(roots)


def _version(binary: Path | None) -> str | None:
    if binary is None:
        return None
    try:
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0][:80] if result.returncode == 0 and text else None


def _codegraph_mcp_configured(engine: str) -> bool:
    home = Path.home()
    files = {
        "claude": [home / ".claude.json", home / ".claude" / "settings.json"],
        "codex": [home / ".codex" / "config.toml"],
        "opencode": [home / ".config" / "opencode" / "opencode.json"],
    }.get(engine, [])
    for path in files:
        try:
            if "codegraph" in path.read_text(encoding="utf-8").lower():
                return True
        except OSError:
            continue
    return False


class SavingsHealthService:
    def module_health(
        self, name: str, engine: str, project_path: str | None = None
    ) -> dict:
        if name not in MODULES:
            raise ValueError(f"Unbekanntes Savings-Modul '{name}'.")
        if engine not in ENGINES:
            raise ValueError(f"Unbekannte Engine '{engine}'.")
        if name in ("caveman", "ponytail"):
            path = _skill_path(name, engine)
            plugin_configured = engine == "opencode" and _opencode_plugin_configured(name)
            installed = path is not None or plugin_configured
            return {
                "name": name,
                "stability": "pilot",
                "installed": installed,
                "healthy": installed,
                "version": None,
                "integration": "native" if installed else "unavailable",
                "supported_engines": list(ENGINES),
                "detail": (
                    str(path)
                    if path
                    else (
                        "Native OpenCode-Plugin konfiguriert."
                        if plugin_configured
                        else f"Skill für {engine} nicht installiert."
                    )
                ),
                "binary_found": None,
                "mcp_configured": None,
                "mcp_reachable": None,
                "project_index_present": None,
                "index_freshness": None,
            }
        binary = _codegraph_binary()
        project = Path(project_path).resolve() if project_path else None
        index = project / ".codegraph" / "codegraph.db" if project else None
        index_present = bool(index and index.is_file())
        mcp_configured = _codegraph_mcp_configured(engine)
        version = _version(binary)
        healthy = (
            binary is not None
            and version is not None
            and index_present
            and mcp_configured
        )
        detail = None
        if binary is None:
            detail = "CodeGraph-Binary nicht auffindbar."
        elif not mcp_configured:
            detail = f"CodeGraph {version or ''} installiert; MCP für {engine} nicht konfiguriert."
        elif not index_present and project:
            detail = "CodeGraph installiert; Projektindex fehlt."
        return {
            "name": name,
            "stability": "pilot",
            "installed": binary is not None,
            "healthy": healthy,
            "version": version,
            "integration": "mcp" if mcp_configured else "unavailable",
            "supported_engines": list(ENGINES),
            "detail": detail,
            "binary_found": binary is not None,
            "binary_path": str(binary) if binary else None,
            "mcp_configured": mcp_configured,
            # Ein echter MCP-Handshake gehört in den späteren Adapter; im MVP wird
            # Erreichbarkeit nicht aus Konfigurationspräsenz erfunden.
            "mcp_reachable": None,
            "project_index_present": index_present,
            "index_freshness": "unknown" if index_present else None,
        }

    def all_health(self, engine: str, project_path: str | None = None) -> list[dict]:
        return [self.module_health(name, engine, project_path) for name in MODULES]


@dataclass(frozen=True)
class SavingsResolution:
    enabled: bool
    source: str
    profile_id: str
    modules: list[dict]
    degraded: list[str]
    prompt: str
    provenance: list[dict]

    def snapshot(self) -> dict:
        return {
            "enabled": self.enabled,
            "source": self.source,
            "profile_id": self.profile_id,
            "profile_version": self.profile_id,
            "modules": self.modules,
            "degraded": self.degraded,
            "provenance": self.provenance,
        }


class SavingsProfileResolver:
    """Global/Override + Health -> effektiver, konfliktfreier Session-Snapshot."""

    CAVEMAN_PROMPT = (
        "Formuliere knapp und präzise. Kürze nur die Darstellung; erhalte Warnungen, "
        "Befehle, Pfade, Diffs, Akzeptanzkriterien und notwendige Begründungen vollständig."
    )
    PONYTAIL_PROMPT = (
        "Implementiere die kleinste vollständige Lösung innerhalb des expliziten Auftrags. "
        "Vermeide ungeforderten Umfang, aber streiche keine Akzeptanzkriterien, Sicherheits- "
        "oder Workflow-Vorgaben."
    )

    def __init__(self, store: SavingsStore, health: SavingsHealthService) -> None:
        self.store = store
        self.health = health

    def resolve(
        self, *, choice: SavingsChoice, engine: str, project_path: str, base_prompt: str
    ) -> SavingsResolution:
        cfg = self.store.config()
        if choice == "on":
            wanted, source = True, "override_on"
        elif choice == "off":
            wanted, source = False, "override_off"
        else:
            wanted, source = bool(cfg["enabled"]), "global"
        if not wanted:
            return SavingsResolution(
                False,
                source,
                cfg["profile_id"],
                [],
                [],
                base_prompt,
                [{"source": "jupiter_constitution", "action": "kept"}],
            )

        health = self.health.all_health(engine, project_path)
        modules: list[dict] = []
        degraded: list[str] = []
        prompt_parts = [base_prompt] if base_prompt else []
        provenance = [{"source": "jupiter_constitution", "action": "kept"}]
        for item in health:
            name = item["name"]
            if not cfg["module_enabled"].get(name, False):
                continue
            if not item["healthy"]:
                degraded.append(f"{name}: {item['detail'] or 'nicht verfügbar'}")
                continue
            modules.append(
                {
                    "name": name,
                    "version": item.get("version"),
                    "integration": item["integration"],
                }
            )
            if name == "caveman":
                prompt_parts.append(self.CAVEMAN_PROMPT)
                provenance.append(
                    {"source": "caveman", "action": "deduplicated_brevity"}
                )
            elif name == "ponytail":
                prompt_parts.append(self.PONYTAIL_PROMPT)
                provenance.append({"source": "ponytail", "action": "added_yagni"})
            else:
                provenance.append({"source": name, "action": "tool_enabled"})
        return SavingsResolution(
            True,
            source,
            cfg["profile_id"],
            modules,
            degraded,
            "\n\n".join(p for p in prompt_parts if p),
            provenance,
        )


savings_store = SavingsStore(settings.token_savings_config_path)
savings_health = SavingsHealthService()
savings_resolver = SavingsProfileResolver(savings_store, savings_health)
