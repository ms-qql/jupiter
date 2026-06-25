"""VPS-Admin Terminal-API (PROJ-43) — read-only Erreichbarkeits-Auskunft.

``/info`` meldet, ob ein ttyd-Terminal-Dienst konfiguriert (``terminal_url``)
und gerade erreichbar ist (kurzer TCP-Connect auf den LOKAL gebundenen ttyd-Port).
Damit kann das Frontend „Dienst aus" (Hinweis+Retry) sauber von „Einbettung
verweigert" (iFrame-Fallback) trennen — kein Crash, keine leere Fläche.

MVP single-user: kein JWT (vgl. ``metrics.py``/``usage.py``). Die URL/Host/Port
kommen AUSSCHLIESSLICH aus der Config — keine Client-Eingabe, keine Shell.
"""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter

from ..config import settings
from ..schemas.terminal import TerminalInfo

router = APIRouter(prefix="/terminal", tags=["terminal"])


async def _probe_reachable(host: str, port: int, timeout: float) -> bool:
    """Kurzer, nicht-blockierender TCP-Connect auf den lokalen ttyd-Port.

    Erfolg → ``True``. Jeder Fehler (Connection refused / Timeout / DNS) →
    ``False`` — NIE eine Exception nach außen (Dienst-aus ist ein normaler
    Zustand, kein 500er).
    """
    if port <= 0:
        return False
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
    except (OSError, asyncio.TimeoutError):
        return False
    # Verbindung sofort wieder schließen — wir wollten nur wissen, ob jemand lauscht.
    writer.close()
    with contextlib.suppress(OSError):
        await writer.wait_closed()
    return True


@router.get("/info", response_model=TerminalInfo)
async def terminal_info() -> TerminalInfo:
    """Konfiguriert? Erreichbar? + einzubettende URL (gleiche Origin, aus Config)."""
    url = settings.terminal_url.strip()
    enabled = bool(url)
    if not enabled:
        # Feature aus → erst gar nicht proben (spart den Socket-Versuch).
        return TerminalInfo(enabled=False, url=None, reachable=False)

    reachable = await _probe_reachable(
        settings.terminal_probe_host,
        settings.terminal_probe_port,
        settings.terminal_probe_timeout_seconds,
    )
    return TerminalInfo(enabled=True, url=url, reachable=reachable)
