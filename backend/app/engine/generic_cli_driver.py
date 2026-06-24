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
from .base import EngineDriver, EventHandler, LaunchSpec
from .events import StreamEvent


def build_generic_argv(profile, spec: LaunchSpec) -> list[str]:
    """Füllt die Platzhalter der ``argv_template`` aus dem ``LaunchSpec``. Reine Funktion.

    Platzhalter (überall in den Argumenten ersetzbar): ``{model}``, ``{session_id}``,
    ``{project_path}``, ``{prompt}``. Beginnt das Template nicht mit dem Binary, wird
    ``profile.bin`` vorangestellt.
    """
    subs = {
        "{model}": spec.model or "",
        "{session_id}": spec.session_id,
        "{project_path}": spec.project_path,
        "{prompt}": spec.initial_prompt or "",
    }
    argv: list[str] = []
    for tok in profile.argv_template:
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

    @property
    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else None

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._on = on_event
        argv = build_generic_argv(self.profile, spec)
        # Engine-agnostischer Init (setzt Status → running), bevor der Strom kommt.
        await self._emit(
            StreamEvent("system", "init", {"session_id": spec.session_id, "model": spec.model})
        )
        self._proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=spec.project_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())
        # Initial-Prompt: per stdin (Default) — außer das Template trägt ihn schon als Arg.
        if spec.initial_prompt and self.profile.prompt_via == "stdin":
            await self.send_input(spec.initial_prompt)

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert — keine Eingaben möglich.")
        if not self.is_alive or self._proc is None or self._proc.stdin is None:
            raise RuntimeError("Session läuft nicht.")
        self._proc.stdin.write(encode_input(text, self.profile.input_format))
        await self._proc.stdin.drain()
        # Single-Turn-CLIs (oneshot): stdin schließen → Engine beendet den Turn + Prozess.
        if self.profile.oneshot:
            try:
                self._proc.stdin.close()
            except (RuntimeError, OSError):
                pass

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
            if event is not None:
                await self._emit(event)
        rc = await self._proc.wait()
        # Selbst gestoppt ODER sauberer Exit → closed (→ done); echtes Crash-Exit → error.
        if self._stopping or rc in (0, None):
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
