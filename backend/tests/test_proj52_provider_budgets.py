"""PROJ-52 — Provider-Budget-Snapshot für Claude/Codex."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.engine.usage import (
    BudgetRefreshRateLimited,
    ProviderBudgetService,
)
from app.routes import usage as usage_route
from app.schemas.usage import ProviderBudgetSnapshot

NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


def _row(**over) -> dict:
    base = {
        "session_id": "s",
        "engine": "claude",
        "created_at": NOW.isoformat(),
        "tokens_used": 0,
    }
    base.update(over)
    return base


class _FakeRepo:
    def __init__(self, rows: list[dict]) -> None:
        self.calls = 0
        self._rows = rows

    async def list_all(self) -> list[dict]:
        self.calls += 1
        return list(self._rows)


class _FakeProfile:
    def __init__(
        self,
        *,
        enabled: bool = True,
        available: bool = True,
        reason: str | None = None,
    ) -> None:
        self.enabled = enabled
        self.kind = "engine"
        self._available = available
        self._reason = reason

    def availability(self) -> tuple[bool, str | None]:
        return self._available, self._reason


class _FakeRegistry:
    def __init__(self, profiles: dict[str, _FakeProfile | None]) -> None:
        self._profiles = profiles

    def get(self, key: str | None, *, include_disabled: bool = False):
        return self._profiles.get(key or "claude")


class _Cfg:
    provider_budget_refresh_minutes = 30
    provider_budget_timeout_seconds = 10.0
    provider_budget_force_refresh_min_seconds = 60
    provider_budget_claude_5h_tokens = 0
    provider_budget_claude_week_tokens = 0
    provider_budget_codex_5h_tokens = 0
    provider_budget_codex_week_tokens = 0


class _FixedClockService(ProviderBudgetService):
    def __init__(self, *args, now: datetime = NOW, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.now = now

    def _now(self) -> datetime:
        return self.now


def _cfg(**over) -> _Cfg:
    cfg = _Cfg()
    for key, value in over.items():
        setattr(cfg, key, value)
    return cfg


def _registry(**profiles) -> _FakeRegistry:
    defaults = {"claude": _FakeProfile(), "codex": _FakeProfile()}
    defaults.update(profiles)
    return _FakeRegistry(defaults)


@pytest.mark.asyncio
async def test_no_configured_limits_returns_unavailable_quality() -> None:
    svc = _FixedClockService(_FakeRepo([_row(tokens_used=1000)]), registry=_registry(), cfg=_cfg())

    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    claude = next(p for p in snap.providers if p.provider == "claude")

    assert claude.availability == "available"
    assert {w.window for w in claude.windows} == {"5h", "week"}
    assert all(w.quality == "unavailable" for w in claude.windows)
    assert all(w.used_pct is None for w in claude.windows)
    assert "Kein providerseitiges Limit" in (claude.windows[0].error or "")


@pytest.mark.asyncio
async def test_configured_limits_estimate_per_provider_and_window() -> None:
    rows = [
        _row(session_id="c1", engine="claude", tokens_used=1000, created_at=NOW.isoformat()),
        _row(session_id="c2", engine="claude", tokens_used=500, created_at=(NOW - timedelta(hours=6)).isoformat()),
        _row(session_id="x1", engine="codex", tokens_used=3000, created_at=NOW.isoformat()),
    ]
    svc = _FixedClockService(
        _FakeRepo(rows),
        registry=_registry(),
        cfg=_cfg(
            provider_budget_claude_5h_tokens=2000,
            provider_budget_claude_week_tokens=3000,
            provider_budget_codex_5h_tokens=6000,
        ),
    )

    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    by_provider = {p.provider: p for p in snap.providers}
    claude_5h = next(w for w in by_provider["claude"].windows if w.window == "5h")
    claude_week = next(w for w in by_provider["claude"].windows if w.window == "week")
    codex_5h = next(w for w in by_provider["codex"].windows if w.window == "5h")
    codex_week = next(w for w in by_provider["codex"].windows if w.window == "week")

    assert claude_5h.quality == "estimated"
    assert claude_5h.used_tokens == 1000
    assert claude_5h.used_pct == 50.0
    assert claude_week.used_tokens == 1500
    assert claude_week.used_pct == 50.0
    assert codex_5h.used_tokens == 3000
    assert codex_5h.used_pct == 50.0
    assert codex_week.quality == "unavailable"  # keine Wochen-Quote konfiguriert


@pytest.mark.asyncio
async def test_disabled_and_missing_provider_are_reported_without_breaking_other_provider() -> None:
    svc = _FixedClockService(
        _FakeRepo([]),
        registry=_registry(codex=_FakeProfile(enabled=False)),
        cfg=_cfg(provider_budget_claude_5h_tokens=1000),
    )

    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    by_provider = {p.provider: p for p in snap.providers}

    assert by_provider["claude"].availability == "available"
    assert by_provider["codex"].availability == "disabled"
    assert by_provider["codex"].unavailable_reason == "Provider ist deaktiviert."
    assert by_provider["codex"].windows[0].quality == "unavailable"
    assert any("Codex" in warning for warning in snap.warnings)


@pytest.mark.asyncio
async def test_cli_unavailable_reason_is_reported() -> None:
    svc = _FixedClockService(
        _FakeRepo([]),
        registry=_registry(codex=_FakeProfile(available=False, reason="CLI fehlt.")),
        cfg=_cfg(),
    )

    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    codex = next(p for p in snap.providers if p.provider == "codex")

    assert codex.availability == "unavailable"
    assert codex.unavailable_reason == "CLI fehlt."


@pytest.mark.asyncio
async def test_snapshot_uses_cache_until_ttl_expires() -> None:
    repo = _FakeRepo([])
    svc = _FixedClockService(
        repo,
        registry=_registry(),
        cfg=_cfg(provider_budget_claude_5h_tokens=1000),
    )

    await svc.snapshot()
    await svc.snapshot()
    assert repo.calls == 1

    svc.now = NOW + timedelta(minutes=31)
    await svc.snapshot()
    assert repo.calls == 2


@pytest.mark.asyncio
async def test_manual_refresh_is_rate_limited() -> None:
    svc = _FixedClockService(_FakeRepo([]), registry=_registry(), cfg=_cfg())

    await svc.refresh()
    with pytest.raises(BudgetRefreshRateLimited):
        await svc.refresh()


def test_provider_budget_endpoints() -> None:
    app = FastAPI()
    app.state.usage = object()  # nicht genutzt von diesen Endpunkten
    app.state.provider_budgets = _FixedClockService(
        _FakeRepo([_row(tokens_used=1000)]),
        registry=_registry(),
        cfg=_cfg(provider_budget_claude_5h_tokens=2000),
    )
    app.include_router(usage_route.router)
    client = TestClient(app)

    resp = client.get("/usage/provider-budgets")
    assert resp.status_code == 200
    body = ProviderBudgetSnapshot.model_validate(resp.json())
    assert body.providers[0].provider == "claude"

    refresh = client.post("/usage/provider-budgets/refresh")
    assert refresh.status_code == 200
    second = client.post("/usage/provider-budgets/refresh")
    assert second.status_code == 429
