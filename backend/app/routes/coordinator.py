"""Koordinator-/Dispatch-API (PROJ-22).

Multi-Agent-Dispatch über dem bestehenden Session-Treiber: Verteilungsplan aus
``features/INDEX.md`` (Human-in-the-Loop), Dispatch in eine Flotte, Live-Sicht,
Pause/Umverteilen und der API-Vertrag als Vault-Artefakt. MVP single-user: kein JWT;
``owner`` wird im Manager gestempelt. Statische Segmente (``/plan``, ``/dispatch``)
stehen vor der dynamischen ``/{coordinator_id}``-Gruppe.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..engine.coordinator import (
    CoordinatorNotFoundError,
    CoordinatorService,
    DispatchDeniedError,
    FeatureCoordinatorService,
    FeatureNotFoundError,
    TicketNotFoundError,
)
from ..engine.manager import EngineUnavailableError, SessionLimitError
from ..schemas.coordinator import (
    CompletionProof,
    ContractRequest,
    CoordinatorFleet,
    CoordinatorPlan,
    CoordinatorPlanRequest,
    DispatchRequest,
    FeatureDecisionRequest,
    FeatureDispatchRequest,
    FeaturePlan,
    FeaturePlanRequest,
    FeatureRun,
    PauseRequest,
    ReassignRequest,
)
from ..schemas.vault import VaultWriteResult

router = APIRouter(prefix="/coordinator", tags=["coordinator"])


def _service(request: Request) -> CoordinatorService:
    return request.app.state.coordinator


def _feature_service(request: Request) -> FeatureCoordinatorService:
    return request.app.state.feature_coordinator


@router.post("/plan", response_model=CoordinatorPlan)
async def coordinator_plan(payload: CoordinatorPlanRequest, request: Request) -> dict:
    """Verteilungsplan erzeugen — startet NICHTS (Human-in-the-Loop)."""
    try:
        return _service(request).plan(payload.project_path)
    except ValueError as exc:  # Pfad außerhalb der erlaubten Roots
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/dispatch", response_model=CoordinatorFleet, status_code=201)
async def coordinator_dispatch(payload: DispatchRequest, request: Request) -> dict:
    """Freigegebenen Plan dispatchen → Koordinator + Spezialisten-Sessions."""
    items = [it.model_dump() for it in payload.items]
    try:
        return await _service(request).dispatch(payload.project_path, items)
    except DispatchDeniedError as exc:  # M1/AC8: Trust-Policy untersagt das Verteilen
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SessionLimitError as exc:  # PROJ-14: schon der Koordinator bekommt keinen Slot
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{coordinator_id}/fleet", response_model=CoordinatorFleet)
async def coordinator_fleet(coordinator_id: str, request: Request) -> dict:
    try:
        return _service(request).fleet(coordinator_id)
    except CoordinatorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{coordinator_id}/pause", response_model=CoordinatorFleet)
async def coordinator_pause(coordinator_id: str, payload: PauseRequest, request: Request) -> dict:
    try:
        return _service(request).set_paused(coordinator_id, payload.paused)
    except CoordinatorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{coordinator_id}/reassign", response_model=CoordinatorFleet)
async def coordinator_reassign(
    coordinator_id: str, payload: ReassignRequest, request: Request
) -> dict:
    try:
        return await _service(request).reassign(
            coordinator_id,
            payload.ticket_id,
            role=payload.role,
            engine=payload.engine,
            model=payload.model,
        )
    except CoordinatorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SessionLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{coordinator_id}/contract", response_model=VaultWriteResult)
async def coordinator_contract(
    coordinator_id: str, payload: ContractRequest, request: Request
) -> dict:
    try:
        return _service(request).set_contract(coordinator_id, payload.body, payload.title)
    except CoordinatorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PermissionError, OSError) as exc:  # Vault nicht schreibbar
        raise HTTPException(status_code=503, detail=f"Vertrag nicht geschrieben (Vault): {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- PROJ-79: Featurezentrierter Koordinator ---------------------------------


@router.post("/feature-plan", response_model=FeaturePlan)
async def coordinator_feature_plan(payload: FeaturePlanRequest, request: Request) -> dict:
    """Internen Verteilungsplan für EIN Feature PROJ-X erzeugen (startet NICHTS)."""
    try:
        return _feature_service(request).feature_plan(payload.project_path, payload.feature_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feature-dispatch", response_model=FeatureRun, status_code=201)
async def coordinator_feature_dispatch(payload: FeatureDispatchRequest, request: Request) -> dict:
    """Freigegebenen Feature-Plan dispatchen → Feature-Ausführung (Koordinator + Pakete)."""
    items = [it.model_dump() for it in payload.items]
    try:
        return await _feature_service(request).feature_dispatch(
            payload.project_path, payload.feature_id, items
        )
    except DispatchDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SessionLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/features/{feature_id}", response_model=FeatureRun)
async def coordinator_feature_run(feature_id: str, request: Request) -> dict:
    try:
        return _feature_service(request).feature_run(feature_id)
    except FeatureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/features/{feature_id}/pause", response_model=FeatureRun)
async def coordinator_feature_pause(
    feature_id: str, payload: PauseRequest, request: Request
) -> dict:
    try:
        return _feature_service(request).feature_set_paused(feature_id, payload.paused)
    except FeatureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/features/{feature_id}/decision", response_model=FeatureRun)
async def coordinator_feature_decision(
    feature_id: str, payload: FeatureDecisionRequest, request: Request
) -> dict:
    try:
        return await _feature_service(request).feature_decision(
            feature_id, payload.action, payload.package_id
        )
    except FeatureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/features/{feature_id}/packages/{package_id}/complete", response_model=FeatureRun)
async def coordinator_package_complete(
    feature_id: str, package_id: str, payload: CompletionProof, request: Request
) -> dict:
    proof = payload.model_dump()
    proof["package_id"] = package_id  # Pfad schlägt Vorrang vor Body
    try:
        return await _feature_service(request).package_complete(feature_id, proof)
    except FeatureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
