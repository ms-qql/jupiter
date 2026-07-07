"""Transport-Abstraktion unterhalb der EngineDriver (PROJ-63, Rollout-Schritt 2).

Ein ``Transport`` ist die I/O-Schicht, die ein ``EngineDriver`` (``claude_driver.py``,
``generic_cli_driver.py``) braucht, um einen CLI-Prozess zu starten, Eingaben zu
schreiben, Ausgabe zeilenweise zu lesen und den Prozess sauber zu beenden. Heute
nutzen beide Treiber dafür direkt ``asyncio.create_subprocess_exec`` — das bindet
den Agentenprozess fest an den Lebenszyklus des Backend-Prozesses (ein Neustart
killt/verwaist ihn). ``DirectTransport`` bildet genau dieses heutige Verhalten
1:1 nach; ``TmuxTransport`` ist die neue, optionale Alternative.

**Diese Datei verdrahtet noch KEINEN Treiber um** — ``ClaudeCodeDriver`` und
``GenericCliDriver`` verwenden weiterhin ihre eigene, unveränderte
``asyncio.create_subprocess_exec``-Logik. Das ist bewusst additiv/risikoarm: die
Transport-Klassen sind eigenständig testbar, bevor ein Treiber sie tatsächlich
nutzt (Direct-Transport bleibt bis dahin byte-identisch unverändert).

Spike-Erkenntnisse (siehe ``features/PROJ-63-tmux-session-transport.md``,
Abschnitt "Spike-Ergebnisse", verifiziert mit echten Claude-/Codex-/OpenCode-Läufen):

- Eine tmux-Pane liefert **immer** ein PTY als stdin. Claudes
  ``-p --input-format stream-json`` bricht sofort ab ("Input must be provided
  either through stdin or as a prompt argument"), wenn der CLI-Befehl direkt als
  Pane-Kommando läuft. Deshalb läuft stdin nie über die PTY, sondern:
  - **long-lived** (Claude, generische Nicht-Oneshot-Profile): der Pane-Wrapper
    öffnet eine FIFO selbst read-write (``exec 9<>fifo``) — das hält dauerhaft
    einen Writer-Handle, sodass der lesende CLI-Prozess **nie EOF** sieht, auch
    wenn ein externer (Backend-)Schreiber zwischendurch schließt. Ohne diesen
    Trick beendet sich der Prozess beim nächsten Schreiberwechsel sauber (Exit 0)
    — sähe wie ein normales Sessionende aus, wäre aber ein stiller Datenverlust
    bei jedem Backend-Neustart (genau das zentrale Akzeptanzkriterium von PROJ-63).
  - **oneshot** (Codex/OpenCode): der Prompt wird vorab in eine Datei geschrieben
    und per echtem Datei-Redirect übergeben (kein PTY, kein TTY-Fehler). Jeder
    Turn ist ohnehin ein neuer Prozess — kein FIFO nötig.
- stdout/stderr werden in Dateien umgeleitet statt über ``capture-pane``/
  ``pipe-pane`` gelesen — einfacher, robuster Cursor (Byte-Offset) statt
  Scrollback-Dedup. tmux trägt damit NUR die Prozess-Lebensdauer (der tmux-Server
  liegt außerhalb des ``jupiter-backend``-Cgroups und übersteht dessen Neustart
  unabhängig von dessen ``KillMode``), nicht die Terminal-Darstellung.
- ``kill-session`` beendet den Kindprozess zuverlässig, keine Waisenprozesse.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shlex
import shutil
import time
from abc import ABC, abstractmethod
from pathlib import Path

from ..config import settings

log = logging.getLogger(__name__)

# Marker-Zeile, die der Pane-Wrapper nach Prozessende ins err-Log schreibt —
# liefert den Exit-Code, auch wenn wir ihn erst später (nach einem Backend-
# Neustart) auslesen.
EXIT_MARKER = "__JUPITER_TMUX_EXIT__"

_NAME_RE = re.compile(r"[^A-Za-z0-9_-]")


def sanitize_tmux_session_name(session_key: str) -> str:
    """Leitet einen tmux-tauglichen Session-Namen aus einer Jupiter-Session-ID ab.

    tmux trennt Session:Fenster.Pane über ``:``/``.`` — beide (und alles andere
    außer ``[A-Za-z0-9_-]``) werden ersetzt. Der Name kommt IMMER aus einer
    serverseitigen ID, nie aus Nutzereingabe (keine Shell-/tmux-Injektion).
    """
    safe = _NAME_RE.sub("_", session_key).strip("_") or "session"
    return f"jupiter-{safe}"


def tmux_available(tmux_bin: str | None = None) -> bool:
    """Ist das tmux-Binary auf diesem Host vorhanden? (für Settings-/Diagnose-Anzeige)."""
    return shutil.which(tmux_bin or settings.tmux_bin) is not None


class TransportError(RuntimeError):
    """Ein Transport konnte nicht gestartet oder bedient werden (z. B. tmux fehlt)."""


class TmuxTimeoutError(TransportError):
    """PROJ-64: ``_tmux()`` hat auch nach den konfigurierten Wiederholungen nicht
    geantwortet — mit derselben Semantik wie ein normaler ``TransportError``
    behandelbar (Unterklasse, jeder bestehende ``except TransportError`` fängt sie
    weiterhin), aber eigens benannt, damit ``TmuxTransport.spawn()`` gezielt
    darauf reagieren kann: die zugrunde liegende Reaping-Störung (siehe PROJ-63,
    BUG-4) bedeutet oft, dass der tmux-Befehl tatsächlich durchgelaufen ist —
    nur die Antwort kam nie an."""


class Transport(ABC):
    """I/O-Schicht unterhalb eines ``EngineDriver``."""

    @abstractmethod
    async def spawn(
        self,
        argv: list[str],
        *,
        cwd: str,
        long_lived: bool,
        stdin_file: str | None = None,
    ) -> None:
        """Startet (oder — bei Oneshot-Engines — erneuert) den Prozess.

        ``long_lived=True``: der Prozess bleibt über mehrere ``write_line``-Aufrufe
        am Leben (Claude-artig). ``long_lived=False``: ein Turn = ein Prozess; ``
        stdin_file`` (falls gesetzt) liefert den Prompt als Datei-Redirect, der
        Prozess endet nach eigenem Ermessen (Oneshot-CLI)."""

    @abstractmethod
    async def write_line(self, data: bytes) -> None:
        """Schreibt eine weitere Eingabe (nur bei ``long_lived``-Sessions sinnvoll)."""

    @abstractmethod
    async def readline(self) -> bytes:
        """Nächste stdout-Zeile (inkl. Trenner) oder ``b""`` bei EOF/Prozessende."""

    @abstractmethod
    async def read_stderr_text(self) -> str:
        """Bisheriger stderr-Inhalt (best-effort, für Fehlerdiagnose)."""

    @abstractmethod
    async def terminate(self) -> None:
        """Sanftes Beenden (SIGTERM-äquivalent)."""

    @abstractmethod
    async def kill(self) -> None:
        """Hartes Beenden (SIGKILL-äquivalent)."""

    @abstractmethod
    async def wait(self) -> int | None:
        """Wartet auf Prozessende, liefert den Exit-Code (best-effort)."""

    @property
    @abstractmethod
    def is_alive(self) -> bool:
        ...

    @property
    def pid(self) -> int | None:
        return None


class DirectTransport(Transport):
    """Heutiges Verhalten (``asyncio.create_subprocess_exec``), 1:1 nachgebildet.

    Referenz-/Paritäts-Implementierung: dient dazu, ``TmuxTransport`` gegen
    dieselben Testszenarien laufen zu lassen wie den heutigen direkten Pfad —
    nicht dazu, die bestehenden Treiber schon umzustellen (die behalten ihre
    eigene, unveränderte Subprozess-Logik).
    """

    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None

    async def spawn(
        self,
        argv: list[str],
        *,
        cwd: str,
        long_lived: bool = True,
        stdin_file: str | None = None,
    ) -> None:
        stdin_src: int | object
        if stdin_file is not None:
            stdin_src = os.open(stdin_file, os.O_RDONLY)
        else:
            stdin_src = asyncio.subprocess.PIPE
        self._proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdin=stdin_src,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=settings.claude_stream_limit_bytes,
        )
        if isinstance(stdin_src, int):
            os.close(stdin_src)

    async def write_line(self, data: bytes) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise TransportError("DirectTransport: Prozess/stdin nicht bereit.")
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()

    async def readline(self) -> bytes:
        if self._proc is None or self._proc.stdout is None:
            return b""
        return await self._proc.stdout.readline()

    async def read_stderr_text(self) -> str:
        if self._proc is None or self._proc.stderr is None:
            return ""
        chunk = await self._proc.stderr.read()
        return chunk.decode("utf-8", errors="replace")

    async def terminate(self) -> None:
        if self._proc is None:
            return
        with contextlib.suppress(ProcessLookupError):
            if self._proc.stdin is not None:
                self._proc.stdin.close()
            self._proc.terminate()

    async def kill(self) -> None:
        if self._proc is None:
            return
        with contextlib.suppress(ProcessLookupError):
            self._proc.kill()

    async def wait(self) -> int | None:
        if self._proc is None:
            return None
        return await self._proc.wait()

    @property
    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else None


class TmuxTransport(Transport):
    """Prozess-Supervisor via tmux (PROJ-63).

    Ein tmux-Session-Name pro Jupiter-Session (``sanitize_tmux_session_name``),
    stabil über die gesamte Lebensdauer — auch über mehrere Oneshot-Turns hinweg
    (jeder Turn ruft ``spawn`` erneut auf; eine bereits laufende Session/Pane mit
    demselben Namen wird zuerst sauber beendet, siehe ``_ensure_no_stale_session``).
    """

    def __init__(
        self,
        session_key: str,
        *,
        data_dir: str | None = None,
        tmux_bin: str | None = None,
        poll_interval: float = 0.2,
        liveness_cache_seconds: float = 0.5,
        cmd_timeout_seconds: float | None = None,
    ) -> None:
        self.tmux_session = sanitize_tmux_session_name(session_key)
        self._tmux_bin = tmux_bin or settings.tmux_bin
        self._dir = Path(data_dir or settings.tmux_data_dir) / self.tmux_session
        self._control_fifo = self._dir / "control.in"
        self.out_path = self._dir / "out.log"
        self.err_path = self._dir / "err.log"
        self._poll_interval = poll_interval
        self._liveness_cache_seconds = liveness_cache_seconds
        # Bug (2026-07-07, Produktionsvorfall): ohne Timeout kann ein einzelner
        # `_tmux()`-Aufruf (has-session/new-session/list-panes) bei einer seltenen
        # Reaping-Störung für IMMER hängen — `spawn()` und damit `POST /sessions`
        # kehren dann nie zurück, obwohl tmux/der Agent im Hintergrund normal
        # weiterläuft (siehe `_tmux()` unten für Details).
        self._cmd_timeout_seconds = (
            cmd_timeout_seconds if cmd_timeout_seconds is not None else settings.tmux_cmd_timeout_seconds
        )
        self._out_fh: object | None = None  # binäres Lese-Handle, über Turns hinweg offen
        self._long_lived = True
        self._spawned = False
        self._alive_cache: tuple[float, bool] | None = None
        self._cached_pid: int | None = None
        self._prompt_counter = 0

    # -- tmux-CLI-Hilfsfunktion ----------------------------------------------

    async def _tmux(self, *args: str, check: bool = True, retries: int = 0) -> tuple[int, str, str]:
        """Führt einen ``tmux``-CLI-Aufruf aus, mit hartem Zeitlimit (BUG-4/PROJ-63).

        ``retries`` (PROJ-64): Anzahl automatischer Wiederholungen, wenn genau
        dieser Aufruf in die seltene Reaping-Störung läuft (siehe Klassen-Docstring
        von ``TmuxTimeoutError``). NUR für Prüf-/Lese-/idempotente Befehle
        (has-session/list-panes/kill-session) von den jeweiligen Aufrufern gesetzt
        — niemals blind für ``new-session`` (siehe ``spawn()``, das dafür einen
        eigenen, sichereren Attach-statt-Duplikat-Pfad nutzt).
        """
        attempt = 0
        while True:
            proc = await asyncio.create_subprocess_exec(
                self._tmux_bin,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=self._cmd_timeout_seconds)
            except asyncio.TimeoutError as exc:
                # Live reproduziert (2026-07-07): ein echter Codex-Turn unter `tmux`
                # blieb in genau diesem `communicate()` für immer hängen — der
                # tmux-Server/die Pane liefen im Hintergrund normal weiter (der
                # Codex-Turn schloss sogar korrekt ab), aber `POST /sessions` bekam
                # NIE eine Antwort (kein Log, kein Timeout, keine Fehlermeldung), weil
                # nichts dieses `communicate()` je beendete. Ohne dieses Timeout ist
                # ein hängender `_tmux()`-Aufruf ein permanenter, nicht wiederherstell-
                # barer Hang der gesamten Session-Erstellung. Best-effort kill()
                # statt eines stillen Leaks; das Ergebnis ist ein klarer, sofort
                # sichtbarer Fehler statt eines für immer hängenden Requests.
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                with contextlib.suppress(Exception):
                    # Best-effort reap nach dem Kill (vermeidet einen Zombie/ungeschlossenen
                    # Transport) — darf den Fehlerpfad selbst aber nicht erneut blockieren.
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                if attempt < retries:
                    attempt += 1
                    log.warning(
                        "tmux %s antwortet nicht (Versuch %d/%d) — Wiederholung "
                        "(PROJ-64, seltene Reaping-Störung).",
                        " ".join(args), attempt, retries + 1,
                    )
                    continue
                raise TmuxTimeoutError(
                    f"tmux {' '.join(args)} antwortet nicht (Timeout nach "
                    f"{self._cmd_timeout_seconds:.0f}s) — Transport 'tmux' nicht verfügbar."
                ) from exc
            rc = proc.returncode or 0
            if check and rc != 0:
                raise TransportError(
                    f"tmux {' '.join(args)} fehlgeschlagen (Code {rc}): "
                    f"{err.decode('utf-8', errors='replace').strip()}"
                )
            return rc, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")

    # -- Spawn / Respawn ------------------------------------------------------

    async def spawn(
        self,
        argv: list[str],
        *,
        cwd: str,
        long_lived: bool = True,
        stdin_file: str | None = None,
    ) -> None:
        if not tmux_available(self._tmux_bin):
            raise TransportError(
                f"tmux ist nicht verfügbar (Binary '{self._tmux_bin}' nicht gefunden) — "
                "Transport 'tmux' kann nicht starten."
            )
        self._long_lived = long_lived
        self._dir.mkdir(parents=True, exist_ok=True)
        # Regressionsfund (beim BUG-1-Fix aufgedeckt): eine "ist das der erste Spawn?"-
        # Prüfung über `self._dir.exists()` ist trügerisch, weil `prepare_prompt_file()`
        # (Oneshot-Prompt) das Verzeichnis bereits VOR diesem Aufruf anlegt — dadurch griff
        # die alte `if first_spawn: write_bytes(b"")`-Initialisierung nie, und `out.log`/
        # `err.log` existierten nur zufällig, sobald die Pane-Shell ihr eigenes `>>`-Redirect
        # geöffnet hatte. Das lief bisher glimpflich, weil der alte Zwei-Schritt-tmux-Aufruf
        # (`new-session` + separates `set-option`) genug Overhead hatte, damit die Pane-Shell
        # meist zuerst dran war — nach dem BUG-1-Fix (ein einziger, schnellerer chained
        # Aufruf) gewann Python das Rennen oft zuerst und `open(out_path, "rb")" schlug mit
        # `FileNotFoundError` fehl. Fix: Dateien IMMER anlegen, falls sie fehlen (idempotent,
        # nie ein Trunkieren bei einem Turn>1-Respawn, da nur bei Nicht-Existenz geschrieben wird).
        if not self.out_path.exists():
            self.out_path.write_bytes(b"")
        if not self.err_path.exists():
            self.err_path.write_bytes(b"")

        await self._ensure_no_stale_session()

        if long_lived:
            if self._control_fifo.exists():
                self._control_fifo.unlink()
            os.mkfifo(self._control_fifo)
            cmd = self._pane_command_long_lived(argv, cwd=cwd)
        else:
            cmd = self._pane_command_oneshot(argv, cwd=cwd, stdin_file=stdin_file)

        # BUG-1 (QA 2026-07-06): `new-session` gefolgt von einem SEPARATEN `set-option`-
        # Aufruf lässt ein Zeitfenster, in dem ein schnell fertiger Oneshot-Befehl (echte
        # Codex-/OpenCode-Läufe sind das nahezu immer) die Pane/Session bereits beendet,
        # bevor der zweite Aufruf greift — als einzige Session fährt der tmux-SERVER dann
        # selbst herunter, und `set-option -t <session>` trifft auf "no server running"
        # (reproduziert: 3/3 echte Codex-/OpenCode-Starts scheiterten daran).
        # Fix: `remain-on-exit` (+ `exit-empty off`, damit der Supervisor-Server auch mit
        # null Sessions bestehen bleibt) GLOBAL setzen, BEVOR die Session angelegt wird —
        # alles in EINEM chained tmux-Aufruf (`;`-getrennt), sodass die Option bereits gilt,
        # während `new-session` läuft, ohne jedes Zeitfenster. Verifiziert: übersteht sogar
        # einen sofort beendeten `true`-Befehl (extremer als jeder reale CLI-Turnaround).
        new_session_args = (
            "start-server", ";",
            "set-option", "-g", "exit-empty", "off", ";",
            "set-option", "-g", "remain-on-exit", "on", ";",
            "new-session", "-d", "-s", self.tmux_session, "-x", "220", "-y", "50", cmd,
        )
        await self._spawn_new_session(new_session_args)
        self._spawned = True
        # Optimistisch geprimt: wir haben die Session gerade selbst angelegt — ohne
        # das wäre `is_alive` bis zum ersten Async-Probe (readline/wait/refresh_liveness)
        # fälschlich "nicht sicher lebend" (Property kann nicht synchron tmux fragen).
        self._alive_cache = (time.monotonic(), True)
        if self._out_fh is None:
            self._out_fh = open(self.out_path, "rb")  # noqa: SIM115 - über Turns hinweg offen
        # Echte OS-PID des Pane-Prozesses cachen -> synchron ueber `.pid` abrufbar (fuer
        # EngineDriver.pid / pid_alive()-Liveness, dieselbe Signal-0-Pruefung wie direct).
        # PROJ-64: rein diagnostisch (nur fuer `.pid`/Liveness) — ein Timeout hier darf
        # einen bereits erfolgreichen Spawn (siehe `_spawn_new_session`) NICHT im
        # Nachhinein zum Fehler machen; best-effort `None` statt eines Crashs.
        try:
            self._cached_pid = await self.pane_pid()
        except TmuxTimeoutError:
            log.warning(
                "tmux list-panes (PID-Ermittlung) für Session %s antwortet nicht — "
                "Spawn bleibt erfolgreich, PID bleibt vorerst unbekannt (PROJ-64).",
                self.tmux_session,
            )
            self._cached_pid = None

    async def _spawn_new_session(self, new_session_args: tuple[str, ...]) -> None:
        """PROJ-64: BUG-4-Nachfolger — der `new-session`-Aufruf wird NIE blind
        wiederholt (Gefahr einer Doppel-Session, falls er trotz Timeout tatsächlich
        durchgelaufen war). Stattdessen bei einem Timeout zuerst prüfen, ob die
        Session bereits existiert (genau der im Produktionsvorfall 2026-07-07
        beobachtete Fall: Session lief im Hintergrund korrekt, nur die Antwort auf
        diesen Aufruf kam nie an) — nur wenn sie das NICHT tut, einmalig erneut
        versuchen. Scheitert auch das, bleibt der bestehende 503-Pfad (PROJ-63/
        BUG-2, ausgelöst über die weiterhin geerbte `TmuxTimeoutError`) als letzte
        Absicherung unverändert erhalten."""
        try:
            await self._tmux(*new_session_args)
            return
        except TmuxTimeoutError:
            log.warning(
                "tmux new-session (Session %s) antwortet nicht — prüfe, ob sie "
                "trotzdem entstanden ist, bevor ein Fehler gemeldet wird (PROJ-64).",
                self.tmux_session,
            )
        if await self._session_exists_after_timeout():
            log.warning(
                "tmux-Session %s existiert trotz Timeout bereits — wird als "
                "erfolgreich gestartet behandelt (kein 503, PROJ-64).",
                self.tmux_session,
            )
            return
        # has-session sagt "existiert nicht" -> ein zweiter new-session-Versuch
        # kann keine Doppel-Session erzeugen.
        try:
            await self._tmux(*new_session_args)
            return
        except TmuxTimeoutError:
            pass
        if await self._session_exists_after_timeout():
            log.warning(
                "tmux-Session %s existiert nach dem Wiederholungsversuch — wird "
                "als erfolgreich gestartet behandelt (PROJ-64).",
                self.tmux_session,
            )
            return
        # Beide Versuche liefen in die Reaping-Störung UND die Session existiert
        # nachweislich nicht -> weiterhin ein sauberer, für den Nutzer sichtbarer
        # Fehler statt eines für immer hängenden Requests (PROJ-63/BUG-2/BUG-4).
        raise TmuxTimeoutError(
            f"tmux new-session (Session {self.tmux_session}) antwortet auch nach "
            "einer Wiederholung nicht — Transport 'tmux' nicht verfügbar."
        )

    async def _session_exists_after_timeout(self) -> bool:
        """``session_exists()`` für den Attach-statt-Fehler-Pfad in
        ``_spawn_new_session`` — bereits über ``tmux_cmd_retries`` gehärtet; ein
        endgültiges Scheitern (auch dieser Check läuft in die Störung) zählt
        konservativ als "existiert nicht" (führt zum bestehenden Retry-/
        Fehlerpfad, nie zu einem stillen Fehlschlag)."""
        try:
            return await self.session_exists()
        except TmuxTimeoutError:
            return False

    def prepare_prompt_file(self, data: bytes) -> str:
        """Schreibt den naechsten Turn-Prompt in eine Datei fuer den Datei-Redirect
        (Oneshot-Engines) — keine offene Pipe noetig, echtes EOF nach dem Prompt.
        Muss VOR ``spawn()`` aufgerufen werden (der Pfad wird als ``stdin_file``
        uebergeben)."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self._prompt_counter += 1
        path = self._dir / f"prompt-{self._prompt_counter}.txt"
        path.write_bytes(data)
        return str(path)

    async def _ensure_no_stale_session(self) -> None:
        """Respawn-Fall (Oneshot-Folgeturn): eine gleichnamige alte Session zuerst
        sauber beenden, bevor die neue angelegt wird (keine Kollision)."""
        rc, _out, _err = await self._tmux(
            "has-session", "-t", self.tmux_session, check=False, retries=settings.tmux_cmd_retries
        )
        if rc == 0:
            await self._tmux(
                "kill-session", "-t", self.tmux_session, check=False, retries=settings.tmux_cmd_retries
            )

    def _pane_command_long_lived(self, argv: list[str], *, cwd: str) -> str:
        quoted_argv = " ".join(shlex.quote(a) for a in argv)
        quoted_cwd = shlex.quote(cwd)
        quoted_fifo = shlex.quote(str(self._control_fifo))
        quoted_out = shlex.quote(str(self.out_path))
        quoted_err = shlex.quote(str(self.err_path))
        # `exec 9<>fifo` haelt selbst einen Writer-Handle offen -> der lesende
        # Prozess sieht nie EOF, nur weil ein externer (Backend-)Schreiber
        # zwischendurch schliesst (Kernbefund des Spikes).
        return (
            f"cd {quoted_cwd} && exec 9<>{quoted_fifo} && "
            f"{quoted_argv} <&9 >> {quoted_out} 2>> {quoted_err}; "
            f"echo {EXIT_MARKER}:$? >> {quoted_err}"
        )

    def _pane_command_oneshot(
        self, argv: list[str], *, cwd: str, stdin_file: str | None
    ) -> str:
        quoted_argv = " ".join(shlex.quote(a) for a in argv)
        quoted_cwd = shlex.quote(cwd)
        quoted_out = shlex.quote(str(self.out_path))
        quoted_err = shlex.quote(str(self.err_path))
        stdin_redirect = f"< {shlex.quote(stdin_file)}" if stdin_file else "< /dev/null"
        return (
            f"cd {quoted_cwd} && {quoted_argv} {stdin_redirect} >> {quoted_out} 2>> {quoted_err}; "
            f"echo {EXIT_MARKER}:$? >> {quoted_err}"
        )

    # -- I/O --------------------------------------------------------------

    async def write_line(self, data: bytes) -> None:
        if not self._long_lived:
            raise TransportError(
                "TmuxTransport: write_line() nur für long-lived Sessions — "
                "Oneshot-Engines erhalten den nächsten Turn über spawn(stdin_file=...)."
            )
        if not self._spawned:
            raise TransportError("TmuxTransport: spawn() wurde noch nicht aufgerufen.")

        def _write() -> None:
            # Kurzlebiger Schreiber (öffnen-schreiben-schließen) — die Offenhaltung
            # kommt bewusst aus dem Pane-Wrapper (`exec 9<>fifo`), NICHT von hier,
            # sonst wiederholt sich der Spike-Bug: ein Backend-Neustart würde diesen
            # Writer-Handle schließen und der Prozess sähe fälschlich EOF.
            with open(self._control_fifo, "wb") as fh:
                fh.write(data)

        await asyncio.to_thread(_write)

    async def readline(self) -> bytes:
        if self._out_fh is None:
            return b""
        while True:
            line = self._out_fh.readline()
            if line:
                return line
            if not await self._is_alive_async():
                # letzte Reste nach Prozessende noch einsammeln (best-effort einmalig).
                line = self._out_fh.readline()
                return line
            await asyncio.sleep(self._poll_interval)

    async def read_stderr_text(self) -> str:
        try:
            return await asyncio.to_thread(self.err_path.read_text, "utf-8")
        except OSError:
            return ""

    def capture_backfill(self, *, max_bytes: int = 200_000) -> bytes:
        """Bounded Snapshot des bisherigen stdout — für Reconnect/Gerätewechsel-Backfill."""
        try:
            size = self.out_path.stat().st_size
        except OSError:
            return b""
        offset = max(0, size - max_bytes)
        with open(self.out_path, "rb") as fh:
            fh.seek(offset)
            return fh.read()

    # -- Lifecycle ----------------------------------------------------------

    async def terminate(self) -> None:
        await self._tmux(
            "kill-session", "-t", self.tmux_session, check=False, retries=settings.tmux_cmd_retries
        )
        # Cache sofort invalidieren -> der naechste is_alive-Check (i. d. R. im
        # readline()-Poll-Loop) sieht ohne Cache-Verzoegerung "tot" statt bis zu
        # `liveness_cache_seconds` auf einen veralteten "lebt"-Wert zu vertrauen.
        self._alive_cache = None

    async def kill(self) -> None:
        await self._tmux(
            "kill-session", "-t", self.tmux_session, check=False, retries=settings.tmux_cmd_retries
        )
        self._alive_cache = None

    async def wait(self) -> int | None:
        while await self._is_alive_async():
            await asyncio.sleep(self._poll_interval)
        return self._parse_exit_code()

    def _parse_exit_code(self) -> int | None:
        try:
            text = self.err_path.read_text("utf-8")
        except OSError:
            return None
        for line in reversed(text.splitlines()):
            if line.startswith(f"{EXIT_MARKER}:"):
                with contextlib.suppress(ValueError):
                    return int(line.split(":", 1)[1])
        return None

    def close(self) -> None:
        """Lese-Handle freigeben (kein tmux-/Prozess-Effekt, nur lokale Ressource)."""
        if self._out_fh is not None:
            with contextlib.suppress(OSError):
                self._out_fh.close()
            self._out_fh = None

    # -- Liveness -------------------------------------------------------------

    @property
    def is_alive(self) -> bool:
        return self._is_alive_sync()

    def _is_alive_sync(self) -> bool:
        # Synchroner Fallback (Property) — best-effort, nutzt denselben Cache.
        now = time.monotonic()
        if self._alive_cache is not None and now - self._alive_cache[0] < self._liveness_cache_seconds:
            return self._alive_cache[1]
        return False  # ohne frischen Async-Check konservativ "nicht sicher lebend"

    async def _is_alive_async(self) -> bool:
        now = time.monotonic()
        if self._alive_cache is not None and now - self._alive_cache[0] < self._liveness_cache_seconds:
            return self._alive_cache[1]
        alive = await self._probe_alive()
        self._alive_cache = (now, alive)
        return alive

    async def refresh_liveness(self) -> bool:
        """Erzwingt einen frischen tmux-Check (ignoriert den kurzen Cache)."""
        self._alive_cache = None
        return await self._is_alive_async()

    async def _probe_alive(self) -> bool:
        if not self._spawned:
            return False
        rc, out, _err = await self._tmux(
            "list-panes", "-t", self.tmux_session, "-F", "#{pane_dead}",
            check=False, retries=settings.tmux_cmd_retries,
        )
        if rc != 0:
            return False  # Session existiert nicht (mehr).
        return any(line.strip() == "0" for line in out.splitlines())

    @property
    def pid(self) -> int | None:
        """Echte OS-PID des Pane-Prozesses, gecacht beim letzten ``spawn()`` — synchron
        abrufbar (wie ``DirectTransport.pid``), obwohl die Ermittlung selbst async ist."""
        return self._cached_pid

    async def pane_pid(self) -> int | None:
        """OS-PID des Pane-Prozesses (best-effort, für Diagnose/Orphan-Check)."""
        rc, out, _err = await self._tmux(
            "list-panes", "-t", self.tmux_session, "-F", "#{pane_pid}",
            check=False, retries=settings.tmux_cmd_retries,
        )
        if rc != 0:
            return None
        line = out.strip().splitlines()[0] if out.strip() else ""
        return int(line) if line.isdigit() else None

    async def session_exists(self) -> bool:
        rc, _out, _err = await self._tmux(
            "has-session", "-t", self.tmux_session, check=False, retries=settings.tmux_cmd_retries
        )
        return rc == 0

    def cleanup_files(self) -> None:
        """Best-effort: FIFO/Logs/Arbeitsverzeichnis entfernen (nach endgültigem Stop)."""
        self.close()
        with contextlib.suppress(OSError):
            if self._control_fifo.exists():
                self._control_fifo.unlink()
        with contextlib.suppress(OSError):
            self.out_path.unlink()
        with contextlib.suppress(OSError):
            self.err_path.unlink()
        with contextlib.suppress(OSError):
            self._dir.rmdir()
