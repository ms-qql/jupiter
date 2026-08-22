"""HermesChatDriver (PROJ-86) — steuert EINE Hermes-Session über `hermes chat`.

PROJ-86 ersetzt den PROJ-85-One-shot-Vertrag (`-z` + `--usage-file`) durch den
dokumentierten, direkt fortsetzbaren Hermes-Chat-Aufruf:

- Erster Turn:   `hermes chat -q <text> --cli -Q -m <modell> --provider <p> --in <dir> --yolo --pass-session-id`
- Folge-Turn:    dieselbe Zeile, ergänzt um `--resume <hermes_conversation_id>`

Hermes liefert die Conversation-ID als **eine einzelne stdout-Kontrollzeile**
`session_id: <opaque-id>` (nie `--usage-file` — das existiert beim `chat`-
Subcommand laut `hermes chat --help` nicht). Diese Zeile wird VOR dem plaintext-
Adapter abgefangen, nie als Assistant-Text gezeigt und (exakt eine pro Turn)
persistiert. Fehlt sie, ist sie mehrdeutig oder lehnt Hermes den Resume ab →
sichtbarer deutscher Fehler, KEIN stiller neuer Chat (ADR-86-4/86-6).

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

# Eine vollständige Kontrollzeile: optionale Leerzeichen, ein nichtleerer Wert
# OHNE Leerzeichen (eine echte opaque Hermes-ID enthält keine). Alles andere
# (null, keine oder mehrere passende Zeilen) ist ungültig.
_CONTROL_LINE = re.compile(r"^\s*session_id:\s*(\S+)\s*$")


class HermesChatDriver(GenericCliDriver):
    """Treiber für die Hermes-CLI im direkten Chat-Modus (PROJ-86)."""

    def __init__(self, profile, *, provider: str, model: str) -> None:
        super().__init__(profile)
        self._provider = provider
        self._hermes_model = model
        # Opaque, von Hermes ausgegebene Conversation-ID (aus der stdout-Kontrollzeile).
        self._resume_ref: str | None = None
        # Während eines Turns gesammelte Kontrollzeilen (exakt eine = gültig).
        self._control_lines: list[str] = []

    @property
    def resume_id(self) -> str | None:
        # Der Manager persistiert das als `hermes_resume_ref`.
        return self._resume_ref

    @property
    def supports_self_resume(self) -> bool:
        # Hermes setzt den Folge-Turn selbst fort (Resume über `--resume <ref>`).
        # `True` verhindert zusätzlich, dass der Manager den generischen
        # `claude --resume`-Pfad auslöst (PROJ-86: Hermes wird NICHT reanimiert).
        return True

    def _build_argv(self, spec: LaunchSpec, *, resume: bool = False) -> list[str]:
        cli = self.profile.bin or "hermes"
        argv = [
            cli, "chat", "-q", spec.initial_prompt or "",
            "--cli", "-Q",
            "-m", self._hermes_model,
            "--provider", self._provider,
            "--in", spec.project_path,
            "--yolo", "--pass-session-id",
        ]
        if resume and self._resume_ref:
            argv += ["--resume", self._resume_ref]
        return argv

    async def _spawn(self, argv: list[str], cwd: str, *, prompt: str | None = None) -> None:
        self._control_lines = []
        await super()._spawn(argv, cwd, prompt=prompt)

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:  # type: ignore[valid-type]
        self._on = on_event
        self._spec = spec
        # ADR-86-3: Hermes IMMER direct (kein tmux, keine Pane-Liveness).
        self._transport_mode = "direct"
        self._control_lines = []
        # Resume nach Treiber-Neubau (Restart): bekannte Ref → kein Frischstart.
        if spec.resume and spec.resume_id:
            self._resume_ref = spec.resume_id
            return
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
        # Direkter Chat-Turn beendet → Folge-Turn als frischer Prozess mit Resume-Ref.
        if self._spec is not None:
            if self._resume_ref is None:
                raise RuntimeError("Fortsetzen nicht möglich: keine Resume-ID der Engine empfangen.")
            spec = self._spec_with_prompt(text)
            await self._spawn(self._build_argv(spec, resume=True), spec.project_path, prompt=None)
            return
        raise RuntimeError("Session läuft nicht.")

    # --- stdout-Kontrollzeile + Turn-Abschluss ---------------------------------

    def _intercept_line(self, line: str) -> bool:
        """`session_id: <id>` aus stdout fischen — nicht als Chat-Text zeigen."""
        m = _CONTROL_LINE.match(line)
        if m:
            self._control_lines.append(m.group(1))
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
        """Nach dem echten Prozessende die Kontrollzeile auswerten (ADR-86-6).

        - Genau eine Kontrollzeile → ID übernehmen, Turn als `waiting` abschließen.
        - Keine/mehrere → sichtbarer Fehler, KEIN scheinbar erfolgreicher Wartezustand.
        - Resume abgelehnt (rc != 0, keine ID) → deutscher Fehler + Hermes-Ursache
          aus stderr (kein stiller Fallback auf einen frischen Chat).
        """
        if len(self._control_lines) == 1:
            self._resume_ref = self._control_lines[0]
            await self._emit(StreamEvent("system", "waiting", {"reason": "turn_complete"}))
            return
        if len(self._control_lines) == 0:
            msg = "Hermes lieferte keine fortsetzbare Conversation-ID (session_id) zurück."
            if rc not in (0, None):
                stderr = "".join(self._stderr_buf).strip()
                if stderr:
                    msg = f"Hermes-Fortsetzung fehlgeschlagen: {stderr}"
        else:
            msg = (
                "Hermes lieferte mehrdeutige Conversation-IDs zurück — Fortsetzung "
                "abgelehnt (kein stiller neuer Chat)."
            )
        await self._emit(StreamEvent("system", "error", {"message": msg}))

    def _turn_completed_normally(self) -> bool:
        # Der Turn-Abschluss (waiting/error) wird vollständig in `_after_process_exit`
        # entschieden — der Generic-Pfad darf kein eigenes `closed`/`error` mehr feuern.
        return True

    def _suppress_terminal_error(self, rc: int | None) -> bool:
        # Wir emittieren das terminale Fehler-Event selbst (siehe `_after_process_exit`).
        return True
