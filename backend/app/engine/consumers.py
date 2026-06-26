"""Konsumenten-Registry (PROJ-24) — wer darf den Vault-Dienst nutzen, mit welchem Scope.

Der Vault wird mit PROJ-24 zu einem **geteilten Dienst**: nicht nur Jupiters eigene
Sessions, auch eingebettete/fremde Apps (PROJ-18, #13) lesen/schreiben/suchen über die
versionierte ``/vault/v1``-API. Jeder externe Konsument identifiziert sich per Header
(``X-Vault-Consumer`` + ``X-Vault-Key``) und hat einen **Scope** — Listen von Glob-Pfaden
(relativ zum Vault-Root), die er lesen bzw. schreiben darf. **Kein Vollzugriff per Default.**

Geladen aus ``consumers.yaml`` (live, mtime-gecacht — gleiches Muster wie ``EngineRegistry``).
Secrets (``api_key``) stehen NUR in dieser gitignored Datei, nie im Repo. Fehlt/kaputt die
Datei → kein externer Konsument (der Dienst bleibt nutzbar, nur leer/intern), statt Crash.

Optionaler eingebauter Voll-Scope-Konsument ``jupiter`` (HTTP-Brücke bis PROJ-25): nur aktiv,
wenn ``settings.vault_internal_consumer_key`` gesetzt ist. Er liest den ganzen Vault und
schreibt im Jupiter-Bereich — derselbe Scope, den interne Aufrufer ohnehin haben.

YAML-Form::

    consumers:
      - id: excalidraw
        api_key: "<secret>"
        read:  ["Agentic OS/Jupiter/Shared/**", "Agentic OS/Jupiter/Knowledge/**"]
        write: ["Agentic OS/Jupiter/Shared/**"]
"""
from __future__ import annotations

import hmac
import logging
import os
import posixpath
import re
from dataclasses import dataclass, field

import yaml

from ..config import settings

log = logging.getLogger(__name__)

INTERNAL_CONSUMER_ID = "jupiter"


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Übersetzt einen Pfad-Glob in eine kompilierte Regex (vault-relativ, ``/``-getrennt).

    ``**`` matcht über Ordnergrenzen hinweg (beliebige Tiefe), ``*`` nur innerhalb eines
    Segments (kein ``/``), ``?`` ein einzelnes Nicht-Slash-Zeichen. Alles andere wird
    literal escaped — so kann ein Scope-Eintrag keine Regex-Sonderzeichen einschleusen.
    """
    g = (glob or "").strip().strip("/")
    out: list[str] = []
    i = 0
    while i < len(g):
        ch = g[i]
        if ch == "*":
            if g[i : i + 2] == "**":
                out.append(".*")
                i += 2
                if i < len(g) and g[i] == "/":  # '**/' soll auch null Segmente matchen
                    i += 1
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def _norm(rel_path: str) -> str:
    """Vault-relativen Pfad für den Scope-Vergleich normalisieren.

    Kollabiert ``..``- und ``.``-Segmente (BUG-24-1-Fix), damit der Scope-Glob auf demselben
    kanonischen Pfad arbeitet wie ``_resolve_read``/``_resolve_write``. Pfade, die nach der
    Normalisierung aus dem Vault-Root ausbrechen (starten mit ``..``), werden als leerer String
    zurückgegeben — kein Scope-Glob matcht ``""`` → automatisch verweigert.
    """
    p = (rel_path or "").replace(os.sep, "/").replace("\\", "/").strip("/")
    if not p:
        return ""
    p = posixpath.normpath(p)          # kollabiert a/../b → b, ./a → a, etc.
    if p.startswith("..") or p == ".":  # Ausbruch aus dem Vault-Root → verweigern
        return ""
    return p


@dataclass
class Consumer:
    """Ein Konsument des geteilten Vault-Dienstes mit Lese-/Schreib-Scope."""

    id: str
    api_key: str
    read: list[str] = field(default_factory=list)
    write: list[str] = field(default_factory=list)
    _read_re: list[re.Pattern[str]] | None = field(default=None, repr=False, compare=False)
    _write_re: list[re.Pattern[str]] | None = field(default=None, repr=False, compare=False)

    def _compile(self) -> None:
        if self._read_re is None:
            self._read_re = [_glob_to_regex(g) for g in self.read]
            self._write_re = [_glob_to_regex(g) for g in self.write]

    def can_read(self, rel_path: str) -> bool:
        self._compile()
        path = _norm(rel_path)
        return any(rx.match(path) for rx in (self._read_re or []))

    def can_write(self, rel_path: str) -> bool:
        self._compile()
        path = _norm(rel_path)
        return any(rx.match(path) for rx in (self._write_re or []))

    def to_read(self) -> dict:
        """Scope-Auszug OHNE Secret (für eine spätere Admin-/Selbstauskunft)."""
        return {"id": self.id, "read": list(self.read), "write": list(self.write)}


def _coerce_consumer(entry: dict) -> Consumer:
    """Baut einen ``Consumer`` aus einem YAML-Eintrag; wirft ``ValueError`` bei Unsinn."""
    if not isinstance(entry, dict):
        raise ValueError("Konsumenten-Eintrag muss ein Objekt sein.")
    cid = str(entry.get("id") or "").strip()
    if not cid:
        raise ValueError("Konsumenten-Eintrag ohne `id`.")
    api_key = str(entry.get("api_key") or "").strip()
    if not api_key:
        raise ValueError(f"Konsument „{cid}“: `api_key` fehlt.")
    read = [str(g) for g in (entry.get("read") or [])]
    write = [str(g) for g in (entry.get("write") or [])]
    return Consumer(id=cid, api_key=api_key, read=read, write=write)


def _builtin_internal() -> Consumer | None:
    """Optionaler Voll-Scope-Konsument ``jupiter`` (nur wenn ein Key konfiguriert ist)."""
    key = (settings.vault_internal_consumer_key or "").strip()
    if not key:
        return None
    subdir = _norm(settings.vault_jupiter_subdir)
    return Consumer(
        id=INTERNAL_CONSUMER_ID,
        api_key=key,
        read=["**"],                       # ganzer Vault lesbar
        write=[f"{subdir}/**"],            # schreiben nur im Jupiter-Bereich
    )


class ConsumerRegistry:
    """Lädt Konsumenten-Profile aus YAML — live, mtime-gecacht. Kein Default-Vollzugriff."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._mtime: float | None = None
        self._consumers: dict[str, Consumer] = {}
        self._warning: str | None = None
        self._source: str = "default"
        self._loaded_once = False

    def _base(self) -> dict[str, Consumer]:
        internal = _builtin_internal()
        return {internal.id: internal} if internal else {}

    def _reload_if_changed(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            # Datei fehlt → nur der (optionale) interne Konsument; nie hängenbleiben.
            if self._source != "default" or not self._loaded_once:
                self._consumers = self._base()
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
        consumers = self._base()
        warnings: list[str] = []
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            entries = data.get("consumers") if isinstance(data, dict) else None
            for entry in entries or []:
                try:
                    cons = _coerce_consumer(entry)
                except ValueError as exc:  # einzelner Eintrag defekt → überspringen, Rest lädt.
                    warnings.append(str(exc))
                    log.warning("Konsumenten-Registry: Eintrag übersprungen — %s", exc)
                    continue
                if cons.id == INTERNAL_CONSUMER_ID:
                    warnings.append(f"id „{INTERNAL_CONSUMER_ID}“ ist reserviert — übersprungen.")
                    continue
                consumers[cons.id] = cons
            self._source = self._path
        except (OSError, yaml.YAMLError) as exc:
            log.warning("Konsumenten-Registry %s ungültig: %s.", self._path, exc)
            warnings.append(f"consumers.yaml ungültig ({exc})")
            self._source = "default"
        self._consumers = consumers
        self._warning = "; ".join(warnings) or None

    def authenticate(self, consumer_id: str | None, api_key: str | None) -> Consumer | None:
        """``Consumer`` bei gültiger id+key, sonst ``None`` (Key konstantzeit-verglichen)."""
        self._reload_if_changed()
        if not consumer_id or not api_key:
            return None
        cons = self._consumers.get(consumer_id)
        if cons is None:
            return None
        if not hmac.compare_digest(cons.api_key, str(api_key)):
            return None
        return cons

    def snapshot(self) -> dict:
        self._reload_if_changed()
        return {
            "consumers": [c.to_read() for c in self._consumers.values()],
            "source": self._source,
            "warning": self._warning,
        }


# Modul-Singleton — eine Registry pro Backend-Prozess (live aus der Datei).
consumer_registry = ConsumerRegistry(settings.consumers_config_path)
