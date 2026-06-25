"""Cross-Agent-Review-/Challenge-API (PROJ-23).

Eine Challenge auf einem Artefakt startet eine Reviewer-Session (möglichst andere
Engine), die adversariell prüft; die Befunde kommen strukturiert als
``review_finding``-Cards zurück und liegen als Audit-Spur im Vault. Der Reviewer
ändert das Artefakt nie — „Übernehmen"/„Mit Kommentar zurück" reichen den Befund an
die Autor-Session. MVP single-user: kein JWT; ``owner`` wird im Manager gestempelt.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..engine.challenge import (
    AuthorSessionNotFoundError,
    ChallengeError,
    ChallengeService,
    FindingNotFoundError,
    ReviewNotFoundError,
    RoundLimitError,
)
from ..engine.manager import EngineUnavailableError, SessionLimitError
from ..schemas.challenge import (
    ChallengeRequest,
    FindingDecision,
    FindingRead,
    ReviewRead,
)

router = APIRouter(tags=["challenge"])


def _service(request: Request) -> ChallengeService:
    return request.app.state.challenge


@router.post("/sessions/{session_id}/challenge", response_model=ReviewRead, status_code=201)
async def start_challenge(session_id: str, payload: ChallengeRequest, request: Request) -> dict:
    """Challenge auf einem Artefakt der Autor-Session starten → Reviewer-Session."""
    try:
        return await _service(request).start(
            session_id,
            artifact_pointer=payload.artifact_pointer,
            reviewer_engine=payload.reviewer_engine,
            focus=payload.focus,
        )
    except AuthorSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RoundLimitError as exc:  # Rundenlimit → an den Menschen eskalieren
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SessionLimitError as exc:  # PROJ-14: kein freier Slot für die Reviewer-Session
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except EngineUnavailableError as exc:  # Reviewer-Engine fehlt CLI/API-Key
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ChallengeError as exc:  # ungültige Engine o. Ä.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:  # ungültiger Pfad / Modell
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/reviews", response_model=list[ReviewRead])
async def list_reviews(session_id: str, request: Request) -> list[dict]:
    """Reviews, in denen diese Session die Autor-Session ist (Befunde werden lazy eingesammelt)."""
    return _service(request).reviews_for(session_id)


@router.get("/reviews/{review_id}", response_model=ReviewRead)
async def get_review(review_id: str, request: Request) -> dict:
    try:
        return _service(request).get_review(review_id)
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reviews/{review_id}/findings/{finding_id}", response_model=FindingRead)
async def resolve_finding(
    review_id: str, finding_id: str, payload: FindingDecision, request: Request
) -> dict:
    """Pro Befund entscheiden: übernehmen / verwerfen / mit Kommentar zurück."""
    try:
        return await _service(request).resolve_finding(
            review_id, finding_id, payload.action, payload.comment
        )
    except (ReviewNotFoundError, FindingNotFoundError, AuthorSessionNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChallengeError as exc:  # Autor-Session beschäftigt / ungültige action
        raise HTTPException(status_code=409, detail=str(exc)) from exc
