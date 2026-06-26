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

from fastapi import Depends

from .config import settings
from .db import (
    SessionIndexRepository,
    VideoSummaryRepository,
    build_auth_repo,
    build_session_index_repo,
    build_video_summary_repo,
)
from .deps import get_current_user
from .engine import liveness
from .engine.auth import AuthService
from .engine.base import EngineDriver
from .engine.challenge import ChallengeService
from .engine.consumers import consumer_registry
from .engine.coordinator import CoordinatorService
from .engine.files import FileService
from .engine.git_service import GitService
from .engine.launcher import LauncherService
from .engine.manager import SessionManager
from .engine.md_reader import MdReaderService
from .engine.metrics import MetricsService
from .engine.recovery import RecoveryService
from .engine.scout import ScoutService
from .engine.transcription import TranscriptionService
from .engine.usage import UsageService
from .engine.vault import VaultService
from .engine.video_summary import VideoSummaryWorker
from .routes import (
    agents,
    auth as auth_routes,
    challenge,
    constitution,
    coordinator,
    engines,
    files,
    git,
    md,
    metrics,
    permission,
    projects,
    recovery,
    sessions,
    settings as settings_routes,
    terminal,
    transcription,
    usage,
    vault,
    vault_v1,
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


async def _coordinator_loop(app: FastAPI) -> None:
    """PROJ-22 (M3): niederfrequenter Tick, der eingereihte Flotten-Tickets nachrückt,
    sobald ein Engine-Slot frei wird. Defensiv — ein Fehler je Tick wird geloggt, der
    Loop lebt weiter."""
    interval = settings.coordinator_drain_interval_seconds
    while True:
        try:
            await asyncio.sleep(interval)
            await app.state.coordinator.drain_all()
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001 — Drain-Tick nie fatal (Loop überlebt).
            logger.warning("Koordinator-Drain-Tick fehlgeschlagen — Loop läuft weiter.", exc_info=True)


async def _metrics_loop(app: FastAPI) -> None:
    """PROJ-42: periodischer Host-Metrik-Tick (VPS-Admin). Misst CPU/RAM/Disk/Load/…
    + systemd-Status, cached Snapshot + rollierenden Verlauf in-memory. Defensiv —
    ein Fehler je Tick wird geloggt, der Loop lebt weiter."""
    interval = settings.metrics_poll_interval_seconds
    while True:
        try:
            await asyncio.sleep(interval)
            await app.state.metrics.tick()
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001 — Metrik-Tick nie fatal (Loop überlebt).
            logger.warning("Metrik-Tick fehlgeschlagen — Loop läuft weiter.", exc_info=True)


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
    # PROJ-25: Auth-Persistenz (Konten + Refresh-Register) auf derselben SQLite-Datei.
    auth_repo = build_auth_repo(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # PROJ-14: Persistenz-Seam öffnen + Live-Index rehydrieren (verwaiste
        # Sessions markieren), damit die Übersicht einen Restart übersteht.
        # PROJ-25: Auth-Schema anlegen (Konten/Tokens müssen den Neustart überleben).
        try:
            await auth_repo.init()
        except Exception:  # noqa: BLE001 — Auth-Init defensiv; App startet trotzdem.
            logger.warning("Auth-Persistenz-Init fehlgeschlagen.", exc_info=True)
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
        # PROJ-42: ersten Metrik-Snapshot ziehen, damit /current sofort Daten liefert.
        try:
            await app.state.metrics.startup()
        except Exception:  # noqa: BLE001 — Metriken sind best-effort, App startet trotzdem.
            pass
        # PROJ-27: Hintergrund-Auswerter starten (erkennt Hänger ohne Tool-Gate).
        liveness_task = asyncio.create_task(_liveness_loop(app))
        # PROJ-41: Video-Summary-Worker-Loop (sequenzielle Queue-Abarbeitung).
        video_summary_task = asyncio.create_task(_video_summary_loop(app))
        # PROJ-42: periodischer Host-Metrik-Tick (VPS-Admin).
        metrics_task = asyncio.create_task(_metrics_loop(app))
        # PROJ-22 (M3): Flotten-Warteschlange nachrücken, sobald Slots frei werden.
        coordinator_task = asyncio.create_task(_coordinator_loop(app))
        try:
            yield
        finally:
            for task in (liveness_task, video_summary_task, metrics_task, coordinator_task):
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
            await auth_repo.close()  # PROJ-25

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
    # PROJ-25: Auth-Dienst (JWT-Login + Refresh-Rotation + Bootstrap).
    app.state.auth_repo = auth_repo
    app.state.auth = AuthService(auth_repo, settings)
    if settings.jwt_secret.startswith("dev-only-insecure"):
        logger.warning(
            "JUPITER_JWT_SECRET nicht gesetzt — unsicherer Dev-Default aktiv. "
            "In Prod ein zufälliges Secret (≥ 32 Byte) setzen."
        )
    vault_service = vault_service or VaultService()
    app.state.vault = vault_service
    # PROJ-24: Konsumenten-Registry des geteilten Vault-Dienstes (id+key+Scope, live aus YAML).
    app.state.consumers = consumer_registry
    app.state.md_reader = MdReaderService()
    # PROJ-42: VPS-Admin Host-Metriken (read-only, in-memory Snapshot + Verlauf).
    app.state.metrics = MetricsService()
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
    # PROJ-22: Multi-Agent-Dispatch — Koordinator über dem Session-Treiber + Vault-Vertrag.
    app.state.coordinator = CoordinatorService(app.state.manager, vault_service)
    # PROJ-23: Cross-Agent-Review — Challenge eines Artefakts durch eine andere Engine.
    app.state.challenge = ChallengeService(app.state.manager, vault_service)
    # PROJ-25: geschützte Router verlangen ein gültiges Token (Soft-Gate in
    # ``get_current_user``: vor dem Bootstrap anonym, danach scharf). Ausgenommen:
    # ``/auth`` (eigene Auth), ``/internal`` (Hook-Token), ``/vault/v1`` (Consumer-Key)
    # und ``/sessions`` (per-Route geschützt wegen WebSocket-Stream + Owner-Scope).
    auth_gate = [Depends(get_current_user)]
    app.include_router(auth_routes.router)  # PROJ-25: Login/Refresh/Bootstrap/…
    app.include_router(sessions.router)  # per-Route geschützt (siehe routes/sessions.py)
    app.include_router(constitution.router, dependencies=auth_gate)
    app.include_router(vault.router, dependencies=auth_gate)
    app.include_router(vault_v1.router)  # PROJ-24: geteilter Dienst (eigener Consumer-Key)
    app.include_router(md.router, dependencies=auth_gate)
    app.include_router(metrics.router, dependencies=auth_gate)
    app.include_router(permission.router)  # interner Hook (localhost + hook_token)
    app.include_router(settings_routes.router, dependencies=auth_gate)
    app.include_router(files.router, dependencies=auth_gate)
    app.include_router(git.router, dependencies=auth_gate)
    app.include_router(projects.router, dependencies=auth_gate)
    app.include_router(recovery.router, dependencies=auth_gate)
    app.include_router(engines.router, dependencies=auth_gate)
    app.include_router(usage.router, dependencies=auth_gate)
    app.include_router(agents.router, dependencies=auth_gate)
    app.include_router(transcription.router, dependencies=auth_gate)
    app.include_router(video_summary.router, dependencies=auth_gate)
    app.include_router(coordinator.router, dependencies=auth_gate)
    app.include_router(challenge.router, dependencies=auth_gate)
    app.include_router(terminal.router, dependencies=auth_gate)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
