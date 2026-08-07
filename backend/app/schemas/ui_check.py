"""Pydantic-v2-Schemas fuer die UI-Check-Micro-App (PROJ-14)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

RunStatus = Literal["queued", "running", "done", "error", "cancelled"]
Mode = Literal["auto", "landing", "app"]
Depth = Literal["audit", "redesign"]
AiProvider = Literal["claude", "codex", "openrouter"]
Severity = Literal["high", "medium", "low"]
RunType = Literal["audit_redesign", "assemble"]
SectionOverrideDecision = Literal["auto", "block", "generate", "exclude"]
RegistryDecision = Literal["registry", "generate"]
ImagesOnly = Literal["safe", "bold"]


class UiCheckDimensionScore(BaseModel):
    key: str
    label: str
    source: str
    score: int | float | None = None


class UiCheckFinding(BaseModel):
    severity: Severity
    title: str
    description: str
    location: str


class UiCheckBranding(BaseModel):
    name: str
    domain: str
    logo_path: str | None = None
    colors: list[str] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    voice: str | None = None
    token_count: int | None = None


class UiCheckArtifactLinks(BaseModel):
    report: str | None = None
    scores: str | None = None
    tokens: str | None = None
    mockup: str | None = None
    screenshots: list[str] | None = None


class UiCheckImageFillStatus(BaseModel):
    total_slots: int = 0
    filled_slots: int = 0
    placeholder_slots: int = 0
    degraded: bool = False


class UiCheckMockupStatus(BaseModel):
    safe_ready: bool = False
    bold_ready: bool = False
    exported: bool = False
    export_conflict: bool = False
    images: UiCheckImageFillStatus = Field(default_factory=UiCheckImageFillStatus)
    score_delta: int | float | None = None


class UiCheckSectionSelection(BaseModel):
    id: str | None = None
    type: str | None = None
    decision: str | None = None
    block: str | None = None
    reason: str | None = None


class UiCheckRegistrySelection(BaseModel):
    safe: list[UiCheckSectionSelection] = Field(default_factory=list)
    bold: list[UiCheckSectionSelection] = Field(default_factory=list)


class UiCheckRunSummary(BaseModel):
    run_id: str
    created_at: str | None = None
    url_hash: str
    display_url: str | None = None
    mode: Mode = "auto"
    depth: Depth = "audit"
    run_type: RunType = "audit_redesign"
    industry: str | None = None
    status: RunStatus
    rubric_version: str | None = None
    score_total: int | float | None = None
    redesign_score: int | float | None = None
    ai_provider: str | None = None
    ai_model: str | None = None


class UiCheckRunDetail(UiCheckRunSummary):
    phase: str | None = None
    progress: int | float | None = None
    prompt: str | None = None
    dimensions: list[UiCheckDimensionScore] = Field(default_factory=list)
    findings: list[UiCheckFinding] = Field(default_factory=list)
    branding: UiCheckBranding | None = None
    artifacts: UiCheckArtifactLinks = Field(default_factory=UiCheckArtifactLinks)
    status_message: str | None = None
    mockup_status: UiCheckMockupStatus = Field(default_factory=UiCheckMockupStatus)
    registry_selection: UiCheckRegistrySelection = Field(default_factory=UiCheckRegistrySelection)
    chain_error: dict | None = None


class UiCheckRunsResponse(BaseModel):
    runs: list[UiCheckRunSummary]
    active_run_id: str | None = None


class UiCheckStartRequest(BaseModel):
    url: HttpUrl
    mode: Mode = "auto"
    depth: Depth = "audit"
    ai_provider: AiProvider = "claude"
    ai_model: str = Field(..., min_length=1, max_length=120)
    prompt: str | None = Field(None, max_length=20_000)
    industry: str | None = Field(None, max_length=120)
    desktop: bool = False
    # AC-3: bei depth="redesign" haengt der Runner Redesign, Bildbefuellung und
    # Mockup-Export automatisch an den Audit-Lauf an, statt nur den Audit zu starten.
    full_pipeline: bool = False

    @field_validator("url", mode="before")
    @classmethod
    def add_url_scheme(cls, value: str) -> str:
        return value if "://" in value else f"https://{value}"


class UiCheckStartResponse(BaseModel):
    run_id: str
    status: RunStatus


class UiCheckImagesRequest(BaseModel):
    force: bool = False
    only: ImagesOnly | None = None


class UiCheckMockupExportRequest(BaseModel):
    force: bool = False


class UiCheckRecycleRequest(BaseModel):
    min_total: int | None = Field(None, ge=0, le=100)
    min_visual: int | None = Field(None, ge=0, le=100)
    force: bool = False


class UiCheckRegistryFile(BaseModel):
    path: str
    type: str | None = None


class UiCheckRegistryItem(BaseModel):
    name: str
    type: str
    title: str | None = None
    description: str | None = None
    section: str | None = None
    style: str | None = None
    industry: list[str] = Field(default_factory=list)
    interactive: bool = False
    source: str | None = None
    image_slots: list[str] = Field(default_factory=list)
    files: list[UiCheckRegistryFile] = Field(default_factory=list)
    assembler_selectable: bool = False


class UiCheckRegistryResponse(BaseModel):
    items: list[UiCheckRegistryItem] = Field(default_factory=list)
    version: str | None = None


class UiCheckBrandingProfileSummary(BaseModel):
    slug: str
    name: str | None = None
    industry: str | None = None
    tags: list[str] = Field(default_factory=list)
    active_version: str | None = None
    colors: list[str] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    has_logo: bool = False
    complete: bool = True
    missing: list[str] = Field(default_factory=list)


class UiCheckBrandingProfilesResponse(BaseModel):
    profiles: list[UiCheckBrandingProfileSummary] = Field(default_factory=list)


class UiCheckAssembleSectionOverride(BaseModel):
    section: str = Field(..., min_length=1, max_length=80)
    decision: SectionOverrideDecision = "auto"
    block: str | None = Field(None, max_length=120)


class UiCheckAssembleRequest(BaseModel):
    branding: str = Field(..., min_length=1, max_length=80)
    industry: str = Field(..., min_length=1, max_length=80)
    sections: list[str] = Field(default_factory=list, max_length=30)
    prompt: str | None = Field(None, max_length=20_000)
    registry_only: bool = False
    overrides: list[UiCheckAssembleSectionOverride] = Field(default_factory=list)


class UiCheckAssembleResponse(BaseModel):
    run_id: str
    status: RunStatus
    run_type: RunType = "assemble"
