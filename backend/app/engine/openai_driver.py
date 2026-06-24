"""OpenAIDriver (PROJ-18) — die exemplarische zweite Engine über die OpenAI-API.

Beweist die Treiber-Abstraktion aus PROJ-1 jenseits einer CLI: ein **HTTP-getriebener**
Treiber, der dasselbe :class:`EngineDriver`-Interface erfüllt (start/eingeben/pausieren/
stoppen) und seinen Strom auf den internen, Claude-förmigen Event-Vertrag normalisiert —
sodass Cockpit/Kanban/Watchdog/Persistenz **unverändert** und engine-agnostisch greifen.

Bewusste, sauber degradierende Grenzen (eine reine Chat-Engine ohne Claude-Code-Tools):
- **Keine Decision Cards / kein Phasen-Gate**: ohne Tool-Hook gibt es nichts freizugeben.
- **Kein `--resume`**: die Konversation lebt in-memory im Treiber (multi-turn via stdin-loser
  ``send_input``); ein Backend-Neustart beendet sie (wie bei CLI-Engines, PROJ-14).
- **Usage**: OpenAI liefert ``prompt_tokens``/``completion_tokens`` → Token-/Kontext-Anzeige
  funktioniert; Kosten (``total_cost_usd``) liefert die API nicht → bleibt 0 (n/v).

Der API-Key steht NIE im Frontend/der Config — nur der Variablenname (``auth_env``);
den Wert liest dieser Treiber serverseitig aus ``os.environ``.
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable

import httpx

from .base import EngineDriver, EventHandler, LaunchSpec
from .events import StreamEvent

log = logging.getLogger(__name__)

# Netzwerk-Timeout je Turn (großzügig — lange Antworten; verbindet sich der Server nicht,
# greift der Fehlerpfad mit klarer deutscher Meldung statt einem Hänger).
_REQUEST_TIMEOUT = httpx.Timeout(connect=15.0, read=300.0, write=30.0, pool=15.0)

ClientFactory = Callable[[], httpx.AsyncClient]


def _build_usage(prompt_tokens: int, completion_tokens: int) -> dict:
    """OpenAI-Usage → Claude-förmige Usage (damit ``events.extract_usage`` unverändert greift)."""
    return {
        "input_tokens": int(prompt_tokens or 0),
        "output_tokens": int(completion_tokens or 0),
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }


class OpenAIDriver(EngineDriver):
    def __init__(self, profile, client_factory: ClientFactory | None = None) -> None:
        self.profile = profile
        self._on: EventHandler | None = None
        self._spec: LaunchSpec | None = None
        self._alive = True
        self._paused = False
        # In-Memory-Konversation (multi_turn): system + abwechselnd user/assistant.
        self._messages: list[dict] = []
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=_REQUEST_TIMEOUT))

    @property
    def is_alive(self) -> bool:
        return self._alive

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._spec = spec
        self._on = on_event
        # Engine-agnostischer Init (wie Claudes system/init): setzt Status → running.
        await self._emit(
            StreamEvent(
                "system", "init",
                {"session_id": spec.session_id, "model": spec.model, "apiKeySource": "api"},
            )
        )
        if spec.system_prompt_append:
            self._messages.append({"role": "system", "content": spec.system_prompt_append})
        if spec.initial_prompt:
            await self._turn(spec.initial_prompt)

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert — keine Eingaben möglich.")
        if not self._alive:
            raise RuntimeError("Session läuft nicht.")
        await self._turn(text)

    async def pause(self) -> None:
        self._paused = True

    async def stop(self) -> None:
        self._alive = False
        await self._emit(StreamEvent("system", "closed", {}))

    # --- intern -----------------------------------------------------------

    async def _emit(self, event: StreamEvent) -> None:
        if self._on is not None:
            await self._on(event)

    async def _turn(self, text: str) -> None:
        """Einen User-Turn an die API senden, Antwort streamen, als Events normalisieren."""
        assert self._spec is not None
        key = os.environ.get(self.profile.auth_env or "OPENAI_API_KEY")
        if not key:
            await self._error(
                f"API-Key fehlt — {self.profile.auth_env or 'OPENAI_API_KEY'} "
                "in der Server-Umgebung setzen."
            )
            return

        self._messages.append({"role": "user", "content": text})
        url = f"{self.profile.api_base}{self.profile.api_path}"
        payload = {
            "model": self._spec.model,
            "messages": self._messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        content_parts: list[str] = []
        usage: dict | None = None
        try:
            async with self._client_factory() as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", errors="replace")
                        await self._error(self._http_message(resp.status_code, body))
                        return
                    async for line in resp.aiter_lines():
                        delta, chunk_usage, done = _parse_sse_line(line)
                        if delta:
                            content_parts.append(delta)
                        if chunk_usage is not None:
                            usage = chunk_usage
                        if done:
                            break
        except httpx.HTTPError as exc:
            await self._error(f"Netzwerkfehler zur OpenAI-API: {exc}")
            return

        full = "".join(content_parts)
        self._messages.append({"role": "assistant", "content": full})

        # 1) assistant-Event (Volltext + Usage → Kontext-Belegung, wie Claudes Message-Event).
        assistant_raw: dict = {"message": {"content": [{"type": "text", "text": full}]}}
        if usage:
            assistant_raw["message"]["usage"] = _build_usage(
                usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            )
        await self._emit(StreamEvent("assistant", None, assistant_raw))

        # 2) result-Event (Turn fertig → waiting; Usage + Kontextfenster aus dem Profil).
        result_raw: dict = {
            "is_error": False,
            "result": full,
            "num_turns": 1,
            "session_id": self._spec.session_id,
        }
        if usage:
            result_raw["usage"] = _build_usage(
                usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            )
            result_raw["modelUsage"] = {
                self._spec.model: {"contextWindow": self.profile.context_window}
            }
        await self._emit(StreamEvent("result", "success", result_raw))

    async def _error(self, message: str) -> None:
        """Fehler als Claude-förmiges system/error-Event → Status ERROR, Claude bleibt nutzbar."""
        await self._emit(StreamEvent("system", "error", {"message": message}))

    @staticmethod
    def _http_message(status: int, body: str) -> str:
        snippet = body.strip()[:300]
        if status == 401:
            return "OpenAI-API: Authentifizierung fehlgeschlagen (Key ungültig?)."
        if status == 429:
            return "OpenAI-API: Rate-Limit/Quota erreicht — später erneut versuchen."
        if status >= 500:
            return f"OpenAI-API: Serverfehler {status}."
        return f"OpenAI-API: Fehler {status}. {snippet}".strip()


def _parse_sse_line(line: str) -> tuple[str, dict | None, bool]:
    """Parst eine SSE-Zeile der Chat-Completions-API.

    Rückgabe ``(text_delta, usage_oder_None, done)``. Unbekannte/leere Zeilen → leer.
    """
    line = line.strip()
    if not line or not line.startswith("data:"):
        return "", None, False
    data = line[len("data:"):].strip()
    if data == "[DONE]":
        return "", None, True
    try:
        obj = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return "", None, False
    delta = ""
    choices = obj.get("choices") or []
    if choices:
        delta = (choices[0].get("delta") or {}).get("content") or ""
    usage = obj.get("usage") if isinstance(obj.get("usage"), dict) else None
    return delta, usage, False
