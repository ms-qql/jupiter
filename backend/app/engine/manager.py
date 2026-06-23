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
from . import policy
from .base import EngineDriver, LaunchSpec
from .claude_driver import ClaudeCodeDriver
from .constitution import combine_with_extra, resolve_constitution
from .decisions import OBSOLETE, OPEN, RESOLVED, DecisionOutcome, PendingDecision
from .events import (
    StreamEvent,
    extract_rate_limit,
    extract_result_text,
    extract_text,
    extract_thinking,
    extract_usage,
    is_error_result,
)
from .hooks import build_hook_settings

# Session-Zustände (entsprechen den Kanban-Spalten in PROJ-3).
# AWAITING_APPROVAL (PROJ-4) → Kanban-Spalte „Review/Approval".
STARTING, RUNNING, WAITING, DONE, ERROR = "starting", "running", "waiting", "done", "error"
AWAITING_APPROVAL = "awaiting_approval"

DriverFactory = Callable[[], EngineDriver]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _model_alias(model: str) -> str:
    """Mappt eine ggf. aufgelöste Modell-ID (z. B. ``claude-haiku-4-5-…``) zurück
    auf den kurzen, garantiert von ``--model`` akzeptierten Alias."""
    m = model.lower()
    for alias in ("haiku", "sonnet", "opus"):
        if alias in m:
            return alias
    return model


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

    def __init__(
        self,
        state: SessionState,
        driver: EngineDriver,
        on_done: Callable[["SessionRuntime"], None] | None = None,
    ) -> None:
        self.state = state
        self.driver = driver
        self.transcript: list[TranscriptEntry] = []
        self._subscribers: set[asyncio.Queue] = set()
        # Hook: wird genau EINMAL gefeuert, wenn die Session DONE erreicht (PROJ-2-Autolog).
        self.on_done = on_done
        self._done_fired = False
        # PROJ-4 — offene Decision Cards (key = decision_id = tool_use_id) + die Futures,
        # auf die der wartende Hook-Aufruf blockiert. „Warum" = letzter Assistenten-Text.
        self.pending: dict[str, PendingDecision] = {}
        self._futures: dict[str, asyncio.Future] = {}
        self._last_assistant_text: str = ""

    def to_read(self) -> dict:
        """Lese-Snapshot inkl. offener Decision Cards (für REST-Liste + WS-Broadcast)."""
        data = self.state.to_read()
        data["pending_decisions"] = [c.to_read() for c in self.pending.values()]
        return data

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
            # „Warum" der nächsten Decision Card: jüngste Assistenten-Äußerung —
            # bevorzugt der Text, sonst der Denk-Block (oft folgt direkt der Tool-Aufruf).
            reasoning = text or thinking
            if reasoning:
                self._last_assistant_text = reasoning
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

        # Stirbt/endet die Session, sind offene Cards hinfällig (Edge-Case: „obsolet").
        if self.state.status in (DONE, ERROR) and self.pending:
            self.abandon_decisions()

        # Nach jedem Event einen Zustands-Snapshot an die UI streamen.
        self._broadcast({"kind": "state", **self.to_read()})

        # Beim Übergang nach DONE genau einmal das Roh-Log in den Vault schreiben (PROJ-2).
        if self.state.status == DONE and not self._done_fired:
            self._done_fired = True
            if self.on_done is not None:
                self.on_done(self)

    def _apply_usage(self, event: StreamEvent) -> None:
        usage = extract_usage(event)
        if usage is None:
            return
        self.state.context_fill_pct = usage.context_fill_pct
        if event.type == "result":
            self.state.tokens_used += usage.billed_tokens
            if usage.total_cost_usd is not None:
                self.state.total_cost_usd += float(usage.total_cost_usd)

    # --- Decision Cards / Freigabe (PROJ-4) --------------------------------

    async def request_decision(
        self, decision_id: str, tool_name: str, tool_input: dict | None
    ) -> DecisionOutcome:
        """Vom Freigabe-Hook aufgerufen, bevor ein Tool läuft.

        Lesezugriffe (``policy.requires_card`` = False) → sofortiges ``allow`` ohne Card.
        Sonst: Card anlegen, Status auf ``awaiting_approval``, und **blockieren**, bis der
        Nutzer entscheidet (``resolve_decision``) oder die Session stirbt (``abandon``).
        """
        if not policy.requires_card(tool_name, tool_input):
            return DecisionOutcome(behavior="allow", auto=True)

        card = PendingDecision(
            decision_id=decision_id,
            session_id=self.state.session_id,
            tool_name=tool_name,
            action=policy.summarize_action(tool_name, tool_input),
            excerpt=policy.extract_excerpt(tool_name, tool_input),
            rationale=policy.clip_rationale(self._last_assistant_text),
            context={
                "project_path": self.state.project_path,
                "role": self.state.role,
                "phase": self.state.constitution_source,
            },
            created_at=_now().isoformat(),
        )
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[decision_id] = card
        self._futures[decision_id] = fut
        self.state.status = AWAITING_APPROVAL
        self.state.last_activity = _now()
        self._broadcast({"kind": "decision", "event": "opened", "decision": card.to_read()})
        self._broadcast({"kind": "state", **self.to_read()})
        return await fut

    def resolve_decision(
        self, decision_id: str, approve: bool, comment: str | None = None
    ) -> PendingDecision:
        """Entscheidung des Nutzers einspielen → entsperrt den wartenden Hook-Aufruf.

        ``approve``  → ``allow`` (Claude führt die Aktion aus).
        nicht approve → ``deny``; ``comment`` reist als Begründung **inline** zu Claude
        zurück („Mit Kommentar zurück" = natives Deny mit Begründung).
        """
        card = self.pending.get(decision_id)
        fut = self._futures.get(decision_id)
        if card is None or fut is None:
            raise KeyError(decision_id)
        if card.state != OPEN or fut.done():
            raise ValueError("Diese Entscheidung wurde bereits getroffen.")

        if approve:
            card.resolution = "approve"
            outcome = DecisionOutcome(behavior="allow")
        else:
            card.resolution = "deny"
            reason = (comment or "").strip() or "Vom Nutzer abgelehnt."
            outcome = DecisionOutcome(behavior="deny", reason=reason)
        card.state = RESOLVED
        fut.set_result(outcome)
        self.pending.pop(decision_id, None)
        self._futures.pop(decision_id, None)
        # Keine offene Card mehr → Session läuft weiter (Claude verarbeitet das Resultat).
        if not self.pending and self.state.status == AWAITING_APPROVAL:
            self.state.status = RUNNING
        self.state.last_activity = _now()
        self._broadcast({"kind": "decision", "event": "resolved", "decision": card.to_read()})
        self._broadcast({"kind": "state", **self.to_read()})
        return card

    def abandon_decisions(
        self, reason: str = "Session beendet — Freigabe hinfällig."
    ) -> None:
        """Alle offenen Cards als ``obsolet`` markieren und ihre Futures als ``deny`` auflösen.

        Aufruf, wenn die Session stirbt/gestoppt wird, damit kein Hook-Aufruf ewig hängt.
        """
        for decision_id, card in list(self.pending.items()):
            fut = self._futures.get(decision_id)
            card.state = OBSOLETE
            if fut is not None and not fut.done():
                fut.set_result(DecisionOutcome(behavior="deny", reason=reason))
            self._broadcast({"kind": "decision", "event": "obsolete", "decision": card.to_read()})
        self.pending.clear()
        self._futures.clear()


class SessionManager:
    def __init__(self, driver_factory: DriverFactory | None = None, vault=None) -> None:
        self._driver_factory: DriverFactory = driver_factory or (lambda: ClaudeCodeDriver())
        self._sessions: dict[str, SessionRuntime] = {}
        # Optionaler VaultService (PROJ-2): rohe Session-Logs am Ende persistieren.
        self._vault = vault

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
        runtime = SessionRuntime(state, driver, on_done=self._write_session_log)
        self._sessions[session_id] = runtime

        spec = LaunchSpec(
            session_id=session_id,
            project_path=real_path,
            model=model,
            permission_mode=permission_mode,
            initial_prompt=initial_prompt,
            system_prompt_append=effective,
            settings_json=self._hook_settings(),
        )
        try:
            await driver.start(spec, runtime.handle_event)
        except Exception as exc:  # Start fehlgeschlagen → Zustand markieren, Fehler weiterreichen.
            state.status = ERROR
            state.error = str(exc)
            raise
        return runtime

    def _hook_settings(self) -> str | None:
        """Session-skopierte ``--settings``-JSON für den Freigabe-Hook (PROJ-4).

        ``None`` (Cards deaktiviert) → Session startet ohne Hook, wie vor PROJ-4.
        """
        if not settings.enable_decision_cards:
            return None
        return build_hook_settings(
            self_url=settings.hook_self_url,
            token=settings.hook_token,
            timeout_seconds=settings.hook_timeout_seconds,
        )

    def get(self, session_id: str) -> SessionRuntime | None:
        return self._sessions.get(session_id)

    def list(self) -> list[SessionRuntime]:
        return list(self._sessions.values())

    async def send_input(self, session_id: str, text: str) -> None:
        runtime = self._require(session_id)
        # Beendete Session (Prozess ist weg) → vor der Eingabe per `claude --resume`
        # fortsetzen, damit der User auch an fertigen Sessions weiterarbeiten kann.
        if not runtime.driver.is_alive:
            await self._resume(runtime)
        await runtime.driver.send_input(text)
        runtime.transcript.append(TranscriptEntry("user", "text", text, _now().isoformat()))
        runtime.state.status = RUNNING
        runtime.state.last_activity = _now()

    async def resume(self, session_id: str) -> None:
        """Setzt eine beendete Session fort (ohne sofortige Eingabe)."""
        runtime = self._require(session_id)
        if not runtime.driver.is_alive:
            await self._resume(runtime)

    async def _resume(self, runtime: SessionRuntime) -> None:
        """Frischer Treiber mit `claude --resume` — lädt die bestehende Konversation.

        Der alte Subprozess ist beendet; ein neuer übernimmt dieselbe Session-ID
        und denselben Konstitutions-Kontext. Eingaben folgen via ``send_input``.
        """
        state = runtime.state
        driver = self._driver_factory()
        runtime.driver = driver
        runtime._done_fired = False  # erlaubt erneutes Vault-Log beim nächsten DONE
        spec = LaunchSpec(
            session_id=state.session_id,
            project_path=state.project_path,
            model=_model_alias(state.model),
            permission_mode=state.permission_mode,
            initial_prompt="",  # Eingabe kommt direkt danach via send_input
            system_prompt_append=state.effective_constitution,
            resume=True,
            settings_json=self._hook_settings(),
        )
        try:
            await driver.start(spec, runtime.handle_event)
        except Exception as exc:  # Resume fehlgeschlagen → Zustand markieren, weiterreichen.
            state.status = ERROR
            state.error = f"Fortsetzen fehlgeschlagen: {exc}"
            raise
        state.status = RUNNING
        state.error = None
        state.last_activity = _now()

    async def pause(self, session_id: str) -> None:
        await self._require(session_id).driver.pause()

    async def stop(self, session_id: str) -> None:
        runtime = self._require(session_id)
        await runtime.driver.stop()
        # Sicherheitsnetz: offene Cards auflösen (der closed-Event tut das i. d. R. schon).
        runtime.abandon_decisions("Session gestoppt — Freigabe hinfällig.")

    # --- Decision Cards / Freigabe (PROJ-4) --------------------------------

    async def request_decision(
        self, session_id: str, decision_id: str, tool_name: str, tool_input: dict | None
    ) -> DecisionOutcome:
        """Freigabe-Anfrage des Hooks → blockiert bis zur Entscheidung."""
        return await self._require(session_id).request_decision(
            decision_id, tool_name, tool_input
        )

    def resolve_decision(
        self, session_id: str, decision_id: str, approve: bool, comment: str | None = None
    ) -> PendingDecision:
        """Nutzer-Entscheidung einspielen (Freigeben/Ablehnen/Mit Kommentar zurück)."""
        return self._require(session_id).resolve_decision(decision_id, approve, comment)

    def transcript_text(self, session_id: str) -> str:
        """Gesamtes Transkript als Klartext (Copy-out)."""
        runtime = self._require(session_id)
        lines = []
        for e in runtime.transcript:
            prefix = {"user": "Du", "assistant": "Claude"}.get(e.role, e.role)
            tag = " (denkt)" if e.kind == "thinking" else ""
            lines.append(f"{prefix}{tag}: {e.text}")
        return "\n\n".join(lines)

    @staticmethod
    def _transcript_md(runtime: SessionRuntime) -> str:
        """Transkript als Obsidian-MD (Überschriften je Sprecher-Block)."""
        blocks = []
        for e in runtime.transcript:
            who = {"user": "Du", "assistant": "Claude"}.get(e.role, e.role)
            tag = " (denkt)" if e.kind == "thinking" else ""
            blocks.append(f"## {who}{tag}\n\n{e.text}")
        return "\n\n".join(blocks) + "\n"

    def _write_session_log(self, runtime: SessionRuntime) -> None:
        """Auto-Hook (Session → DONE): rohes Log in den Vault schreiben (PROJ-2).

        Fehler dürfen die Session NICHT abbrechen (Edge-Case: Vault nicht erreichbar).
        """
        if self._vault is None or not settings.vault_autolog:
            return
        try:
            self._vault.write_session_log(runtime.state, self._transcript_md(runtime))
        except Exception:  # noqa: BLE001 — Vault-Fehler bewusst schlucken (Session läuft weiter)
            pass

    def _require(self, session_id: str) -> SessionRuntime:
        runtime = self._sessions.get(session_id)
        if runtime is None:
            raise KeyError(session_id)
        return runtime
