"""FastAPI-App für Jupiter (PROJ-1 — Engine-Treiber).

``create_app`` erlaubt das Einschleusen einer alternativen Treiber-Factory
(z. B. FakeDriver in Tests), damit keine echte Claude-Session nötig ist.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import (
    SessionIndexRepository,
    VideoSummaryRepository,
    build_session_index_repo,
    build_video_summary_repo,
)
from .engine import liveness
from .engine.base import EngineDriver
from .engine.files import FileService
from .engine.git_service import GitService
from .engine.launcher import LauncherService
from .engine.manager import SessionManager
from .engine.md_reader import MdReaderService
from .engine.recovery import RecoveryService
from .engine.scout import ScoutService
from .engine.transcription import TranscriptionService
from .engine.usage import UsageService
from .engine.vault import VaultService
from .engine.video_summary import VideoSummaryWorker
from .routes import (
    agents,
    constitution,
    engines,
    files,
    git,
    md,
    permission,
    projects,
    recovery,
    sessions,
    settings as settings_routes,
    transcription,
    usage,
    vault,
    video_summary,
)


logger = logging.getLogger(__name__)


async def _liveness_loop(app: FastAPI) -> None:
    """PROJ-27: niedrigfrequenter Hintergrund-Poll für den verifizierten Liveness-Zustand.

    Schließt die Lücke des Watchdogs, der nur am Tool-Gate auswertet: eine komplett
    stillstehende Session erreicht nie ein Gate, wird aber hier als „hängt" erkannt und
    (sofern aktiviert) automatisch reanimiert. Defensiv — ein Fehler je Tick wird
    geloggt, der Loop lebt weiter; die Frequenz kommt live aus der Liveness-Config.
    """
    while True:
        interval = liveness.liveness_store.config()["poll_interval_seconds"]
        try:
            await asyncio.sleep(interval)
            await app.state.manager.evaluate_liveness_once()
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001 — Poll-Tick nie fatal (Loop überlebt).
            logger.warning("Liveness-Poll-Tick fehlgeschlagen — Loop läuft weiter.", exc_info=True)


async def _video_summary_loop(app: FastAPI) -> None:
    """PROJ-41: niederfrequenter Worker-Tick, der die Video-Summary-Warteschlange
    sequenziell abarbeitet (Drossel/Cooldown/Zeitplan). Defensiv — ein Fehler je
    Tick wird geloggt, der Loop lebt weiter."""
    interval = settings.video_summary_poll_interval_seconds
    while True:
        try:
            await asyncio.sleep(interval)
            await app.state.video_summary.tick()
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001 — Worker-Tick nie fatal (Loop überlebt).
            logger.warning("Video-Summary-Tick fehlgeschlagen — Loop läuft weiter.", exc_info=True)


def create_app(
    driver_factory: Callable[[], EngineDriver] | None = None,
    vault_service: VaultService | None = None,
    session_index_repo: SessionIndexRepository | None = None,
    engine_factory: Callable[..., EngineDriver] | None = None,
    video_summary_repo: VideoSummaryRepository | None = None,
) -> FastAPI:
    # PROJ-14: Live-Index-Repository (SQLite, host-nativ). Tests können eine
    # eigene/In-Memory-Variante einschleusen; ohne Angabe greift die Settings-Factory.
    repo = session_index_repo or build_session_index_repo(settings)
    # PROJ-41: Warteschlangen-Repo der Video-Summary-Micro-App (eigene SQLite-Datei).
    vs_repo = video_summary_repo or build_video_summary_repo(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # PROJ-14: Persistenz-Seam öffnen + Live-Index rehydrieren (verwaiste
        # Sessions markieren), damit die Übersicht einen Restart übersteht.
        try:
            await repo.init()
            await app.state.manager.rehydrate()
            # PROJ-33: nach geordnetem Drain pausierte Sessions automatisch fortsetzen.
            await app.state.manager.auto_resume_drained()
        except Exception:  # noqa: BLE001 — Persistenz ist best-effort, App startet trotzdem.
            pass
        # PROJ-41: Video-Summary-Warteschlange initialisieren (Schema + verwaiste
        # running→pending) — best-effort, die App startet auch ohne.
        try:
            await app.state.video_summary.startup()
        except Exception:  # noqa: BLE001 — Queue-Persistenz ist best-effort.
            pass
        # PROJ-27: Hintergrund-Auswerter starten (erkennt Hänger ohne Tool-Gate).
        liveness_task = asyncio.create_task(_liveness_loop(app))
        # PROJ-41: Video-Summary-Worker-Loop (sequenzielle Queue-Abarbeitung).
        video_summary_task = asyncio.create_task(_video_summary_loop(app))
        try:
            yield
        finally:
            for task in (liveness_task, video_summary_task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            # PROJ-33: laufende Sessions geordnet drainen (drained_at + persist), BEVOR
            # systemd die Kindprozesse killt → Auto-Resume nach dem Neustart.
            try:
                await app.state.manager.drain()
            except Exception:  # noqa: BLE001 — best-effort; Shutdown darf nie hängen.
                pass
            await repo.close()
            await vs_repo.close()  # PROJ-41

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
    app.state.launcher = LauncherService()
    app.state.files = FileService()
    # PROJ-13: in-App Git-Branch-Handling (Subprozess-Git innerhalb der Roots).
    app.state.git = GitService()
    app.state.session_index_repo = repo
    app.state.manager = SessionManager(
        driver_factory=driver_factory,
        vault=vault_service,
        repo=repo,
        engine_factory=engine_factory,
    )
    # PROJ-17: Recovery-Sicht über Live-Index (verwaiste Stränge) + Vault (Handover/Log).
    app.state.recovery = RecoveryService(app.state.manager, vault_service)
    # PROJ-19 (#28): Token-/Kosten-Aggregat über den persistenten Live-Index.
    app.state.usage = UsageService(repo)
    # PROJ-19 (#26): billige Späher-Agenten (RAG-Kontext + günstiges Modell → nur Fazit).
    app.state.scout = ScoutService(vault_service)
    # PROJ-20: Spracheingabe-Transkription (self-hosted Whisper, optional Groq-Fallback).
    app.state.transcription = TranscriptionService()
    # PROJ-41: Video-Summary-Worker (Warteschlange + Drossel/Cooldown/Zeitplan).
    app.state.video_summary_repo = vs_repo
    app.state.video_summary = VideoSummaryWorker(app.state.manager, vs_repo)
    app.include_router(sessions.router)
    app.include_router(constitution.router)
    app.include_router(vault.router)
    app.include_router(md.router)
    app.include_router(permission.router)
    app.include_router(settings_routes.router)
    app.include_router(files.router)
    app.include_router(git.router)
    app.include_router(projects.router)
    app.include_router(recovery.router)
    app.include_router(engines.router)
    app.include_router(usage.router)
    app.include_router(agents.router)
    app.include_router(transcription.router)
    app.include_router(video_summary.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
