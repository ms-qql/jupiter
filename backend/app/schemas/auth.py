"""Pydantic-Schemas für Auth (PROJ-25 — JWT-Login + Owner-Scope).

Alle Fehlermeldungen/Texte sind deutsch (Projektkonvention). Der ``owner`` kommt
NIE aus diesen Eingaben — er wird serverseitig aus dem Token gesetzt.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Eingabe für ``POST /auth/login`` und ``POST /auth/bootstrap``."""

    username: str = Field(..., min_length=1, max_length=64, description="Benutzername.")
    password: str = Field(..., min_length=1, max_length=256, description="Passwort.")


class UserPublic(BaseModel):
    """Öffentliche Identität (nie Passwort-Hash o. Ä.)."""

    user_id: str
    username: str


class TokenResponse(BaseModel):
    """Antwort von Login/Bootstrap: Access-Token + Identität.

    Der Refresh-Token wird NICHT im Body, sondern als httpOnly-Cookie gesetzt.
    """

    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class AccessTokenResponse(BaseModel):
    """Antwort von ``POST /auth/refresh`` — nur ein neuer Access-Token."""

    access_token: str
    token_type: str = "bearer"


class AuthStatus(BaseModel):
    """Öffentlicher Bootstrap-Check (``GET /auth/status``)."""

    has_users: bool
