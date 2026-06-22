"""FakeDriver — ein EngineDriver für Tests ohne echte Claude-Session.

Emittiert deterministisch denselben Event-Vertrag wie Claude Code, sodass
Manager-/API-Logik ohne Subprozess und ohne Subscription-Quota testbar ist.
"""
from __future__ import annotations

from app.engine.base import EngineDriver, EventHandler, LaunchSpec
from app.engine.events import StreamEvent


class FakeDriver(EngineDriver):
    def __init__(self) -> None:
        self._on: EventHandler | None = None
        self._alive = True
        self._paused = False
        self._spec: LaunchSpec | None = None
        self.sent: list[str] = []

    @property
    def is_alive(self) -> bool:
        return self._alive

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._on = on_event
        self._spec = spec
        await on_event(
            StreamEvent(
                "system",
                "init",
                {
                    "session_id": spec.session_id,
                    "model": "claude-haiku-4-5-20251001",
                    "permissionMode": spec.permission_mode,
                    "apiKeySource": "none",
                },
            )
        )
        if spec.initial_prompt:
            await self._respond(f"Antwort auf: {spec.initial_prompt}")

    async def send_input(self, text: str) -> None:
        if self._paused:
            raise RuntimeError("Session ist pausiert — keine Eingaben möglich.")
        if not self._alive:
            raise RuntimeError("Session läuft nicht.")
        self.sent.append(text)
        await self._respond(f"Echo: {text}")

    async def pause(self) -> None:
        self._paused = True

    async def stop(self) -> None:
        self._alive = False
        if self._on is not None:
            await self._on(StreamEvent("system", "closed", {}))

    async def _respond(self, text: str) -> None:
        assert self._on is not None and self._spec is not None
        usage = {
            "input_tokens": 100,
            "output_tokens": 10,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        await self._on(
            StreamEvent("assistant", None, {"message": {"content": [{"type": "text", "text": text}], "usage": usage}})
        )
        await self._on(
            StreamEvent(
                "result",
                "success",
                {
                    "is_error": False,
                    "result": text,
                    "num_turns": 1,
                    "total_cost_usd": 0.01,
                    "usage": usage,
                    "modelUsage": {"claude-haiku-4-5-20251001": {"contextWindow": 200000}},
                    "session_id": self._spec.session_id,
                },
            )
        )
