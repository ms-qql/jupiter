"""Pydantic-v2-Schemas für die Buch-Nuggets-Micro-App (PROJ-53)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

QueueStatus = Literal["pending", "running", "done", "error"]
WorkerStatus = Literal["idle", "running"]
SourceType = Literal["url", "upload"]
ModelMode = Literal["staged", "single"]
ModelName = Literal[
    "haiku", "sonnet", "opus",
    "opencode-go/glm-5.2", "opencode-go/qwen3.7-max",
    "opencode-go/kimi-k2.7-code", "opencode-go/minimax-m3",
    "opencode-go/mimo-v2.5-pro", "opencode-go/deepseek-v4-pro",
    "opencode-go/qwen3.7-plus", "opencode-go/mimo-v2.5",
    "opencode-go/deepseek-v4-flash",
]
OnDuplicate = Literal["overwrite", "new_version"]


class QueueItemRead(BaseModel):
    """Ein Warteschlangen-Eintrag (eine Zeile pro eingereichtem Buch)."""

    id: int
    owner: str | None = None
    source_type: str
    source_ref: str
    title: str | None = None
    author: str | None = None
    model_mode: str
    model_extract: str
    model_consolidate: str
    page_limit: int | None = None
    cost_estimate: float | None = None
    status: QueueStatus
    phase: str | None = None
    result_dir: str | None = None
    result_note_path: str | None = None
    result_pdf_path: str | None = None
    error_message: str | None = None
    session_id: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class WorkerStateRead(BaseModel):
    status: WorkerStatus
    draining: bool
    current_id: int | None = None


class QueueRead(BaseModel):
    """Warteschlange + Worker-Zustand (Polling-Antwort)."""

    items: list[QueueItemRead]
    state: WorkerStateRead


class QueueAddRequest(BaseModel):
    """Ein Buch einreihen — Quelle als URL oder Pfad einer zuvor (via /files/upload)
    hochgeladenen Datei, plus Modellwahl (Stufen-Logik) + optionales Seitenlimit."""

    source_type: SourceType
    source_ref: str = Field(..., min_length=1, description="URL oder Upload-Pfad.")
    model_mode: ModelMode = "staged"
    model_extract: ModelName = "opencode-go/deepseek-v4-flash"
    model_consolidate: ModelName = "opencode-go/deepseek-v4-flash"
    page_limit: int | None = Field(None, ge=1, le=5000)
    on_duplicate: OnDuplicate | None = Field(
        None, description="Bei erkanntem Duplikat (D9): overwrite | new_version."
    )


class QueueAddResult(BaseModel):
    item: QueueItemRead
    queue: list[QueueItemRead]


class EstimateRequest(BaseModel):
    source_type: SourceType
    source_ref: str = Field(..., min_length=1)
    model_mode: ModelMode = "staged"
    model_extract: ModelName = "opencode-go/deepseek-v4-flash"
    model_consolidate: ModelName = "opencode-go/deepseek-v4-flash"
    page_limit: int | None = Field(None, ge=1, le=5000)


class EstimateResult(BaseModel):
    """Best-effort-Kostenschätzung vor dem Einreihen (D7). Unbekannte Größe
    (z. B. URL ohne Download) → Felder ``null``."""

    source_type: str
    pages: int | None = None
    est_tokens: int | None = None
    est_cost: float | None = Field(None, description="Geschätzte Kosten in USD (grob).")


class DuplicateConflict(BaseModel):
    """409-Body bei erkanntem Duplikat (D9) — die UI bietet Overwrite/Neue-Version an."""

    detail: str
    existing_id: int
    existing_status: str


class BookNuggetsSettingsRead(BaseModel):
    default_model_mode: str = "staged"
    default_model_extract: str = "opencode-go/deepseek-v4-flash"
    default_model_consolidate: str = "opencode-go/deepseek-v4-flash"
    default_page_limit: int | None = None


class BookNuggetsSettingsPatch(BaseModel):
    """Default-Einstellungen ändern. Felder optional — nur Angegebene überschreiben."""

    default_model_mode: ModelMode | None = None
    default_model_extract: ModelName | None = None
    default_model_consolidate: ModelName | None = None
    default_page_limit: int | None = Field(None, ge=1, le=5000)


class BookNuggetsLibraryItem(BaseModel):
    """Ein bereits erzeugtes Nugget im Standard-Ordner (Vault-Scan)."""

    title: str
    md_path: str
    pdf_path: str | None = None
    mtime: str | None = None
