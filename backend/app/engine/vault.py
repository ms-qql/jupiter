"""VaultService — bindet den Hal-Vault (Obsidian-MD) als Daten-/Wissensschicht an (PROJ-2).

Reine Datei-I/O (kein DB/RLS im MVP). Asymmetrie (Tech-Design):
- **Lesen/Suchen** dürfen den GANZEN Vault sehen (read-only) → Grundlage RAG (#23).
- **Schreiben** ist IMMER auf den Jupiter-Unterbaum ``<vault>/Agentic OS/Jupiter`` begrenzt
  (Pfad-Härtung wie ``validate_project_path`` in ``manager.py``).

Layout (verändert die bestehende PARA-Struktur NICHT):

    <vault_root>/Agentic OS/Jupiter/
        Sessions/    # rohe Session-Logs (1 Datei je Session, immutable Snapshots)
        Handovers/   # kuratierte Übergabe-Dokumente (getrennt → AC "roh vs. kuratiert")

Geschriebene Dateien sind valides Obsidian-MD mit YAML-Frontmatter
(mind. ``owner``, ``session_id``, ``created``, ``type``). Writes sind atomar
(temp + ``os.replace``); Default bei Kollision = ``append`` (mit Datei-Lock).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import settings

# type → Unterordner im Jupiter-Bereich.
# PROJ-15: dritte Schicht ``curated`` (Knowledge/) — kuratiertes Wissen, getrennt von
# rohen Logs (Sessions/) und Handovers/. Roh ↔ kuratiert ist damit eine Dateisystem-Grenze.
_TYPE_DIRS = {"session_log": "Sessions", "handover": "Handovers", "curated": "Knowledge"}

_UMLAUT = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}
# Obergrenzen für die Suche (DoS-Schutz / saubere Ausschnitte).
_MAX_SEARCH_HITS = 100
_EXCERPT_CHARS = 160
_MAX_FILE_BYTES = 2_000_000  # Dateien darüber bei der Suche überspringen.

# PROJ-19 (#23) — Pointer/RAG: längere, gerankte Ausschnitte statt First-Hit.
_RAG_SNIPPET_CHARS = 400
_RAG_TOP_N_MAX = 20
_RAG_MAX_POSITIONS = 2000  # Treffer-Positionen je Datei kappen (DoS-Schutz).
# Mini-Stoppwörter (DE/EN) — verhindern, dass Allerweltswörter das Ranking dominieren.
_STOPWORDS = frozenset(
    "der die das und oder ein eine einen dem den des ist sind war auf für mit von "
    "im in zu zum zur als auch nicht wie was wer wo wann warum welche welcher "
    "the and for with from this that are was you your what how why".split()
)


def _rag_terms(query: str) -> list[str]:
    """Query in suchbare Terme zerlegen (lowercase, ≥2 Zeichen, ohne Stoppwörter, dedupliziert)."""
    raw = re.split(r"[^a-z0-9äöüß]+", (query or "").lower())
    seen: dict[str, None] = {}
    for t in raw:
        if len(t) >= 2 and t not in _STOPWORDS:
            seen.setdefault(t, None)
    return list(seen)


def _best_window(text_lower: str, terms: list[str], width: int) -> tuple[int, int]:
    """Dichtestes Fenster der Breite ``width`` → (Start-Offset, Treffer im Fenster).

    Sammelt alle Term-Positionen und schiebt ein Fenster darüber; liefert den Start
    des Fensters mit den meisten Treffern, damit der Ausschnitt dort landet, wo die
    Query-Begriffe gehäuft auftreten (statt am ersten zufälligen Vorkommen).
    """
    positions: list[int] = []
    for term in terms:
        start = 0
        while True:
            idx = text_lower.find(term, start)
            if idx == -1:
                break
            positions.append(idx)
            start = idx + len(term)
            if len(positions) >= _RAG_MAX_POSITIONS:
                break
    if not positions:
        return 0, 0
    positions.sort()
    best_pos, best_count, right = positions[0], 1, 0
    for left in range(len(positions)):
        if right < left:
            right = left
        while right + 1 < len(positions) and positions[right + 1] - positions[left] <= width:
            right += 1
        count = right - left + 1
        if count > best_count:
            best_count, best_pos = count, positions[left]
    # Fenster leicht vor den ersten Cluster-Treffer setzen → etwas Kontext davor.
    return max(0, best_pos - width // 4), best_count


def _now() -> datetime:
    return datetime.now(timezone.utc)


def slugify(text: str) -> str:
    """ASCII-Slug für Dateinamen — Umlaute/Sonderzeichen sauber abbilden (Edge-Case Spec)."""
    text = "".join(_UMLAUT.get(ch, ch) for ch in (text or ""))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or "untitled"


def safe_id_segment(session_id: str | None) -> str:
    """Sichere Kurz-ID für den Dateinamen (QA-2.1).

    Client-gelieferte ``session_id`` kann ``/`` oder ``..`` enthalten → würde sonst
    verschachtelte Ordner erzeugen. Hier auf ``[A-Za-z0-9_-]`` reduziert und auf 8
    Zeichen gekürzt; der echte Wert landet unverändert (escaped) im Frontmatter.
    """
    return re.sub(r"[^A-Za-z0-9_-]+", "", session_id or "")[:8]


def _build_frontmatter(meta: dict) -> str:
    """YAML-Frontmatter aus einem flachen dict (None-Werte werden ausgelassen)."""
    lines = ["---"]
    for key, value in meta.items():
        if value is None:
            continue
        # json.dumps liefert einen gültigen doppelt-gequoteten YAML-Scalar (auch für Umlaute).
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Trennt einen führenden ``---``-Block vom Body (tolerant, best-effort)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        # Block reicht bis Dateiende (ohne nachfolgenden Body).
        if text.rstrip().endswith("---"):
            block = text[4 : text.rstrip().rfind("\n---")]
            return _parse_block(block), ""
        return {}, text
    return _parse_block(text[4:end]), text[end + 5 :]


def _parse_block(block: str) -> dict:
    out: dict = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value[:1] == '"':
            try:
                value = json.loads(value)
            except ValueError:
                pass
        elif value[:1] == "'":
            value = value.strip("'")
        out[key] = value
    return out


@dataclass
class VaultWriteResult:
    path: str       # relativ zu vault_root (direkt über die Read-API lesbar)
    type: str
    created: str


class VaultService:
    """Datei-I/O gegen den Hal-Vault. Lesen/Suchen vault-weit, Schreiben nur im Jupiter-Bereich."""

    def __init__(self, vault_root: str | None = None, jupiter_subdir: str | None = None) -> None:
        self.vault_root = os.path.realpath(vault_root or settings.vault_root)
        self.jupiter_subdir = jupiter_subdir or settings.vault_jupiter_subdir
        self.write_root = os.path.realpath(os.path.join(self.vault_root, self.jupiter_subdir))

    # --- Pfad-Härtung ------------------------------------------------------

    def _resolve_read(self, rel_path: str) -> str:
        """Realpfad innerhalb des GANZEN Vaults; wirft ``ValueError`` bei Ausbruch."""
        return self._resolve(rel_path, self.vault_root)

    def _resolve_write(self, rel_path: str) -> str:
        """Realpfad innerhalb des Jupiter-Unterbaums; wirft ``ValueError`` bei Ausbruch."""
        return self._resolve(rel_path, self.write_root)

    @staticmethod
    def _resolve(rel_path: str, base: str) -> str:
        if not rel_path or os.path.isabs(rel_path):
            raise ValueError("Pfad muss relativ zum Vault angegeben werden.")
        real = os.path.realpath(os.path.join(base, rel_path))
        if real != base and not real.startswith(base + os.sep):
            raise ValueError("Pfad liegt außerhalb des erlaubten Vault-Bereichs.")
        return real

    def _rel(self, real_path: str) -> str:
        return os.path.relpath(real_path, self.vault_root)

    # --- Lesen / Auflisten / Suchen ----------------------------------------

    def read_file(self, rel_path: str) -> dict:
        """Liest eine MD-Datei (vault-weit). Wirft ``FileNotFoundError`` wenn nicht vorhanden."""
        real = self._resolve_read(rel_path)
        with open(real, encoding="utf-8") as fh:  # FileNotFoundError → 404 in der Route
            content = fh.read()
        frontmatter, body = _parse_frontmatter(content)
        return {"path": self._rel(real), "frontmatter": frontmatter, "body": body, "content": content}

    def list_files(self, subdir: str = "") -> list[dict]:
        """Listet ``*.md`` im Jupiter-Schreibbereich (optional ein Unterordner darunter)."""
        root = self._resolve_write(subdir) if subdir else self.write_root
        out: list[dict] = []
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if not name.endswith(".md"):
                    continue
                full = os.path.join(dirpath, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                out.append(
                    {
                        "path": self._rel(full),
                        "name": name,
                        "size": st.st_size,
                        "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                    }
                )
        out.sort(key=lambda f: f["path"])
        return out

    def search(self, query: str, limit: int = 20, subdir: str = "") -> list[dict]:
        """Substring-Suche (case-insensitiv) über MD im Vault → Pfad + Ausschnitt.

        ``subdir`` (relativ zum Vault) grenzt die Suche auf einen Unterbaum ein —
        z. B. den kuratierten ``Knowledge/``-Bereich (PROJ-15); leer = ganzer Vault.
        """
        needle = (query or "").strip().lower()
        if not needle:
            return []
        limit = max(1, min(limit, _MAX_SEARCH_HITS))
        base = self._resolve_read(subdir) if subdir else self.vault_root
        hits: list[dict] = []
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                if not name.endswith(".md"):
                    continue
                full = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(full) > _MAX_FILE_BYTES:
                        continue
                    with open(full, encoding="utf-8") as fh:
                        text = fh.read()
                except OSError:
                    continue
                idx = text.lower().find(needle)
                if idx == -1:
                    continue
                line_no = text.count("\n", 0, idx) + 1
                start = max(0, idx - _EXCERPT_CHARS // 2)
                excerpt = text[start : start + _EXCERPT_CHARS].replace("\n", " ").strip()
                hits.append({"path": self._rel(full), "line": line_no, "excerpt": excerpt})
                if len(hits) >= limit:
                    hits.sort(key=lambda h: h["path"])
                    return hits
        hits.sort(key=lambda h: h["path"])
        return hits

    # --- Pointer/RAG (PROJ-19 #23) -----------------------------------------

    def relevant_snippets(
        self, query: str, top_n: int = 5, snippet_chars: int = _RAG_SNIPPET_CHARS, subdir: str = ""
    ) -> list[dict]:
        """Gerankte, relevante Ausschnitte statt Volltext (Pointer/RAG).

        Im Gegensatz zu :meth:`search` (erster Substring-Treffer je Datei) wird hier
        mehr-termig gesucht, je Datei der **dichteste** Ausschnitt gewählt und über
        Dateien hinweg nach Relevanz sortiert (mehr getroffene Query-Begriffe zuerst,
        dann Gesamthäufigkeit). Liefert ``[{path, line, snippet, score, terms_matched,
        full_chars}]`` — ``full_chars`` ist die Volltext-Größe der Datei (für die
        Kontext-Ersparnis-Messung). Leere Liste = kein Treffer (Caller-Fallback).
        """
        terms = _rag_terms(query)
        if not terms:
            return []
        top_n = max(1, min(top_n, _RAG_TOP_N_MAX))
        base = self._resolve_read(subdir) if subdir else self.vault_root
        scored: list[dict] = []
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                if not name.endswith(".md"):
                    continue
                full = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(full) > _MAX_FILE_BYTES:
                        continue
                    with open(full, encoding="utf-8") as fh:
                        text = fh.read()
                except OSError:
                    continue
                lower = text.lower()
                counts = {t: lower.count(t) for t in terms}
                total = sum(counts.values())
                if total == 0:
                    continue
                matched = sum(1 for t in terms if counts[t])
                # Mehr getroffene Begriffe dominieren die Häufigkeit (distinct zuerst).
                score = matched * 1000 + total
                start, _ = _best_window(lower, terms, snippet_chars)
                excerpt = " ".join(text[start : start + snippet_chars].split())
                scored.append(
                    {
                        "path": self._rel(full),
                        "line": text.count("\n", 0, start) + 1,
                        "snippet": excerpt,
                        "score": score,
                        "terms_matched": matched,
                        "full_chars": len(text),
                    }
                )
        scored.sort(key=lambda s: (-s["score"], s["path"]))
        return scored[:top_n]

    def rag_preview(
        self,
        query: str,
        top_n: int = 5,
        snippet_chars: int = _RAG_SNIPPET_CHARS,
        *,
        curated: bool = False,
    ) -> dict:
        """:meth:`relevant_snippets` + Mess-/Fallback-Hülle für die Route.

        ``curated=True`` grenzt auf den kuratierten ``Knowledge/``-Bereich ein
        (analog :meth:`search_curated`). Macht die Kontext-Ersparnis sichtbar
        (AC „messbar geringerer Verbrauch"): ``context_chars`` (Summe der Snippets)
        vs. ``fulltext_chars`` (Volltext der Top-N-Dateien). ``fallback=True``
        signalisiert „kein relevanter Ausschnitt" → der Caller lädt größeren
        Ausschnitt/Volltext mit Hinweis (Edge Case).
        """
        subdir = self._curated_subdir if curated else ""
        snippets = self.relevant_snippets(query, top_n, snippet_chars, subdir)
        context_chars = sum(len(s["snippet"]) for s in snippets)
        fulltext_chars = sum(s["full_chars"] for s in snippets)
        reduction = (
            round(100.0 * (1.0 - context_chars / fulltext_chars), 1)
            if fulltext_chars > 0
            else 0.0
        )
        fallback = not snippets
        return {
            "query": query,
            "snippets": snippets,
            "fallback": fallback,
            "reason": (
                "Kein relevanter Ausschnitt gefunden — Caller sollte auf größeren "
                "Ausschnitt/Volltext zurückfallen."
                if fallback
                else None
            ),
            "context_chars": context_chars,
            "fulltext_chars": fulltext_chars,
            "reduction_pct": reduction,
        }

    # --- Schreiben ---------------------------------------------------------

    def write(
        self,
        *,
        type: str,
        body: str,
        session_id: str | None = None,
        owner: str | None = None,
        title: str | None = None,
        created: datetime | None = None,
        on_exists: str = "append",
        extra_meta: dict | None = None,
        dated: bool = True,
    ) -> VaultWriteResult:
        """Schreibt valides MD in den Jupiter-Bereich. ``on_exists``: append | version | error.

        ``extra_meta`` ergänzt zusätzliche Frontmatter-Felder (PROJ-15: z. B.
        ``source_session_id``, ``curation_marker``). ``dated=False`` erzeugt eine
        themen-stabile Datei ohne Datums-/ID-Präfix (kuratiertes Wissen ist eine
        lebende Notiz → gleicher Titel = gleiche Datei → Append-Dedup).
        """
        subdir = _TYPE_DIRS.get(type)
        if subdir is None:
            raise ValueError(f"Unbekannter type '{type}'. Erlaubt: {sorted(_TYPE_DIRS)}.")
        if on_exists not in ("append", "version", "error"):
            raise ValueError("on_exists muss append | version | error sein.")

        ts = created or _now()
        if dated:
            filename = f"{ts.strftime('%Y-%m-%d')}--{slugify(title or type)}"
            short_id = safe_id_segment(session_id)  # QA-2.1: keine ../-Ordner über den Dateinamen
            if short_id:
                filename += f"-{short_id}"
        else:
            filename = slugify(title or type)
        filename += ".md"

        target = self._resolve_write(os.path.join(subdir, filename))
        body_text = body if body.endswith("\n") else body + "\n"
        meta = {
            "owner": owner or settings.default_owner,
            "session_id": session_id,
            "created": ts.isoformat(),
            "type": type,
            "title": title,
        }
        if extra_meta:
            meta.update(extra_meta)  # None-Werte lässt _build_frontmatter aus.
        frontmatter = _build_frontmatter(meta)
        full = frontmatter + "\n" + body_text

        if not os.path.exists(target):
            self._atomic_write(target, full)
        elif on_exists == "error":
            raise FileExistsError(f"Datei existiert bereits: {self._rel(target)}")
        elif on_exists == "version":
            target = self._next_version(target)
            self._atomic_write(target, full)
        else:  # append: nur den Body anhängen (kein zweites Frontmatter), per Lock abgesichert
            self._append_locked(target, "\n" + body_text)

        return VaultWriteResult(path=self._rel(target), type=type, created=ts.isoformat())

    def write_curated_note(
        self,
        *,
        title: str,
        body: str,
        source_session_id: str | None = None,
        marker: str | None = None,
        owner: str | None = None,
        created: datetime | None = None,
        on_exists: str = "append",
    ) -> VaultWriteResult:
        """PROJ-15: kuratierte Wissens-Notiz nach ``Knowledge/`` schreiben.

        Themen-stabile Datei (``dated=False`` → Dateiname = Titel-Slug): gleicher
        Titel ⇒ gleiche Datei ⇒ Default ``append`` (Dedup „gleiches Thema → anhängen"
        statt neu anlegen; eine bereits manuell editierte Notiz wird **nie** blind
        überschrieben). ``source_session_id`` + ``marker`` landen im Frontmatter
        (Nachvollziehbarkeit).
        """
        return self.write(
            type="curated",
            body=body,
            title=title,
            session_id=None,  # kein Kurz-ID-Suffix → themen-stabiler Dateiname
            owner=owner,
            created=created,
            on_exists=on_exists,
            dated=False,
            extra_meta={"source_session_id": source_session_id, "curation_marker": marker},
        )

    @property
    def _curated_subdir(self) -> str:
        """Pfad des kuratierten Bereichs relativ zum Vault (für die scoped Suche)."""
        return os.path.join(self.jupiter_subdir, _TYPE_DIRS["curated"])

    def search_curated(self, query: str, limit: int = 20) -> list[dict]:
        """PROJ-15: Suche NUR über kuratiertes Wissen (``Knowledge/``) — projektübergreifend.

        Der zurückgelieferte ``path`` ist vault-relativ und dient zugleich als Backlink
        (über den MD-Reader öffenbar).
        """
        return self.search(query, limit, subdir=self._curated_subdir)

    def write_session_log(self, state, body_md: str, on_exists: str = "append") -> VaultWriteResult:
        """Convenience: rohes Session-Log nach ``Sessions/`` schreiben (Auto-Hook im Manager)."""
        title = os.path.basename(state.project_path.rstrip("/")) or "session"
        return self.write(
            type="session_log",
            body=body_md,
            session_id=state.session_id,
            owner=state.owner,
            title=title,
            created=state.created_at,
            on_exists=on_exists,
            # PROJ-17: Projektpfad ins Frontmatter, damit ein reiner Vault-Wiederaufbau
            # (Live-Index weg) den Strang wiederherstellen kann — das Session-Log
            # trägt sonst keinen Pfad und die Recovery wäre blockiert.
            extra_meta={
                "project_path": state.project_path,
                "project_name": state.project_name or title,
            },
        )

    # --- atomare Datei-Operationen -----------------------------------------

    @staticmethod
    def _atomic_write(path: str, content: str) -> None:
        """temp-Datei im Zielordner + ``os.replace`` → kein halb geschriebenes MD bei Absturz."""
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)  # atomar auf POSIX
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @staticmethod
    def _append_locked(path: str, content: str) -> None:
        """Anhängen mit exklusivem Datei-Lock → kein Datenverlust bei parallelen Sessions."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            try:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            except (ImportError, OSError):
                pass  # Lock best-effort (non-POSIX) — Append bleibt korrekt.
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())

    @staticmethod
    def _next_version(path: str) -> str:
        base, ext = os.path.splitext(path)
        n = 2
        while os.path.exists(f"{base}-{n}{ext}"):
            n += 1
        return f"{base}-{n}{ext}"
