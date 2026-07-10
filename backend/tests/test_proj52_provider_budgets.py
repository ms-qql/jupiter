"""PROJ-52 — Provider-Budget-Snapshot für Claude/Codex."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.engine.provider_budget import ProviderBudgetStore
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
    provider_budget_opencode_5h_tokens = 0
    provider_budget_opencode_week_tokens = 0


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
    defaults = {"claude": _FakeProfile(), "codex": _FakeProfile(), "opencode": _FakeProfile()}
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
        _row(
            session_id="x1",
            engine="codex",
            model="gpt-5.6-terra",
            tokens_used=3000,
            created_at=NOW.isoformat(),
        ),
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


class _FakeStore:
    """Minimaler Store-Stub: liefert den nutzergepflegten Schnappschuss zurück."""

    def __init__(self, values: dict) -> None:
        self._values = values

    def values(self) -> dict:
        return dict(self._values)


@pytest.mark.asyncio
async def test_manual_snapshot_shows_entered_pct_and_reset() -> None:
    # Reale Provider-Zahlen (z. B. aus Claude /usage), vom Nutzer eingetragen.
    store = _FakeStore(
        {
            "claude_5h_pct": 6,
            "claude_5h_reset_at": "2026-06-28T10:39:00Z",
            "claude_week_pct": 44,
            "claude_week_reset_at": "2026-07-01T19:59:00Z",
            # Codex bewusst leer → n/v.
            "codex_5h_pct": None,
            "codex_5h_reset_at": None,
            "codex_week_pct": None,
            "codex_week_reset_at": None,
        }
    )
    svc = _FixedClockService(_FakeRepo([]), registry=_registry(), cfg=_cfg(), store=store)

    snap = await svc.snapshot()
    claude = next(p for p in snap["providers"] if p["provider"] == "claude")
    win5h = next(w for w in claude["windows"] if w["window"] == "5h")
    week = next(w for w in claude["windows"] if w["window"] == "week")
    # Exakt die eingetragenen Werte — keine lokale Schätzung, keine erfundenen Resets.
    assert win5h["used_pct"] == 6.0
    assert win5h["reset_at"].startswith("2026-06-28T10:39:00")
    assert win5h["quality"] == "live"
    assert week["used_pct"] == 44.0
    assert week["reset_at"].startswith("2026-07-01T19:59:00")

    # Leerer Codex-Wert → n/v, kein erfundener Prozentwert.
    codex = next(p for p in snap["providers"] if p["provider"] == "codex")
    assert all(w["used_pct"] is None for w in codex["windows"])
    assert all(w["quality"] == "unavailable" for w in codex["windows"])


@pytest.mark.asyncio
async def test_manual_snapshot_auto_reset_when_no_time_given() -> None:
    store = _FakeStore({"claude_5h_pct": 10, "claude_5h_reset_at": None})
    svc = _FixedClockService(_FakeRepo([]), registry=_registry(), cfg=_cfg(), store=store)

    snap = await svc.snapshot()
    claude = next(p for p in snap["providers"] if p["provider"] == "claude")
    win5h = next(w for w in claude["windows"] if w["window"] == "5h")
    # Ohne Reset-Eingabe: jetzt + 5h (kein Crash, keine negative Restzeit).
    assert win5h["used_pct"] == 10.0
    assert win5h["reset_at"] == (NOW + timedelta(hours=5)).isoformat()


def test_store_save_roundtrip_and_validation(tmp_path) -> None:
    store = ProviderBudgetStore(str(tmp_path / "provider_budgets.yaml"))

    # Frische Datei: alles leer (n/v), Quelle = default.
    snap = store.snapshot()
    assert snap["claude_5h_pct"] is None
    assert snap["source"] == "default"

    # Speichern + Live-Reload: Werte kommen zurück.
    saved = store.save(
        {
            "claude_5h_pct": 6,
            "claude_5h_reset_at": "2026-06-28T10:39:00Z",
            "claude_week_pct": 44,
        }
    )
    assert saved["claude_5h_pct"] == 6.0
    assert saved["claude_week_pct"] == 44.0
    assert store.values()["claude_5h_reset_at"] == "2026-06-28T10:39:00Z"

    # Ungültige Eingaben werden hart abgelehnt (Route → 400).
    with pytest.raises(ValueError):
        store.save({"claude_5h_pct": -1})
    with pytest.raises(ValueError):
        store.save({"claude_5h_reset_at": "kein-datum"})


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
