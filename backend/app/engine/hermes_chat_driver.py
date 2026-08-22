"""HermesChatDriver (PROJ-85) — steuert EINE Hermes-Session über die Hermes-CLI.

Wiederverwendet die ``GenericCliDriver``-Grundlage (Process-Handling, Reader,
alive-Prüfung), überschreibt aber das argv-Building auf den Hermes-eigenen
Vertrag und fängt die strukturierte Usage + Resume-Referenz aus der
``--usage-file`` (eine JSON-Datei, die Hermes nach jedem One-Shot-Turn schreibt).

Hermes-CLI-Vertrag (real verifiziert via ``hermes --help``):
- ``-z <prompt>``      One-Shot-Prompt (startet SOFORT, kein REPL).
- ``-m <model>``       Modell.
- ``--provider <p>``    Provider-Override (z. B. ``anthropic``).
- ``--cli``             klassischer (nicht-TUI-)REPL/Output → Klartext-Stream.
- ``--yolo``            Gefahren-Prompts umgehen (Bypass, fester Wert des Dialogs).
- ``--in <dir>``        Arbeitsverzeichnis.
- ``--usage-file <p>``  Nach dem Lauf: JSON-Usage (One-Shot-Mode only).
- ``--pass-session-id`` Session-ID in den System-Prompt aufnehmen.
- ``--resume <ref>``    Fortsetzen einer Hermes-Session (Ref aus der Usage-Datei).

Hermes liefert KEINEN Stream-JSON-Usage → der ``plaintext``-Adapter übersetzt die
Klartext-Ausgabe in assistant-Text; die Kontext-Usage kommt ausschließlich aus der
``--usage-file`` (sauber getrennt, keine erfundenen Zahlen — ADR-85-3).
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile

from .base import LaunchSpec, pid_alive
from .generic_cli_driver import GenericCliDriver
from .events import StreamEvent
from .transport import TransportError

# Felder, unter denen die Hermes-Usage-Datei Kontextverbrauch/Referenz ablegen kann
# (defensiv, mehrere Namen — Hermes-Versionen variieren).
_USAGE_WINDOW_KEYS = ("context_window", "contextWindow", "window_tokens", "max_context")
_USAGE_USED_KEYS = ("context_used", "contextUsed", "used_tokens", "used_context")
_USAGE_REF_KEYS = ("session_id", "sessionId", "id", "resume_ref", "resumeRef")


class HermesChatDriver(GenericCliDriver):
    """Treiber für die Hermes-CLI (PROJ-85)."""

    def __init__(self, profile, *, provider: str, model: str) -> None:
        super().__init__(profile)
        self._provider = provider
        self._hermes_model = model
        # Jeder Turn schreibt in eine eigene Usage-Datei (Pfad bleibt über Turns stabil).
        self._usage_file = os.path.join(
            tempfile.gettempdir(), f"hermes_usage_{os.getpid()}_{id(self)}.json"
        )
        # Hermes-Referenz für Resume (opaque, aus der Usage-Datei).
        self._resume_ref: str | None = None

    @property
    def resume_id(self) -> str | None:
        # Der Manager persistiert das als `hermes_resume_ref`.
        return self._resume_ref

    @property
    def supports_self_resume(self) -> bool:
        # Hermes kann über `--resume <ref>` fortsetzen — sobald eine Ref vorliegt,
        # übernimmt der Manager den self-resume-Zweig (persistierte Ref).
        return self._resume_ref is not None or self.profile.resume_argv_template != []

    def _build_argv(self, spec: LaunchSpec, *, resume: bool = False) -> list[str]:
        cli = self.profile.bin or "hermes"
        argv = [cli, "-z", spec.initial_prompt or "", "-m", self._hermes_model,
                "--provider", self._provider, "--cli", "--yolo",
                "--in", spec.project_path, "--usage-file", self._usage_file,
                "--pass-session-id"]
        if resume and self._resume_ref:
            argv += ["--resume", self._resume_ref]
        return argv

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:  # type: ignore[valid-type]
        self._on = on_event
        self._spec = spec
        self._transport_mode = "tmux" if spec.transport == "tmux" else "direct"
        # Resume nach Treiber-Neubau (Restart): bekannte Ref → kein Frischstart.
        if spec.resume and spec.resume_id:
            self._resume_ref = spec.resume_id
            return
        await self._emit(StreamEvent("system", "init",
                                     {"session_id": spec.session_id, "model": self._hermes_model}))
        prompt = spec.initial_prompt
        if not prompt or not prompt.strip():
            # Freier Chat ohne Initial-Prompt: auf erste Nutzereingabe warten.
            self._awaiting_first_input = True
            await self._emit(StreamEvent("system", "waiting", {"reason": "initial_prompt_empty"}))
            return
        await self._spawn(self._build_argv(spec), spec.project_path, prompt=None)

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert — keine Eingaben möglich.")
        if self._awaiting_first_input and self._spec is not None:
            self._awaiting_first_input = False
            spec = LaunchSpec(
                session_id=self._spec.session_id,
                project_path=self._spec.project_path,
                model=self._spec.model,
                permission_mode=self._spec.permission_mode,
                initial_prompt=text,
                transport=self._spec.transport,
            )
            self._spec = spec
            await self._spawn(self._build_argv(spec), spec.project_path, prompt=None)
            return
        if self.is_alive:
            raise RuntimeError("Antwort läuft noch — bitte warten, bis der aktuelle Turn abgeschlossen ist.")
        # One-Shot-Turn beendet → Folge-Turn als frischer Prozess mit Resume-Ref.
        if self._spec is not None:
            if self._resume_ref is None:
                raise RuntimeError("Fortsetzen nicht möglich: keine Resume-Referenz der Engine empfangen.")
            spec = LaunchSpec(
                session_id=self._spec.session_id,
                project_path=self._spec.project_path,
                model=self._spec.model,
                permission_mode=self._spec.permission_mode,
                initial_prompt=text,
                transport=self._spec.transport,
            )
            await self._spawn(self._build_argv(spec, resume=True), spec.project_path, prompt=None)
            return
        raise RuntimeError("Session läuft nicht.")

    async def _after_process_exit(self, rc: int | None) -> None:
        # Läuft NACH dem echten Prozessende (Hook der Basisklasse) — genau dann hat
        # Hermes die Usage-Datei fertig geschrieben. Ein früherer Versuch rief
        # _after_turn() beim Start des Readers auf (vor jeder Ausgabe) statt hier —
        # die Datei existierte da nie, jeder Turn wurde fälschlich als abgebrochen
        # gemeldet ("Prozess wurde beendet, ohne den Turn regulär abzuschließen").
        await self._after_turn()

    def _turn_completed_normally(self) -> bool:
        # Hermes' plaintext-Adapter emittiert nie ein "result"-Event (siehe
        # adapters.py) — _saw_final_result der Basisklasse bleibt daher immer False.
        # Das eigentliche Signal für ein sauberes Turn-Ende ist die Resume-Ref aus
        # der Usage-Datei (von _after_process_exit oben gerade gesetzt).
        return self._resume_ref is not None

    async def _after_turn(self) -> None:
        """Usage-Datei lesen: Resume-Ref + Kontext-Usage extrahieren und emittieren."""
        usage = self._read_usage_file()
        if usage is None:
            return
        ref = self._first_str(usage, _USAGE_REF_KEYS)
        if ref:
            self._resume_ref = str(ref)
        used = self._first_int(usage, _USAGE_USED_KEYS)
        window = self._first_int(usage, _USAGE_WINDOW_KEYS)
        if used is not None or window is not None:
            await self._emit(StreamEvent("system", "usage", {
                "used_tokens": used,
                "window_tokens": window,
            }))

    def _read_usage_file(self) -> dict | None:
        try:
            with open(self._usage_file, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _first_str(obj: dict, keys: tuple[str, ...]) -> str | None:
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v
        return None

    @staticmethod
    def _first_int(obj: dict, keys: tuple[str, ...]) -> int | None:
        for k in keys:
            v = obj.get(k)
            try:
                if v is not None:
                    return int(v)
            except (TypeError, ValueError):
                continue
        return None
