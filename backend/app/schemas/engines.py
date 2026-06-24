"""Pydantic-v2-Schemas für die Engine-Registry-API (PROJ-18)."""
from __future__ import annotations

from pydantic import BaseModel


class EngineRead(BaseModel):
    """Ein Engine-Eintrag für den Smart Launcher / Tools-Panel.

    Engine-agnostisch + secret-frei: kein API-Key, kein argv. ``available`` steuert
    Ausgrauen, ``unavailable_reason`` liefert den deutschen Setup-Hinweis.
    """

    key: str
    label: str
    kind: str                      # "engine" | "iframe" | "launch"
    driver: str | None = None      # nur bei kind=engine: "claude" | "generic_cli" | "openai"
    available: bool = True
    unavailable_reason: str | None = None
    models: list[str] = []
    default_model: str | None = None
    capabilities: list[str] = []
    url: str | None = None         # iFrame-Quelle (kind=iframe)
    sandbox: str | None = None
    target: str | None = None      # Launch-Ziel (kind=launch)


class EnginesOverview(BaseModel):
    """GET /engines — alle konfigurierten Engines + Registry-Herkunft/Warnung."""

    engines: list[EngineRead]
    source: str
    warning: str | None = None
