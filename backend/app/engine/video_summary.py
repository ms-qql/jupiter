"""Video-Summary-Worker (PROJ-41).

Orchestrierungs-Schicht um den **unveränderten** ``hal-video-summary``-Skill:
ein asyncio-Worker (Vorbild ``_liveness_loop``) arbeitet die SQLite-Warteschlange
**sequenziell** ab — pro Video genau eine headless Claude-Session
(``SessionManager.create``) — und setzt **Drossel/Cooldown/Zeitplan** durch.

Grundsatz: **alle** Drossel-/Zeitplan-Logik liegt hier im Backend, nie im Client
(Tab zu = Verarbeitung läuft serverseitig weiter). Sequenziell + Cooldown nach je
``batch_size`` Videos erfüllt „nie mehr als 4 in Folge" zwangsläufig und ist am
schonendsten gegen YouTube-Blocking.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from ..config import settings
from ..db.video_summary_queue import DONE, ERROR, PENDING, RUNNING, VideoSummaryRepository
from .manager import (
    DONE as SESSION_DONE,
    ERROR as SESSION_ERROR,
    WAITING as SESSION_WAITING,
    SessionLimitError,
    SessionManager,
)

logger = logging.getLogger(__name__)

# Trenner, an denen ein per Copy-and-Paste eingefügter URL-Block zerlegt wird
# (Zeilenumbruch, Leerzeichen, Tab, Komma, Semikolon).
_SPLIT_RE = re.compile(r"[\s,;]+")

# Maschinenlesbarer Abschluss-Marker, den der Prompt von der Session anfordert.
# Pfade enthalten Leerzeichen („04 Resources") → Pfad pro eigener Zeile,
# robust gegen Whitespace.
_RESULT_MARKER = "JUPITER_VIDEO_RESULT"
_NOTE_RE = re.compile(r"^\s*note:\s*(.+?)\s*$", re.MULTILINE)
_PDF_RE = re.compile(r"^\s*pdf:\s*(.+?)\s*$", re.MULTILINE)


def parse_urls(raw) -> tuple[list[str], list[str]]:
    """Zerlegt eine/mehrere eingefügte URLs in (gültige, abgewiesene) Listen.

    Akzeptiert einen String (Block) **oder** eine Liste von Strings; jeder Eintrag
    wird zusätzlich an Whitespace/Komma/Semikolon zerlegt, getrimmt und dedupliziert
    (Reihenfolge bleibt erhalten). Gültig = ``http(s)``-Schema mit Host.
    """
    parts: list[str] = []
    items = raw if isinstance(raw, (list, tuple)) else [raw]
    for item in items:
        for token in _SPLIT_RE.split(str(item or "")):
            token = token.strip()
            if token:
                parts.append(token)

    valid: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for token in parts:
        if token in seen:
            continue
        seen.add(token)
        if _is_valid_url(token):
            valid.append(token)
        else:
            rejected.append(token)
    return valid, rejected


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except (ValueError, AttributeError):
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def build_prompt(url: str, output_subdir: str) -> str:
    """Initial-Prompt der Verarbeitungs-Session: ruft den Skill auf + erzwingt
    einen **festen Zielordner** (statt Auto-Kategorie, PROJ-44), Nicht-Interaktivität
    und einen maschinenlesbaren Abschlussbericht.

    Der Skill selbst bleibt **unverändert** — wir steuern nur sein Verhalten über
    den Prompt (headless kann kein ``AskUserQuestion`` bedienen). ``output_subdir``
    ist relativ zum cwd/Vault-Root (z. B. ``04 Resources/Video Summaries``)."""
    subdir = output_subdir.strip().strip("/")
    return (
        f"/hal-video-summary {url}\n\n"
        "Wichtige Rahmenbedingungen (headless, KEINE Rueckfragen moeglich):\n"
        f"- Speichere die Markdown-Notiz UND das PDF AUSSCHLIESSLICH im festen Ordner "
        f"\"{subdir}/\" (relativ zum Vault-Root). Lege diesen Ordner an, falls er fehlt.\n"
        "- Waehle KEINE Kategorie selbst und verschiebe nichts in Unterordner. "
        "Stelle KEINE Rueckfragen, nutze KEIN AskUserQuestion.\n"
        "- Bild-/Anhang-Dateien duerfen wie gewohnt unter \"07 Attachments/<slug>/\" liegen.\n"
        "- Gib GANZ AM ENDE deiner Arbeit exakt diesen Block aus (jeder Pfad in "
        "einer eigenen Zeile, absolute Pfade):\n"
        f"{_RESULT_MARKER}\n"
        "note: <absoluter Pfad zur .md-Notiz>\n"
        "pdf: <absoluter Pfad zum .pdf>\n"
    )


def parse_result_paths(text: str) -> tuple[str | None, str | None]:
    """Liest Notiz-/PDF-Pfad aus dem Abschlussbericht der Session (best-effort).

    Sucht den letzten ``JUPITER_VIDEO_RESULT``-Marker und die darauf folgenden
    ``note:``/``pdf:``-Zeilen. Kein Marker / Parsing schlägt fehl → ``(None, None)``;
    der Eintrag bleibt trotzdem „fertig" (Link best-effort, Tech-Design F)."""
    if not text:
        return None, None
    idx = text.rfind(_RESULT_MARKER)
    tail = text[idx + len(_RESULT_MARKER):] if idx != -1 else text
    note_m = _NOTE_RE.search(tail)
    pdf_m = _PDF_RE.search(tail)
    note = note_m.group(1).strip() if note_m else None
    pdf = pdf_m.group(1).strip() if pdf_m else None
    return (note or None), (pdf or None)


def _now() -> datetime:
    return datetime.now()


class VideoSummaryWorker:
    """Sequenzieller Queue-Worker + Drossel/Cooldown/Zeitplan (PROJ-41).

    Genau **eine** Session gleichzeitig. ``tick()`` wird vom Lifespan-Loop
    niederfrequent aufgerufen und ist defensiv (ein Fehler je Tick ist nie fatal).
    Laufzeit-Zustand (consecutive_count/paused_until/draining) lebt im Speicher und
    wird beim Start rekonstruiert; Queue + Einstellungen sind persistent.
    """

    def __init__(self, manager: SessionManager, repo: VideoSummaryRepository) -> None:
        self._manager = manager
        self._repo = repo
        # Laufzeit-Zustand (nicht persistent — bewusst, Tech-Design B).
        self._draining = False
        self._consecutive = 0
        self._paused_until: datetime | None = None
        self._current_id: int | None = None
        self._current_session_id: str | None = None
        # Gecachte Einstellungen (aus der DB geladen; bei Änderung neu gesetzt).
        self._cooldown_minutes = settings.video_summary_default_cooldown_minutes
        self._batch_size = settings.video_summary_batch_size
        self._schedule = ""
        self._model = settings.video_summary_model  # PROJ-44: persistiert wählbar
        self._next_scheduled_run: datetime | None = None

    # --- Lifecycle ---------------------------------------------------------

    async def startup(self) -> None:
        """Idempotenter Start: Schema anlegen, verwaiste ``running``-Einträge auf
        ``pending`` zurücksetzen, Einstellungen laden, nächsten Plan-Lauf berechnen."""
        await self._repo.init()
        await self._repo.reset_running()
        await self._load_settings()

    async def _load_settings(self) -> None:
        cfg = await self._repo.get_settings()
        self._cooldown_minutes = int(cfg.get("cooldown_minutes") or self._cooldown_minutes)
        self._batch_size = max(1, int(cfg.get("batch_size") or self._batch_size))
        self._schedule = (cfg.get("schedule") or "").strip()
        self._model = (cfg.get("model") or self._model).strip()
        self._recompute_schedule()

    # --- Öffentliche Steuerung (von den Routen aufgerufen) -----------------

    async def add_urls(self, raw) -> dict:
        """URL(s) einreihen. Zerlegt/validiert/dedupliziert serverseitig (zweite
        Verteidigungslinie zur Client-Vorprüfung). Gibt added/rejected/duplicates
        + die aktualisierte Queue zurück."""
        valid, rejected = parse_urls(raw)
        existing = {row["url"] for row in await self._repo.list_queue()}
        added: list[dict] = []
        duplicates: list[str] = []
        now = _now().isoformat()
        for url in valid:
            if url in existing:
                duplicates.append(url)
                continue
            existing.add(url)
            added.append(await self._repo.add(url, settings.default_owner, now))
        return {
            "added": added,
            "rejected": rejected,
            "duplicates": duplicates,
            "queue": await self._repo.list_queue(),
        }

    async def run_now(self) -> dict:
        """„Jetzt ausführen": Drain anstoßen (idempotent — kein Doppelstart, läuft
        bereits eine Verarbeitung, werden nur die offenen Einträge mit abgearbeitet)."""
        self._draining = True
        return self.state()

    async def remove(self, item_id: int) -> None:
        """Eintrag entfernen. Ist es der gerade laufende, wird die zugehörige
        Session best-effort gestoppt (kein Geister-Prozess)."""
        row = await self._repo.get(item_id)
        if row is None:
            raise KeyError(item_id)
        if item_id == self._current_id:
            await self._stop_current_session()
            self._current_id = None
            self._current_session_id = None
        await self._repo.delete(item_id)

    async def retry(self, item_id: int) -> dict:
        """Fehlgeschlagenen Eintrag erneut einreihen (→ pending) und Drain anstoßen."""
        row = await self._repo.get(item_id)
        if row is None:
            raise KeyError(item_id)
        if row["status"] != ERROR:
            raise ValueError("Nur fehlgeschlagene Einträge können erneut versucht werden.")
        await self._repo.update(
            item_id,
            status=PENDING,
            error_message=None,
            result_note_path=None,
            result_pdf_path=None,
            session_id=None,
            started_at=None,
            finished_at=None,
        )
        self._draining = True
        return await self._repo.get(item_id)

    async def get_settings(self) -> dict:
        return {
            "cooldown_minutes": self._cooldown_minutes,
            "batch_size": self._batch_size,
            "schedule": self._schedule,
            "model": self._model,
        }

    async def save_settings(
        self, cooldown_minutes: int, batch_size: int, schedule: str, model: str
    ) -> dict:
        saved = await self._repo.save_settings(cooldown_minutes, batch_size, schedule, model)
        self._cooldown_minutes = int(saved["cooldown_minutes"])
        self._batch_size = max(1, int(saved["batch_size"]))
        self._schedule = (saved["schedule"] or "").strip()
        self._model = (saved["model"] or self._model).strip()
        self._recompute_schedule()
        return await self.get_settings()

    async def list_queue(self) -> list[dict]:
        return await self._repo.list_queue()

    async def list_library(self) -> list[dict]:
        """Bibliothek (PROJ-44): scannt den festen Standard-Ordner und liefert ALLE
        ``.md``-Notizen darin (auch außerhalb der App erzeugte) — nicht die DB-Queue.
        Der Vault ist die Wahrheit; ein fehlender Ordner → leere Liste (kein Fehler)."""
        return await asyncio.to_thread(self._scan_library_sync)

    def _scan_library_sync(self) -> list[dict]:
        out_dir = Path(settings.video_summary_project_path) / settings.video_summary_output_subdir
        if not out_dir.is_dir():
            return []
        items: list[dict] = []
        for md in out_dir.glob("*.md"):
            if not md.is_file():
                continue
            title = md.stem
            # MOC-Datei des Ordners (gleichnamig zum Ordner) ausblenden.
            if title == out_dir.name:
                continue
            pdf = md.with_suffix(".pdf")
            try:
                mtime = datetime.fromtimestamp(md.stat().st_mtime).isoformat()
            except OSError:
                mtime = None
            items.append({
                "title": title,
                "md_path": str(md),
                "pdf_path": str(pdf) if pdf.is_file() else None,
                "mtime": mtime,
            })
        # Neueste zuerst (None-mtime ans Ende).
        items.sort(key=lambda i: i["mtime"] or "", reverse=True)
        return items

    def state(self) -> dict:
        """Worker-Laufzeit-Zustand für die UI (Leerlauf / Läuft / Pausiert bis …)."""
        if self._current_id is not None:
            status = "running"
        elif self._paused_until is not None and _now() < self._paused_until:
            status = "paused"
        else:
            status = "idle"
        return {
            "status": status,
            "draining": self._draining,
            "paused_until": self._paused_until.isoformat() if self._paused_until else None,
            "next_scheduled_run": (
                self._next_scheduled_run.isoformat() if self._next_scheduled_run else None
            ),
        }

    # --- Worker-Tick -------------------------------------------------------

    async def tick(self) -> None:
        """Ein Schritt des sequenziellen Workers (vom Lifespan-Loop getrieben)."""
        self._check_schedule()

        # 1) Läuft gerade eine Verarbeitung? → ihren Zustand einsammeln (nur EINE
        #    Session zur Zeit — kein Nachstarten, solange eine läuft).
        if self._current_id is not None:
            await self._poll_current()
            return

        # 2) Kein Drain gewünscht → Leerlauf.
        if not self._draining:
            return

        # 3) Cooldown-Pause aktiv? → warten.
        if self._paused_until is not None and _now() < self._paused_until:
            return
        self._paused_until = None

        # 4) Nächsten wartenden Eintrag starten — oder Drain beenden.
        nxt = await self._next_pending()
        if nxt is None:
            self._draining = False
            self._consecutive = 0  # Queue leer → frischer Batch beim nächsten Lauf
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
                project_path=settings.video_summary_project_path,
                initial_prompt=build_prompt(
                    row["url"], settings.video_summary_output_subdir
                ),
                model=self._model,
                permission_mode=settings.video_summary_permission_mode,
                owner=settings.default_owner,
                project_name="Video Summary",
            )
        except SessionLimitError:
            # Alle Slots belegt (parallele Sessions) → Eintrag bleibt pending,
            # nächster Tick versucht es erneut (kein harter Fehler).
            logger.info("Video-Summary: Session-Limit erreicht — Eintrag %s wartet.", item_id)
            return
        except Exception as exc:  # noqa: BLE001 — nur DIESER Eintrag scheitert.
            await self._repo.update(
                item_id,
                status=ERROR,
                error_message=f"Start fehlgeschlagen: {exc}",
                finished_at=_now().isoformat(),
            )
            logger.warning("Video-Summary: Start fehlgeschlagen (Eintrag %s): %s", item_id, exc)
            return
        self._current_id = item_id
        self._current_session_id = runtime.state.session_id
        await self._repo.update(
            item_id,
            status=RUNNING,
            session_id=runtime.state.session_id,
            started_at=_now().isoformat(),
        )

    async def _poll_current(self) -> None:
        runtime = self._manager.get(self._current_session_id) if self._current_session_id else None
        if runtime is None:
            # Session aus der Registry verschwunden → als Fehler werten.
            await self._finish(success=False, error="Verarbeitungs-Session verloren.")
            return
        status = runtime.state.status
        # Turn fertig (one-shot Skill-Lauf): WAITING (Prozess lebt noch) oder DONE.
        if status in (SESSION_WAITING, SESSION_DONE):
            note, pdf = parse_result_paths(self._transcript_text(runtime))
            await self._finish(success=True, note=note, pdf=pdf)
        elif status == SESSION_ERROR:
            await self._finish(
                success=False, error=runtime.state.error or "Verarbeitung fehlgeschlagen."
            )
        # sonst (STARTING/RUNNING/AWAITING_APPROVAL): läuft noch → warten.

    @staticmethod
    def _transcript_text(runtime) -> str:
        """Konkateniert die Assistenten-Text-Ausgaben der Session (für die Pfad-Suche)."""
        return "\n".join(
            e.text for e in runtime.transcript if e.role == "assistant" and e.kind == "text"
        )

    async def _finish(
        self,
        *,
        success: bool,
        note: str | None = None,
        pdf: str | None = None,
        error: str | None = None,
    ) -> None:
        item_id = self._current_id
        finished_at = _now().isoformat()
        if success:
            await self._repo.update(
                item_id,
                status=DONE,
                result_note_path=note,
                result_pdf_path=pdf,
                finished_at=finished_at,
            )
        else:
            await self._repo.update(
                item_id, status=ERROR, error_message=error, finished_at=finished_at
            )
        # Session beenden — der headless ``claude -p``-Prozess bleibt sonst idle am
        # Leben und belegt einen Slot (PROJ-14-Limit).
        await self._stop_current_session()
        self._current_id = None
        self._current_session_id = None
        # Drossel: jedes verarbeitete Video zählt; nach je ``batch_size`` Cooldown.
        self._consecutive += 1
        if self._consecutive % self._batch_size == 0:
            self._paused_until = _now() + timedelta(minutes=self._cooldown_minutes)
            logger.info(
                "Video-Summary: %d Videos verarbeitet → Cooldown bis %s.",
                self._consecutive, self._paused_until.isoformat(),
            )

    async def _stop_current_session(self) -> None:
        if not self._current_session_id:
            return
        try:
            await self._manager.stop(self._current_session_id)
        except Exception as exc:  # noqa: BLE001 — best-effort.
            logger.warning("Video-Summary: Session-Stop fehlgeschlagen: %s", exc)

    # --- Zeitplan ----------------------------------------------------------

    def _recompute_schedule(self) -> None:
        self._next_scheduled_run = _next_run_at(self._schedule, _now())

    def _check_schedule(self) -> None:
        """Ist der Zeitplan fällig → Drain anstoßen + nächsten Lauf vormerken.

        Keine Überlappung: ``run_now`` ist idempotent (setzt nur ``_draining``);
        eine bereits laufende Queue verarbeitet einfach weiter."""
        if self._next_scheduled_run is None:
            return
        now = _now()
        if now >= self._next_scheduled_run:
            self._draining = True
            # Direkt den nächsten Lauf (am Folgetag) vormerken — kein Doppelfeuern.
            self._next_scheduled_run = _next_run_at(self._schedule, now + timedelta(minutes=1))


def _next_run_at(schedule: str, after: datetime) -> datetime | None:
    """Nächster Zeitpunkt für einen ``HH:MM``-Tagesplan nach ``after`` (lokale Zeit).

    Leerer/ungültiger Plan → ``None`` (nur manuell). Bewusst dependency-frei
    (kein cron-Parser, Tech-Design F „keine neuen Pakete")."""
    schedule = (schedule or "").strip()
    if not schedule:
        return None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", schedule)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= after:
        candidate += timedelta(days=1)
    return candidate
