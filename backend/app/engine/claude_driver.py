"""ClaudeCodeDriver — eine Claude-Max-Session via Claude Code headless.

Startet `claude -p --output-format stream-json --input-format stream-json --verbose`
als Subprozess (Subscription-Auth, kein API-Key), liest den Event-Strom und
reicht jede Zeile als geparstes :class:`StreamEvent` nach oben.

Wichtige, im Live-Spike (PROJ-1) bestätigte Punkte:
- `--output-format stream-json` erfordert `--verbose`.
- Eigene `--session-id` (UUID) → 1:1-Mapping Jupiter-Record ↔ Claude-Session.
- Multi-turn-Eingabe über stdin als stream-json-User-Message.
- PROJ-4: ein PreToolUse-Hook (via `--settings`) fängt genehmigungspflichtige
  Tools ab und fragt den Nutzer (Decision Cards) statt sie headless auto-zu-verweigern.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from ..config import settings
from .base import EngineDriver, EventHandler, LaunchSpec, pid_alive
from .events import StreamEvent, parse_line
from .transport import EXIT_MARKER, TmuxTransport, TransportError

log = logging.getLogger(__name__)


def _strip_exit_marker(text: str) -> str:
    """Entfernt die interne tmux-Exit-Code-Marker-Zeile aus stderr, bevor sie dem
    Nutzer als Fehlermeldung gezeigt wird (siehe ``transport.py: EXIT_MARKER``)."""
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith(EXIT_MARKER))


def build_argv(spec: LaunchSpec, claude_bin: str = "claude") -> list[str]:
    """Baut die CLI-Argumente. Reine Funktion → unit-testbar."""
    argv = [
        claude_bin,
        "-p",
        "--output-format", "stream-json",
        "--input-format", "stream-json",
        "--verbose",
        "--model", spec.model,
        # Resume lädt die bestehende Konversation (Fortsetzen einer beendeten Session);
        # sonst legt --session-id eine neue Session mit fester ID an.
        *(["--resume", spec.session_id] if spec.resume else ["--session-id", spec.session_id]),
        "--permission-mode", spec.permission_mode,
    ]
    if spec.system_prompt_append:
        argv += ["--append-system-prompt", spec.system_prompt_append]
    # PROJ-4: Freigabe-Hook (PreToolUse) als session-skopierte Settings einschleusen.
    if spec.settings_json:
        argv += ["--settings", spec.settings_json]
    return argv


def classify_exit(returncode: int | None, stopping: bool, stderr: str = "") -> StreamEvent:
    """Klassifiziert das Prozess-Ende als sauberen Abschluss oder Fehler.

    Ein von uns ausgelöster Stop (SIGTERM → negativer Code) ist KEIN Fehler.
    Nur ein unerwartetes Ende mit Nicht-Null-Code (z. B. Crash/OOM) ist einer.
    """
    if stopping or returncode in (0, None):
        return StreamEvent(type="system", subtype="closed", raw={})
    msg = stderr.strip() or f"Prozess endete unerwartet mit Code {returncode}."
    return StreamEvent(type="system", subtype="error", raw={"message": msg})


def _user_message(text: str) -> bytes:
    """stream-json-Envelope einer User-Eingabe (eine Zeile + Newline)."""
    payload = {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }
    return (json.dumps(payload) + "\n").encode("utf-8")


class ClaudeCodeDriver(EngineDriver):
    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None
        self._on_event: EventHandler | None = None
        self._reader_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._stderr_buf: list[str] = []
        self._paused = False
        self._stopping = False
        # PROJ-63: "direct" (bisheriges Verhalten, unverändert) oder "tmux". Claude ist
        # ein LANG-lebiger Multi-Turn-Prozess → im tmux-Modus der long-lived-Pfad
        # (FIFO-Selbst-Open, `write_line` je Folge-Turn), NICHT der oneshot-Datei-Redirect
        # von Codex/OpenCode. Nur bei "tmux" wird `self._transport_obj` genutzt; für
        # "direct" bleibt `self._proc` der alleinige Prozess-Zugriffspfad wie vor PROJ-63.
        self._transport_mode = "direct"
        self._transport_obj: TmuxTransport | None = None

    @property
    def is_alive(self) -> bool:
        if self._transport_mode == "tmux":
            # PROJ-63: dieselbe OS-Signal-0-Prüfung wie im direct-Pfad — der tmux-Pane-
            # Prozess hat eine echte OS-PID, `pid_alive` ist transport-agnostisch.
            transport = self._transport_obj
            return transport is not None and pid_alive(transport.pid)
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return False
        # PROJ-33: ``returncode`` allein kann veralten (Prozess tot, aber nicht
        # gereapt → Geister-„aktiv"). Zusätzlich die OS-PID verifizieren.
        return pid_alive(proc.pid)

    @property
    def pid(self) -> int | None:
        """OS-PID des laufenden Subprozesses (PROJ-14): für die Persistenz des
        Live-Index und den Verwaist-Check nach einem Backend-Neustart."""
        if self._transport_mode == "tmux":
            return self._transport_obj.pid if self._transport_obj is not None else None
        return self._proc.pid if self._proc is not None else None

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._on_event = on_event
        # PROJ-63: nur bei "tmux" wird der neue Pfad genutzt; jeder andere Wert
        # (insb. der Default "direct") verhält sich exakt wie vor PROJ-63.
        self._transport_mode = "tmux" if spec.transport == "tmux" else "direct"
        argv = build_argv(spec, settings.claude_bin)
        if self._transport_mode == "tmux":
            await self._spawn_tmux(argv, spec)
        else:
            # PROJ-80: zusätzliche Prozess-Umgebung (z. B. Koordinator-Capability-Token)
            # in die bestehende Umgebung mergen, damit der Subprozess sie sieht.
            proc_env = {**os.environ, **(spec.env or {})}
            self._proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=spec.project_path,
                env=proc_env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # PROJ-47: großzügiges Zeilenlimit statt asyncio-Default (64 KiB) — eine
                # einzelne große stream-json-Zeile darf den Reader nicht mehr sprengen.
                limit=settings.claude_stream_limit_bytes,
            )
            # stderr kommt im tmux-Modus über die err.log-Datei (kein PIPE-Reader nötig).
            self._stderr_task = asyncio.create_task(self._read_stderr())
        self._reader_task = asyncio.create_task(self._read_stdout())
        # PROJ-47: Reader beaufsichtigen — endet er unerwartet, wird das geloggt
        # (kein stiller Tod / verwaister Subprozess).
        self._reader_task.add_done_callback(self._on_reader_done)
        # Erster Turn: Initial-Prompt über stdin (uniformer multi-turn-Pfad).
        if spec.initial_prompt:
            await self.send_input(spec.initial_prompt)

    async def _spawn_tmux(self, argv: list[str], spec: LaunchSpec) -> None:
        """PROJ-63: Claude als long-lived tmux-Session starten. Der Pane-Wrapper hält
        stdin über eine selbst read-write geöffnete FIFO offen (``exec 9<>fifo``), sodass
        der Claude-Prozess nie EOF sieht, wenn ein externer Schreiber (Backend) zwischen
        Turns schließt — genau der im Spike verifizierte Kern für Backend-Restart-Überleben
        (siehe features/PROJ-63-*.md)."""
        self._transport_obj = TmuxTransport(spec.session_id)
        try:
            await self._transport_obj.spawn(
                argv, cwd=spec.project_path, long_lived=True, env=spec.env,
                # PROJ-72: Claude bindet sich stets ans Ende seiner session-skopierten
                # Append-Log. Bei einem echten Erststart ist sie leer; existiert bereits
                # Inhalt, ist er live/aus der DB im Transkript abgebildet und darf nie
                # erneut durch handle_event laufen. Diese Transport-Invariante bewusst
                # NICHT an `spec.resume` koppeln: Fehlt der Merker in nur einem Recovery-
                # Pfad, entsteht sonst wieder ein vollständiger Text-/Fragekarten-Replay.
                seek_to_end=True,
            )
        except TransportError as exc:
            await self._emit(StreamEvent(type="system", subtype="error", raw={"message": str(exc)}))
            raise

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert — keine Eingaben möglich.")
        if not self.is_alive:
            raise RuntimeError("Session läuft nicht.")
        if self._transport_mode == "tmux":
            # PROJ-63: Folge-Turn über die Kontroll-FIFO (kurzlebiger Schreiber); die
            # Offenhaltung liegt im Pane-Wrapper, nicht hier.
            assert self._transport_obj is not None
            await self._transport_obj.write_line(_user_message(text))
            return
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("Session läuft nicht.")
        self._proc.stdin.write(_user_message(text))
        await self._proc.stdin.drain()

    async def pause(self) -> None:
        # MVP: „Pause" = keine neuen Eingaben annehmen (laufender Turn wird beendet).
        self._paused = True

    async def stop(self) -> None:
        self._stopping = True
        if self._transport_mode == "tmux":
            # PROJ-63: `self._proc` bleibt im tmux-Modus immer None — die tmux-Session
            # muss explizit beendet werden (sonst Prozess-/Ressourcen-Leck), bevor das
            # terminale `closed` emittiert wird.
            if self._transport_obj is not None:
                await self._transport_obj.kill()
            if self._stderr_task is not None:
                self._stderr_task.cancel()
            await self._emit(StreamEvent(type="system", subtype="closed", raw={}))
            return
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.stdin is not None and not proc.stdin.is_closing():
                proc.stdin.close()
        except (RuntimeError, OSError):
            pass
        if proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=settings.process_stop_grace_seconds)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            except ProcessLookupError:
                # Prozess ist zwischenzeitlich selbst beendet — nichts zu tun.
                pass
        # Hintergrund-Reader sauber abräumen (kein Zombie, keine Pending-Tasks).
        if self._stderr_task is not None:
            self._stderr_task.cancel()
        await self._emit(StreamEvent(type="system", subtype="closed", raw={}))

    # --- intern -----------------------------------------------------------

    async def _emit(self, event: StreamEvent) -> None:
        if self._on_event is not None:
            await self._on_event(event)

    async def _read_stdout(self) -> None:
        is_tmux = self._transport_mode == "tmux"
        if is_tmux:
            assert self._transport_obj is not None
            stream = self._transport_obj
        else:
            assert self._proc is not None and self._proc.stdout is not None
            stream = self._proc.stdout
        try:
            while True:
                try:
                    line = await stream.readline()
                except (ValueError, asyncio.LimitOverrunError) as exc:
                    # PROJ-47: Eine stream-json-Zeile sprengte das StreamReader-Limit
                    # (großer Turn / großes Tool-Result). FRÜHER tötete diese Ausnahme
                    # den Reader lautlos → verwaister Subprozess, eingefrorene Anzeige.
                    # JETZT: loggen + überlange Zeile überspringen, der Reader liest
                    # weiter — nachfolgende Events (inkl. `result`) kommen weiter an.
                    log.warning(
                        "Session-Reader übersprang eine überlange stdout-Zeile "
                        "(Limit %d Bytes überschritten): %s",
                        settings.claude_stream_limit_bytes,
                        exc,
                    )
                    continue
                if not line:  # EOF → Prozess fertig
                    break
                event = parse_line(line.decode("utf-8", errors="replace"))
                if event is not None:
                    await self._emit(event)
        except asyncio.CancelledError:
            raise  # von stop() gewollt — kein Fehler.
        except Exception:
            # PROJ-47: Kein stiller Tod. Jede unerwartete Reader-Ausnahme wird mit
            # vollem Traceback geloggt UND als Fehler-Event nach oben gereicht, damit
            # die Session als ERROR sichtbar wird statt verwaist „läuft" anzuzeigen.
            log.exception("Session-Reader (stdout) ist unerwartet abgestürzt.")
            await self._emit(
                StreamEvent(
                    type="system",
                    subtype="error",
                    raw={
                        "message": "Interner Lesefehler des Session-Streams — "
                        "bitte Stop + Fortsetzen."
                    },
                )
            )
            return
        # Prozess-Ende klassifizieren (von uns gestoppt ≠ Fehler).
        if is_tmux:
            assert self._transport_obj is not None
            rc = await self._transport_obj.wait()
            stderr_text = _strip_exit_marker(await self._transport_obj.read_stderr_text())
        else:
            rc = await self._proc.wait()
            stderr_text = "".join(self._stderr_buf)
        await self._emit(classify_exit(rc, self._stopping, stderr_text))

    def _on_reader_done(self, task: asyncio.Task) -> None:
        """PROJ-47: Aufsicht über den stdout-Reader.

        Endet der Reader-Task unerwartet, darf das nicht im Stillen geschehen:
        - mit Ausnahme beendet  → Traceback ins Log,
        - regulär beendet, obwohl der Subprozess noch lebt und kein Stop läuft
          → Reader-Stall: diagnostisch klar loggen (Session per Stop + Fortsetzen
          re-synchronisierbar), statt den Subprozess unbemerkt verwaisen zu lassen.
        """
        if task.cancelled():
            return  # von stop() gewollt.
        exc = task.exception()
        if exc is not None:
            log.error("stdout-Reader-Task endete mit Ausnahme.", exc_info=exc)
        elif not self._stopping and self.is_alive:
            log.error(
                "Reader-Stall: stdout-Reader endete, obwohl der Subprozess (pid=%s) "
                "noch lebt und kein Stop läuft — Session re-synchronisieren "
                "(Stop + Fortsetzen).",
                self.pid,
            )

    async def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        stream = self._proc.stderr
        while True:
            line = await stream.readline()
            if not line:
                break
            self._stderr_buf.append(line.decode("utf-8", errors="replace"))
