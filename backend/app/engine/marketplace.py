"""Marktplatz/Registry für Rollen/Skills/Agenten (PROJ-26).

File-first, kein Postgres — konsistent mit Konstitution/Policy/Engines (PROJ-6/10/18).
Jeder Eintrag ist ein Verzeichnis unter ``<registry_root>/installed/<typ>s/<id>/``:

    manifest.yaml      # Metadaten + Default-Policy + Schema-Version + owner + capabilities + status
    definition.md      # der eigentliche Rollen-/Skill-/Agenten-Prompt
    versions/<v>/      # frühere Versionen (Rollback-Quelle): manifest.yaml + definition.md

**Aktiv = Datei am Resolver-Pfad.** Eine aktive *Rolle* wird als ``<id>.md`` dorthin
gelegt, wo ``resolve_constitution()`` / ``list_roles()`` ohnehin lesen
(``constitution_dir/roles/``) → Sessions/Launcher (PROJ-9) sehen sie ohne Umbau.
Skills/Agenten landen in einem konfigurierten Aktiv-Ordner (Best-Effort; die
Session-Start-Anbindung für Skills/Agenten ist Ausbaustufe — siehe Spec).

Sicherheitslinie (PROJ-10): importierte Definitionen laufen NIE ungeprüft mit
Vollrechten. ``default_policy`` ist konservativ (``card``/``deny`` — nie ``auto-allow``);
fordert ein Paket unbekannte/gefährliche Tools, wird es als ``limited`` markiert und
auf ``deny`` gestuft. Aktivierung erst nach menschlicher Bestätigung (Import zweistufig).

Wir überschreiben NIE eine fremde Datei am Resolver-Pfad: nur was die Registry selbst
gelegt hat (``resolver_placed: true`` im Manifest) wird wieder entfernt — von Hand
gepflegte Konstitutions-Rollen (PROJ-6) bleiben unangetastet.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone

import yaml

from ..config import settings
from . import policy

# Paket-/Manifest-Schema. Kompatibel = gleicher MAJOR-Teil (1.x ↔ 1.y).
SCHEMA_VERSION = "1.0"

# BUG-26-1: Dekomprimierungs-Limits gegen Zip-Bomben. Der komprimierte Upload-Cap
# (Route, 2 MB) sagt NICHTS über die entpackte Größe — ein wenige KB großes .jupkg
# kann zig MB entpacken. Daher die ENTPACKTEN Bytes deckeln (gestreamt gelesen, damit
# auch ein gefälschter Größen-Header im Zip nicht greift) + die Eintragszahl begrenzen.
MAX_MANIFEST_BYTES = 64 * 1024
MAX_DEFINITION_BYTES = 1 * 1024 * 1024
MAX_PACKAGE_ENTRIES = 16

# BUG-26-3: Staging-Pakete einer nicht bestätigten Vorschau sollen nicht ewig liegen
# bleiben. Beim Stagen werden ältere Reste (mtime älter als TTL) opportunistisch entfernt.
STAGING_TTL_SECONDS = 3600.0

ROLE, SKILL, AGENT = "role", "skill", "agent"
VALID_TYPES: frozenset[str] = frozenset({ROLE, SKILL, AGENT})

INSTALLED, ACTIVE, INACTIVE = "installed", "active", "inactive"

# Sichere ID/Version (verhindert Pfad-Traversal über Dateinamen).
_VALID_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_VALID_VERSION = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")

# Bekannte Tools (für Capability-Risiko + ``limited``-Markierung). Alles andere gilt als
# „unbekannt/gefährlich" → Default-Policy ``deny`` + Hinweis „eingeschränkt lauffähig".
_KNOWN_TOOLS: frozenset[str] = policy.AUTO_ALLOW_TOOLS | frozenset(
    {
        "Bash",
        "Edit",
        "Write",
        "MultiEdit",
        "NotebookEdit",
        "Task",
        "Agent",
        "AskUserQuestion",
        "SlashCommand",
        "KillShell",
    }
)


class RegistryError(Exception):
    """Fachlicher Fehler (Route → passender HTTP-Status über ``status_code``)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _plural(typ: str) -> str:
    return f"{typ}s"


def schema_compatible(version: str) -> bool:
    """Gleiche MAJOR-Version = kompatibel; alles andere wird abgewiesen."""
    try:
        return str(version).split(".", 1)[0] == SCHEMA_VERSION.split(".", 1)[0]
    except (AttributeError, IndexError):
        return False


def assess_capabilities(capabilities: list[str]) -> tuple[str, bool, list[str]]:
    """Leitet ``(default_policy, limited, warnings)`` aus den angeforderten Tools ab.

    Konservativ: unbekannte/gefährliche Tools → ``deny`` + ``limited`` + Warnung; sonst
    ``card`` (nie ``auto-allow`` — importierte Definitionen erhalten nie stillschweigend
    volle Autonomie, PROJ-10).
    """
    unknown = [c for c in capabilities if c not in _KNOWN_TOOLS]
    warnings = [f"Fordert unbekanntes/potenziell gefährliches Tool: {c}" for c in unknown]
    default_policy = policy.DENY if unknown else policy.CARD
    return default_policy, bool(unknown), warnings


@dataclass
class _Manifest:
    """In-Memory-Abbild der ``manifest.yaml`` eines Eintrags."""

    id: str
    typ: str
    name: str
    beschreibung: str
    status: str
    version: str
    owner: str | None
    capabilities: list[str]
    default_policy: str
    verified: bool
    schema_version: str = SCHEMA_VERSION
    resolver_placed: bool = False
    versions: list[dict] | None = None  # Historie: [{version, created_at, note}], neueste zuerst

    def to_yaml_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "typ": self.typ,
            "name": self.name,
            "beschreibung": self.beschreibung,
            "status": self.status,
            "version": self.version,
            "owner": self.owner,
            "capabilities": list(self.capabilities),
            "default_policy": self.default_policy,
            "verified": self.verified,
            "resolver_placed": self.resolver_placed,
            "versions": self.versions or [],
        }


def _parse_manifest(raw: dict, *, source: str) -> _Manifest:
    """Validiert einen Manifest-Dict (aus Paket ODER Plattenspeicher). Wirft ``RegistryError``."""
    if not isinstance(raw, dict):
        raise RegistryError(f"{source}: manifest.yaml ist kein Objekt.")
    schema_version = str(raw.get("schema_version") or "")
    if not schema_version:
        raise RegistryError(f"{source}: schema_version fehlt — kein gültiges Paket.")
    if not schema_compatible(schema_version):
        raise RegistryError(
            f"{source}: inkompatible Schema-Version {schema_version} "
            f"(erwartet {SCHEMA_VERSION.split('.', 1)[0]}.x) — Import abgelehnt."
        )
    typ = str(raw.get("typ") or "").strip()
    if typ not in VALID_TYPES:
        raise RegistryError(f"{source}: unbekannter Typ „{typ or '?'}“ (role|skill|agent).")
    entry_id = str(raw.get("id") or "").strip()
    if not _VALID_ID.match(entry_id):
        raise RegistryError(f"{source}: ungültige id „{entry_id}“ (nur Buchstaben/Ziffern/-/_, max 64).")
    version = str(raw.get("version") or "1.0.0").strip()
    if not _VALID_VERSION.match(version):
        raise RegistryError(f"{source}: ungültige Version „{version}“.")
    caps = [str(c) for c in (raw.get("capabilities") or [])]
    return _Manifest(
        id=entry_id,
        typ=typ,
        name=str(raw.get("name") or entry_id),
        beschreibung=str(raw.get("beschreibung") or ""),
        status=str(raw.get("status") or INSTALLED),
        version=version,
        owner=(str(raw["owner"]) if raw.get("owner") else None),
        capabilities=caps,
        default_policy=str(raw.get("default_policy") or assess_capabilities(caps)[0]),
        verified=bool(raw.get("verified", False)),
        schema_version=schema_version,
        resolver_placed=bool(raw.get("resolver_placed", False)),
        versions=list(raw.get("versions") or []),
    )


class RegistryStore:
    """Datei-basierter Katalog + Import/Export. Eine Instanz pro Backend-Prozess."""

    def __init__(self, root: str) -> None:
        self._root = root

    # --- Pfade ------------------------------------------------------------

    def _installed_dir(self, typ: str) -> str:
        return os.path.join(self._root, "installed", _plural(typ))

    def _entry_dir(self, typ: str, entry_id: str) -> str:
        return os.path.join(self._installed_dir(typ), entry_id)

    def _staging_dir(self) -> str:
        return os.path.join(self._root, "packages", "_staging")

    def _resolver_path(self, typ: str, entry_id: str) -> str:
        """Wohin eine AKTIVE Definition gelegt wird (Resolver liest sie ohne Umbau)."""
        if typ == ROLE:
            base = os.path.join(settings.constitution_dir, "roles")
        else:
            base = os.path.join(self._root, "active", _plural(typ))
        return os.path.join(base, f"{entry_id}.md")

    # --- Helpers ----------------------------------------------------------

    @staticmethod
    def _check_type(typ: str) -> None:
        if typ not in VALID_TYPES:
            raise RegistryError(f"Unbekannter Typ „{typ}“.", status_code=404)

    @staticmethod
    def _check_id(entry_id: str) -> None:
        if not _VALID_ID.match(entry_id):
            raise RegistryError("Ungültige Eintrags-ID.", status_code=400)

    def _load_manifest(self, typ: str, entry_id: str) -> _Manifest:
        path = os.path.join(self._entry_dir(typ, entry_id), "manifest.yaml")
        try:
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise RegistryError("Eintrag nicht gefunden.", status_code=404) from exc
        except (OSError, yaml.YAMLError) as exc:
            raise RegistryError(f"Manifest defekt: {exc}", status_code=500) from exc
        return _parse_manifest(raw, source=f"{typ}/{entry_id}")

    def _write_manifest(self, man: _Manifest) -> None:
        entry_dir = self._entry_dir(man.typ, man.id)
        os.makedirs(entry_dir, exist_ok=True)
        tmp = os.path.join(entry_dir, "manifest.yaml.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            yaml.safe_dump(man.to_yaml_dict(), fh, allow_unicode=True, sort_keys=False)
        os.replace(tmp, os.path.join(entry_dir, "manifest.yaml"))

    def _read_definition(self, typ: str, entry_id: str) -> str:
        path = os.path.join(self._entry_dir(typ, entry_id), "definition.md")
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except (FileNotFoundError, OSError):
            return ""

    def _is_limited(self, man: _Manifest) -> bool:
        """Referenziert die aktuelle Version ein unbekanntes/fehlendes Tool?"""
        return assess_capabilities(man.capabilities)[1]

    def _to_entry(self, man: _Manifest) -> dict:
        return {
            "id": man.id,
            "typ": man.typ,
            "name": man.name,
            "beschreibung": man.beschreibung,
            "status": man.status,
            "version": man.version,
            "owner": man.owner,
            "capabilities": list(man.capabilities),
            "default_policy": man.default_policy,
            "verified": man.verified,
            "limited": self._is_limited(man),
        }

    # --- Resolver-Anbindung (aktiv = Datei am Resolver-Pfad) --------------

    def _place_resolver(self, man: _Manifest) -> None:
        """Legt die aktive Definition am Resolver-Pfad ab. Schützt fremde Dateien (409)."""
        target = self._resolver_path(man.typ, man.id)
        if os.path.exists(target) and not man.resolver_placed:
            raise RegistryError(
                f"Eine gleichnamige Datei „{man.id}“ existiert bereits am Resolver-Pfad — "
                "Aktivierung würde sie überschreiben (z. B. eine von Hand gepflegte Rolle). Abgebrochen.",
                status_code=409,
            )
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(self._read_definition(man.typ, man.id))
        man.resolver_placed = True

    def _remove_resolver(self, man: _Manifest) -> None:
        """Entfernt die Resolver-Datei NUR, wenn die Registry sie selbst gelegt hat."""
        if not man.resolver_placed:
            return
        target = self._resolver_path(man.typ, man.id)
        try:
            os.remove(target)
        except FileNotFoundError:
            pass
        man.resolver_placed = False

    # --- Lese-API ---------------------------------------------------------

    def catalog(
        self, typ: str | None = None, status: str | None = None, query: str | None = None
    ) -> list[dict]:
        """Durchsuchbarer Katalog. Filtert serverseitig nach Typ/Status/Freitext."""
        entries: list[dict] = []
        types = [typ] if typ in VALID_TYPES else list(VALID_TYPES)
        for t in types:
            base = self._installed_dir(t)
            try:
                ids = sorted(os.listdir(base))
            except (FileNotFoundError, NotADirectoryError):
                continue
            for entry_id in ids:
                if not _VALID_ID.match(entry_id):
                    continue
                if not os.path.isdir(self._entry_dir(t, entry_id)):
                    continue
                try:
                    man = self._load_manifest(t, entry_id)
                except RegistryError:
                    continue  # defekter Eintrag überspringen, Katalog bleibt nutzbar
                if status and man.status != status:
                    continue
                if query:
                    hay = f"{man.id} {man.name} {man.beschreibung}".lower()
                    if query.lower() not in hay:
                        continue
                entries.append(self._to_entry(man))
        entries.sort(key=lambda e: (e["typ"], e["name"].lower()))
        return entries

    def detail(self, typ: str, entry_id: str) -> dict:
        self._check_type(typ)
        self._check_id(entry_id)
        man = self._load_manifest(typ, entry_id)
        entry = self._to_entry(man)
        entry["definition"] = self._read_definition(typ, entry_id)
        entry["versions"] = self._version_history(man)
        return entry

    def _version_history(self, man: _Manifest) -> list[dict]:
        """Versions-Historie inkl. der aktuellen Version, neueste zuerst."""
        history: list[dict] = []
        seen: set[str] = set()
        # aktuelle Version zuerst
        history.append(
            {
                "version": man.version,
                "created_at": _meta_created_at(man.versions, man.version),
                "note": _meta_note(man.versions, man.version),
                "limited": self._is_limited(man),
            }
        )
        seen.add(man.version)
        versions_dir = os.path.join(self._entry_dir(man.typ, man.id), "versions")
        recorded = {str(v.get("version")): v for v in (man.versions or [])}
        try:
            on_disk = sorted(os.listdir(versions_dir), reverse=True)
        except (FileNotFoundError, NotADirectoryError):
            on_disk = []
        for ver in on_disk:
            if ver in seen or not _VALID_VERSION.match(ver):
                continue
            meta = recorded.get(ver, {})
            caps = self._archived_caps(man.typ, man.id, ver)
            history.append(
                {
                    "version": ver,
                    "created_at": str(meta.get("created_at") or ""),
                    "note": (str(meta["note"]) if meta.get("note") else None),
                    "limited": assess_capabilities(caps)[1],
                }
            )
            seen.add(ver)
        return history

    def _archived_caps(self, typ: str, entry_id: str, version: str) -> list[str]:
        path = os.path.join(self._entry_dir(typ, entry_id), "versions", version, "manifest.yaml")
        try:
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            return [str(c) for c in (raw.get("capabilities") or [])]
        except (OSError, yaml.YAMLError):
            return []

    # --- Lebenszyklus -----------------------------------------------------

    def install(self, typ: str, entry_id: str) -> dict:
        """Aktiviert einen vorhandenen Eintrag (Datei am Resolver-Pfad ablegen)."""
        self._check_type(typ)
        self._check_id(entry_id)
        man = self._load_manifest(typ, entry_id)
        if man.status != ACTIVE:
            self._place_resolver(man)
            man.status = ACTIVE
            self._write_manifest(man)
        return self._to_entry(man)

    def toggle(self, typ: str, entry_id: str) -> dict:
        """Aktivieren ↔ Deaktivieren. Deaktivieren entfernt die Resolver-Datei (nur eigene)."""
        self._check_type(typ)
        self._check_id(entry_id)
        man = self._load_manifest(typ, entry_id)
        if man.status == ACTIVE:
            self._remove_resolver(man)
            man.status = INACTIVE
        else:
            self._place_resolver(man)
            man.status = ACTIVE
        self._write_manifest(man)
        return self._to_entry(man)

    def rollback(self, typ: str, entry_id: str, version: str) -> dict:
        """Stellt eine frühere Version als aktuelle her (Hinweis statt Crash bei fehlendem Tool)."""
        self._check_type(typ)
        self._check_id(entry_id)
        if not _VALID_VERSION.match(version):
            raise RegistryError("Ungültige Versionsangabe.", status_code=400)
        man = self._load_manifest(typ, entry_id)
        if version == man.version:
            raise RegistryError("Diese Version ist bereits aktiv.", status_code=400)
        ver_dir = os.path.join(self._entry_dir(typ, entry_id), "versions", version)
        ver_manifest = os.path.join(ver_dir, "manifest.yaml")
        ver_def = os.path.join(ver_dir, "definition.md")
        if not os.path.isfile(ver_manifest):
            raise RegistryError(f"Version {version} nicht gefunden.", status_code=404)

        # aktuelle Version vor dem Überschreiben archivieren (Rollback ist reversibel)
        self._archive_current(man)

        with open(ver_manifest, encoding="utf-8") as fh:
            archived = _parse_manifest(yaml.safe_load(fh) or {}, source=f"{typ}/{entry_id}@{version}")
        archived_def = ""
        try:
            with open(ver_def, encoding="utf-8") as fh:
                archived_def = fh.read()
        except (FileNotFoundError, OSError):
            pass

        # Definition + Metadaten der Zielversion übernehmen, Identität/Historie bewahren
        with open(os.path.join(self._entry_dir(typ, entry_id), "definition.md"), "w", encoding="utf-8") as fh:
            fh.write(archived_def)
        man.version = archived.version
        man.capabilities = archived.capabilities
        man.default_policy = assess_capabilities(archived.capabilities)[0]
        self._write_manifest(man)

        # eine aktive Rolle muss am Resolver-Pfad die zurückgerollte Definition zeigen
        if man.status == ACTIVE and man.resolver_placed:
            man.resolver_placed = True  # gehört uns → überschreiben erlaubt
            self._place_resolver(man)
            self._write_manifest(man)
        return self._to_entry(man)

    def _archive_current(self, man: _Manifest) -> None:
        """Sichert die aktuelle Version unter ``versions/<v>/`` + Metadaten (idempotent)."""
        ver_dir = os.path.join(self._entry_dir(man.typ, man.id), "versions", man.version)
        os.makedirs(ver_dir, exist_ok=True)
        snapshot = _Manifest(
            id=man.id, typ=man.typ, name=man.name, beschreibung=man.beschreibung,
            status=INSTALLED, version=man.version, owner=man.owner,
            capabilities=man.capabilities, default_policy=man.default_policy,
            verified=man.verified, schema_version=man.schema_version, versions=[],
        )
        with open(os.path.join(ver_dir, "manifest.yaml"), "w", encoding="utf-8") as fh:
            yaml.safe_dump(snapshot.to_yaml_dict(), fh, allow_unicode=True, sort_keys=False)
        with open(os.path.join(ver_dir, "definition.md"), "w", encoding="utf-8") as fh:
            fh.write(self._read_definition(man.typ, man.id))
        # Versions-Metadaten festhalten (created_at für die Historie), dedupliziert.
        man.versions = man.versions or []
        if not any(str(v.get("version")) == man.version for v in man.versions):
            man.versions.insert(
                0,
                {"version": man.version, "created_at": datetime.now(timezone.utc).isoformat(), "note": None},
            )

    def delete(self, typ: str, entry_id: str) -> None:
        """Deinstalliert (entfernt Resolver-Datei + Eintrags-Verzeichnis mit Versionen)."""
        self._check_type(typ)
        self._check_id(entry_id)
        man = self._load_manifest(typ, entry_id)
        self._remove_resolver(man)
        shutil.rmtree(self._entry_dir(typ, entry_id), ignore_errors=True)

    # --- Export -----------------------------------------------------------

    def export_package(self, typ: str, entry_id: str) -> bytes:
        """Packt manifest.yaml + definition.md der aktuellen Version als ``.jupkg`` (Zip)."""
        self._check_type(typ)
        self._check_id(entry_id)
        man = self._load_manifest(typ, entry_id)
        # Export-Manifest: neutraler Status, ohne lokale Resolver-Spuren.
        export_man = _Manifest(
            id=man.id, typ=man.typ, name=man.name, beschreibung=man.beschreibung,
            status=INSTALLED, version=man.version, owner=man.owner,
            capabilities=man.capabilities, default_policy=man.default_policy,
            verified=man.verified, schema_version=SCHEMA_VERSION, versions=[],
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "manifest.yaml",
                yaml.safe_dump(export_man.to_yaml_dict(), allow_unicode=True, sort_keys=False),
            )
            zf.writestr("definition.md", self._read_definition(typ, entry_id))
        return buf.getvalue()

    # --- Import (zweistufig: Vorschau → Bestätigen) -----------------------

    def import_preview(self, data: bytes) -> dict:
        """Validiert ein hochgeladenes ``.jupkg`` und liefert die Capability-/Policy-Vorschau.

        Aktiviert NICHTS — das Paket wird gestaged; ``token`` führt zu ``import_confirm``.
        """
        man, _definition = self._read_package(data)
        # Importierte Pakete gelten als „nicht verifiziert" (keine PROJ-25-Signatur/Trust-Chain).
        man.verified = False
        default_policy, limited, cap_warnings = assess_capabilities(man.capabilities)
        man.default_policy = default_policy

        collision = os.path.isdir(self._entry_dir(man.typ, man.id))
        warnings = list(cap_warnings)
        warnings.append("Quelle nicht verifiziert (kein PROJ-25-Trust) — vor Aktivierung prüfen.")
        if collision:
            warnings.append(
                f"Ein Eintrag „{man.id}“ existiert bereits — der Import erzeugt eine neue Version "
                "statt zu überschreiben."
            )
        if limited:
            warnings.append("Eingeschränkt lauffähig: referenziert unbekannte/fehlende Tools.")

        token = self._stage_package(data)
        return {
            "token": token,
            "id": man.id,
            "typ": man.typ,
            "name": man.name,
            "beschreibung": man.beschreibung,
            "version": man.version,
            "owner": man.owner,
            "schema_version": man.schema_version,
            "capabilities": list(man.capabilities),
            "default_policy": man.default_policy,
            "verified": man.verified,
            "collision": collision,
            "warnings": warnings,
        }

    def import_confirm(self, token: str, owner: str | None) -> dict:
        """Installiert das gestagte Paket nach menschlicher Bestätigung und aktiviert es."""
        data = self._read_staged(token)
        man, definition = self._read_package(data)
        man.verified = False
        man.owner = owner
        man.default_policy = assess_capabilities(man.capabilities)[0]

        entry_dir = self._entry_dir(man.typ, man.id)
        if os.path.isdir(entry_dir):
            # ID-Kollision → neue Version des bestehenden Eintrags, kein stilles Überschreiben.
            existing = self._load_manifest(man.typ, man.id)
            self._archive_current(existing)
            man.version = _bump_version(existing.version, man.version, existing.versions or [])
            man.owner = existing.owner or owner
            man.versions = existing.versions
            man.resolver_placed = existing.resolver_placed
            with open(os.path.join(entry_dir, "definition.md"), "w", encoding="utf-8") as fh:
                fh.write(definition)
            man.status = existing.status
            self._write_manifest(man)
            if man.status == ACTIVE and man.resolver_placed:
                self._place_resolver(man)
                self._write_manifest(man)
        else:
            # BUG-26-2: Resolver-Kollision (fremde Datei) VOR dem Anlegen prüfen → kein
            # halber „installed"-Eintrag bleibt zurück, wenn die Aktivierung mit 409 scheitert.
            target = self._resolver_path(man.typ, man.id)
            if os.path.exists(target):
                raise RegistryError(
                    f"Eine gleichnamige Datei „{man.id}“ existiert bereits am Resolver-Pfad — "
                    "Aktivierung würde sie überschreiben (z. B. eine von Hand gepflegte Rolle). Abgebrochen.",
                    status_code=409,
                )
            os.makedirs(entry_dir, exist_ok=True)
            with open(os.path.join(entry_dir, "definition.md"), "w", encoding="utf-8") as fh:
                fh.write(definition)
            man.status = INSTALLED
            man.resolver_placed = False
            self._write_manifest(man)
            # Bestätigung aktiviert (Human-in-the-Loop) — Resolver-Datei legen.
            self._place_resolver(man)
            man.status = ACTIVE
            self._write_manifest(man)

        self._discard_staged(token)
        return self._to_entry(man)

    # --- Paket-/Staging-Interna ------------------------------------------

    def _read_package(self, data: bytes) -> tuple[_Manifest, str]:
        """Liest + validiert ein ``.jupkg``. Wirft ``RegistryError`` bei jedem Defekt.

        Schutz gegen Zip-Bomben (BUG-26-1): Eintragszahl begrenzt + beide Dateien
        gestreamt mit hartem Byte-Limit gelesen (gefälschter Größen-Header greift nicht).
        """
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise RegistryError("Defektes Paket: keine gültige .jupkg-Datei (Zip).") from exc
        with zf:
            names = set(zf.namelist())
            if len(names) > MAX_PACKAGE_ENTRIES:
                raise RegistryError("Paket abgelehnt: zu viele Einträge (mögliche Zip-Bombe).", status_code=413)
            if "manifest.yaml" not in names:
                raise RegistryError("Defektes Paket: manifest.yaml fehlt.")
            if "definition.md" not in names:
                raise RegistryError("Defektes Paket: definition.md fehlt.")
            manifest_bytes = self._read_capped(zf, "manifest.yaml", MAX_MANIFEST_BYTES, "manifest.yaml")
            definition_bytes = self._read_capped(zf, "definition.md", MAX_DEFINITION_BYTES, "definition.md")
            try:
                raw = yaml.safe_load(manifest_bytes.decode("utf-8")) or {}
            except (yaml.YAMLError, UnicodeDecodeError) as exc:
                raise RegistryError(f"Defektes Paket: manifest.yaml unlesbar ({exc}).") from exc
            definition = definition_bytes.decode("utf-8", errors="replace")
        man = _parse_manifest(raw, source="Paket")
        return man, definition

    @staticmethod
    def _read_capped(zf: zipfile.ZipFile, name: str, limit: int, label: str) -> bytes:
        """Liest höchstens ``limit`` entpackte Bytes (gestreamt) → DoS-fest gegen Zip-Bomben."""
        try:
            with zf.open(name) as fh:
                data = fh.read(limit + 1)
        except (zipfile.BadZipFile, OSError) as exc:
            raise RegistryError(f"Defektes Paket: {label} unlesbar ({exc}).") from exc
        if len(data) > limit:
            raise RegistryError(
                f"Paket abgelehnt: {label} überschreitet das Größenlimit ({limit // 1024} KB).",
                status_code=413,
            )
        return data

    def _stage_package(self, data: bytes) -> str:
        import secrets

        os.makedirs(self._staging_dir(), exist_ok=True)
        self._sweep_staging()  # BUG-26-3: alte, nie bestätigte Reste opportunistisch entfernen.
        token = secrets.token_urlsafe(18)
        with open(os.path.join(self._staging_dir(), f"{token}.jupkg"), "wb") as fh:
            fh.write(data)
        return token

    def _sweep_staging(self) -> None:
        """Entfernt Staging-Pakete, deren Vorschau nie bestätigt wurde (älter als TTL)."""
        from time import time

        staging = self._staging_dir()
        try:
            names = os.listdir(staging)
        except (FileNotFoundError, NotADirectoryError):
            return
        cutoff = time() - STAGING_TTL_SECONDS
        for name in names:
            if not name.endswith(".jupkg"):
                continue
            path = os.path.join(staging, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except FileNotFoundError:
                continue
            except OSError:
                continue

    def _staged_path(self, token: str) -> str:
        if not re.match(r"^[A-Za-z0-9_-]{1,64}$", token or ""):
            raise RegistryError("Ungültiges Import-Token.", status_code=400)
        return os.path.join(self._staging_dir(), f"{token}.jupkg")

    def _read_staged(self, token: str) -> bytes:
        try:
            with open(self._staged_path(token), "rb") as fh:
                return fh.read()
        except FileNotFoundError as exc:
            raise RegistryError(
                "Import-Vorschau abgelaufen oder unbekannt — bitte das Paket erneut hochladen.",
                status_code=404,
            ) from exc

    def _discard_staged(self, token: str) -> None:
        try:
            os.remove(self._staged_path(token))
        except (FileNotFoundError, RegistryError):
            pass


def _meta_created_at(versions: list[dict] | None, version: str) -> str:
    for v in versions or []:
        if str(v.get("version")) == version:
            return str(v.get("created_at") or "")
    return ""


def _meta_note(versions: list[dict] | None, version: str) -> str | None:
    for v in versions or []:
        if str(v.get("version")) == version and v.get("note"):
            return str(v["note"])
    return None


def _bump_version(existing: str, incoming: str, history: list[dict]) -> str:
    """Vergibt bei Kollision eine eindeutige Version. Erst die Paket-Version probieren,
    dann numerisch hochzählen, falls sie schon belegt ist."""
    taken = {existing} | {str(v.get("version")) for v in history}
    if incoming and incoming not in taken:
        return incoming
    n = 1
    while True:
        candidate = f"{existing}+{n}"
        if candidate not in taken:
            return candidate
        n += 1


# Modul-Singleton — eine Registry pro Backend-Prozess (Datei-basiert, vgl. policy_store).
registry_store = RegistryStore(settings.registry_root)
