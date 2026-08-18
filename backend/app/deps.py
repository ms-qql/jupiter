"""FastAPI-Abhängigkeiten für Auth/Scope (PROJ-25).

``get_current_user`` ist die zentrale Identitäts-Fassade. Sie setzt die
**Soft-Gate**-Strategie des Tech-Designs um:

- **Token vorhanden** → Signatur/exp werden geprüft; gültig → Identität, ungültig
  → 401 (nie Vertrauen in Payload-Claims ohne Signaturprüfung).
- **Kein Token, aber Nutzer existieren** → 401 (geschützte Endpunkte verlangen ein
  gültiges Token, sobald die Instanz „scharf" ist).
- **Kein Token UND leere Nutzerbasis** → anonymer Single-User (``default_owner``).
  Das hält eine frische Installation vor dem Bootstrap rückwärtskompatibel und
  erfüllt die Migration: vor dem Auth angelegte ``owner="dev"``-Artefakte bleiben
  nutzbar, bis der erste Account (mit genau diesem ``user_id``) angelegt ist.

Der ``owner`` kommt damit **immer serverseitig** — entweder aus dem Token oder
(vor Bootstrap) aus der Server-Config; nie aus dem Client-Payload.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import Depends, Header, HTTPException, Request

from .config import settings
from .engine.auth import AuthError, AuthService
from .engine.coordinator import FeatureNotFoundError, _norm_feature_id


@dataclass(frozen=True)
class CurrentUser:
    """Aufgelöste Identität eines Requests. ``user_id`` == ``owner``-Scope."""

    user_id: str
    username: str
    anonymous: bool = False  # True = Vor-Bootstrap-Single-User (kein Token)


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


async def get_current_user(
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth_service),
) -> CurrentUser:
    """Identität des Requests; 401 bei fehlendem/ungültigem Token (scharfe Instanz)."""
    token = _bearer_token(authorization)
    if token:
        try:
            ident = auth.resolve_access(token)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=exc.message) from exc
        return CurrentUser(user_id=ident.user_id, username=ident.username)

    # Kein Token: vor dem Bootstrap anonym erlaubt, danach gesperrt.
    if await auth.has_users():
        raise HTTPException(status_code=401, detail="Nicht angemeldet — gültiges Token erforderlich.")
    return CurrentUser(user_id=settings.default_owner, username=settings.default_owner, anonymous=True)


# --- PROJ-80: einheitliches Owner-/Capability-Gate für Feature-Routen ---------


@dataclass(frozen=True)
class FeaturePrincipal:
    """Aufgelöste Berechtigung für eine Feature-Lauf-Aktion.

    ``kind`` ist ``"capability"`` (Koordinator-Session via eng geschnittenem
    Token), ``"user"`` (angemeldeter Nutzer) oder ``"anonymous"`` (Single-User
    vor dem Bootstrap).
    """

    owner: str
    kind: str
    coordinator_id: str | None = None
    feature_id: str | None = None


async def _resolve_feature_principal(
    feature_id: str | None,
    action: str,
    require_existing: bool,
    request: Request,
    authorization: str | None,
    auth: AuthService,
) -> FeaturePrincipal:
    """Einheitliches Gate für die Feature-Koordinator-Routen.

    Akzeptiert entweder einen gültigen Koordinator-Capability-Token (eng
    geschnitten auf ``feature_id`` + ``action`` + ``owner``) ODER einen
    normalen Access-Token (Owner-Scope gegen den existierenden Feature-Lauf)
    ODER — vor dem Bootstrap/Owner-Loss — anonyme Single-User-Nutzung.

    ``feature_id`` ist optional: Routen ohne Lauf-Bezug (Plan/Dispatch) übergeben
    ``None`` und werden nur auf die ``action`` geprüft (kein Feature-Scope).
    """
    token = _bearer_token(authorization)
    num = _norm_feature_id(feature_id) if feature_id else None
    if token:
        # 1) Capability-Token (Koordinator-Session)
        cap = None
        try:
            cap = auth.resolve_capability(token)
        except AuthError:
            cap = None
        if cap is not None:
            if action not in cap.actions:
                raise HTTPException(
                    status_code=403, detail="Capability-Token deckt Aktion '%s' nicht ab." % action
                )
            if num is not None:
                if cap.feature_id != num:
                    raise HTTPException(
                        status_code=403, detail="Capability-Token gehört zu einem anderen Feature-Lauf."
                    )
                if require_existing:
                    coordinator = _require_feature_run(request, num)
                    if coordinator.state.session_id != cap.coordinator_id:
                        raise HTTPException(
                            status_code=403, detail="Capability-Token gehört zu einem anderen Lauf."
                        )
                    if coordinator.state.owner != cap.owner:
                        raise HTTPException(status_code=403, detail="Capability-Owner stimmt nicht überein.")
            return FeaturePrincipal(
                owner=cap.owner,
                kind="capability",
                coordinator_id=cap.coordinator_id,
                feature_id=cap.feature_id,
            )
        # 2) normaler Access-Token (Browser/Nutzer)
        try:
            ident = auth.resolve_access(token)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=exc.message) from exc
        owner = ident.user_id
        if num is not None and require_existing:
            coordinator = _require_feature_run(request, num)
            if coordinator.state.owner != owner:
                raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Feature-Lauf.")
        return FeaturePrincipal(owner=owner, kind="user")
    # 3) kein Token
    if await auth.has_users():
        raise HTTPException(status_code=401, detail="Nicht angemeldet — gültiges Token erforderlich.")
    return FeaturePrincipal(owner=settings.default_owner, kind="anonymous")


def _require_feature_run(request: Request, num: str):
    svc = request.app.state.feature_coordinator
    try:
        return svc._require_feature(num)
    except FeatureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def feature_access(action: str, *, require_existing: bool = True) -> Callable[..., Awaitable[FeaturePrincipal]]:
    """Factory für eine ``Depends``-fähige Feature-Gate-Abhängigkeit.

    ``action`` ist der Capability-Name (z. B. ``"package_followup"``);
    ``require_existing=False`` für Routen ohne existierenden Lauf (Plan/Dispatch).
    """

    async def _dep(
        feature_id: str | None = None,
        request: Request = None,
        authorization: str | None = Header(default=None),
        auth: AuthService = Depends(get_auth_service),
    ) -> FeaturePrincipal:
        return await _resolve_feature_principal(
            feature_id, action, require_existing, request, authorization, auth
        )

    return _dep
