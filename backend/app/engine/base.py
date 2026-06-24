"""Treiber-Abstraktion (EngineDriver).

Nach oben sehen alle Engines gleich aus (#6); darunter steckt ein austauschbarer
Treiber. PROJ-1 liefert den ClaudeCodeDriver; weitere (Codex/Gemini/GLM/Ollama, #13)
implementieren später dieselbe Schnittstelle.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .events import StreamEvent

# Callback, das der Manager dem Treiber übergibt; der Treiber ruft es je Event.
EventHandler = Callable[[StreamEvent], Awaitable[None]]


def pid_alive(pid: int | None) -> bool:
    """PROJ-33: Existiert der OS-Prozess noch? (Signal 0, best-effort.)

    Härtet die ``is_alive``-Prüfung der Subprozess-Treiber: asyncios ``returncode``
    kann veralten, wenn der Prozess starb, ohne dass der Event-Loop ihn reapte
    (beobachteter Geister-„aktiv"-Zustand). Ein nicht (mehr) existierender PID gilt
    als tot. Identische Semantik wie ``SessionManager._pid_alive`` (eine Quelle der
    Lebendigkeits-Logik).
    """
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # existiert, gehört aber anderem User → lebt
        return True
    except (OSError, ValueError):  # im Zweifel als lebend werten (kein Fehlalarm „tot")
        return True
    return True


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

    @property
    def pid(self) -> int | None:
        """OS-PID des Subprozesses (PROJ-14 Persistenz/Verwaist-Check).

        Default ``None`` — Treiber ohne echten Prozess (z. B. Fakes, ein
        rehydrierter Platzhalter nach Restart) müssen das nicht überschreiben.
        """
        return None


class DeadDriver(EngineDriver):
    """Platzhalter-Treiber ohne Prozess (PROJ-14).

    Wird beim Startup für aus dem Live-Index **rehydrierte** Sessions gesetzt:
    der ursprüngliche Subprozess hat den Backend-Neustart nicht steuerbar
    überlebt. ``is_alive`` ist ``False`` → eine Eingabe löst regulär den
    ``claude --resume``-Pfad aus, der einen frischen Treiber einsetzt.
    """

    def __init__(self, pid: int | None = None) -> None:
        # PROJ-21: die persistierte OS-PID überlebt den Restart hier, damit ein
        # verwaister, evtl. noch lebender Prozess beim Löschen beendet werden kann.
        self._pid = pid

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:  # pragma: no cover - nie aufgerufen
        raise RuntimeError("DeadDriver kann nicht gestartet werden (rehydrierter Platzhalter).")

    async def send_input(self, text: str) -> None:  # pragma: no cover - durch _resume ersetzt
        raise RuntimeError("Session ist verwaist — bitte fortsetzen (resume), dann eingeben.")

    async def pause(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    @property
    def is_alive(self) -> bool:
        return False

    @property
    def pid(self) -> int | None:
        return self._pid
