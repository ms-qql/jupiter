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

from .adapters import get_adapter
from .base import EngineDriver, EventHandler, LaunchSpec, pid_alive
from .events import StreamEvent


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

    @property
    def is_alive(self) -> bool:
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return False
        # PROJ-33: zusätzlich zur asyncio-``returncode`` die OS-PID prüfen (kein Geister-„aktiv").
        return pid_alive(proc.pid)

    @property
    def pid(self) -> int | None:
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
        await self._spawn(build_generic_argv(self.profile, spec), spec.project_path)
        # Initial-Prompt: per stdin (Default) — außer das Template trägt ihn schon als Arg.
        if spec.initial_prompt and self.profile.prompt_via == "stdin":
            await self._write_stdin(spec.initial_prompt)

    async def _spawn(self, argv: list[str], cwd: str) -> None:
        """Startet einen Subprozess für GENAU einen Turn und hängt die Reader an."""
        self._stopping = False
        self._saw_final_result = False
        self._stderr_buf = []
        self._stdin_closed = False
        self._proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())

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
            await self._spawn(argv, spec.project_path)
            if self.profile.prompt_via == "stdin":
                await self._write_stdin(text)
            return
        raise RuntimeError("Session läuft nicht.")

    async def pause(self) -> None:
        self._paused = True

    async def stop(self) -> None:
        proc = self._proc
        self._stopping = True
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
        rc = await self._proc.wait()
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
            msg = "".join(self._stderr_buf).strip() or f"Prozess endete mit Code {rc}."
            await self._emit(StreamEvent("system", "error", {"message": msg}))

    async def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        stream = self._proc.stderr
        while True:
            line = await stream.readline()
            if not line:
                break
            self._stderr_buf.append(line.decode("utf-8", errors="replace"))
