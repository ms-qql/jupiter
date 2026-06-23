"""FastAPI-App für Jupiter (PROJ-1 — Engine-Treiber).

``create_app`` erlaubt das Einschleusen einer alternativen Treiber-Factory
(z. B. FakeDriver in Tests), damit keine echte Claude-Session nötig ist.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import SessionIndexRepository, build_session_index_repo
from .engine.base import EngineDriver
from .engine.files import FileService
from .engine.manager import SessionManager
from .engine.md_reader import MdReaderService
from .engine.vault import VaultService
from .routes import constitution, files, md, permission, sessions, settings as settings_routes, vault


def create_app(
    driver_factory: Callable[[], EngineDriver] | None = None,
    vault_service: VaultService | None = None,
    session_index_repo: SessionIndexRepository | None = None,
) -> FastAPI:
    # PROJ-14: Live-Index-Repository (SQLite, host-nativ). Tests können eine
    # eigene/In-Memory-Variante einschleusen; ohne Angabe greift die Settings-Factory.
    repo = session_index_repo or build_session_index_repo(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # PROJ-14: Persistenz-Seam öffnen + Live-Index rehydrieren (verwaiste
        # Sessions markieren), damit die Übersicht einen Restart übersteht.
        try:
            await repo.init()
            await app.state.manager.rehydrate()
        except Exception:  # noqa: BLE001 — Persistenz ist best-effort, App startet trotzdem.
            pass
        yield
        await repo.close()

    app = FastAPI(title="Jupiter", version="0.1.0", lifespan=lifespan)
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
    app.state.md_reader = MdReaderService()
    app.state.files = FileService()
    app.state.session_index_repo = repo
    app.state.manager = SessionManager(
        driver_factory=driver_factory, vault=vault_service, repo=repo
    )
    app.include_router(sessions.router)
    app.include_router(constitution.router)
    app.include_router(vault.router)
    app.include_router(md.router)
    app.include_router(permission.router)
    app.include_router(settings_routes.router)
    app.include_router(files.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
