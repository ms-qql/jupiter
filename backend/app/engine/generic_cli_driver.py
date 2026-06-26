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
        self._saw_result = False            # Turn lieferte ein Turn-Ende → kein DONE bei EOF

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

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._on = on_event
        self._spec = spec
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
        self._saw_result = False
        self._stderr_buf = []
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

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert — keine Eingaben möglich.")
        # Lebt der Prozess noch → direkt in stdin (z. B. nicht-oneshot oder mid-turn).
        if self.is_alive and self._proc is not None and self._proc.stdin is not None:
            await self._write_stdin(text)
            return
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
        if proc is None:
            return
        self._stopping = True
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
            if event.type == "result":
                self._saw_result = True
            await self._emit(event)
        rc = await self._proc.wait()
        # Selbst gestoppt → closed (→ done). PROJ-48: ein resumefähiger oneshot-Turn, der
        # sauber mit Turn-Ende endete, ist NICHT „done" — die Session bleibt fortsetzbar
        # (Status bleibt „wartet", gesetzt vom result-Event); kein `closed` emittieren.
        if self._stopping:
            await self._emit(StreamEvent("system", "closed", {}))
        elif rc in (0, None):
            if self.supports_self_resume and self._saw_result:
                return  # Turn fertig, Session fortsetzbar → kein DONE
            await self._emit(StreamEvent("system", "closed", {}))
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
