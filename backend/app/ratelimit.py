"""Rate-Limiting (PROJ-25 Hardening).

Begrenzt Brute-Force auf die öffentlichen Auth-Endpunkte (``/auth/login``,
``/auth/bootstrap``, ``/auth/refresh``), seit der Forward-Auth-Perimeter entfernt
wurde und ``/auth/*`` direkt internet-exponiert ist.

**Warum eine Dependency statt slowapi-Decorator:** Dieses Modul nutzt ``from
__future__ import annotations`` (projektweit) → Parameter-Annotations sind Strings.
slowapis ``@limiter.limit`` ersetzt die Route durch einen Wrapper, dessen
``__globals__`` das slowapi-Modul sind; FastAPI kann die String-Annotation
``LoginRequest`` dort nicht auflösen und behandelt den Body fälschlich als
Query-Param (422). Eine Dependency lässt die Endpunkt-Signatur unangetastet und
vermeidet das Problem vollständig.

Caddy ist der einzige Reverse-Proxy davor → die TCP-Verbindung kommt von
``127.0.0.1``. Die echte Client-IP steht in ``X-Forwarded-For`` (Caddy hängt sie
als **letzte** Adresse an); ``_client_ip`` nimmt die letzte XFF-Adresse
(spoof-resistent bei genau einem vertrauenswürdigen Proxy) und fällt sonst auf die
Peer-IP zurück.

Speicher: in-memory — passend für den Single-Prozess-uvicorn. Bei mehreren
Workern/Replikas bräuchte es einen geteilten Store (z. B. Redis).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from .config import settings

_limiter = FixedWindowRateLimiter(MemoryStorage())


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        last = xff.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


def rate_limit(rate: str) -> Callable[[Request], Awaitable[None]]:
    """Baut eine FastAPI-Dependency, die ``rate`` (z. B. ``"5/minute"``) pro
    Client-IP erzwingt. Bei Überschreitung → 429 mit deutscher Meldung. Der
    Endpunkt-Pfad ist Teil des Schlüssels, sodass Login/Bootstrap/Refresh eigene
    Kontingente haben."""
    item = parse(rate)

    async def _dependency(request: Request) -> None:
        if not settings.auth_rate_limit_enabled:
            return
        if not _limiter.hit(item, request.url.path, _client_ip(request)):
            raise HTTPException(
                status_code=429,
                detail="Zu viele Versuche. Bitte einen Moment warten und erneut versuchen.",
            )

    return _dependency
