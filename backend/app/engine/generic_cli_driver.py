"""GenericCliDriver (PROJ-18) — ein konfigurierbarer Treiber für **fremde CLIs**.

Erfüllt dasselbe :class:`EngineDriver`-Interface wie der ClaudeCodeDriver (start/eingeben/
pausieren/stoppen), ist aber **nicht** auf Claude verdrahtet: Aufruf (``argv_template``),
Eingabe-Weg (``prompt_via``/``input_format``) und Strom-Parsing (``adapter``) kommen aus
dem :class:`EngineProfile` — also aus ``engines.yaml``, ohne Codeänderung pro Engine.
Damit lassen sich Codex/Gemini/GLM/Ollama u. a. als Plug-in einhängen (AC: generischer
CLI-Treiber, per Konfiguration gemappt).

Der Strom wird über den gewählten **Adapter** auf den internen, Claude-förmigen
Event-Vertrag normalisiert → der gesamte Manager-/Cockpit-Code bleibt engine-agnostisch.
Liefert die Engine kein strukturiertes Protokoll, degradiert der ``plaintext``-Adapter
sichtbar (eingeschränkte Live-Sicht), statt zu crashen.
"""
from __future__ import annotations

import asyncio
import json
import os

from .adapters import get_adapter
from .base import EngineDriver, EventHandler, LaunchSpec, pid_alive
from .events import StreamEvent
from .transport import EXIT_MARKER, TmuxTransport, TransportError


def build_generic_argv(
    profile, spec: LaunchSpec, *, resume: bool = False, resume_id: str | None = None
) -> list[str]:
    """Füllt die Platzhalter eines argv-Templates aus dem ``LaunchSpec``. Reine Funktion.

    Platzhalter (überall in den Argumenten ersetzbar): ``{model}``, ``{session_id}``,
    ``{project_path}``, ``{prompt}``, ``{resume_id}``. Beginnt das Template nicht mit dem
    Binary, wird ``profile.bin`` vorangestellt.

    ``resume=True`` (PROJ-48) wählt ``profile.resume_argv_template`` für Folge-Turns einer
    oneshot-CLI; ``resume_id`` füllt ``{resume_id}`` (z. B. Codex' ``thread_id``).
    """
    template = profile.resume_argv_template if resume else profile.argv_template
    subs = {
        "{model}": spec.model or "",
        "{session_id}": spec.session_id,
        "{project_path}": spec.project_path,
        "{prompt}": spec.initial_prompt or "",
        "{resume_id}": resume_id or "",
    }
    argv: list[str] = []
    for tok in template:
        s = str(tok)
        for needle, value in subs.items():
            s = s.replace(needle, value)
        argv.append(s)
    if profile.bin and (not argv or argv[0] != profile.bin):
        argv = [profile.bin, *argv]
    return argv


def _strip_exit_marker(text: str) -> str:
    """Entfernt die interne tmux-Exit-Code-Marker-Zeile aus stderr, bevor sie dem
    Nutzer als Fehlermeldung gezeigt wird (siehe ``transport.py: EXIT_MARKER``)."""
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith(EXIT_MARKER))


def encode_input(text: str, input_format: str) -> bytes:
    """Kodiert eine Eingabe für stdin: ``stream_json`` (Claude-artiger Envelope) oder ``text``."""
    if input_format == "stream_json":
        payload = {
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        }
        return (json.dumps(payload) + "\n").encode("utf-8")
    return (text + "\n").encode("utf-8")


class GenericCliDriver(EngineDriver):
    def __init__(self, profile) -> None:
        self.profile = profile
        self._parse = get_adapter(profile.adapter)
        self._proc: asyncio.subprocess.Process | None = None
        self._on: EventHandler | None = None
        self._reader_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._stderr_buf: list[str] = []
        self._paused = False
        self._stopping = False
        # PROJ-48: Merker für den Resume-Pfad (oneshot-CLIs, die je Turn neu spawnen).
        self._spec: LaunchSpec | None = None
        self._resume_id: str | None = None  # z. B. Codex' thread_id (aus system/resume_token)
        # PROJ-60: NUR ein echtes Turn-Ende (result.raw["final"] ist bei Claude/Codex immer
        # True, da sie nur EIN result je Turn liefern; OpenCode markiert Tool-Zwischenschritte
        # explizit mit final=False, siehe PROJ-58) unterdrückt das `closed`-Event bei EOF.
        # Ein reines "irgendein result kam schon" reichte nicht: bricht der Prozess NACH einem
        # Tool-Zwischenschritt ab (Provider-Timeout/Crash, rc=0, kein finaler step_finish),
        # wurde das fälschlich als „Turn normal beendet, wartet auf nächste Eingabe" gewertet
        # — die Session hing für immer im letzten Status (kein `closed`, kein Fehler, still).
        self._saw_final_result = False
        # PROJ-58: bei `oneshot`-CLIs schließt `_write_stdin` die Pipe bereits am TURN-START
        # (nicht -ende) — der Prozess bleibt aber bis zum Turn-Ende `is_alive`. Ohne diesen
        # Merker prüfte `send_input` nur `is_alive` und schrieb erneut auf die längst
        # geschlossene Pipe → uvloop-Transport-Fehler ("handler is closed").
        self._stdin_closed = False
        # PROJ-63: "direct" (heutiges Verhalten, unverändert) oder "tmux". Nur bei "tmux"
        # wird `self._transport_obj` genutzt — für "direct" bleibt `self._proc` (s. o.)
        # der alleinige Prozess-Zugriffspfad, exakt wie vor PROJ-63.
        self._transport_mode = "direct"
        self._transport_obj: TmuxTransport | None = None
        # OpenCode lehnt einen Prozessstart ohne Nachricht ab. Im freien Chat-Modus
        # darf Jupiter aber bewusst ohne Initial-Prompt starten (PROJ-34). Dann wird
        # der erste CLI-Prozess bis zur ersten echten Nutzereingabe aufgeschoben.
        # Codex bleibt unverändert: dessen CLI akzeptiert den bisherigen Leerstart.
        self._awaiting_first_input = False

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
        # PROJ-33: zusätzlich zur asyncio-``returncode`` die OS-PID prüfen (kein Geister-„aktiv").
        return pid_alive(proc.pid)

    @property
    def pid(self) -> int | None:
        if self._transport_mode == "tmux":
            return self._transport_obj.pid if self._transport_obj is not None else None
        return self._proc.pid if self._proc is not None else None

    @property
    def supports_self_resume(self) -> bool:
        """PROJ-48: Treiber kann einen toten oneshot-Prozess selbst per Resume-argv
        fortsetzen (Kontext bleibt erhalten) → der Manager soll **nicht** den
        ``claude --resume``-Pfad (frischer, kontextloser Treiber) auslösen."""
        return bool(self.profile.resume_argv_template)

    @property
    def resume_id(self) -> str | None:
        """PROJ-56: aufgefangene Wiederaufnahme-ID (z. B. Codex' thread_id) — der Manager
        persistiert sie, damit sie einen Backend-Restart überlebt."""
        return self._resume_id

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._on = on_event
        self._spec = spec
        # PROJ-63: nur bei "tmux" wird der neue Pfad genutzt; jeder andere Wert
        # (insb. der Default "direct") verhält sich exakt wie vor PROJ-63.
        self._transport_mode = "tmux" if spec.transport == "tmux" else "direct"
        # PROJ-56: kontext-erhaltender Resume nach Treiber-Neubau (Restart/Reanimierung).
        # Für eine self-resume-fähige oneshot-CLI mit bekannter Resume-ID KEINEN frischen
        # Thread spawnen — nur die ID vormerken; der nächste ``send_input`` nimmt über das
        # Resume-argv den bestehenden serverseitigen Kontext wieder auf. Fehlt die ID,
        # fällt es bewusst auf den normalen (kontextlosen) Frischstart zurück.
        if spec.resume and self.supports_self_resume and spec.resume_id:
            self._resume_id = spec.resume_id
            return
        # Engine-agnostischer Init (setzt Status → running), bevor der Strom kommt.
        await self._emit(
            StreamEvent("system", "init", {"session_id": spec.session_id, "model": spec.model})
        )
        if self.profile.adapter == "opencode" and not spec.initial_prompt.strip():
            self._awaiting_first_input = True
            await self._emit(StreamEvent("system", "waiting", {"reason": "initial_prompt_empty"}))
            return
        # Initial-Prompt: per stdin (Default) — außer das Template trägt ihn schon als Arg.
        prompt = spec.initial_prompt if (spec.initial_prompt and self.profile.prompt_via == "stdin") else None
        await self._spawn(build_generic_argv(self.profile, spec), spec.project_path, prompt=prompt)

    async def _spawn(self, argv: list[str], cwd: str, *, prompt: str | None = None) -> None:
        """Startet einen Subprozess (direct) bzw. respawnt die tmux-Session (tmux) für
        GENAU einen Turn und hängt die Reader an."""
        self._stopping = False
        self._saw_final_result = False
        self._stderr_buf = []
        self._stdin_closed = False
        if self._transport_mode == "tmux":
            await self._spawn_tmux(argv, cwd, prompt=prompt)
            return
        # PROJ-80: zusätzliche Prozess-Umgebung (z. B. Koordinator-Capability-Token) mergen.
        proc_env = {**os.environ, **(self._spec.env or {})} if self._spec else dict(os.environ)
        self._proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=proc_env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())
        # Verhalten unverändert: Schreiben ERST nachdem der Prozess/die Reader stehen
        # (identische Reihenfolge zu vor PROJ-63, nur in `_spawn` verlagert).
        if prompt is not None and self.profile.prompt_via == "stdin":
            await self._write_stdin(prompt)

    async def _spawn_tmux(self, argv: list[str], cwd: str, *, prompt: str | None) -> None:
        """PROJ-63: Oneshot-Turn unter tmux — Prompt (falls vorhanden) vorab in eine
        Datei schreiben und per echtem Datei-Redirect übergeben (kein PTY, kein
        TTY-Fehler, siehe Spike-Ergebnisse in features/PROJ-63-*.md). Jeder Turn ruft
        `TmuxTransport.spawn()` erneut auf — eine gleichnamige Vorgänger-Session wird
        dabei zuerst sauber beendet (respawn), der tmux-Session-Name bleibt stabil."""
        if self._transport_obj is None:
            session_key = self._spec.session_id if self._spec is not None else "session"
            self._transport_obj = TmuxTransport(session_key)
        stdin_file: str | None = None
        if prompt is not None and self.profile.prompt_via == "stdin":
            data = encode_input(prompt, self.profile.input_format)
            stdin_file = self._transport_obj.prepare_prompt_file(data)
        try:
            await self._transport_obj.spawn(
                argv, cwd=cwd, long_lived=False, stdin_file=stdin_file,
                env=self._spec.env if self._spec else None,
            )
        except TransportError as exc:
            await self._emit(StreamEvent("system", "error", {"message": str(exc)}))
            raise
        # Oneshot-Semantik: der Prompt ist bereits vollständig übergeben (Datei-Redirect),
        # kein separates `send_input` auf eine offene Pipe möglich/nötig.
        self._stdin_closed = True
        self._reader_task = asyncio.create_task(self._read_stdout())

    async def _write_stdin(self, text: str) -> None:
        """Schreibt eine Eingabe in den laufenden Prozess (oneshot: schließt stdin danach)."""
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(encode_input(text, self.profile.input_format))
        await self._proc.stdin.drain()
        # Single-Turn-CLIs (oneshot): stdin schließen → Engine beendet den Turn + Prozess.
        if self.profile.oneshot:
            try:
                self._proc.stdin.close()
            except (RuntimeError, OSError):
                pass
            self._stdin_closed = True

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert — keine Eingaben möglich.")
        if self._awaiting_first_input and self._spec is not None:
            # Noch keine OpenCode-Session vorhanden → erster echter Turn ist ein
            # Frischstart, kein Resume. Erst dessen Stream liefert die resume_id.
            self._awaiting_first_input = False
            spec = LaunchSpec(
                session_id=self._spec.session_id,
                project_path=self._spec.project_path,
                model=self._spec.model,
                permission_mode=self._spec.permission_mode,
                initial_prompt=text,
                transport=self._spec.transport,
            )
            prompt = text if self.profile.prompt_via == "stdin" else None
            await self._spawn(build_generic_argv(self.profile, spec), spec.project_path, prompt=prompt)
            return
        # Lebt der Prozess noch UND stdin ist noch offen → direkt schreiben (z. B.
        # langlebiger Treiber wie Claude, oder ein oneshot-Prozess vor dem ersten Write).
        if (
            self.is_alive
            and self._proc is not None
            and self._proc.stdin is not None
            and not self._stdin_closed
        ):
            await self._write_stdin(text)
            return
        # PROJ-58: Prozess läuft noch (Tool-Aufrufe etc.), stdin aber bereits zu (oneshot) —
        # weder erneut schreiben (uvloop-Transport-Fehler) noch parallel einen zweiten
        # Prozess über den Resume-Pfad spawnen (zwei Prozesse dürften nicht gleichzeitig
        # dieselbe Resume-Session der Engine anfassen). Klare, abfangbare Fehlermeldung
        # statt eines internen Crashs.
        if self.is_alive:
            raise RuntimeError(
                "Antwort läuft noch — bitte warten, bis der aktuelle Turn abgeschlossen ist."
            )
        # PROJ-48: oneshot-Turn beendet, Prozess weg → Folge-Turn als frischen Prozess
        # mit dem Resume-argv spawnen (Kontext bleibt serverseitig am resume_id).
        if self.supports_self_resume and self._spec is not None:
            if "{resume_id}" in "".join(self.profile.resume_argv_template) and not self._resume_id:
                raise RuntimeError(
                    "Fortsetzen nicht möglich: keine Resume-ID der Engine empfangen."
                )
            spec = LaunchSpec(
                session_id=self._spec.session_id,
                project_path=self._spec.project_path,
                model=self._spec.model,
                permission_mode=self._spec.permission_mode,
                initial_prompt=text,
            )
            argv = build_generic_argv(
                self.profile, spec, resume=True, resume_id=self._resume_id
            )
            prompt = text if self.profile.prompt_via == "stdin" else None
            await self._spawn(argv, spec.project_path, prompt=prompt)
            return
        raise RuntimeError("Session läuft nicht.")

    async def pause(self) -> None:
        self._paused = True

    async def stop(self) -> None:
        self._stopping = True
        if self._transport_mode == "tmux":
            # PROJ-63: `self._proc` bleibt im tmux-Modus immer None — ohne diesen
            # eigenen Zweig würde der `proc is None`-Fall unten greifen und NUR das
            # `closed`-Event emittieren, ohne die tmux-Session tatsächlich zu beenden
            # (Prozess-/Ressourcen-Leck).
            if self._transport_obj is not None:
                await self._transport_obj.kill()
            if self._stderr_task is not None:
                self._stderr_task.cancel()
            await self._emit(StreamEvent("system", "closed", {}))
            return
        proc = self._proc
        if proc is None:
            # PROJ-59: Self-Resume-Zustand (oneshot-CLI zwischen Turns nach Reanimierung/
            # Neustart) — kein Prozess gespawnt, aber die Session gilt als aktiv/wartend.
            # Ohne dieses Event bleibt sie für immer in „Aktive Sessions" hängen, weil der
            # Manager nie ein terminales Event bekommt.
            await self._emit(StreamEvent("system", "closed", {}))
            return
        try:
            if proc.stdin is not None and not proc.stdin.is_closing():
                proc.stdin.close()
        except (RuntimeError, OSError):
            pass
        if proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            except ProcessLookupError:
                pass
        if self._stderr_task is not None:
            self._stderr_task.cancel()
        await self._emit(StreamEvent("system", "closed", {}))

    # --- intern -----------------------------------------------------------

    async def _emit(self, event: StreamEvent) -> None:
        if self._on is not None:
            await self._on(event)

    async def _read_stdout(self) -> None:
        is_tmux = self._transport_mode == "tmux"
        if is_tmux:
            assert self._transport_obj is not None
            stream = self._transport_obj
        else:
            assert self._proc is not None and self._proc.stdout is not None
            stream = self._proc.stdout
        while True:
            line = await stream.readline()
            if not line:  # EOF → Prozess fertig
                break
            event = self._parse(line.decode("utf-8", errors="replace"))
            if event is None:
                continue
            # PROJ-48: Resume-ID (z. B. Codex' thread_id) abfangen — kein Anzeige-Event.
            if event.type == "system" and event.subtype == "resume_token":
                token = event.raw.get("resume_token")
                if token:
                    self._resume_id = str(token)
                continue
            if event.type == "result" and event.raw.get("final", True):
                self._saw_final_result = True
            await self._emit(event)
        rc = await self._transport_obj.wait() if is_tmux else await self._proc.wait()
        # Selbst gestoppt → closed (→ done). PROJ-48: ein resumefähiger oneshot-Turn, der
        # sauber mit Turn-Ende endete, ist NICHT „done" — die Session bleibt fortsetzbar
        # (Status bleibt „wartet", gesetzt vom result-Event); kein `closed` emittieren.
        if self._stopping:
            await self._emit(StreamEvent("system", "closed", {}))
        elif rc in (0, None):
            if self.supports_self_resume and self._saw_final_result:
                return  # Turn fertig, Session fortsetzbar → kein DONE
            # PROJ-60: Prozess endete (rc 0/None), OHNE je ein echtes Turn-Ende geliefert zu
            # haben (Provider-Timeout/Crash nach einem Tool-Zwischenschritt o. Ä.) — das ist
            # KEIN normales Turn-Ende. `closed` emittieren, damit die Session terminiert
            # (sichtbar/archivierbar) statt für immer im letzten Status hängenzubleiben.
            # PROJ-62: Grund mitgeben, damit der Nutzer nicht vor einem stillen, unerklärten
            # Sessionende steht (manager.py befüllt daraus state.error, falls noch leer).
            await self._emit(
                StreamEvent("system", "closed", {"reason": "no_final_result"})
            )
        else:
            if is_tmux:
                stderr_text = _strip_exit_marker(await self._transport_obj.read_stderr_text())
            else:
                stderr_text = "".join(self._stderr_buf)
            msg = stderr_text.strip() or f"Prozess endete mit Code {rc}."
            await self._emit(StreamEvent("system", "error", {"message": msg}))

    async def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        stream = self._proc.stderr
        while True:
            line = await stream.readline()
            if not line:
                break
            self._stderr_buf.append(line.decode("utf-8", errors="replace"))
