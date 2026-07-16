"""Buch-Nuggets-Worker (PROJ-53).

Orchestrierungs-Schicht um den **neuen** ``hal-book-nuggets``-Skill: ein
asyncio-Worker (Vorbild ``VideoSummaryWorker``) arbeitet die SQLite-Warteschlange
**sequenziell** ab — pro Buch genau eine headless Claude-Session
(``SessionManager.create``).

Unterschiede zu Video Summary (PROJ-41):
- Quelle ist eine **Datei (Upload) oder URL**, nicht nur eine URL.
- **Modellwahl pro Buch** mit Stufen-Logik (günstig für Chunk-Extrakte, stark für
  Konsolidierung + Contra). Die Session läuft auf dem **Konsolidierungs-Modell**;
  die günstigen Extrakte realisiert der Skill über Sub-Agenten mit Modell-Override.
- **Kein Cooldown/Zeitplan** — Bücher blocken nicht wie YouTube; Sequenzialität +
  die bestehenden Session-Limits (PROJ-14/16) genügen.
- **Kostenschätzung** (best-effort) + **Duplikaterkennung** (D9).

Grundsatz wie PROJ-41: alle Steuerlogik liegt im Backend, nie im Client (Tab zu =
Verarbeitung läuft serverseitig weiter).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from ..config import settings
from ..db.book_nuggets_queue import DONE, ERROR, PENDING, RUNNING, BookNuggetsRepository
from .manager import (
    DONE as SESSION_DONE,
    ERROR as SESSION_ERROR,
    WAITING as SESSION_WAITING,
    SessionLimitError,
    SessionManager,
)

logger = logging.getLogger(__name__)

# Erlaubte Umwandlungs-Modelle (Kurz-Aliase der Claude-CLI). Server-Whitelist
# gegen ungültige Slugs (PROJ-18-Slug-Falle).
VALID_MODELS: tuple[str, ...] = ("haiku", "sonnet", "opus")
VALID_MODES: tuple[str, ...] = ("staged", "single")

# Im MVP unterstützte Dateiformate (D-Entscheidung: mobi = Fast-Follow/Phase 2).
MVP_EXTENSIONS: frozenset[str] = frozenset({"pdf", "epub", "txt", "docx"})

# Grobe, gemittelte Preise pro 1 Mio. Tokens (USD) — NUR für die Best-effort-
# Kostenschätzung, keine Abrechnung. Bücher sind fast nur Input.
PRICE_PER_MTOK: dict[str, float] = {"haiku": 1.0, "sonnet": 6.0, "opus": 18.0}

# Maschinenlesbarer Abschluss-Marker, den der Prompt von der Session anfordert.
_RESULT_MARKER = "JUPITER_BOOK_RESULT"
# ponytail: Safety ceiling for pathological "still waiting" loops; configure only if real runs hit it.
_MAX_CONTINUATIONS = 12
_CONTINUE_PROMPT = (
    "Setze die Buchzusammenfassung jetzt fort. Warte nicht nur auf Sub-Agenten: "
    "Bearbeite fehlende Chunks bei Bedarf selbst. Erstelle die Markdown-Notiz und PDF "
    "und gib erst danach den vollständigen JUPITER_BOOK_RESULT-Block aus."
)
_NOTE_RE = re.compile(r"^\s*note:\s*(.+?)\s*$", re.MULTILINE)
_PDF_RE = re.compile(r"^\s*pdf:\s*(.+?)\s*$", re.MULTILINE)
_DIR_RE = re.compile(r"^\s*dir:\s*(.+?)\s*$", re.MULTILINE)
_TITLE_RE = re.compile(r"^\s*title:\s*(.+?)\s*$", re.MULTILINE)
_AUTHOR_RE = re.compile(r"^\s*author:\s*(.+?)\s*$", re.MULTILINE)

# Phasen-Marker (best-effort Fortschrittsanzeige aus dem Transcript).
_PHASE_MARKER = "JUPITER_BOOK_PHASE:"
_VALID_PHASES = ("parsing", "analysis", "contra", "pdf")


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except (ValueError, AttributeError):
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def extension_of(ref: str) -> str:
    """Kleingeschriebene Datei-Endung ohne Punkt (aus Pfad ODER URL-Pfadteil)."""
    name = ref
    if is_valid_url(ref):
        name = urlparse(ref).path
    return Path(name).suffix.lower().lstrip(".")


def validate_source(source_type: str, source_ref: str) -> tuple[str | None, str | None]:
    """Prüft eine Quelle. Gibt ``(error_message, normalized_ref)`` zurück;
    ``error_message`` ist ``None`` bei gültiger Quelle (deutsche Meldungen)."""
    ref = (source_ref or "").strip()
    if not ref:
        return "Keine Quelle angegeben.", None
    if source_type == "url":
        if not is_valid_url(ref):
            return (
                "Keine gültige Datei-URL erkannt. Bitte einen direkten http(s)-Link "
                "zu einer Buchdatei (pdf/epub/txt/docx) angeben — keine Produktseite.",
                None,
            )
    elif source_type == "upload":
        pass  # Pfad wurde über /files/upload bereits auf allowed_roots geprüft.
    else:
        return "Unbekannter Quelltyp (erlaubt: url | upload).", None

    ext = extension_of(ref)
    if ext == "mobi":
        return (
            "mobi wird im MVP nicht unterstützt (DRM-anfällig, Konverter nicht "
            "installiert). Bitte pdf, epub, txt oder docx verwenden.",
            None,
        )
    if ext and ext not in MVP_EXTENSIONS:
        return (
            f"Format .{ext} wird nicht unterstützt. Erlaubt: "
            f"{', '.join(sorted(MVP_EXTENSIONS))}.",
            None,
        )
    # Leere Endung bei URL ist erlaubt (Content-Type kennt erst der Skill).
    return None, ref


def compute_book_hash_sync(source_type: str, source_ref: str) -> str:
    """Identität eines Buchs für die Duplikaterkennung (D9).

    Upload → SHA-256 des Datei-Inhalts (gleiche Datei = gleiches Buch).
    URL → die URL selbst (ohne Download keine Inhalts-Identität verfügbar)."""
    if source_type == "upload":
        try:
            h = hashlib.sha256()
            with open(source_ref, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            return "sha256:" + h.hexdigest()
        except OSError:
            # Datei (noch) nicht lesbar → auf Pfad-Identität zurückfallen.
            return "path:" + source_ref
    return "url:" + source_ref.strip()


def estimate_cost(
    size_bytes: int | None,
    model_mode: str,
    model_extract: str,
    model_consolidate: str,
    page_limit: int | None = None,
) -> dict:
    """Best-effort-Kostenschätzung aus der Dateigröße (Tech-Design E: bewusst grob,
    kein hartes Limit). Unbekannte Größe (z. B. URL) → ``est_tokens``/``est_cost`` None.

    Heuristik: ~4 Byte/Token (Text). Bei ``staged`` verarbeitet das günstige
    Extrakt-Modell ~die ganze Buchmenge, das starke Modell ~20 % (Konsolidierung +
    Contra). Bei ``single`` läuft alles über ein Modell."""
    pages = None
    est_tokens = None
    est_cost = None
    if size_bytes is not None and size_bytes > 0:
        est_tokens = int(size_bytes / 4)
        pages = max(1, int(size_bytes / 2000))  # ~2 KB/Seite (sehr grob)
        if page_limit:
            cap_tokens = page_limit * 500  # ~500 Token/Seite
            est_tokens = min(est_tokens, cap_tokens)
            pages = min(pages, page_limit)
        p_ext = PRICE_PER_MTOK.get(model_extract, PRICE_PER_MTOK["sonnet"])
        p_con = PRICE_PER_MTOK.get(model_consolidate, PRICE_PER_MTOK["opus"])
        if model_mode == "single":
            est_cost = est_tokens / 1_000_000 * p_con
        else:
            est_cost = (
                est_tokens / 1_000_000 * p_ext
                + est_tokens * 0.2 / 1_000_000 * p_con
            )
        est_cost = round(est_cost, 4)
    return {"pages": pages, "est_tokens": est_tokens, "est_cost": est_cost}


def build_prompt(
    source_type: str,
    source_ref: str,
    output_subdir: str,
    model_mode: str,
    model_extract: str,
    page_limit: int | None,
    on_duplicate: str | None,
) -> str:
    """Initial-Prompt der Verarbeitungs-Session: ruft den ``hal-book-nuggets``-Skill
    auf und steckt die Rahmenbedingungen ab (headless, keine Rückfragen).

    Die Stufen-Logik (D7) wird dem Skill mitgeteilt: bei ``staged`` soll er die
    Chunk-Extrakte über Sub-Agenten mit dem günstigen ``model_extract`` fahren; bei
    ``single`` ein Modell für alles. Das **Haupt**-Modell der Session ist das starke
    Konsolidierungs-Modell (wird vom Worker als ``model=`` gesetzt)."""
    subdir = output_subdir.strip().strip("/")
    src_line = (
        f"Quelle (URL): {source_ref}" if source_type == "url"
        else f"Quelle (lokale Datei): {source_ref}"
    )
    limit_line = (
        f"- Seitenlimit: max. {page_limit} Seiten verarbeiten.\n" if page_limit
        else "- Kein Seitenlimit.\n"
    )
    if model_mode == "staged":
        model_line = (
            f"- Modell-Modus: STAGED. Fahre die Kapitel-/Chunk-Extrakte über "
            f"Sub-Agenten mit dem günstigen Modell \"{model_extract}\"; "
            f"Konsolidierung der 11 Blöcke + Contra-Kapitel mit DEINEM Hauptmodell.\n"
        )
    else:
        model_line = (
            "- Modell-Modus: SINGLE. Nutze für ALLES dein Hauptmodell "
            "(keine günstigen Sub-Agenten).\n"
        )
    dup_line = (
        "- Existiert der Zielordner bereits: bestehende Dateien ÜBERSCHREIBEN.\n"
        if on_duplicate == "overwrite"
        else (
            "- Existiert der Zielordner bereits: eine NEUE VERSION mit Zeitstempel-"
            "Suffix \"--vJJJJMMTT-HHMM\" anlegen (nichts überschreiben).\n"
            if on_duplicate == "new_version" else ""
        )
    )
    return (
        f"/hal-book-nuggets\n\n"
        f"{src_line}\n\n"
        "Wichtige Rahmenbedingungen (headless, KEINE Rueckfragen moeglich):\n"
        f"- Speichere das Nugget (Markdown + Abbildungen + konsolidierte PDF) "
        f"AUSSCHLIESSLICH unter \"{subdir}/<Autor>-<Titel>/\" (relativ zum "
        f"Vault-Root). Lege Ordner bei Bedarf an.\n"
        f"{model_line}"
        f"{limit_line}"
        f"{dup_line}"
        "- Stelle KEINE Rueckfragen, nutze KEIN AskUserQuestion.\n"
        "- Kann der Text nicht extrahiert werden (DRM / nur gescannte Bilder ohne "
        "Textebene): brich ab und gib eine knappe Fehlerursache aus, erfinde NICHTS.\n"
        "- Melde Fortschritt mit Zeilen \"JUPITER_BOOK_PHASE: parsing|analysis|contra|pdf\".\n"
        "- Gib GANZ AM ENDE exakt diesen Block aus (je eigene Zeile, absolute Pfade):\n"
        f"{_RESULT_MARKER}\n"
        "title: <erkannter Buchtitel>\n"
        "author: <erkannter Autor>\n"
        "dir: <absoluter Pfad des Nugget-Ordners>\n"
        "note: <absoluter Pfad zur .md-Notiz>\n"
        "pdf: <absoluter Pfad zum .pdf>\n"
    )


def parse_result_paths(text: str) -> dict:
    """Liest Ergebnis-Felder aus dem Abschlussbericht (best-effort).

    Sucht den letzten ``JUPITER_BOOK_RESULT``-Marker und die darauf folgenden
    Felder. Kein Marker → alles ``None`` (Eintrag bleibt trotzdem „fertig")."""
    out = {"title": None, "author": None, "dir": None, "note": None, "pdf": None}
    if not text:
        return out
    idx = text.rfind(_RESULT_MARKER)
    tail = text[idx + len(_RESULT_MARKER):] if idx != -1 else text
    for key, rx in (
        ("title", _TITLE_RE), ("author", _AUTHOR_RE), ("dir", _DIR_RE),
        ("note", _NOTE_RE), ("pdf", _PDF_RE),
    ):
        m = rx.search(tail)
        val = m.group(1).strip() if m else None
        # Platzhalter aus dem Prompt (z. B. „<erkannter Autor>") nicht übernehmen.
        out[key] = val if (val and not val.startswith("<")) else None
    return out


def result_is_complete(text: str, result: dict) -> bool:
    """Ein Nugget zählt erst mit Abschlussmarker und beiden Artefakten als fertig."""
    return (
        _RESULT_MARKER in text
        and all(result.get(key) and Path(result[key]).is_file() for key in ("note", "pdf"))
    )


def parse_phase(text: str) -> str | None:
    """Letzte gemeldete Verarbeitungs-Phase aus dem Transcript (best-effort)."""
    if not text:
        return None
    last = None
    for m in re.finditer(re.escape(_PHASE_MARKER) + r"\s*(\w+)", text):
        cand = m.group(1).strip().lower()
        if cand in _VALID_PHASES:
            last = cand
    return last


def _now() -> datetime:
    return datetime.now()


class BookNuggetsWorker:
    """Sequenzieller Queue-Worker (PROJ-53). Genau **eine** Session gleichzeitig.

    ``tick()`` wird vom Lifespan-Loop niederfrequent aufgerufen und ist defensiv.
    Laufzeit-Zustand (draining/current) lebt im Speicher; Queue + Einstellungen
    sind persistent (überleben Neustart)."""

    def __init__(self, manager: SessionManager, repo: BookNuggetsRepository) -> None:
        self._manager = manager
        self._repo = repo
        self._draining = False
        self._current_id: int | None = None
        self._current_session_id: str | None = None
        self._continuations = 0
        self._last_incomplete_output: str | None = None

    # --- Lifecycle ---------------------------------------------------------

    async def startup(self) -> None:
        """Idempotenter Start: Schema anlegen, verwaiste ``running`` → ``pending``."""
        await self._repo.init()
        await self._repo.reset_running()
        rows = await self._repo.list_queue()
        for row in rows:
            if row["status"] == DONE and not all(
                row.get(key) and Path(row[key]).is_file()
                for key in ("result_note_path", "result_pdf_path")
            ):
                await self._repo.update(
                    row["id"], status=ERROR,
                    error_message="Historischer Eintrag ohne vollständige Markdown-/PDF-Artefakte.",
                )
        self._draining = any(row["status"] == PENDING for row in rows)

    # --- Öffentliche Steuerung (von den Routen aufgerufen) -----------------

    async def estimate(
        self,
        source_type: str,
        source_ref: str,
        model_mode: str,
        model_extract: str,
        model_consolidate: str,
        page_limit: int | None = None,
    ) -> dict:
        """Best-effort-Kostenschätzung VOR dem Einreihen (D7)."""
        err, ref = validate_source(source_type, source_ref)
        if err:
            raise ValueError(err)
        size = None
        if source_type == "upload":
            try:
                size = await asyncio.to_thread(lambda: Path(ref).stat().st_size)
            except OSError:
                size = None
        est = estimate_cost(size, model_mode, model_extract, model_consolidate, page_limit)
        return {"source_type": source_type, **est}

    async def add_source(
        self,
        source_type: str,
        source_ref: str,
        model_mode: str,
        model_extract: str,
        model_consolidate: str,
        page_limit: int | None = None,
        on_duplicate: str | None = None,
    ) -> dict:
        """Ein Buch einreihen. Validiert Quelle/Modelle, erkennt Duplikate (D9) und
        stößt die Verarbeitung an. Wirft ``ValueError`` (→ 400) bei ungültiger
        Eingabe und ``DuplicateError`` (→ 409) bei erkanntem Duplikat ohne
        ``on_duplicate``-Vorgabe."""
        err, ref = validate_source(source_type, source_ref)
        if err:
            raise ValueError(err)
        if model_mode not in VALID_MODES:
            raise ValueError(f"Ungültiger Modell-Modus. Erlaubt: {', '.join(VALID_MODES)}.")
        for m in (model_extract, model_consolidate):
            if m not in VALID_MODELS:
                raise ValueError(f"Ungültiges Modell. Erlaubt: {', '.join(VALID_MODELS)}.")
        if model_mode == "single":
            model_extract = model_consolidate

        book_hash = await asyncio.to_thread(compute_book_hash_sync, source_type, ref)

        # Duplikaterkennung (D9): gleiche Identität bereits in der Queue?
        if on_duplicate not in ("overwrite", "new_version"):
            for row in await self._repo.list_queue():
                if row.get("book_hash") != book_hash:
                    continue
                if row["status"] in (PENDING, RUNNING):
                    raise DuplicateError(
                        "Dieses Buch ist bereits in Bearbeitung.", existing_id=row["id"],
                        existing_status=row["status"],
                    )
                if row["status"] == DONE:
                    raise DuplicateError(
                        "Dieses Buch wurde bereits verarbeitet. Überschreiben oder neue Version?",
                        existing_id=row["id"], existing_status=row["status"],
                    )

        size = None
        if source_type == "upload":
            try:
                size = await asyncio.to_thread(lambda: Path(ref).stat().st_size)
            except OSError:
                size = None
        est = estimate_cost(size, model_mode, model_extract, model_consolidate, page_limit)

        row = await self._repo.add({
            "owner": settings.default_owner,
            "source_type": source_type,
            "source_ref": ref,
            "book_hash": book_hash,
            "model_mode": model_mode,
            "model_extract": model_extract,
            "model_consolidate": model_consolidate,
            "page_limit": page_limit,
            "cost_estimate": est["est_cost"],
            "created_at": _now().isoformat(),
        })
        # Auto-Drain: ein eingereihtes Buch wird ohne weiteren Klick verarbeitet.
        self._draining = True
        return {"item": row, "queue": await self._repo.list_queue()}

    async def run_now(self) -> dict:
        """„Jetzt ausführen": Drain anstoßen (idempotent)."""
        self._draining = True
        return self.state()

    async def remove(self, item_id: int) -> None:
        row = await self._repo.get(item_id)
        if row is None:
            raise KeyError(item_id)
        if item_id == self._current_id:
            await self._stop_current_session()
            self._current_id = None
            self._current_session_id = None
        await self._repo.delete(item_id)

    async def retry(self, item_id: int) -> dict:
        row = await self._repo.get(item_id)
        if row is None:
            raise KeyError(item_id)
        if row["status"] != ERROR:
            raise ValueError("Nur fehlgeschlagene Einträge können erneut versucht werden.")
        await self._repo.update(
            item_id, status=PENDING, phase=None, error_message=None,
            result_dir=None, result_note_path=None, result_pdf_path=None,
            session_id=None, started_at=None, finished_at=None,
        )
        self._draining = True
        return await self._repo.get(item_id)

    async def get_settings(self) -> dict:
        return await self._repo.get_settings()

    async def save_settings(self, fields: dict) -> dict:
        return await self._repo.save_settings(fields)

    async def list_queue(self) -> list[dict]:
        return await self._repo.list_queue()

    async def list_library(self) -> list[dict]:
        """Bibliothek: scannt den Standard-Ordner nach erzeugten Nuggets (Vault =
        Wahrheit). Jedes Nugget liegt in einem eigenen Unterordner ``<Autor>-<Titel>/``
        mit einer gleichnamigen ``.md``. Fehlender Ordner → leere Liste."""
        return await asyncio.to_thread(self._scan_library_sync)

    def _scan_library_sync(self) -> list[dict]:
        out_dir = Path(settings.book_nuggets_project_path) / settings.book_nuggets_output_subdir
        if not out_dir.is_dir():
            return []
        items: list[dict] = []
        for sub in out_dir.iterdir():
            if not sub.is_dir():
                continue
            md = sub / f"{sub.name}.md"
            if not md.is_file():
                # Fallback: erste .md im Ordner.
                mds = sorted(sub.glob("*.md"))
                if not mds:
                    continue
                md = mds[0]
            pdf = md.with_suffix(".pdf")
            try:
                mtime = datetime.fromtimestamp(md.stat().st_mtime).isoformat()
            except OSError:
                mtime = None
            items.append({
                "title": sub.name,
                "md_path": str(md),
                "pdf_path": str(pdf) if pdf.is_file() else None,
                "mtime": mtime,
            })
        items.sort(key=lambda i: i["mtime"] or "", reverse=True)
        return items

    def state(self) -> dict:
        status = "running" if self._current_id is not None else "idle"
        return {"status": status, "draining": self._draining, "current_id": self._current_id}

    # --- Worker-Tick -------------------------------------------------------

    async def tick(self) -> None:
        """Ein Schritt des sequenziellen Workers (vom Lifespan-Loop getrieben)."""
        if self._current_id is not None:
            await self._poll_current()
            return
        if not self._draining:
            return
        nxt = await self._next_pending()
        if nxt is None:
            self._draining = False
            return
        await self._start(nxt)

    async def _next_pending(self) -> dict | None:
        for row in await self._repo.list_queue():
            if row["status"] == PENDING:
                return row
        return None

    async def _start(self, row: dict) -> None:
        item_id = row["id"]
        try:
            runtime = await self._manager.create(
                project_path=settings.book_nuggets_project_path,
                initial_prompt=build_prompt(
                    row["source_type"], row["source_ref"],
                    settings.book_nuggets_output_subdir,
                    row.get("model_mode") or "staged",
                    row.get("model_extract") or "sonnet",
                    row.get("page_limit"),
                    None,  # vault-seitige Versionierung erledigt der Skill bei Bedarf
                ),
                model=row.get("model_consolidate") or settings.book_nuggets_model,
                permission_mode=settings.book_nuggets_permission_mode,
                owner=settings.default_owner,
                project_name="Buch-Nuggets",
            )
        except SessionLimitError:
            logger.info("Buch-Nuggets: Session-Limit erreicht — Eintrag %s wartet.", item_id)
            return
        except Exception as exc:  # noqa: BLE001 — nur DIESER Eintrag scheitert.
            await self._repo.update(
                item_id, status=ERROR, error_message=f"Start fehlgeschlagen: {exc}",
                finished_at=_now().isoformat(),
            )
            logger.warning("Buch-Nuggets: Start fehlgeschlagen (Eintrag %s): %s", item_id, exc)
            return
        self._current_id = item_id
        self._current_session_id = runtime.state.session_id
        self._continuations = 0
        self._last_incomplete_output = None
        await self._repo.update(
            item_id, status=RUNNING, phase="parsing",
            session_id=runtime.state.session_id, started_at=_now().isoformat(),
        )

    async def _poll_current(self) -> None:
        runtime = self._manager.get(self._current_session_id) if self._current_session_id else None
        if runtime is None:
            await self._finish(success=False, error="Verarbeitungs-Session verloren.")
            return
        text = self._transcript_text(runtime)
        phase = parse_phase(text)
        if phase:
            await self._repo.update(self._current_id, phase=phase)
        status = runtime.state.status
        if status in (SESSION_WAITING, SESSION_DONE):
            res = parse_result_paths(text)
            if result_is_complete(text, res):
                await self._finish(success=True, result=res)
            else:
                latest_output = next(
                    (
                        e.text for e in reversed(runtime.transcript)
                        if e.role == "assistant" and e.kind == "text"
                    ),
                    "",
                )
                if (
                    self._continuations < _MAX_CONTINUATIONS
                    and latest_output != self._last_incomplete_output
                ):
                    self._last_incomplete_output = latest_output
                    self._continuations += 1
                    try:
                        await self._manager.send_input(self._current_session_id, _CONTINUE_PROMPT)
                    except Exception as exc:  # noqa: BLE001 — Abschlussfehler nur für dieses Buch.
                        await self._finish(success=False, error=f"Fortsetzung fehlgeschlagen: {exc}")
                else:
                    await self._finish(
                        success=False,
                        error=(
                            "Verarbeitung ohne neuen Fortschritt oder nach "
                            f"{_MAX_CONTINUATIONS} Fortsetzungen ohne vollständiges Ergebnis "
                            "beendet (Markdown/PDF fehlen)."
                        ),
                    )
        elif status == SESSION_ERROR:
            await self._finish(
                success=False, error=runtime.state.error or "Verarbeitung fehlgeschlagen."
            )
        # sonst: läuft noch → warten.

    @staticmethod
    def _transcript_text(runtime) -> str:
        return "\n".join(
            e.text for e in runtime.transcript if e.role == "assistant" and e.kind == "text"
        )

    async def _finish(
        self, *, success: bool, result: dict | None = None, error: str | None = None,
    ) -> None:
        item_id = self._current_id
        finished_at = _now().isoformat()
        if success:
            res = result or {}
            fields = {
                "status": DONE, "phase": None, "finished_at": finished_at,
                "result_dir": res.get("dir"), "result_note_path": res.get("note"),
                "result_pdf_path": res.get("pdf"),
            }
            if res.get("title"):
                fields["title"] = res["title"]
            if res.get("author"):
                fields["author"] = res["author"]
            await self._repo.update(item_id, **fields)
        else:
            await self._repo.update(
                item_id, status=ERROR, phase=None, error_message=error,
                finished_at=finished_at,
            )
        await self._stop_current_session()
        self._current_id = None
        self._current_session_id = None
        self._continuations = 0
        self._last_incomplete_output = None

    async def _stop_current_session(self) -> None:
        if not self._current_session_id:
            return
        try:
            await self._manager.stop(self._current_session_id)
        except Exception as exc:  # noqa: BLE001 — best-effort.
            logger.warning("Buch-Nuggets: Session-Stop fehlgeschlagen: %s", exc)


class DuplicateError(Exception):
    """Buch bereits in der Queue/verarbeitet (D9) — Route mappt auf HTTP 409."""

    def __init__(self, message: str, *, existing_id: int, existing_status: str) -> None:
        super().__init__(message)
        self.existing_id = existing_id
        self.existing_status = existing_status
