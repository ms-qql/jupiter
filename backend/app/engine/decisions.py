"""Decision Cards — Datenmodell des Freigabe-Flows (PROJ-4).

Eine Decision lebt nur im Speicher und nur solange die Session auf die Entscheidung
blockiert (kein Postgres/Vault im MVP). ``decision_id`` ist die ``tool_use_id`` des
blockierenden Aufrufs → erlaubt mehrere parallele Cards je Session, jede einzeln
auflösbar.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Card-Zustände.
OPEN, RESOLVED, OBSOLETE = "open", "resolved", "obsolete"


@dataclass
class PendingDecision:
    decision_id: str          # = tool_use_id des blockierenden Aufrufs
    session_id: str
    tool_name: str
    action: str               # „Was" — kurze, menschenlesbare Aktionszeile
    excerpt: str              # relevanter Ausschnitt (Befehl/Diff), NICHT der Volltext
    rationale: str            # „Warum" — letzter Assistenten-Text vor dem Aufruf
    context: dict             # „Kontext" — Projekt, Rolle/Phase
    created_at: str
    state: str = OPEN
    resolution: str | None = None   # "approve" | "deny" (nach dem Auflösen)
    # Roh-Input des Tools — für Frage-Tools (AskUserQuestion) rendert das Frontend
    # daraus eine Auswahlliste statt eines JSON-Blobs.
    tool_input: dict = field(default_factory=dict)

    def to_read(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "action": self.action,
            "excerpt": self.excerpt,
            "rationale": self.rationale,
            "context": self.context,
            "created_at": self.created_at,
            "state": self.state,
            "resolution": self.resolution,
            "tool_input": self.tool_input,
        }


@dataclass
class DecisionOutcome:
    """Rückgabe an den PreToolUse-Hook → wird zu Claudes Permission-Entscheidung."""

    behavior: str             # "allow" | "deny"
    reason: str = ""          # bei deny: Begründung, die Claude inline sieht
    auto: bool = False        # True = ohne Card automatisch entschieden (Lesezugriff)

    def to_hook_response(self) -> dict:
        """Exakter PreToolUse-Hook-Output-Vertrag von Claude Code."""
        decision = "allow" if self.behavior == "allow" else "deny"
        out: dict = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
            }
        }
        if decision == "deny":
            out["hookSpecificOutput"]["permissionDecisionReason"] = (
                self.reason or "Vom Nutzer abgelehnt."
            )
        return out
