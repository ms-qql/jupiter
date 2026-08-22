"""HermesChatDriver (PROJ-86) — direkter, benannter `hermes chat`.

Jede Jupiter-Session verwendet `--continue jupiter-<Jupiter-ID>`; der erste
Turn legt sie mit `--create-if-missing` an. Damit hängt die Fortsetzung nicht
von einer unzuverlässigen stdout-Conversation-ID ab.

Hermes läuft IMMER im direkten Prozessmodus (ADR-86-3): kein tmux, keine
Pane-Liveness, keine Auto-Reanimation — das schützt alle anderen Engines vor
Regressionen, weil nur der `engine="hermes"`-Zweig berührt wird.
"""
from __future__ import annotations

import asyncio
import re

from .base import LaunchSpec
from .generic_cli_driver import GenericCliDriver
from .events import StreamEvent

# Hermes gibt diese optionale Metazeile auch bei benannten Sessions aus. Sie ist
# Diagnoseausgabe, niemals Voraussetzung für den nächsten Turn.
_CONTROL_LINE = re.compile(r"^\s*session_id:\s*(\S+)\s*$")
_RESUME_BANNER = re.compile(r"^\s*↻ Resumed session ")


class HermesChatDriver(GenericCliDriver):
    """Treiber für die Hermes-CLI im direkten Chat-Modus (PROJ-86)."""

    def __init__(self, profile, *, provider: str, model: str) -> None:
        super().__init__(profile)
        self._provider = provider
        self._hermes_model = model
        self._resume_ref: str | None = None  # Legacy-Metadatum für rehydrierte Sessions.

    @property
    def resume_id(self) -> str | None:
        return self._resume_ref
    @property
    def supports_self_resume(self) -> bool:
        # Hermes setzt den Folge-Turn selbst über den stabilen Session-Namen fort.
        # `True` verhindert zusätzlich, dass der Manager den generischen
        # `claude --resume`-Pfad auslöst (PROJ-86: Hermes wird NICHT reanimiert).
        return True

    def _build_argv(self, spec: LaunchSpec) -> list[str]:
        cli = self.profile.bin or "hermes"
        argv = [
            cli, "chat", "-q", spec.initial_prompt or "",
            "--cli", "-Q",
            "-m", self._hermes_model,
            "--provider", self._provider,
            "--in", spec.project_path,
            "--yolo",
        ]
        session_name = f"jupiter-{spec.session_id}"
        if self._resume_ref and self._resume_ref != session_name:
            # Bestehende PROJ-86-Sessions einmalig über ihre alte Hermes-ID migrieren.
            argv += ["--resume", self._resume_ref]
        else:
            argv += ["--continue", session_name]
            if self._resume_ref is None:
                argv.append("--create-if-missing")
        return argv

    async def _spawn(self, argv: list[str], cwd: str, *, prompt: str | None = None) -> None:
        await super()._spawn(argv, cwd, prompt=prompt)

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:  # type: ignore[valid-type]
        self._on = on_event
        self._spec = spec
        self._resume_ref = spec.resume_id
        # ADR-86-3: Hermes IMMER direct (kein tmux, keine Pane-Liveness).
        self._transport_mode = "direct"
        await self._emit(StreamEvent("system", "init",
                                     {"session_id": spec.session_id, "model": self._hermes_model}))
        if not spec.initial_prompt or not spec.initial_prompt.strip():
            # Freier Chat ohne Initial-Prompt: auf erste Nutzereingabe warten.
            self._awaiting_first_input = True
            await self._emit(StreamEvent("system", "waiting", {"reason": "initial_prompt_empty"}))
            return
        await self._spawn(self._build_argv(spec), spec.project_path, prompt=None)

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert — keine Eingaben möglich.")
        if self._awaiting_first_input and self._spec is not None:
            # Erster echter Turn ist ein Frischstart (kein Resume), kein künstlicher Prompt.
            self._awaiting_first_input = False
            spec = self._spec_with_prompt(text)
            await self._spawn(self._build_argv(spec), spec.project_path, prompt=None)
            return
        if self.is_alive:
            raise RuntimeError("Antwort läuft noch — bitte warten, bis der aktuelle Turn abgeschlossen ist.")
        # Direkter Chat-Turn beendet → Folge-Turn mit demselben Hermes-Namen.
        if self._spec is not None:
            spec = self._spec_with_prompt(text)
            await self._spawn(self._build_argv(spec), spec.project_path, prompt=None)
            return
        raise RuntimeError("Session läuft nicht.")

    # --- stdout-Diagnosezeilen + Turn-Abschluss --------------------------------

    def _intercept_line(self, line: str) -> bool:
        """Hermes-Metazeilen abfangen, nie als Chat-Text anzeigen."""
        if _CONTROL_LINE.match(line) or _RESUME_BANNER.match(line):
            return True
        return False

    def _spec_with_prompt(self, text: str) -> LaunchSpec:
        assert self._spec is not None
        return LaunchSpec(
            session_id=self._spec.session_id,
            project_path=self._spec.project_path,
            model=self._spec.model,
            permission_mode=self._spec.permission_mode,
            initial_prompt=text,
            transport="direct",
        )

    async def _after_process_exit(self, rc: int | None) -> None:
        """Exit 0 schließt den benannten Hermes-Turn erfolgreich ab."""
        if rc in (0, None):
            assert self._spec is not None
            self._resume_ref = f"jupiter-{self._spec.session_id}"
            await self._emit(StreamEvent("system", "waiting", {"reason": "turn_complete"}))
            return
        stderr = "".join(self._stderr_buf).strip()
        msg = f"Hermes-Fortsetzung fehlgeschlagen: {stderr}" if stderr else f"Prozess endete mit Code {rc}."
        await self._emit(StreamEvent("system", "error", {"message": msg}))

    def _turn_completed_normally(self) -> bool:
        # Der Turn-Abschluss (waiting/error) wird vollständig in `_after_process_exit`
        # entschieden — der Generic-Pfad darf kein eigenes `closed`/`error` mehr feuern.
        return True

    def _suppress_terminal_error(self, rc: int | None) -> bool:
        # Wir emittieren das terminale Fehler-Event selbst (siehe `_after_process_exit`).
        return True
