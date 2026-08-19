"""Pydantic-Modelle für die Hermes-Kanban-API (PROJ-82).

Reine Durchreich-Schicht: das Backend hält keine eigenen Task-Daten, sondern
leitet valide Anfragen an die Hermes-CLI weiter. Die Modelle hier dienen der
serverseitigen Eingabe-Validierung (Dozenten-Fehler vor dem CLI-Aufruf) — die
CLI-Antworten werden als ``dict``/``list`` durchgereicht und vom Frontend
gerendert.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

# --- Größen-Deckel (DoS-Schutz, siehe Tech Design D) ------------------------
_TITLE_MAX = 500
_BODY_MAX = 50_000
_TEXT_MAX = 10_000  # Kommentar: serverseitig abgewiesen, bevor die CLI gerufen wird.
_GENERIC_MAX = 1_000  # tenant / idempotency-key / max-runtime / projekt-ids etc.

_WORKTREE_MODES = ("worktree", "worktree_path")
_PATH_MODES = ("dir", "worktree_path")


class CreateTaskRequest(BaseModel):
    """Neuer Kanban-Task — alle Felder der ``hermes kanban create``-CLI.

    Nicht ausgefüllte optionale Felder werden NICHT als leere Flags an die CLI
    durchgereicht (siehe Service, der die Argumentliste 1:1 baut).
    """

    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    body: str | None = Field(default=None, max_length=_BODY_MAX)
    assignee: str | None = Field(default=None, max_length=_GENERIC_MAX)
    project: str | None = Field(default=None, max_length=_GENERIC_MAX)
    workspace_mode: str = Field(default="scratch", pattern="^(scratch|dir|worktree|worktree_path)$")
    workspace_path: str | None = Field(default=None, max_length=_GENERIC_MAX)
    branch: str | None = Field(default=None, max_length=_GENERIC_MAX)
    parents: list[str] = Field(default_factory=list)
    priority: int | None = None
    skills: list[str] = Field(default_factory=list)
    initial_status: str = Field(default="normal", pattern="^(normal|blocked|running)$")
    triage: bool = False
    tenant: str | None = Field(default=None, max_length=_GENERIC_MAX)
    idempotency_key: str | None = Field(default=None, max_length=_GENERIC_MAX)
    max_runtime: str | None = Field(default=None, max_length=_GENERIC_MAX)
    max_retries: int | None = Field(default=None, ge=0)
    model_override: str | None = Field(default=None, max_length=_GENERIC_MAX)
    provider_override: str | None = Field(default=None, max_length=_GENERIC_MAX)
    goal_mode: bool = False
    goal_max_turns: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _cross_field(self) -> "CreateTaskRequest":
        if (self.model_override is None) != (self.provider_override is None):
            raise ValueError("Modell-Override und Provider-Override gehören zusammen oder keines von beiden.")
        if self.workspace_mode in _PATH_MODES and not self.workspace_path:
            raise ValueError("Bei Workspace 'dir:'/'worktree:<pfad>' ist ein Pfad erforderlich.")
        if self.workspace_mode in _WORKTREE_MODES and not self.branch:
            raise ValueError("Bei einer Worktree-Variante ist ein Branch erforderlich.")
        if self.triage and self.initial_status != "normal":
            raise ValueError("Triage und ein von 'normal' abweichender Initial-Status schließen sich aus.")
        return self


class BlockRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=_TEXT_MAX)
    kind: str | None = Field(default=None, pattern="^(capability|dependency|needs_input|transient)$")


class CommentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=_TEXT_MAX)

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class HermesKanbanSettingsRead(BaseModel):
    poll_interval_seconds: int
    source: str
    warning: str | None = None


class HermesKanbanSettingsPatch(BaseModel):
    poll_interval_seconds: int = Field(ge=5, le=60)
