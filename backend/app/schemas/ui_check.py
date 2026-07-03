"""Pydantic-v2-Schemas fuer die UI-Check-Micro-App (PROJ-14)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

RunStatus = Literal["queued", "running", "done", "error", "cancelled"]
Mode = Literal["auto", "landing", "app"]
Depth = Literal["audit", "redesign"]
AiProvider = Literal["claude", "codex", "openrouter"]
Severity = Literal["high", "medium", "low"]


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


class UiCheckRunSummary(BaseModel):
    run_id: str
    created_at: str | None = None
    url_hash: str
    display_url: str | None = None
    mode: Mode = "auto"
    depth: Depth = "audit"
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


class UiCheckStartResponse(BaseModel):
    run_id: str
    status: RunStatus
