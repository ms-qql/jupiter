"""Treiber-Abstraktion (EngineDriver).

Nach oben sehen alle Engines gleich aus (#6); darunter steckt ein austauschbarer
Treiber. PROJ-1 liefert den ClaudeCodeDriver; weitere (Codex/Gemini/GLM/Ollama, #13)
implementieren später dieselbe Schnittstelle.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .events import StreamEvent

# Callback, das der Manager dem Treiber übergibt; der Treiber ruft es je Event.
EventHandler = Callable[[StreamEvent], Awaitable[None]]


@dataclass
class LaunchSpec:
    """Alle Parameter, um eine Session zu starten."""

    session_id: str
    project_path: str
    model: str
    permission_mode: str
    initial_prompt: str
    # Hook für die Knappheits-Konstitution (#24, PROJ-6) — heute meist None.
    system_prompt_append: str | None = None
    # Fortsetzen einer bereits beendeten Session: statt `--session-id` (neu anlegen)
    # wird `--resume <session_id>` genutzt — Claude Code lädt die Konversation.
    resume: bool = False
    # Session-skopierte Settings-JSON (PROJ-4): registriert den PreToolUse-Freigabe-Hook.
    # Wird via `--settings` durchgereicht; None = ohne Decision Cards (z. B. in Tests).
    settings_json: str | None = None


class EngineDriver(ABC):
    """Steuert genau EINE Session (ein Subprozess / eine Engine-Instanz)."""

    @abstractmethod
    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        """Startet die Session. Events werden via ``on_event`` nach oben gereicht."""

    @abstractmethod
    async def send_input(self, text: str) -> None:
        """Sendet eine weitere Eingabe (multi-turn / Paste-in)."""

    @abstractmethod
    async def pause(self) -> None:
        """Pausiert: nimmt keine neuen Eingaben mehr an."""

    @abstractmethod
    async def stop(self) -> None:
        """Beendet die Session sauber (kein Zombie-Prozess)."""

    @property
    @abstractmethod
    def is_alive(self) -> bool:
        ...
