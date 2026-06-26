"""Auth-Dienst (PROJ-25) — JWT-Login + Refresh-Rotation + Bootstrap.

Setzt die Leitentscheidung des Tech-Designs um: **Identität kommt ausschließlich
aus dem signierten Token**, der ``owner`` wird serverseitig gesetzt und nie aus
Client-Payloads übernommen.

- **JWT HS256** (``python-jose``): kurzer Access-Token + langer Refresh-Token.
- **Passwort-Hash**: ``bcrypt`` direkt (umgeht die passlib/bcrypt-4.x-Inkompatibilität).
- **Refresh-Register** in SQLite (:mod:`app.db.auth_store`) für **Rotation/Widerruf**:
  jeder Refresh trägt eine ``jti``; beim Einlösen wird die alte ``jti`` widerrufen und
  eine neue ausgegeben — ein gestohlener Refresh wird so beim nächsten legitimen
  Refresh ungültig.
- **Bootstrap**: der erste Account bekommt ``user_id = default_owner`` (heute "dev"),
  damit vor dem Auth angelegte Artefakte (``owner="dev"``) nahtlos diesem Nutzer
  gehören — Migration ohne Datenverlust.

Alle Fehler sind :class:`AuthError` (vom Route-Layer auf HTTP-Codes gemappt).
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from ..db.auth_store import SqliteAuthRepository


class AuthError(Exception):
    """Auth-Fehler mit deutscher Meldung + grobem Code (Route mappt auf HTTP)."""

    def __init__(self, message: str, code: str = "invalid") -> None:
        super().__init__(message)
        self.message = message
        self.code = code  # "invalid" | "exists" | "forbidden" | "credentials"


@dataclass(frozen=True)
class TokenIdentity:
    """Aus einem gültigen Access-Token aufgelöste Identität."""

    user_id: str
    username: str


def _hash_password(password: str) -> str:
    # bcrypt deckelt bei 72 Byte — defensiv kürzen (UTF-8), sonst wirft bcrypt 4.x.
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("ascii")


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    """Geschäftslogik für Login/Refresh/Bootstrap/Logout + Token-Auflösung."""

    def __init__(self, repo: SqliteAuthRepository, settings) -> None:
        self._repo = repo
        self._settings = settings

    # --- Token-Bau / -Prüfung ---------------------------------------------

    def _encode(self, claims: dict, expires: datetime) -> str:
        payload = {**claims, "iat": int(_now().timestamp()), "exp": int(expires.timestamp())}
        return jwt.encode(payload, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm)

    def _decode(self, token: str) -> dict:
        """Signatur + ``exp`` prüfen. Wirft :class:`AuthError` bei Fehlschlag."""
        try:
            return jwt.decode(
                token, self._settings.jwt_secret, algorithms=[self._settings.jwt_algorithm]
            )
        except JWTError as exc:  # ungültige Signatur / abgelaufen / manipuliert
            raise AuthError("Token ungültig oder abgelaufen.", code="credentials") from exc

    def _make_access(self, user: dict) -> str:
        expires = _now() + timedelta(minutes=self._settings.access_token_ttl_minutes)
        return self._encode(
            {"sub": user["user_id"], "username": user["username"], "type": "access"},
            expires,
        )

    async def _make_refresh(self, user: dict) -> str:
        """Refresh-Token ausgeben + im Register hinterlegen (für Rotation/Widerruf)."""
        token_id = uuid.uuid4().hex
        issued = _now()
        expires = issued + timedelta(days=self._settings.refresh_token_ttl_days)
        await self._repo.store_refresh(
            {
                "token_id": token_id,
                "user_id": user["user_id"],
                "issued_at": issued.isoformat(),
                "expires_at": expires.isoformat(),
            }
        )
        return self._encode(
            {"sub": user["user_id"], "username": user["username"], "type": "refresh", "jti": token_id},
            expires,
        )

    def resolve_access(self, token: str) -> TokenIdentity:
        """Access-Token → Identität. Wirft :class:`AuthError` (401-würdig) sonst."""
        claims = self._decode(token)
        if claims.get("type") != "access":
            raise AuthError("Falscher Token-Typ.", code="credentials")
        sub = claims.get("sub")
        if not sub:
            raise AuthError("Token ohne Subjekt.", code="credentials")
        return TokenIdentity(user_id=str(sub), username=str(claims.get("username") or sub))

    # --- Status / Bootstrap -----------------------------------------------

    async def has_users(self) -> bool:
        return (await self._repo.count_users()) > 0

    async def bootstrap(self, username: str, password: str) -> tuple[str, str, dict]:
        """ERSTEN Account anlegen — nur solange die Nutzerbasis leer ist.

        Gibt ``(access_token, refresh_token, user)`` zurück. Wirft, wenn bereits
        Nutzer existieren (kein offener Default-Zugang)."""
        if await self.has_users():
            raise AuthError("Bootstrap nicht möglich — es existiert bereits ein Konto.", code="forbidden")
        self._validate_password(password)
        # Erstes Konto erbt den bisherigen Single-User-Owner → Migration ohne Datenverlust.
        user = {
            "user_id": self._settings.default_owner,
            "username": username.strip(),
            "password_hash": _hash_password(password),
            "status": "active",
            "created_at": _now().isoformat(),
        }
        try:
            await self._repo.create_user(user)
        except sqlite3.IntegrityError as exc:  # Race: paralleler Bootstrap
            raise AuthError("Benutzername bereits vergeben.", code="exists") from exc
        return await self._issue_pair(user)

    async def create_account(self, username: str, password: str) -> dict:
        """WEITEREN Account anlegen (nach dem Bootstrap) — geschützt, vom Route-Layer
        nur für authentifizierte Nutzer erreichbar. Gibt die öffentliche Identität
        zurück (kein Token — der neue Nutzer meldet sich selbst an).

        Deviation ggü. Tech-Design (API Shape C kannte nur Bootstrap/Login): nötig,
        damit ein **zweiter** Nutzer dieselbe Instanz nutzen kann (AC „teamfähig")."""
        self._validate_password(password)
        user = {
            "user_id": uuid.uuid4().hex,
            "username": username.strip(),
            "password_hash": _hash_password(password),
            "status": "active",
            "created_at": _now().isoformat(),
        }
        try:
            await self._repo.create_user(user)
        except sqlite3.IntegrityError as exc:
            raise AuthError("Benutzername bereits vergeben.", code="exists") from exc
        return {"user_id": user["user_id"], "username": user["username"]}

    # --- Login / Refresh / Logout -----------------------------------------

    async def login(self, username: str, password: str) -> tuple[str, str, dict]:
        user = await self._repo.get_user_by_username(username.strip())
        # Konstante Fehlermeldung (kein User-Enumeration-Leak).
        if user is None or not _verify_password(password, user["password_hash"]):
            raise AuthError("Anmeldung fehlgeschlagen — Benutzername oder Passwort falsch.", code="credentials")
        if user.get("status") != "active":
            raise AuthError("Konto ist gesperrt.", code="forbidden")
        return await self._issue_pair(user)

    async def refresh(self, refresh_token: str | None) -> tuple[str, str, dict]:
        """Gültigen Refresh einlösen → neuer Access + **rotierter** Refresh.

        Validiert Signatur/exp/Typ UND das Register (nicht widerrufen, bekannt).
        Die alte ``jti`` wird widerrufen (Rotation)."""
        if not refresh_token:
            raise AuthError("Kein Refresh-Token.", code="credentials")
        claims = self._decode(refresh_token)
        if claims.get("type") != "refresh":
            raise AuthError("Falscher Token-Typ.", code="credentials")
        token_id = claims.get("jti")
        if not token_id:
            raise AuthError("Refresh ohne jti.", code="credentials")
        record = await self._repo.get_refresh(token_id)
        if record is None or int(record.get("revoked") or 0) == 1:
            raise AuthError("Refresh-Token widerrufen oder unbekannt.", code="credentials")
        user = await self._repo.get_user_by_id(str(claims.get("sub")))
        if user is None or user.get("status") != "active":
            raise AuthError("Konto nicht verfügbar.", code="forbidden")
        # Rotation: alten Refresh entwerten, neuen ausgeben.
        await self._repo.revoke_refresh(token_id)
        return await self._issue_pair(user)

    async def logout(self, refresh_token: str | None) -> None:
        """Refresh-Cookie widerrufen (idempotent — fehlender/ungültiger Token = no-op)."""
        if not refresh_token:
            return
        try:
            claims = self._decode(refresh_token)
        except AuthError:
            return
        token_id = claims.get("jti")
        if token_id:
            await self._repo.revoke_refresh(token_id)

    # --- Helfer ------------------------------------------------------------

    async def _issue_pair(self, user: dict) -> tuple[str, str, dict]:
        access = self._make_access(user)
        refresh = await self._make_refresh(user)
        return access, refresh, {"user_id": user["user_id"], "username": user["username"]}

    def _validate_password(self, password: str) -> None:
        if len(password) < self._settings.password_min_length:
            raise AuthError(
                f"Passwort zu kurz — mindestens {self._settings.password_min_length} Zeichen.",
                code="invalid",
            )
