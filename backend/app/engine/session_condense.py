"""Session-Kondensierungs-Worker (PROJ-55).

Wochen-Sweep über die rohen Session-Logs im Hal-Vault (``Agentic OS/Jupiter/
Sessions/``): alle Sessions **älter als 7 Tage** werden evaluiert, die wichtigsten
Erkenntnisse **kondensiert** (kuratierte Knowledge-Notizen) und die Roh-Logs danach
**archiviert + gzip-komprimiert**, damit der Sessions-Ordner nicht endlos wächst.

Orchestrierungs-Muster wie Video Summary (PROJ-41) / Buch-Nuggets (PROJ-53): ein
asyncio-Worker arbeitet eine SQLite-Warteschlange **sequenziell** ab — pro
signalhafter Session genau eine headless Claude-Session (``SessionManager.create``),
die den unveränderten ``hal-session-condense``-Skill fährt.

Arbeitsteilung (Tech-Design):
- **Backend (hier)** — mechanisch: Auswahl nach Alter, Trivial-Vorfilter, Archivierung
  + gzip, Archiv-Pruning, Wochenplan, Lauf-Protokoll. Kein LLM-Urteil.
- **Skill** — das eigentliche Urteil (trivial vs. Signal) + Kondensierung + Schreiben
  der Knowledge-Notiz(en) inkl. Secret-Scrub. Meldet das Ergebnis maschinenlesbar.

Grundsatz: **kein Datenverlust**. Ein Roh-Log wird erst nach erfolgreicher
Verarbeitung (kondensiert ODER als trivial verworfen) + erfolgreicher Archivierung
aus ``Sessions/`` entfernt. Jeder Fehler lässt das Roh-Log an Ort und Stelle → der
nächste Lauf versucht es erneut.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db.session_condense_queue import (
    DONE,
    ERROR,
    OUTCOME_CONDENSED,
    OUTCOME_TRIVIAL,
    PENDING,
    RUNNING,
    SessionCondenseRepository,
)
from .curation import detect_marker
from .manager import (
    DONE as SESSION_DONE,
    ERROR as SESSION_ERROR,
    WAITING as SESSION_WAITING,
    SessionLimitError,
    SessionManager,
)

logger = logging.getLogger(__name__)

# Dateiname der Session-Logs: ``YYYY-MM-DD--<slug>-<hash>.md`` (siehe VaultService.write).
_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}--(?P<slug>.+)-[0-9a-fA-F]{6,}\.md$")

# Titel-Slugs, die immer trivial sind (Test-/Smoke-/Wegwerf-Sessions).
_TRIVIAL_SLUGS: frozenset[str] = frozenset({
    "test", "sess-test-tmp", "smoke", "tmp", "scratch",
})

# Wochenplan ``DOW HH:MM`` (z. B. ``MON 03:00``). Bewusst dependency-frei
# (kein cron-Parser, Tech-Design „keine neuen Pakete").
_DOW = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
_SCHEDULE_RE = re.compile(r"^(MON|TUE|WED|THU|FRI|SAT|SUN)\s+(\d{1,2}):(\d{2})$", re.I)

# Maschinenlesbarer Abschluss-Marker, den der Prompt von der Session anfordert.
_RESULT_MARKER = "JUPITER_CONDENSE_RESULT"
_OUTCOME_RE = re.compile(r"^\s*outcome:\s*(condensed|trivial)\s*$", re.IGNORECASE | re.MULTILINE)
_NOTE_RE = re.compile(r"^\s*note:\s*(.+?)\s*$", re.MULTILINE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def project_from_filename(filename: str) -> str:
    """Projekt-Tag aus dem Titel-Slug des Dateinamens (Fallback ``unbekannt``)."""
    m = _FILENAME_RE.match(filename or "")
    if not m:
        return "unbekannt"
    return m.group("slug")


def _parse_created(value) -> datetime | None:
    """ISO-Zeitstempel aus dem Frontmatter robust parsen (mit/ohne ``Z``)."""
    if not value or not isinstance(value, str):
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_older_than(created: datetime | None, age_days: int, *, ref: datetime | None = None) -> bool:
    """Ist ``created`` älter als ``age_days`` Tage? Unbekanntes Datum → ``False``
    (nie anfassen — Edge-Case „kaputtes Frontmatter")."""
    if created is None:
        return False
    now = ref or _now()
    return (now - created) > timedelta(days=age_days)


def is_trivial(filename: str, body: str, min_chars: int) -> bool:
    """Trivial-Vorfilter (spart teure Skill-Läufe). Trivial =
    (a) Titel-Slug in der Blockliste, ODER
    (b) Netto-Body unter ``min_chars`` UND keinerlei Kuratierungs-Marker.
    Grenzfälle mit Marker gehen zum Skill, der final urteilt."""
    if project_from_filename(filename) in _TRIVIAL_SLUGS:
        return True
    net = (body or "").strip()
    if len(net) < max(0, min_chars) and detect_marker(net) is None:
        return True
    return False


def build_prompt(abspath: str, project: str, session_id: str) -> str:
    """Initial-Prompt der Kondensier-Session: ruft den ``hal-session-condense``-Skill
    auf und steckt die Rahmenbedingungen ab (headless, keine Rückfragen). Der Skill
    selbst bleibt unverändert — wir steuern nur sein Verhalten über den Prompt."""
    return (
        f"/hal-session-condense {abspath}\n\n"
        "Rahmenbedingungen (headless, KEINE Rueckfragen moeglich):\n"
        f"- Projekt-Tag: \"{project}\". Quell-Session-ID: \"{session_id}\".\n"
        "- Lies das Session-Log unter dem obigen absoluten Pfad vollstaendig "
        "(bei sehr grossen Logs gezielt die relevanten Turns).\n"
        "- Entscheide, ob es verwertbares Wissen enthaelt: geloester Bug (Ursache+Fix), "
        "Architektur-Entscheidung, Sackgasse/verworfener Ansatz, Gotcha/Stolperfalle, "
        "bestaetigte Nutzer-Praeferenz.\n"
        "- OHNE Signal (Test/Smoke/trivialer Verlauf): schreibe NICHTS und melde "
        "\"outcome: trivial\".\n"
        "- MIT Signal: schreibe je Erkenntnis EINE kuratierte Notiz nach "
        "\"Agentic OS/Jupiter/Knowledge/\" mit Frontmatter (type: curated, "
        f"source_session_id: \"{session_id}\", curation_marker, project: \"{project}\", "
        "created) und einem GEFUELLTEN Abschnitt \"## Erkenntnis\" (knapp, "
        "handlungsorientiert; bei bug/sackgasse Ursache+Lehre, bei Nutzer-Praeferenz "
        "zusaetzlich Warum + Anwendung). Dateiname eindeutig je Session/Erkenntnis "
        f"(z. B. <marker>-{project}-{session_id[:8] if session_id else 'sess'}.md); "
        "eine bereits hand-kuratierte Notiz NIEMALS blind ueberschreiben.\n"
        "- Entferne Secrets/Tokens/.env-Werte; zitiere KEINE Passwoerter/Keys "
        "(Secret-Scrub).\n"
        "- Stelle KEINE Rueckfragen, nutze KEIN AskUserQuestion.\n"
        "- Gib GANZ AM ENDE deiner Arbeit exakt diesen Block aus (absolute Pfade):\n"
        f"{_RESULT_MARKER}\n"
        "outcome: condensed | trivial\n"
        "note: <absoluter Pfad je geschriebener Notiz>   (eine Zeile je Notiz, nur bei condensed)\n"
    )


def parse_result(text: str) -> tuple[str | None, list[str]]:
    """Liest ``(outcome, note_paths)`` aus dem Abschlussbericht (best-effort).

    Kein Marker / kein ``outcome`` → ``(None, [])`` (der Worker wertet das als Fehler,
    lässt das Roh-Log liegen und versucht es erneut). Platzhalter ``<…>`` werden
    verworfen."""
    if not text:
        return None, []
    idx = text.rfind(_RESULT_MARKER)
    if idx == -1:
        return None, []
    tail = text[idx + len(_RESULT_MARKER):]
    mo = _OUTCOME_RE.search(tail)
    if not mo:
        return None, []
    outcome = mo.group(1).lower()
    notes = [
        m.group(1).strip()
        for m in _NOTE_RE.finditer(tail)
        if m.group(1).strip() and not m.group(1).strip().startswith("<")
    ]
    return outcome, notes


class SessionCondenseWorker:
    """Sequenzieller Sweep-Worker (PROJ-55). Genau **eine** Session gleichzeitig.

    ``tick()`` wird vom Lifespan-Loop niederfrequent aufgerufen und ist defensiv
    (ein Fehler je Tick ist nie fatal). Laufzeit-Zustand (draining/current/run) lebt
    im Speicher; Queue + Einstellungen + Lauf-Protokoll sind persistent."""

    def __init__(self, manager: SessionManager, repo: SessionCondenseRepository, vault) -> None:
        self._manager = manager
        self._repo = repo
        self._vault = vault
        self._draining = False
        self._current_id: int | None = None
        self._current_session_id: str | None = None
        self._run_id: int | None = None
        # Gecachte Einstellungen (aus der DB geladen).
        self._schedule = ""
        self._age_days = settings.session_condense_age_days
        self._retention_days = settings.session_condense_archive_retention_days
        self._min_chars = settings.session_condense_min_body_chars
        self._engine = settings.session_condense_engine
        self._model = settings.session_condense_model
        self._next_scheduled_run: datetime | None = None

    # --- Lifecycle ---------------------------------------------------------

    async def startup(self) -> None:
        """Idempotenter Start: Schema, verwaiste ``running`` → ``pending``, Einstellungen
        laden, Kandidaten scannen (ohne automatisch zu starten), nächsten Plan berechnen."""
        await self._repo.init()
        await self._repo.reset_running()
        await self._load_settings()
        try:
            await self.scan()
        except Exception:  # noqa: BLE001 — Scan ist best-effort; App startet trotzdem.
            logger.warning("Session-Kondensierung: initialer Scan fehlgeschlagen.", exc_info=True)

    async def _load_settings(self) -> None:
        cfg = await self._repo.get_settings()
        self._schedule = (cfg.get("schedule") or "").strip()
        self._age_days = int(cfg.get("age_days") or self._age_days)
        self._retention_days = int(cfg.get("retention_days") or self._retention_days)
        self._min_chars = int(cfg.get("min_chars") or self._min_chars)
        self._engine = (cfg.get("engine") or self._engine).strip()
        self._model = (cfg.get("model") or self._model).strip()
        self._recompute_schedule()

    # --- Öffentliche Steuerung (von den Routen aufgerufen) -----------------

    async def scan(self) -> dict:
        """Rohe Session-Logs > Altersschwelle als ``pending`` einreihen (idempotent via
        UNIQUE ``session_filename``). Bereits verarbeitete (→ archiviert, aus ``Sessions/``
        verschwunden) tauchen nicht mehr auf. Gibt eine Zählung zurück."""
        logs = await asyncio.to_thread(self._vault.list_session_logs)
        ref = _now()
        added = 0
        skipped_recent = 0
        skipped_broken = 0
        for entry in logs:
            created = _parse_created(entry.get("created"))
            if created is None:
                skipped_broken += 1
                continue
            if not is_older_than(created, self._age_days, ref=ref):
                skipped_recent += 1
                continue
            row = await self._repo.add_candidate({
                "session_filename": entry["filename"],
                "session_id": entry.get("session_id"),
                "project": project_from_filename(entry["filename"]),
                "session_created": entry.get("created"),
                "created_at": ref.isoformat(),
            })
            if row is not None:
                added += 1
        if skipped_broken:
            logger.info("Session-Kondensierung: %d Logs mit unlesbarem Datum übersprungen.", skipped_broken)
        return {
            "added": added,
            "skipped_recent": skipped_recent,
            "skipped_broken": skipped_broken,
            "queue": await self._repo.list_queue(),
        }

    async def run_now(self) -> dict:
        """„Jetzt kondensieren": scannen + Drain anstoßen (idempotent — kein Doppelstart)."""
        await self.scan()
        self._draining = True
        return self.state()

    async def remove(self, item_id: int) -> None:
        """Einen Queue-Eintrag entfernen (laufenden: Session best-effort stoppen)."""
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
            item_id, status=PENDING, outcome=None, error_message=None,
            knowledge_paths=None, archived_path=None, worker_session_id=None,
            started_at=None, finished_at=None,
        )
        self._draining = True
        return await self._repo.get(item_id)

    async def get_settings(self) -> dict:
        return {
            "schedule": self._schedule,
            "age_days": self._age_days,
            "retention_days": self._retention_days,
            "min_chars": self._min_chars,
            "engine": self._engine,
            "model": self._model,
        }

    async def save_settings(self, fields: dict) -> dict:
        await self._repo.save_settings(fields)
        await self._load_settings()
        return await self.get_settings()

    async def list_queue(self) -> list[dict]:
        return await self._repo.list_queue()

    async def list_runs(self, limit: int = 20) -> list[dict]:
        return await self._repo.list_runs(limit)

    def state(self) -> dict:
        """Worker-Laufzeit-Zustand für die UI."""
        status = "running" if self._current_id is not None else (
            "draining" if self._draining else "idle"
        )
        return {
            "status": status,
            "draining": self._draining,
            "current_id": self._current_id,
            "next_scheduled_run": (
                self._next_scheduled_run.isoformat() if self._next_scheduled_run else None
            ),
        }

    # --- Worker-Tick -------------------------------------------------------

    async def tick(self) -> None:
        """Ein Schritt des sequenziellen Sweeps (vom Lifespan-Loop getrieben)."""
        await self._maybe_fire_schedule()

        # 1) Läuft gerade eine Kondensier-Session? → Zustand einsammeln.
        if self._current_id is not None:
            await self._poll_current()
            return

        # 2) Kein Drain gewünscht → Leerlauf.
        if not self._draining:
            return

        # 3) Nächsten wartenden Eintrag holen — oder Drain beenden (+ Archiv prunen).
        nxt = await self._next_pending()
        if nxt is None:
            await self._end_run()
            self._draining = False
            return

        if self._run_id is None:
            self._run_id = await self._repo.open_run(_now().isoformat())
        await self._start(nxt)

    async def _next_pending(self) -> dict | None:
        for row in await self._repo.list_queue():
            if row["status"] == PENDING:
                return row
        return None

    async def _start(self, row: dict) -> None:
        item_id = row["id"]
        filename = row["session_filename"]
        # Roh-Log lesen (für Prefilter + absoluten Pfad).
        try:
            info = await asyncio.to_thread(self._vault.read_session_log, filename)
        except OSError:
            # Datei verschwunden (manuell entfernt/archiviert) → aus der Queue nehmen.
            logger.info("Session-Kondensierung: %s nicht mehr vorhanden — entferne Eintrag.", filename)
            await self._repo.delete(item_id)
            return

        # Trivial-Vorfilter: ohne Skill nur archivieren.
        if is_trivial(filename, info["body"], self._min_chars):
            await self._complete(item_id, filename, OUTCOME_TRIVIAL, [])
            return

        # Signal-Kandidat → headless Skill-Session.
        try:
            runtime = await self._manager.create(
                project_path=settings.session_condense_project_path,
                initial_prompt=build_prompt(
                    info["abspath"], row.get("project") or "unbekannt",
                    row.get("session_id") or "",
                ),
                engine=self._engine,
                model=self._model,
                permission_mode=settings.session_condense_permission_mode,
                owner=settings.default_owner,
                project_name="Session-Kondensierung",
            )
        except SessionLimitError:
            # Alle Slots belegt → Eintrag bleibt pending, nächster Tick erneut.
            logger.info("Session-Kondensierung: Session-Limit erreicht — Eintrag %s wartet.", item_id)
            return
        except Exception as exc:  # noqa: BLE001 — nur DIESER Eintrag scheitert.
            await self._fail(item_id, f"Start fehlgeschlagen: {exc}")
            logger.warning("Session-Kondensierung: Start fehlgeschlagen (Eintrag %s): %s", item_id, exc)
            return
        self._current_id = item_id
        self._current_session_id = runtime.state.session_id
        await self._repo.update(
            item_id, status=RUNNING,
            worker_session_id=runtime.state.session_id, started_at=_now().isoformat(),
        )

    async def _poll_current(self) -> None:
        runtime = self._manager.get(self._current_session_id) if self._current_session_id else None
        item_id = self._current_id
        row = await self._repo.get(item_id) if item_id is not None else None
        filename = row["session_filename"] if row else None
        if runtime is None:
            # Session aus der Registry verschwunden → Fehler, Roh-Log bleibt liegen.
            await self._stop_current_session()
            self._clear_current()
            await self._fail(item_id, "Kondensier-Session verloren.")
            return
        status = runtime.state.status
        if status in (SESSION_WAITING, SESSION_DONE):
            outcome, notes = parse_result(self._transcript_text(runtime))
            await self._stop_current_session()
            self._clear_current()
            if outcome is None:
                # Session fertig, aber kein verwertbarer Abschluss → Fehler (Roh-Log bleibt).
                await self._fail(item_id, "Kein Abschluss-Marker im Ergebnis.")
                return
            await self._complete(item_id, filename, outcome, notes)
        elif status == SESSION_ERROR:
            await self._stop_current_session()
            self._clear_current()
            await self._fail(item_id, runtime.state.error or "Kondensierung fehlgeschlagen.")
        # sonst (STARTING/RUNNING/AWAITING_APPROVAL): läuft noch → warten.

    async def _complete(
        self, item_id: int, filename: str | None, outcome: str, notes: list[str]
    ) -> None:
        """Erfolgreich verarbeitet → Roh-Log archivieren, Eintrag als ``done`` markieren.

        Schlägt die Archivierung fehl, wird der Eintrag zum Fehler und das Roh-Log
        bleibt an Ort und Stelle (kein Datenverlust)."""
        archived_path = None
        if filename:
            try:
                archived_path = await asyncio.to_thread(self._vault.archive_session_log, filename)
            except OSError as exc:
                await self._fail(item_id, f"Archivierung fehlgeschlagen: {exc}")
                logger.warning("Session-Kondensierung: Archivierung fehlgeschlagen (%s): %s", filename, exc)
                return
        await self._repo.update(
            item_id, status=DONE, outcome=outcome,
            knowledge_paths=json.dumps(notes, ensure_ascii=False),
            archived_path=archived_path, finished_at=_now().isoformat(),
        )
        await self._bump("checked")
        await self._bump("archived")
        await self._bump("condensed" if outcome == OUTCOME_CONDENSED else "trivial")

    async def _fail(self, item_id: int | None, error: str) -> None:
        if item_id is None:
            return
        await self._repo.update(
            item_id, status=ERROR, error_message=error, finished_at=_now().isoformat()
        )
        await self._bump("checked")
        await self._bump("errors")

    async def _bump(self, field: str) -> None:
        if self._run_id is not None:
            await self._repo.bump_run(self._run_id, field)

    async def _end_run(self) -> None:
        """Drain zu Ende → Archiv prunen + laufendes Protokoll schließen."""
        pruned = 0
        try:
            pruned = await asyncio.to_thread(self._vault.prune_archive, self._retention_days)
        except Exception:  # noqa: BLE001 — Pruning ist best-effort.
            logger.warning("Session-Kondensierung: Archiv-Pruning fehlgeschlagen.", exc_info=True)
        if self._run_id is not None:
            await self._repo.close_run(self._run_id, _now().isoformat(), pruned)
            self._run_id = None

    def _clear_current(self) -> None:
        self._current_id = None
        self._current_session_id = None

    @staticmethod
    def _transcript_text(runtime) -> str:
        return "\n".join(
            e.text for e in runtime.transcript if e.role == "assistant" and e.kind == "text"
        )

    async def _stop_current_session(self) -> None:
        if not self._current_session_id:
            return
        try:
            await self._manager.stop(self._current_session_id)
        except Exception as exc:  # noqa: BLE001 — best-effort.
            logger.warning("Session-Kondensierung: Session-Stop fehlgeschlagen: %s", exc)

    # --- Zeitplan (wöchentlich) --------------------------------------------

    def _recompute_schedule(self) -> None:
        self._next_scheduled_run = _next_weekly_run_at(self._schedule, _now())

    async def _maybe_fire_schedule(self) -> None:
        """Ist der Wochenplan fällig → scannen + Drain anstoßen + nächsten Lauf vormerken."""
        if self._next_scheduled_run is None:
            return
        now = _now()
        if now < self._next_scheduled_run:
            return
        # Nächsten Lauf sofort vormerken (kein Doppelfeuern), dann diesen starten.
        self._next_scheduled_run = _next_weekly_run_at(self._schedule, now + timedelta(minutes=1))
        try:
            await self.scan()
        except Exception:  # noqa: BLE001 — geplanter Scan nie fatal.
            logger.warning("Session-Kondensierung: geplanter Scan fehlgeschlagen.", exc_info=True)
        self._draining = True


def _next_weekly_run_at(schedule: str, after: datetime) -> datetime | None:
    """Nächster Zeitpunkt für einen ``DOW HH:MM``-Wochenplan nach ``after`` (lokal/UTC
    konsistent zu ``_now``). Leerer/ungültiger Plan → ``None`` (nur manuell)."""
    schedule = (schedule or "").strip()
    if not schedule:
        return None
    m = _SCHEDULE_RE.match(schedule)
    if not m:
        return None
    dow = _DOW[m.group(1).upper()]
    hour, minute = int(m.group(2)), int(m.group(3))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    days_ahead = (dow - after.weekday()) % 7
    candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
    if candidate <= after:
        candidate += timedelta(days=7)
    return candidate
