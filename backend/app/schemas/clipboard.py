"""Pydantic-v2-Schemas für die Clipboard-Micro-App (PROJ-69)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ClipboardStatus = Literal["active", "removed_from_clipboard", "error"]
SourceMethod = Literal["drag_drop", "paste", "upload", "ios_share"]
SourceDevice = Literal["pc", "mac", "ipad", "iphone", "unknown"]


class ClipboardItemRead(BaseModel):
    id: int
    owner: str | None = None
    created_at: str
    source_method: SourceMethod
    source_device: SourceDevice | None = None
    original_filename: str | None = None
    display_name: str
    mime_type: str | None = None
    extension: str | None = None
    size_bytes: int
    hal_inbox_path: str
    metadata_path: str
    status: ClipboardStatus
    notes: str | None = None
    error_message: str | None = None
    removed_at: str | None = None


class ClipboardListRead(BaseModel):
    items: list[ClipboardItemRead]


class ClipboardItemUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=240)
    notes: str | None = Field(None, max_length=2000)


class ClipboardSettingsRead(BaseModel):
    inbox_dir: str
    max_file_bytes: int
    allowed_extensions: list[str]
