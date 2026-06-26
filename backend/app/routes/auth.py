"""Auth-API (PROJ-25) — Login / Refresh / Bootstrap / Logout / Me / Status.

Öffentlich: ``/auth/login``, ``/auth/refresh``, ``/auth/bootstrap``, ``/auth/status``.
Geschützt: ``/auth/me``, ``/auth/logout`` (gültiges Access-Token nötig).

Der Refresh-Token reist als **httpOnly-Cookie** (nie im Body → kein JS-Zugriff,
XSS-Diebstahl erschwert); der Access-Token kommt im Body und lebt im Frontend nur
im Speicher. Alle Texte deutsch.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..config import settings
from ..deps import CurrentUser, get_auth_service, get_current_user
from ..engine.auth import AuthError, AuthService
from ..ratelimit import rate_limit
from ..schemas.auth import (
    AccessTokenResponse,
    AuthStatus,
    LoginRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# AuthError.code → HTTP-Status.
_CODE_STATUS = {
    "credentials": 401,
    "forbidden": 403,
    "exists": 409,
    "invalid": 400,
}


def _http(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=_CODE_STATUS.get(exc.code, 400), detail=exc.message)


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


@router.get("/status", response_model=AuthStatus)
async def auth_status(auth: AuthService = Depends(get_auth_service)) -> dict:
    """Öffentlich: gibt es bereits Konten? Steuert den Bootstrap-Modus im Frontend."""
    return {"has_users": await auth.has_users()}


@router.post(
    "/bootstrap",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("5/minute"))],
)
async def bootstrap(
    payload: LoginRequest, response: Response, auth: AuthService = Depends(get_auth_service)
) -> dict:
    """Ersten Account anlegen — nur bei leerer Nutzerbasis (sonst 403/409)."""
    try:
        access, refresh, user = await auth.bootstrap(payload.username, payload.password)
    except AuthError as exc:
        raise _http(exc) from exc
    _set_refresh_cookie(response, refresh)
    return {"access_token": access, "user": user}


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("5/minute"))],
)
async def login(
    payload: LoginRequest, response: Response, auth: AuthService = Depends(get_auth_service)
) -> dict:
    try:
        access, refresh, user = await auth.login(payload.username, payload.password)
    except AuthError as exc:
        raise _http(exc) from exc
    _set_refresh_cookie(response, refresh)
    return {"access_token": access, "user": user}


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    dependencies=[Depends(rate_limit("30/minute"))],
)
async def refresh(
    request: Request, response: Response, auth: AuthService = Depends(get_auth_service)
) -> dict:
    """Liest den Refresh-Cookie → neuer Access + rotierter Refresh-Cookie."""
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    try:
        access, new_refresh, _user = await auth.refresh(refresh_token)
    except AuthError as exc:
        # Refresh fehlgeschlagen → Cookie räumen (sauberer Logout-Übergang).
        _clear_refresh_cookie(response)
        raise _http(exc) from exc
    _set_refresh_cookie(response, new_refresh)
    return {"access_token": access}


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Refresh-Token widerrufen + Cookie löschen (204)."""
    await auth.logout(request.cookies.get(settings.refresh_cookie_name))
    _clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Aktuelle Identität (geschützt)."""
    return {"user_id": user.user_id, "username": user.username}


@router.post("/users", response_model=UserPublic, status_code=201)
async def create_user(
    payload: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Weiteren Account anlegen (geschützt — angemeldete Nutzer können einen Kollegen
    aufnehmen). Der neue Nutzer meldet sich anschließend selbst an."""
    try:
        return await auth.create_account(payload.username, payload.password)
    except AuthError as exc:
        raise _http(exc) from exc
