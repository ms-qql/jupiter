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

from fastapi import Depends, Header, HTTPException, Request

from .config import settings
from .engine.auth import AuthError, AuthService


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
