"""FastAPI-App für Jupiter (PROJ-1 — Engine-Treiber).

``create_app`` erlaubt das Einschleusen einer alternativen Treiber-Factory
(z. B. FakeDriver in Tests), damit keine echte Claude-Session nötig ist.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from .engine.base import EngineDriver
from .engine.manager import SessionManager
from .routes import constitution, sessions


def create_app(driver_factory: Callable[[], EngineDriver] | None = None) -> FastAPI:
    app = FastAPI(title="Jupiter", version="0.1.0")
    app.state.manager = SessionManager(driver_factory=driver_factory)
    app.include_router(sessions.router)
    app.include_router(constitution.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
