"""Pydantic-v2-Schemas für die Token-/Kosten-Dashboard-API (PROJ-19 #28).

Read-only Aggregat über den Session-Live-Index (PROJ-14). ``cost_status`` macht
die Kosten-Lage explizit: ``complete`` (echte Kosten, nur Claude), ``partial``
(gemischt) oder ``none`` (keine echten Kosten → Frontend zeigt „n/v").
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UsageRange = Literal["today", "7d", "30d", "all"]
CostStatus = Literal["complete", "partial", "none"]


class UsageGroup(BaseModel):
    key: str = Field(..., description="Gruppen-Schlüssel (Projektpfad bzw. Modell-Label).")
    label: str
    tokens: int
    cost_usd: float
    cost_status: CostStatus
    session_count: int


class UsageSummary(BaseModel):
    range: UsageRange
    session_count: int
    total_tokens: int
    total_cost_usd: float
    cost_status: CostStatus
    # PROJ-19 (#27): Prompt-Cache-Sichtbarkeit.
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_hit_ratio: float = Field(
        default=0.0, description="Anteil cachefähiger Tokens aus dem Cache (read / (read+creation)) in %."
    )
    by_model: list[UsageGroup]
    by_project: list[UsageGroup]


class UsageDrilldownRow(BaseModel):
    session_id: str
    project_path: str
    project_name: str | None = None
    model: str
    engine: str
    role: str | None = None
    abc_phase: str | None = None
    tokens_used: int
    total_cost_usd: float
    cost_status: CostStatus
    created_at: str | None = None


class UsageDrilldown(BaseModel):
    range: UsageRange
    rows: list[UsageDrilldownRow]
