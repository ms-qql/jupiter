"""SessionManager — In-Memory-Registry aller laufenden Sessions (PROJ-1).

Im MVP ist die Registry die maßgebliche Quelle für den Live-Zustand (so im
Tech-Design vorgesehen). Persistenz (Postgres-Live-Index + Vault-Transkript via
PROJ-2) wird über das hier offen gehaltene Repository-Seam nachgerüstet.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..config import (
    MVP_ALLOWED_PERMISSION_MODES,
    VALID_MODELS,
    clamp_session_limit,
    clamp_threshold,
    settings,
)
from ..db import NullSessionIndexRepository, SessionIndexRepository
from . import abc_phases, curation, policy, watchdog
from .base import DeadDriver, EngineDriver, LaunchSpec
from .claude_driver import ClaudeCodeDriver
from .constitution import combine_with_extra, resolve_constitution
from .decisions import OBSOLETE, OPEN, RESOLVED, DecisionOutcome, PendingDecision
from .handover import build_handover_md, build_title
from .events import (
    DEFAULT_CONTEXT_WINDOW,
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

# PROJ-14: nur diese Zustände zählen gegen das Limit paralleler Sessions
# (done/error sind terminal und blockieren keine Slots).
ACTIVE_STATES: frozenset[str] = frozenset({STARTING, RUNNING, WAITING, AWAITING_APPROVAL})

DriverFactory = Callable[[], EngineDriver]

logger = logging.getLogger(__name__)


class SessionLimitError(RuntimeError):
    """PROJ-14: Erstellung abgelehnt, weil das Limit aktiver Sessions erreicht ist.

    Die Route übersetzt das in HTTP 429 mit deutscher Meldung.
    """


class SessionActiveError(RuntimeError):
    """PROJ-21: Löschen abgelehnt, weil die Session noch aktiv ist (nicht terminal).

    Die Route übersetzt das in HTTP 409 mit deutscher Meldung.
    """

# Default-Auftakt der Reset-Kind-Session, wenn der Nutzer keinen eigenen Prompt gibt.
# Der verdichtete Handover liegt als System-Kontext (Seed) bereits an.
_DEFAULT_RESET_PROMPT = (
    "Du übernimmst eine laufende Arbeit per Handover (siehe System-Kontext). "
    "Mach dich kurz damit vertraut und arbeite an den offenen Punkten weiter."
)


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
    # PROJ-5 — Kontext-Management & Handover.
    parent_session_id: str | None = None  # Reset-Kind-Session → Vorgänger (Staffelstab).
    child_session_id: str | None = None  # Vorgänger → Reset-Nachfolger (1 Strang = 1 Nachfolger).
    context_known: bool = False  # Treiber-Daten da? sonst Gauge „unbekannt" statt 0 %.
    context_threshold_override_pct: int | None = None  # pro-Session-Schwelle (None → global).
    threshold_warned: bool = False  # one-shot Auto-Vorschlag bei Schwellenüberschreitung.
    # PROJ-8 — ABC-Workflow-Gantt: sprechendes Label + dynamisch erkannte Phase/Feature.
    project_name: str | None = None  # Gantt-Zeilen-Label (Fallback: Basename von project_path).
    abc_phase: str | None = None  # AKTUELLE Phase (hervorgehoben). None = „keine Phase".
    abc_phase_reached: str | None = None  # WEITESTE bisher erreichte Phase (Bar-Füllung).
    abc_feature: str | None = None  # Feature-Referenz, z. B. „8" (aus Skill-Arg/berührtem Spec).
    # PROJ-10: zuletzt aufgerufener Skill (für Skill-Kontext der Trust-Policy).
    current_skill: str | None = None
    # PROJ-17: aus der Recovery-Ansicht verworfen (kein Recovery-Kandidat mehr).
    # Der Vault-Eintrag/das Log bleibt unberührt — nur die Sicht blendet ihn aus.
    recovery_dismissed: bool = False

    @property
    def effective_threshold_pct(self) -> int:
        """Wirksame Kontext-Schwelle: Session-Override oder globaler Wert, geklemmt."""
        base = self.context_threshold_override_pct
        if base is None:
            base = settings.context_fill_threshold_pct
        return clamp_threshold(base)

    @property
    def threshold_warning(self) -> bool:
        """True, sobald der (bekannte) Füllstand die wirksame Schwelle erreicht."""
        return self.context_known and self.context_fill_pct >= self.effective_threshold_pct

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
            "context_known": self.context_known,
            "context_fill_threshold_pct": self.effective_threshold_pct,
            "threshold_warning": self.threshold_warning,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "num_turns": self.num_turns,
            "error": self.error,
            "rate_limit": self.rate_limit,
            "parent_session_id": self.parent_session_id,
            "child_session_id": self.child_session_id,
            "project_name": self.project_name,
            "abc_phase": self.abc_phase,
            "abc_phase_reached": self.abc_phase_reached,
            "abc_feature": self.abc_feature,
        }


class SessionRuntime:
    """Bündelt Zustand + Treiber + Transkript + WebSocket-Abonnenten einer Session."""

    def __init__(
        self,
        state: SessionState,
        driver: EngineDriver,
        on_done: Callable[["SessionRuntime"], None] | None = None,
        on_persist: Callable[["SessionRuntime"], None] | None = None,
    ) -> None:
        self.state = state
        self.driver = driver
        self.transcript: list[TranscriptEntry] = []
        self._subscribers: set[asyncio.Queue] = set()
        # Hook: wird genau EINMAL gefeuert, wenn die Session DONE erreicht (PROJ-2-Autolog).
        self.on_done = on_done
        self._done_fired = False
        # PROJ-14: Persistenz-Hook (best-effort), gefeuert bei Zustandswechseln.
        self.on_persist = on_persist
        self._last_persisted_status: str | None = None
        # PROJ-4 — offene Decision Cards (key = decision_id = tool_use_id) + die Futures,
        # auf die der wartende Hook-Aufruf blockiert. „Warum" = letzter Assistenten-Text.
        self.pending: dict[str, PendingDecision] = {}
        self._futures: dict[str, asyncio.Future] = {}
        self._last_assistant_text: str = ""
        # PROJ-15: bereits vorgeschlagene Marker-Arten dieser Session (Entprellung —
        # je Marker-Art max. ein Wissens-Vorschlag pro Session, keine Card-Flut).
        self._seen_markers: set[str] = set()
        # Kontext-Füllstand korrekt rechnen (PROJ4-QA-3): aktuelle Turn-Belegung aus
        # assistant-Events, das (modellabhängige) Kontextfenster aus result-Events.
        self._ctx_occupancy: int = 0
        self._ctx_window: int = 0
        # PROJ-16: Amok-Watchdog — Sliding-Window-Monitor (Tokens/Zeit, Stillstand,
        # Schleife, Schreibrate). Liest die Limits live aus dem Modul-Singleton.
        self.watchdog = watchdog.WatchdogMonitor(watchdog.watchdog_store)

    def to_read(self) -> dict:
        """Lese-Snapshot inkl. offener Decision Cards (für REST-Liste + WS-Broadcast)."""
        data = self.state.to_read()
        data["pending_decisions"] = [c.to_read() for c in self.pending.values()]
        return data

    def _maybe_persist(self) -> None:
        """PROJ-14: bei Zustandswechsel den Live-Index spiegeln (best-effort).

        Feuert nur, wenn sich der Status seit dem letzten Spiegeln geändert hat —
        so bleibt der hochfrequente Event-Loop unbelastet (kein Write pro Event).
        ``on_persist`` aktualisiert ``_last_persisted_status``.
        """
        if self.on_persist is not None and self.state.status != self._last_persisted_status:
            self.on_persist(self)

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
                # PROJ-15: denselben Strom auf Kuratierungs-Marker scannen (entprellt).
                self._maybe_propose_knowledge(reasoning)
                # PROJ-16: Assistenten-Output = echter Fortschritt → Stillstands-Uhr resetten.
                self.watchdog.note_progress()
            self._apply_usage(event)

        elif event.type == "result":
            self._apply_usage(event)
            self.state.num_turns = int(event.raw.get("num_turns", self.state.num_turns) or 0)
            if is_error_result(event):
                self.state.status = ERROR
                # api_error_status kommt als int (z.B. 500) → in str casten,
                # sonst scheitert die Response-Validierung (error: str | None).
                api_status = event.raw.get("api_error_status")
                self.state.error = (
                    f"API-Fehler {api_status}" if api_status else extract_result_text(event)
                )
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

        # PROJ-5: beim ERSTEN Überschreiten der Kontext-Schwelle einmalig einen
        # Handover vorschlagen (Auto-Trigger = Schwelle).
        self._maybe_warn_threshold()

        # Beim Übergang nach DONE genau einmal das Roh-Log in den Vault schreiben (PROJ-2).
        if self.state.status == DONE and not self._done_fired:
            self._done_fired = True
            if self.on_done is not None:
                self.on_done(self)

        # PROJ-14: Zustandswechsel in den persistenten Live-Index spiegeln.
        self._maybe_persist()

    def _apply_usage(self, event: StreamEvent) -> None:
        usage = extract_usage(event)
        if usage is None:
            return
        self.state.context_known = True  # ab jetzt echte Daten → Gauge nicht mehr „unbekannt".

        # Füllstand = Größe des AKTUELLEN Turn-Prompts (assistant-Usage: input + cache_read
        # + cache_creation), NICHT die über alle Turns kumulierte result-Usage — die wuchs
        # sonst mit jeder Runde ins Absurde (z. B. 97 % bei real ~20 %) und löste die
        # Handover-Schwelle fälschlich aus (PROJ4-QA-3).
        if event.type == "assistant":
            self._ctx_occupancy = usage.context_used_tokens
        if event.type == "result":
            # Das modellabhängige Kontextfenster liefert nur das result-Event (modelUsage).
            self._ctx_window = usage.context_window
            self.state.tokens_used += usage.billed_tokens
            if usage.total_cost_usd is not None:
                self.state.total_cost_usd += float(usage.total_cost_usd)
            # PROJ-16: abgerechnete Tokens ins Watchdog-Fenster (+ zählt als Fortschritt).
            self.watchdog.feed_usage(usage.billed_tokens)

        window = self._ctx_window or DEFAULT_CONTEXT_WINDOW
        if self._ctx_occupancy and window > 0:
            self.state.context_fill_pct = min(
                100.0, round(self._ctx_occupancy / window * 100, 1)
            )

    def _maybe_warn_threshold(self) -> None:
        """One-shot Handover-Vorschlag, sobald der Füllstand die Schwelle erreicht.

        Feuert genau einmal pro Session (``threshold_warned``). Das ist der einzige
        Auto-Trigger im MVP (phasen-basierter Trigger → PROJ-8). Generieren/Schreiben
        des Handovers bleiben bewusst nutzerbestätigt — hier wird nur *vorgeschlagen*.
        """
        s = self.state
        if s.threshold_warned or s.status in (DONE, ERROR):
            return
        if not s.threshold_warning:
            return
        s.threshold_warned = True
        self._broadcast(
            {
                "kind": "notice",
                "event": "threshold_reached",
                "session_id": s.session_id,
                "context_fill_pct": s.context_fill_pct,
                "threshold_pct": s.effective_threshold_pct,
            }
        )

    # --- ABC-Workflow-Phase (PROJ-8) ---------------------------------------

    def _detect_abc(self, tool_name: str, tool_input: dict | None) -> None:
        """Leitet aus dem Tool-Aufruf die aktuelle ABC-Phase + Feature-Referenz ab.

        Reiner Seiteneffekt für den Gantt (PROJ-8): ``Skill``-Aufrufe mit abc-Workflow-
        Skill setzen Phase/erreichte-Phase/Feature; berührte ``features/PROJ-X-*.md``
        liefern das Fallback-Feature. Ändert sich etwas, wird ein State-Snapshot
        gestreamt (Live-Aktualisierung der Bars, gratis über ``to_read``).
        """
        s = self.state
        # PROJ-10: zuletzt genutzten Skill mitführen (Policy-Kontext „skill").
        if tool_name == "Skill":
            skill = str((tool_input or {}).get("skill", "")).strip()
            if skill:
                s.current_skill = skill
        before = (s.abc_phase, s.abc_phase_reached, s.abc_feature)
        s.abc_phase, s.abc_phase_reached, s.abc_feature = abc_phases.detect_phase_signal(
            tool_name,
            tool_input,
            phase=s.abc_phase,
            reached=s.abc_phase_reached,
            feature=s.abc_feature,
        )
        if before != (s.abc_phase, s.abc_phase_reached, s.abc_feature):
            self._broadcast({"kind": "state", **self.to_read()})

    # --- Decision Cards / Freigabe (PROJ-4) --------------------------------

    async def request_decision(
        self, decision_id: str, tool_name: str, tool_input: dict | None
    ) -> DecisionOutcome:
        """Vom Freigabe-Hook aufgerufen, bevor ein Tool läuft (PROJ-4/PROJ-10).

        Reihenfolge (eine Entscheidungsstelle, zwei Sorten Gate):
        1. **Hartes Phasen-Gate** (bypass-fest): erkannter ABC-Phasenwechsel → Card,
           pausiert die Session — **auch im Bypass**.
        2. **Operativer Evaluator**: ``auto-allow`` → durch; ``deny`` → nie ausgeführt
           (ablehnende Notiz); ``card`` → Freigabe nötig (im Bypass durchlässig).
        """
        # PROJ-16: Watchdog-Reißleine ZUERST — vor jedem anderen Gate UND vor dem
        # Bypass-Auto-Allow (Reißleine sticht Komfort). Reißt ein Limit (Tokens/Zeit,
        # Stillstand, Schleife, Schreibrate), wird DIESER Aufruf in eine Watchdog-Card
        # umgelenkt: die Session pausiert (Prozess lebt), bis der Nutzer Fortsetzen/
        # Korrigieren/Abbrechen wählt.
        alarm = self.watchdog.evaluate(tool_name, tool_input)
        if alarm is not None:
            outcome = await self._open_card(
                decision_id, tool_name, tool_input,
                card_type="watchdog_pause",
                triggering_rule=alarm.reason,
                action=f"Watchdog-Pause: {alarm.reason}",
            )
            # Fortsetzen ODER Mit-Kommentar-korrigieren: ausgelöstes Limit zurücksetzen
            # + Cooldown, damit es nicht sofort erneut feuert (AC + Card-Flut-Schutz).
            self.watchdog.reset(alarm.metric)
            return outcome
        # Kein Alarm → diesen erlaubten Aufruf in die Watchdog-Fenster aufnehmen.
        self.watchdog.record(tool_name, tool_input)

        # PROJ-8/PROJ-10: prospektive Phase/Feature OHNE Seiteneffekt berechnen — die
        # Übernahme erfolgt erst NACH einem evtl. Phasen-Gate (QA-Bug B: ein abgelehnter
        # Übergang darf die Phase NICHT vorrücken).
        s = self.state
        old_phase = s.abc_phase
        prospective = abc_phases.detect_phase_signal(
            tool_name, tool_input,
            phase=s.abc_phase, reached=s.abc_phase_reached, feature=s.abc_feature,
        )
        new_phase = prospective[0]

        # 1) Hartes, bypass-festes Phasen-Übergangs-Gate.
        if self._should_gate_phase(old_phase, new_phase):
            outcome = await self._open_card(
                decision_id, tool_name, tool_input,
                card_type="phase_transition",
                triggering_rule=f"Phasen-Gate: {old_phase} → {new_phase}",
                action=f"Phasenwechsel {old_phase} → {new_phase}",
            )
            if outcome.behavior == "allow":
                self._apply_phase(tool_name, tool_input, prospective)  # erst bei Freigabe
            return outcome

        # Kein Gate → Phase/Skill/Feature regulär übernehmen (mutiert + broadcastet).
        self._detect_abc(tool_name, tool_input)

        # 2) Operative Auswertung der abgestuften Trust-Policy.
        decision = policy.policy_store.evaluate(
            tool_name,
            role=self.state.role,
            skill=self.state.current_skill,
            project=self.state.project_name or self.state.project_path,
        )

        if decision.level == policy.AUTO_ALLOW:
            return DecisionOutcome(behavior="allow", auto=True)

        if decision.level == policy.DENY:
            # Hart verboten: Aktion wird NIE ausgeführt; Claude erhält die Begründung
            # inline (deny), die Session blockiert NICHT. Eine ablehnende Notiz-Card wird
            # in die offene Liste gehängt (QA-Bug A: im Cockpit sichtbar) — ohne Future,
            # ohne awaiting_approval; der Nutzer quittiert sie mit „Zur Kenntnis".
            reason = decision.reason or "Durch Trust-Policy verboten."
            self._register_deny_notice(decision_id, tool_name, tool_input, decision, reason)
            return DecisionOutcome(behavior="deny", reason=f"{reason} ({decision.rule})")

        # decision.level == CARD
        # bypassPermissions (PROJ-1): OPERATIVE Freigaben laufen OHNE Card durch
        # (nur die harten Gates oben feuern auch im Bypass).
        if self.state.permission_mode == "bypassPermissions":
            return DecisionOutcome(behavior="allow", auto=True)

        return await self._open_card(
            decision_id, tool_name, tool_input,
            card_type="normal", triggering_rule=decision.rule,
        )

    def _should_gate_phase(self, old_phase: str | None, new_phase: str | None) -> bool:
        """Echter, zu gatender ABC-Phasenübergang? (Entprellung über old≠new.)

        Gilt nur für Übergänge ZWISCHEN zwei erkannten Phasen (``old`` ≠ None) — der
        allererste Phaseneintritt (None→X, Session-Start) ist kein Übergang. Welche
        Ziel-Phasen gaten, kommt aus der Policy (leere Liste = jeder Wechsel).
        """
        if old_phase is None or new_phase is None or old_phase == new_phase:
            return False
        gate = policy.policy_store.phase_gate()
        if not gate.get("enabled"):
            return False
        transitions = gate.get("transitions") or []
        return not transitions or new_phase in transitions

    async def _open_card(
        self,
        decision_id: str,
        tool_name: str,
        tool_input: dict | None,
        *,
        card_type: str,
        triggering_rule: str,
        action: str | None = None,
    ) -> DecisionOutcome:
        """Legt eine blockierende Decision Card an und wartet auf die Auflösung."""
        card = PendingDecision(
            decision_id=decision_id,
            session_id=self.state.session_id,
            tool_name=tool_name,
            action=action or policy.summarize_action(tool_name, tool_input),
            excerpt=policy.extract_excerpt(tool_name, tool_input),
            rationale=policy.clip_rationale(self._last_assistant_text),
            context={
                "project_path": self.state.project_path,
                "role": self.state.role,
                "phase": self.state.abc_phase,  # PROJ-10-Fix: echte Phase (war constitution_source).
            },
            created_at=_now().isoformat(),
            tool_input=tool_input or {},
            triggering_rule=triggering_rule,
            card_type=card_type,
        )
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[decision_id] = card
        self._futures[decision_id] = fut
        self.state.status = AWAITING_APPROVAL
        self.state.last_activity = _now()
        self._broadcast({"kind": "decision", "event": "opened", "decision": card.to_read()})
        self._broadcast({"kind": "state", **self.to_read()})
        self._maybe_persist()  # PROJ-14: awaiting_approval spiegeln (zählt aktiv).
        return await fut

    def _apply_phase(self, tool_name: str, tool_input: dict | None, prospective: tuple) -> None:
        """Übernimmt die (zuvor seiteneffektfrei berechnete) Phase nach Gate-Freigabe.

        Spiegelt den Skill-Kontext (``current_skill``) und das ABC-Tripel und streamt bei
        Änderung einen State-Snapshot (Live-Gantt). Wird NUR im Gate-Approve-Pfad genutzt.
        """
        s = self.state
        if tool_name == "Skill":
            skill = str((tool_input or {}).get("skill", "")).strip()
            if skill:
                s.current_skill = skill
        before = (s.abc_phase, s.abc_phase_reached, s.abc_feature)
        s.abc_phase, s.abc_phase_reached, s.abc_feature = prospective
        if before != (s.abc_phase, s.abc_phase_reached, s.abc_feature):
            self._broadcast({"kind": "state", **self.to_read()})

    def _register_deny_notice(
        self, decision_id: str, tool_name: str, tool_input: dict | None, decision, reason: str
    ) -> None:
        """Hängt eine NICHT-blockierende Ablehnungs-Notiz in die offene Liste (QA-Bug A).

        Bewusst ohne Future und ohne ``awaiting_approval`` — die Aktion ist bereits
        verworfen, die Session läuft weiter; die Karte ist nur sichtbar/quittierbar
        (``card_type='deny'`` → Frontend zeigt „Zur Kenntnis"). ``resolve_decision``
        entfernt sie wieder.
        """
        card = PendingDecision(
            decision_id=decision_id,
            session_id=self.state.session_id,
            tool_name=tool_name,
            action=policy.summarize_action(tool_name, tool_input),
            excerpt=policy.extract_excerpt(tool_name, tool_input),
            rationale=reason,
            context={"project_path": self.state.project_path, "role": self.state.role,
                     "phase": self.state.abc_phase},
            created_at=_now().isoformat(),
            tool_input=tool_input or {},
            triggering_rule=decision.rule,
            card_type="deny",
            state=RESOLVED,
            resolution="deny",
        )
        self.pending[decision_id] = card  # KEIN Future, KEIN awaiting_approval.
        self.state.last_activity = _now()
        self._broadcast({"kind": "decision", "event": "denied", "decision": card.to_read()})
        self._broadcast({"kind": "state", **self.to_read()})

    def resolve_decision(
        self, decision_id: str, approve: bool, comment: str | None = None
    ) -> PendingDecision:
        """Entscheidung des Nutzers einspielen → entsperrt den wartenden Hook-Aufruf.

        ``approve``  → ``allow`` (Claude führt die Aktion aus).
        nicht approve → ``deny``; ``comment`` reist als Begründung **inline** zu Claude
        zurück („Mit Kommentar zurück" = natives Deny mit Begründung).
        """
        card = self.pending.get(decision_id)
        if card is None:
            raise KeyError(decision_id)
        fut = self._futures.get(decision_id)
        if fut is None:
            # Future-lose Notiz (z. B. deny, QA-Bug A): nur quittieren/entfernen — die
            # Aktion war nie blockierend, es gibt nichts zu entsperren.
            self.pending.pop(decision_id, None)
            self.state.last_activity = _now()
            self._broadcast({"kind": "decision", "event": "resolved", "decision": card.to_read()})
            self._broadcast({"kind": "state", **self.to_read()})
            return card
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
        # Keine BLOCKIERENDE Card mehr → Session läuft weiter (Claude verarbeitet das
        # Resultat). Nur Cards mit Future blockieren; nicht-blockierende deny-Notizen
        # (QA-Bug C) dürfen den Status NICHT auf awaiting_approval festhalten.
        if not self._futures and self.state.status == AWAITING_APPROVAL:
            self.state.status = RUNNING
        self.state.last_activity = _now()
        self._broadcast({"kind": "decision", "event": "resolved", "decision": card.to_read()})
        self._broadcast({"kind": "state", **self.to_read()})
        self._maybe_persist()  # PROJ-14: Rückkehr nach running spiegeln.
        return card

    # --- Kuratierung / Wissens-Vorschläge (PROJ-15) ------------------------

    def _maybe_propose_knowledge(self, text: str) -> None:
        """Scannt den Assistenten-/Denk-Strom auf Kuratierungs-Marker → NICHT-blockierende Card.

        Entprellung: je Marker-Art (Bug gelöst / ADR / Sackgasse) höchstens ein
        Vorschlag pro Session (``_seen_markers``). Die Karte hält die Session NICHT an
        (kein Future, kein ``awaiting_approval``) — Kuratierung darf nie blockieren.
        """
        if not settings.enable_curation:
            return
        marker = curation.detect_marker(text)
        if marker is None or marker.kind in self._seen_markers:
            return
        self._seen_markers.add(marker.kind)
        title, body = curation.build_proposal(
            marker, text,
            project_name=self.state.project_name,
            session_id=self.state.session_id,
        )
        decision_id = f"know-{marker.kind}-{len(self._seen_markers)}"
        card = PendingDecision(
            decision_id=decision_id,
            session_id=self.state.session_id,
            tool_name="KnowledgeProposal",
            action=f"Wissens-Vorschlag: {marker.label}",
            excerpt=curation._clip(body, policy.MAX_EXCERPT_CHARS),
            rationale=marker.label,
            context={
                "project_path": self.state.project_path,
                "role": self.state.role,
                "phase": self.state.abc_phase,
                "curation_marker": marker.kind,
            },
            created_at=_now().isoformat(),
            triggering_rule=f"Kuratierung: {marker.label} (Marker „{marker.keyword}“)",
            card_type="knowledge_proposal",
            proposal_title=title,
            proposal_body=body,
        )
        self.pending[decision_id] = card  # nicht-blockierend: kein Future, kein awaiting_approval
        self.state.last_activity = _now()
        self._broadcast({"kind": "decision", "event": "proposed", "decision": card.to_read()})
        self._broadcast({"kind": "state", **self.to_read()})

    def resolve_knowledge(
        self,
        decision_id: str,
        approve: bool,
        edited_title: str | None,
        edited_body: str | None,
        writer: Callable[[PendingDecision], None],
    ) -> PendingDecision:
        """Wissens-Vorschlag entscheiden (Freigeben/Editieren/Verwerfen) — nicht-blockierend.

        ``approve`` → ``writer`` schreibt die (ggf. editierte) Notiz **vor** dem Auflösen;
        schlägt der Vault-Write fehl, propagiert der Fehler und die Card **bleibt offen**
        (Edge-Case „Vault nicht schreibbar → kein Verlust"). ``deny`` (Verwerfen) → nichts
        geschrieben (nur das Roh-Log dokumentiert den Marker).
        """
        card = self.pending.get(decision_id)
        if card is None or card.card_type != "knowledge_proposal":
            raise KeyError(decision_id)
        if card.state != OPEN:
            raise ValueError("Dieser Wissens-Vorschlag wurde bereits entschieden.")
        if approve:
            if edited_title:
                card.proposal_title = edited_title
            if edited_body:
                card.proposal_body = edited_body
            writer(card)  # kann werfen → Card bleibt OPEN, Route übersetzt in 503
            card.resolution = "approve"
        else:
            card.resolution = "deny"
        card.state = RESOLVED
        self.pending.pop(decision_id, None)
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
    def __init__(
        self,
        driver_factory: DriverFactory | None = None,
        vault=None,
        repo: SessionIndexRepository | None = None,
    ) -> None:
        self._driver_factory: DriverFactory = driver_factory or (lambda: ClaudeCodeDriver())
        self._sessions: dict[str, SessionRuntime] = {}
        # Optionaler VaultService (PROJ-2): rohe Session-Logs am Ende persistieren.
        self._vault = vault
        # PROJ-14: Persistenz-Seam (Live-Index). None → reines In-Memory (wie Tests/MVP).
        self._repo: SessionIndexRepository = repo or NullSessionIndexRepository()
        # Atomare Limit-Prüfung: ``create`` hat await-Punkte → ohne Lock wäre
        # „zählen → prüfen → reservieren" nicht atomar (Edge-Case Limit-Race).
        self._create_lock = asyncio.Lock()
        # Referenzen auf laufende best-effort-Persist-Tasks (gegen vorzeitiges GC).
        self._persist_tasks: set[asyncio.Task] = set()

    # --- PROJ-14: Limit + Persistenz --------------------------------------

    def active_count(self) -> int:
        """Anzahl aktuell aktiver Sessions (zählt gegen das Limit)."""
        return sum(1 for r in self._sessions.values() if r.state.status in ACTIVE_STATES)

    @property
    def max_parallel_sessions(self) -> int:
        return clamp_session_limit(settings.max_parallel_sessions)

    def _row(self, runtime: SessionRuntime) -> dict:
        """Persistierbarer Snapshot (Metadaten + PID) für den Live-Index."""
        s = runtime.state
        return {
            "session_id": s.session_id,
            "owner": s.owner,
            "project_path": s.project_path,
            "project_name": s.project_name,
            "model": s.model,
            "permission_mode": s.permission_mode,
            "role": s.role,
            "status": s.status,
            "pid": runtime.driver.pid,
            "error": s.error,
            "created_at": s.created_at.isoformat(),
            "last_activity": s.last_activity.isoformat(),
            "tokens_used": s.tokens_used,
            "total_cost_usd": float(s.total_cost_usd),
            "parent_session_id": s.parent_session_id,
            "child_session_id": s.child_session_id,
            "abc_phase": s.abc_phase,
            "abc_phase_reached": s.abc_phase_reached,
            "abc_feature": s.abc_feature,
            "recovery_dismissed": 1 if s.recovery_dismissed else 0,
        }

    def _persist(self, runtime: SessionRuntime) -> None:
        """Best-effort: Live-Index-Zeile schreiben (off-thread, nie blockierend).

        Wird als ``on_persist``-Hook bei Zustandswechseln gefeuert. Fehler degradieren
        zu einer Warnung — der In-Memory-Pfad bleibt führend (AC „DB nicht erreichbar")."""
        runtime._last_persisted_status = runtime.state.status
        if isinstance(self._repo, NullSessionIndexRepository):
            return
        row = self._row(runtime)
        task = asyncio.create_task(self._safe_upsert(row))
        self._persist_tasks.add(task)
        task.add_done_callback(self._persist_tasks.discard)

    async def _safe_upsert(self, row: dict) -> None:
        try:
            await self._repo.upsert(row)
        except Exception as exc:  # noqa: BLE001 — Persistenz ist best-effort.
            logger.warning("Session-Live-Index konnte nicht geschrieben werden: %s", exc)

    async def _safe_delete(self, session_id: str) -> None:
        try:
            await self._repo.delete(session_id)
        except Exception as exc:  # noqa: BLE001 — Persistenz ist best-effort.
            logger.warning("Live-Index-Eintrag konnte nicht gelöscht werden: %s", exc)

    async def rehydrate(self) -> None:
        """PROJ-14: beim Startup den Live-Index laden und verwaiste Sessions markieren.

        Nach einem Backend-Neustart ist KEINE persistierte Session mehr steuerbar
        (der ``asyncio.subprocess``-Handle/Stream ist weg). Aktive Sessions werden
        daher als **verwaist** markiert (raus aus der Aktiv-Zählung), terminale
        bleiben als Historie sichtbar — die Übersicht überlebt den Restart.
        In-Memory/Prozess-Realität gewinnt bei Inkonsistenz.
        """
        try:
            rows = await self._repo.list_all()
        except Exception as exc:  # noqa: BLE001 — DB nicht erreichbar → ohne Rehydrierung starten.
            logger.warning("Live-Index nicht lesbar — starte ohne Rehydrierung: %s", exc)
            return
        for row in rows:
            sid = row.get("session_id")
            if not sid or sid in self._sessions:  # In-Memory gewinnt.
                continue
            state = self._state_from_row(row)
            runtime = SessionRuntime(
                state,
                DeadDriver(pid=row.get("pid")),  # PROJ-21: PID für Orphan-Kill bewahren.
                on_done=self._write_session_log,
                on_persist=self._persist,
            )
            runtime._last_persisted_status = state.status
            if row.get("status") in ACTIVE_STATES:
                alive = self._pid_alive(row.get("pid"))
                note = "Prozess läuft evtl. noch, ist aber nicht steuerbar" if alive else "Prozess beendet"
                state.status = ERROR
                state.error = f"Verwaist nach Backend-Neustart ({note})."
            self._sessions[sid] = runtime
            if state.status != row.get("status"):  # verwaist → korrigierten Status spiegeln.
                self._persist(runtime)
        if rows:
            logger.info("Live-Index rehydriert: %d Session(s).", len(rows))

    @staticmethod
    def _pid_alive(pid) -> bool:
        """Best-effort-Lebendigkeitscheck eines Prozesses (Signal 0)."""
        if not pid:
            return False
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return False
        except PermissionError:  # existiert, gehört aber anderem User → lebt.
            return True
        except (OSError, ValueError):
            return False
        return True

    def _state_from_row(self, row: dict) -> SessionState:
        """Rekonstruiert den Übersichts-``SessionState`` aus einer Index-Zeile."""
        def _dt(value) -> datetime:
            try:
                return datetime.fromisoformat(value) if value else _now()
            except (TypeError, ValueError):
                return _now()

        return SessionState(
            session_id=row["session_id"],
            owner=row.get("owner") or settings.default_owner,
            project_path=row.get("project_path") or "",
            model=row.get("model") or settings.default_model,
            permission_mode=row.get("permission_mode") or settings.default_permission_mode,
            role=row.get("role"),
            status=row.get("status") or DONE,
            created_at=_dt(row.get("created_at")),
            last_activity=_dt(row.get("last_activity")),
            tokens_used=int(row.get("tokens_used") or 0),
            total_cost_usd=float(row.get("total_cost_usd") or 0.0),
            error=(str(e) if (e := row.get("error")) is not None else None),
            parent_session_id=row.get("parent_session_id"),
            child_session_id=row.get("child_session_id"),
            project_name=row.get("project_name"),
            abc_phase=row.get("abc_phase"),
            abc_phase_reached=row.get("abc_phase_reached"),
            abc_feature=row.get("abc_feature"),
            recovery_dismissed=bool(row.get("recovery_dismissed")),
        )

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
        parent_session_id: str | None = None,
        project_name: str | None = None,
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
            parent_session_id=parent_session_id,
            # PROJ-8: sprechendes Gantt-Label; ohne Angabe der Verzeichnis-Basename.
            project_name=(project_name or "").strip() or os.path.basename(real_path) or real_path,
        )
        driver = self._driver_factory()
        runtime = SessionRuntime(
            state, driver, on_done=self._write_session_log, on_persist=self._persist
        )

        # PROJ-14: Limit atomar prüfen und Slot reservieren (Insert in die Registry,
        # solange der Lock hält → konkurrierende Creates sehen den belegten Slot).
        async with self._create_lock:
            limit = self.max_parallel_sessions
            if self.active_count() >= limit:
                raise SessionLimitError(
                    f"Limit erreicht: maximal {limit} gleichzeitige Sessions. "
                    "Bitte eine laufende Session beenden, bevor eine neue startet."
                )
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
            self._persist(runtime)  # PROJ-14: Fehlversuch spiegeln (zählt nicht aktiv).
            raise
        # PROJ-14: initialen Zustand spiegeln (falls noch kein Event den Status wechselte).
        self._persist(runtime)
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
        # PROJ-4: Bei offener Decision Card KEINE Eingabe annehmen. Sonst überschriebe
        # `send_input` den Status (awaiting_approval → running), während die Card-Future
        # ungelöst weiterhängt, und der Event-Strom der Session verkeilt (Bug PROJ4-QA-1).
        # Erst entscheiden (Freigeben/Ablehnen/Mit Kommentar zurück), dann weiter eingeben.
        # PROJ-15: nicht-blockierende Wissens-Vorschläge zählen NICHT als offene Freigabe —
        # Kuratierung darf die Eingabe nie sperren.
        blocking = [c for c in runtime.pending.values() if c.card_type != "knowledge_proposal"]
        if blocking:
            raise RuntimeError(
                "Offene Freigabe — bitte erst die Decision Card entscheiden, dann weiter eingeben."
            )
        # Beendete Session (Prozess ist weg) → vor der Eingabe per `claude --resume`
        # fortsetzen, damit der User auch an fertigen Sessions weiterarbeiten kann.
        if not runtime.driver.is_alive:
            await self._resume(runtime)
        await runtime.driver.send_input(text)
        runtime.transcript.append(TranscriptEntry("user", "text", text, _now().isoformat()))
        runtime.state.status = RUNNING
        runtime.state.last_activity = _now()
        self._persist(runtime)  # PROJ-14: running (inkl. evtl. neuer PID nach resume) spiegeln.

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
        self._persist(runtime)  # PROJ-14: rehydrierte/fortgesetzte Session läuft wieder.

    async def pause(self, session_id: str) -> None:
        await self._require(session_id).driver.pause()

    async def stop(self, session_id: str) -> None:
        runtime = self._require(session_id)
        await runtime.driver.stop()
        # Sicherheitsnetz: offene Cards auflösen (der closed-Event tut das i. d. R. schon).
        runtime.abandon_decisions("Session gestoppt — Freigabe hinfällig.")
        self._persist(runtime)  # PROJ-14: terminalen Zustand (PID weg) spiegeln.

    # --- Löschen / Aufräumen (PROJ-21) -------------------------------------

    async def delete(self, session_id: str) -> None:
        """Eine **terminale** Session aus Registry + Live-Index entfernen.

        - Unbekannte ID → ``KeyError`` (Route → 404).
        - Aktive Session (Status in ``ACTIVE_STATES``) → ``SessionActiveError``
          (Route → 409): laufende Arbeit darf nicht abgewürgt werden.
        - Lebt eine persistierte PID noch (typisch: verwaiste Session nach
          Backend-Neustart), wird der OS-Prozess best-effort per SIGTERM beendet,
          damit kein Geister-Prozess Tokens verbrennt — Fehler blockieren das
          Löschen nicht.
        - Gelöscht wird nur der Live-Index (SQLite + In-Memory); das Session-Log
          im Vault bleibt erhalten (Prinzip „Live-Index, nicht die Wahrheit").
        """
        runtime = self._require(session_id)  # KeyError → 404
        if runtime.state.status in ACTIVE_STATES:
            raise SessionActiveError(
                "Aktive Session kann nicht gelöscht werden — zuerst stoppen."
            )
        self._terminate_orphan(runtime)
        del self._sessions[session_id]
        await self._safe_delete(session_id)

    async def cleanup_terminal(self) -> int:
        """Alle terminalen Sessions (done/error/verwaist) auf einmal entfernen.

        Aktive Sessions werden **still übersprungen**. Gibt die Anzahl gelöschter
        Sessions zurück und wendet dieselbe Orphan-Kill-Regel je Session an.
        """
        terminal_ids = [
            sid
            for sid, r in self._sessions.items()
            if r.state.status not in ACTIVE_STATES
        ]
        deleted = 0
        for sid in terminal_ids:
            runtime = self._sessions.get(sid)
            if runtime is None:  # konkurrierendes Einzel-Delete kam zuvor.
                continue
            self._terminate_orphan(runtime)
            del self._sessions[sid]
            await self._safe_delete(sid)
            deleted += 1
        return deleted

    def _terminate_orphan(self, runtime: SessionRuntime) -> None:
        """Best-effort-SIGTERM an einen evtl. noch lebenden, nicht steuerbaren
        Prozess einer terminalen Session. Nur relevant für verwaiste Sessions mit
        lebender PID; Fehler (Permission/Race) werden geschluckt — das Löschen darf
        nie daran scheitern (geloggt als Warnung)."""
        pid = getattr(runtime.driver, "pid", None)
        if not self._pid_alive(pid):
            return
        try:
            os.kill(int(pid), signal.SIGTERM)
            logger.info("Verwaisten Session-Prozess PID %s per SIGTERM beendet.", pid)
        except Exception as exc:  # noqa: BLE001 — best-effort, blockiert das Löschen nicht.
            logger.warning("SIGTERM an PID %s fehlgeschlagen: %s", pid, exc)

    # --- Decision Cards / Freigabe (PROJ-4) --------------------------------

    async def request_decision(
        self, session_id: str, decision_id: str, tool_name: str, tool_input: dict | None
    ) -> DecisionOutcome:
        """Freigabe-Anfrage des Hooks → blockiert bis zur Entscheidung."""
        return await self._require(session_id).request_decision(
            decision_id, tool_name, tool_input
        )

    def resolve_decision(
        self,
        session_id: str,
        decision_id: str,
        approve: bool,
        comment: str | None = None,
        edited_title: str | None = None,
        edited_body: str | None = None,
    ) -> PendingDecision:
        """Nutzer-Entscheidung einspielen.

        - **Wissens-Vorschlag** (PROJ-15, nicht-blockierend): Freigeben/Editieren →
          kuratierte Notiz nach ``Knowledge/``; Verwerfen → nichts geschrieben.
        - **Freigabe-Card** (PROJ-4): Freigeben/Ablehnen/Mit Kommentar zurück.
        """
        runtime = self._require(session_id)
        card = runtime.pending.get(decision_id)
        if card is not None and card.card_type == "knowledge_proposal":
            return runtime.resolve_knowledge(
                decision_id, approve, edited_title, edited_body,
                writer=lambda c: self._write_curated_note(runtime, c),
            )
        return runtime.resolve_decision(decision_id, approve, comment)

    def _write_curated_note(self, runtime: SessionRuntime, card: PendingDecision) -> None:
        """PROJ-15: freigegebenen Wissens-Vorschlag als kuratierte MD-Notiz persistieren.

        Fehler (Vault nicht verfügbar/schreibbar) werden bewusst **nicht** geschluckt →
        ``resolve_knowledge`` lässt die Card offen, die Route meldet 503 (kein Verlust).
        """
        if self._vault is None:
            raise RuntimeError("Vault nicht verfügbar — Wissensnotiz nicht geschrieben.")
        self._vault.write_curated_note(
            title=card.proposal_title or card.action,
            body=card.proposal_body or "",
            source_session_id=runtime.state.session_id,
            marker=(card.context or {}).get("curation_marker") or card.triggering_rule,
            owner=runtime.state.owner,
        )

    # --- Context-Management & Handover (PROJ-5) ----------------------------

    def generate_handover(self, session_id: str) -> dict:
        """Erzeugt den Handover-INHALT (Vorschau) — schreibt noch NICHT in den Vault.

        Hybrid: mechanisches Gerüst aus dem Session-Zustand + optionaler LLM-Anreicherung
        (heute über ``settings.handover_llm_enrich`` abschaltbar; fällt sie aus, bleibt das
        Gerüst gültig). Rückgabe: ``{title, body}`` — der Body geht (ggf. editiert) an
        ``/handover``.
        """
        runtime = self._require(session_id)
        body = build_handover_md(
            runtime.state,
            runtime.transcript,
            list(runtime.pending.values()),
            enrichment=None,  # LLM-Anreicherungs-Seam (Tech-Design PROJ-5) — MVP: Gerüst.
        )
        return {"title": build_title(runtime.state), "body": body}

    async def reset(
        self,
        session_id: str,
        *,
        seed_context: str,
        initial_prompt: str | None = None,
    ) -> SessionRuntime:
        """„Session zurücksetzen" (Staffelstab): alte Session archivieren, Kind-Session
        mit dem verdichteten Handover als Seed-Kontext frisch starten.

        Bewusst KEIN ``--resume`` (das schleppt den vollen alten Kontext mit — genau das
        Problem). Die Kind-Session startet frisch und bekommt nur die verdichtete Übergabe
        als ``--append-system-prompt`` (Seed). ``parent_session_id`` verweist zurück.
        """
        old = self._require(session_id)
        old_state = old.state
        # Ein Strang hat genau EINEN Nachfolger (QA5-1): ein zweiter Reset würde sonst
        # eine verwaiste, lebende Kind-Session erzeugen. Vor jeder Nebenwirkung prüfen.
        if old_state.child_session_id is not None:
            raise RuntimeError(
                "Diese Session wurde bereits zurückgesetzt "
                f"(Nachfolger {old_state.child_session_id[:8]})."
            )
        # Alte Session archivieren: sauber stoppen → DONE → Auto-Log in den Vault (PROJ-2).
        await self.stop(session_id)
        child = await self.create(
            project_path=old_state.project_path,
            initial_prompt=initial_prompt or _DEFAULT_RESET_PROMPT,
            model=_model_alias(old_state.model),
            permission_mode=old_state.permission_mode,
            role=old_state.role,
            extra_system_prompt=seed_context,
            owner=old_state.owner,
            parent_session_id=old_state.session_id,
            project_name=old_state.project_name,  # PROJ-8: Kind erbt das Projekt-Label.
        )
        old_state.child_session_id = child.state.session_id
        return child

    async def recover(
        self,
        session_id: str,
        *,
        seed_context: str,
        initial_prompt: str | None = None,
        project_path: str | None = None,
        model: str | None = None,
        permission_mode: str | None = None,
        role: str | None = None,
        owner: str | None = None,
        project_name: str | None = None,
    ) -> SessionRuntime:
        """PROJ-17: einen verwaisten/aus dem Vault rekonstruierten Strang wieder als
        Live-Session aufnehmen — wie ``reset()``, aber OHNE ``stop()`` (der alte Strang
        ist bereits terminal/verwaist) und mit serverseitig verdichtetem Seed.

        Idempotent (1 Strang = 1 Nachfolger): existiert schon eine Session, deren
        ``parent_session_id`` auf diesen Strang zeigt, wird abgebrochen (→ 409). Das
        deckt sowohl In-Memory-Verwaiste (mit ``child_session_id``) als auch reine
        Vault-Kandidaten ab. Liegt der alte Strang noch im Speicher, werden seine
        Metadaten übernommen; sonst müssen sie (Projektpfad etc.) übergeben werden.
        """
        if any(r.state.parent_session_id == session_id for r in self._sessions.values()):
            raise RuntimeError("Dieser Strang wurde bereits wiederhergestellt.")
        old = self._sessions.get(session_id)
        if old is not None:
            s = old.state
            project_path = s.project_path
            model = s.model
            permission_mode = s.permission_mode
            role = s.role
            owner = s.owner
            project_name = s.project_name
        if not project_path:
            raise ValueError(
                "Projektpfad nicht rekonstruierbar — Wiederherstellung nicht möglich."
            )
        child = await self.create(
            project_path=project_path,
            initial_prompt=initial_prompt or _DEFAULT_RESET_PROMPT,
            model=_model_alias(model or settings.default_model),
            permission_mode=permission_mode or settings.default_permission_mode,
            role=role,
            extra_system_prompt=seed_context,
            owner=owner,
            parent_session_id=session_id,
            project_name=project_name,
        )
        if old is not None:
            old.state.child_session_id = child.state.session_id
            self._persist(old)  # Staffelstab-Verknüpfung spiegeln (best-effort).
        return child

    def mark_recovery_dismissed(self, session_id: str) -> bool:
        """PROJ-17: einen verwaisten Strang aus der Recovery-Ansicht ausblenden.

        Setzt nur das Flag (Status/Log bleiben unberührt) und spiegelt es best-effort
        in den Live-Index, damit das Verwerfen einen Neustart überdauert. ``True``,
        wenn der Strang im Speicher lag (sonst übernimmt der RecoveryService die
        In-Process-Ausblendung für reine Vault-Kandidaten)."""
        runtime = self._sessions.get(session_id)
        if runtime is None:
            return False
        runtime.state.recovery_dismissed = True
        self._persist(runtime)
        return True

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
