"""FastAPI-App für Jupiter (PROJ-1 — Engine-Treiber).

``create_app`` erlaubt das Einschleusen einer alternativen Treiber-Factory
(z. B. FakeDriver in Tests), damit keine echte Claude-Session nötig ist.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .engine.base import EngineDriver
from .engine.manager import SessionManager
from .engine.vault import VaultService
from .routes import constitution, sessions, vault


def create_app(
    driver_factory: Callable[[], EngineDriver] | None = None,
    vault_service: VaultService | None = None,
) -> FastAPI:
    app = FastAPI(title="Jupiter", version="0.1.0")
    # CORS für das Browser-Frontend (PROJ-3 Cockpit). Origins via JUPITER_CORS_ORIGINS
    # konfigurierbar; allow_credentials=True, damit später Cookies/Auth möglich sind.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    vault_service = vault_service or VaultService()
    app.state.vault = vault_service
    app.state.manager = SessionManager(driver_factory=driver_factory, vault=vault_service)
    app.include_router(sessions.router)
    app.include_router(constitution.router)
    app.include_router(vault.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
