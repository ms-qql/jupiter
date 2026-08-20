"""Pydantic-Modelle für die Hermes-Kanban-API (PROJ-82).

Reine Durchreich-Schicht: das Backend hält keine eigenen Task-Daten, sondern
leitet valide Anfragen an die Hermes-CLI weiter. Die Modelle hier dienen der
serverseitigen Eingabe-Validierung (Dozenten-Fehler vor dem CLI-Aufruf) — die
CLI-Antworten werden als ``dict``/``list`` durchgereicht und vom Frontend
gerendert.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

# --- Größen-Deckel (DoS-Schutz, siehe Tech Design D) ------------------------
_TITLE_MAX = 500
_BODY_MAX = 50_000
_TEXT_MAX = 10_000  # Kommentar: serverseitig abgewiesen, bevor die CLI gerufen wird.
_GENERIC_MAX = 1_000  # tenant / idempotency-key / max-runtime / projekt-ids etc.

# Kanonische Workspace-Wurzel: der einzige erlaubte Projekt-Ordner.
_WORKSPACE_ROOT = Path("/home/dev/projects")


class CreateTaskRequest(BaseModel):
    """Neuer Kanban-Task — verengter Contract (PROJ-84).

    ``workspace_mode``/``project``/``branch`` wurden entfernt: der Handler
    erzwingt serverseitig immer ``dir:<kanonischer_workspace_path>``. ``extra``
    ist ``forbid``, damit direkte API-Calls mit einem dieser Alt-Felder mit 422
    abgewiesen werden, statt still einen anderen Workspace anzulegen.

    ``workspace_path`` wird per ``field_validator`` kanonisch aufgelöst und auf
    ein existierendes Verzeichnis strikt unter ``_WORKSPACE_ROOT`` begrenzt
    (Root und Pfade, die über ``..`` oder Symlinks ausbrechen, werden abgewiesen).
    """

    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    body: str | None = Field(default=None, max_length=_BODY_MAX)
    assignee: str | None = Field(default=None, max_length=_GENERIC_MAX)
    workspace_path: str = Field(min_length=1, max_length=_GENERIC_MAX)
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

    @field_validator("workspace_path")
    @classmethod
    def _canonical_workspace_path(cls, v: str) -> str:
        """Löst den Pfad kanonisch auf und begrenzt ihn auf ``_WORKSPACE_ROOT``.

        Akzeptiert nur ein existierendes Verzeichnis strikt unterhalb von
        ``/home/dev/projects``. Root selbst, nicht existierende Pfade, sowie
        Pfade, die durch ``..`` oder Symlinks aus der Wurzel ausbrechen, werden
        mit verständlicher deutscher Meldung abgewiesen.
        """
        if not v.strip():
            raise ValueError("Ein Workspace-Pfad unter /home/dev/projects ist erforderlich.")
        raw = Path(v)
        # resolve(strict=True) folgt Symlinks und prüft die Existenz. Es wirft
        # FileNotFoundError, wenn der Pfad (oder ein Zwischensegment) fehlt.
        try:
            resolved = raw.resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            raise ValueError("Der angegebene Workspace-Pfad existiert nicht.") from None
        if not resolved.is_dir():
            raise ValueError("Der Workspace-Pfad muss ein existierendes Verzeichnis sein.")
        root = _WORKSPACE_ROOT.resolve()
        # strict=True verhindert, dass ein Symlink oberhalb der Wurzel die Prüfung
        # umgeht: resolved muss echtes Kind von root sein (kein root selbst).
        try:
            resolved.relative_to(root)
        except ValueError:
            raise ValueError("Der Workspace-Pfad muss unter /home/dev/projects liegen.") from None
        if resolved == root:
            raise ValueError("Der Workspace-Pfad darf nicht die Projekt-Wurzel selbst sein.")
        return str(resolved)

    @model_validator(mode="after")
    def _cross_field(self) -> "CreateTaskRequest":
        if (self.model_override is None) != (self.provider_override is None):
            raise ValueError("Modell-Override und Provider-Override gehören zusammen oder keines von beiden.")
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
