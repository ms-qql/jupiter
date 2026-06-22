"""SessionManager — In-Memory-Registry aller laufenden Sessions (PROJ-1).

Im MVP ist die Registry die maßgebliche Quelle für den Live-Zustand (so im
Tech-Design vorgesehen). Persistenz (Postgres-Live-Index + Vault-Transkript via
PROJ-2) wird über das hier offen gehaltene Repository-Seam nachgerüstet.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..config import MVP_ALLOWED_PERMISSION_MODES, VALID_MODELS, settings
from .base import EngineDriver, LaunchSpec
from .claude_driver import ClaudeCodeDriver
from .constitution import combine_with_extra, resolve_constitution
from .events import (
    StreamEvent,
    extract_rate_limit,
    extract_result_text,
    extract_text,
    extract_thinking,
    extract_usage,
    is_error_result,
)

# Session-Zustände (entsprechen den Kanban-Spalten in PROJ-3).
STARTING, RUNNING, WAITING, DONE, ERROR = "starting", "running", "waiting", "done", "error"

DriverFactory = Callable[[], EngineDriver]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate_project_path(path: str) -> str:
    """Prüft, ob ``path` innerhalb der erlaubten Roots liegt und ein Verzeichnis ist.

    Wirft ``ValueError`` (→ 400) bei Verletzung des Projekt-Scopes.
    """
    real = os.path.realpath(path)
    roots = [os.path.realpath(r) for r in settings.allowed_roots]
    if not any(real == r or real.startswith(r + os.sep) for r in roots):
        raise ValueError(
            "Projektpfad liegt außerhalb des erlaubten Bereichs "
            f"({', '.join(settings.allowed_roots)})."
        )
    if not os.path.isdir(real):
        raise ValueError("Projektpfad existiert nicht oder ist kein Verzeichnis.")
    return real


@dataclass
class TranscriptEntry:
    role: str  # "assistant"
    kind: str  # "text" | "thinking"
    text: str
    ts: str


@dataclass
class SessionState:
    session_id: str
    owner: str
    project_path: str
    model: str
    permission_mode: str
    role: str | None = None
    constitution_source: str | None = None
    effective_constitution: str = ""
    status: str = STARTING
    created_at: datetime = field(default_factory=_now)
    last_activity: datetime = field(default_factory=_now)
    tokens_used: int = 0
    context_fill_pct: float = 0.0
    total_cost_usd: float = 0.0
    num_turns: int = 0
    error: str | None = None
    rate_limit: dict | None = None

    def to_read(self) -> dict:
        return {
            "session_id": self.session_id,
            "owner": self.owner,
            "project_path": self.project_path,
            "model": self.model,
            "permission_mode": self.permission_mode,
            "role": self.role,
            "constitution_source": self.constitution_source,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "tokens_used": self.tokens_used,
            "context_fill_pct": self.context_fill_pct,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "num_turns": self.num_turns,
            "error": self.error,
            "rate_limit": self.rate_limit,
        }


class SessionRuntime:
    """Bündelt Zustand + Treiber + Transkript + WebSocket-Abonnenten einer Session."""

    def __init__(self, state: SessionState, driver: EngineDriver) -> None:
        self.state = state
        self.driver = driver
        self.transcript: list[TranscriptEntry] = []
        self._subscribers: set[asyncio.Queue] = set()

    # --- WebSocket-Fan-out -------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _broadcast(self, message: dict) -> None:
        for q in self._subscribers:
            q.put_nowait(message)

    # --- Event-Verarbeitung ------------------------------------------------

    async def handle_event(self, event: StreamEvent) -> None:
        self.state.last_activity = _now()

        if event.type == "system":
            if event.subtype == "init":
                self.state.status = RUNNING
                model = event.raw.get("model")
                if model:
                    self.state.model = model
            elif event.subtype == "error":
                self.state.status = ERROR
                self.state.error = event.raw.get("message")
            elif event.subtype == "closed":
                if self.state.status != ERROR:
                    self.state.status = DONE
            # hook_* / thinking_tokens: kein Zustandswechsel.

        elif event.type == "assistant":
            self.state.status = RUNNING
            thinking = extract_thinking(event)
            if thinking:
                self.transcript.append(
                    TranscriptEntry("assistant", "thinking", thinking, _now().isoformat())
                )
            text = extract_text(event)
            if text:
                self.transcript.append(
                    TranscriptEntry("assistant", "text", text, _now().isoformat())
                )
                self._broadcast({"kind": "message", "role": "assistant", "text": text})
            self._apply_usage(event)

        elif event.type == "result":
            self._apply_usage(event)
            self.state.num_turns = int(event.raw.get("num_turns", self.state.num_turns) or 0)
            if is_error_result(event):
                self.state.status = ERROR
                self.state.error = event.raw.get("api_error_status") or extract_result_text(event)
            else:
                # Turn fertig → wartet auf nächste Eingabe (bzw. done, falls Prozess endet).
                self.state.status = WAITING if self.driver.is_alive else DONE

        elif event.type == "rate_limit_event":
            self.state.rate_limit = extract_rate_limit(event)

        # Nach jedem Event einen Zustands-Snapshot an die UI streamen.
        self._broadcast({"kind": "state", **self.state.to_read()})

    def _apply_usage(self, event: StreamEvent) -> None:
        usage = extract_usage(event)
        if usage is None:
            return
        self.state.context_fill_pct = usage.context_fill_pct
        if event.type == "result":
            self.state.tokens_used += usage.billed_tokens
            if usage.total_cost_usd is not None:
                self.state.total_cost_usd += float(usage.total_cost_usd)


class SessionManager:
    def __init__(self, driver_factory: DriverFactory | None = None) -> None:
        self._driver_factory: DriverFactory = driver_factory or (lambda: ClaudeCodeDriver())
        self._sessions: dict[str, SessionRuntime] = {}

    async def create(
        self,
        *,
        project_path: str,
        initial_prompt: str,
        model: str | None = None,
        permission_mode: str | None = None,
        role: str | None = None,
        extra_system_prompt: str | None = None,
        owner: str | None = None,
    ) -> SessionRuntime:
        model = model or settings.default_model
        permission_mode = permission_mode or settings.default_permission_mode
        if model not in VALID_MODELS:
            raise ValueError(f"Unbekanntes Modell '{model}'. Erlaubt: {sorted(VALID_MODELS)}.")
        if permission_mode not in MVP_ALLOWED_PERMISSION_MODES:
            raise ValueError(
                f"permission_mode '{permission_mode}' ist im MVP nicht erlaubt. "
                f"Erlaubt: {sorted(MVP_ALLOWED_PERMISSION_MODES)} (Safety-Net bis PROJ-4/#19)."
            )
        real_path = validate_project_path(project_path)

        # Knappheits-Konstitution auflösen (#24): global + optionaler Rollen-Override,
        # danach optionaler session-spezifischer Zusatz (kann Konstitution nicht entfernen).
        resolved = resolve_constitution(role, settings.constitution_dir)  # ValueError bei ungültiger Rolle
        effective = combine_with_extra(resolved.text, extra_system_prompt)

        session_id = str(uuid.uuid4())
        state = SessionState(
            session_id=session_id,
            owner=owner or settings.default_owner,
            project_path=real_path,
            model=model,
            permission_mode=permission_mode,
            role=resolved.role,
            constitution_source=resolved.source,
            effective_constitution=effective,
        )
        driver = self._driver_factory()
        runtime = SessionRuntime(state, driver)
        self._sessions[session_id] = runtime

        spec = LaunchSpec(
            session_id=session_id,
            project_path=real_path,
            model=model,
            permission_mode=permission_mode,
            initial_prompt=initial_prompt,
            system_prompt_append=effective,
        )
        try:
            await driver.start(spec, runtime.handle_event)
        except Exception as exc:  # Start fehlgeschlagen → Zustand markieren, Fehler weiterreichen.
            state.status = ERROR
            state.error = str(exc)
            raise
        return runtime

    def get(self, session_id: str) -> SessionRuntime | None:
        return self._sessions.get(session_id)

    def list(self) -> list[SessionRuntime]:
        return list(self._sessions.values())

    async def send_input(self, session_id: str, text: str) -> None:
        runtime = self._require(session_id)
        await runtime.driver.send_input(text)
        runtime.transcript.append(TranscriptEntry("user", "text", text, _now().isoformat()))
        runtime.state.status = RUNNING
        runtime.state.last_activity = _now()

    async def pause(self, session_id: str) -> None:
        await self._require(session_id).driver.pause()

    async def stop(self, session_id: str) -> None:
        await self._require(session_id).driver.stop()

    def transcript_text(self, session_id: str) -> str:
        """Gesamtes Transkript als Klartext (Copy-out)."""
        runtime = self._require(session_id)
        lines = []
        for e in runtime.transcript:
            prefix = {"user": "Du", "assistant": "Claude"}.get(e.role, e.role)
            tag = " (denkt)" if e.kind == "thinking" else ""
            lines.append(f"{prefix}{tag}: {e.text}")
        return "\n\n".join(lines)

    def _require(self, session_id: str) -> SessionRuntime:
        runtime = self._sessions.get(session_id)
        if runtime is None:
            raise KeyError(session_id)
        return runtime
