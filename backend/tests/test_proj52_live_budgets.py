"""PROJ-52 Iteration 2 — Live-Budgets und OpenCode-Go-Kostenbudget."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.engine.provider_budget_live import (
    CodexRolloutProbe,
    LiveWindow,
    latest_rollout_file,
    parse_claude_usage,
    parse_codex_rate_limits,
    read_codex_rate_limits,
)
from app.engine.usage import ProviderBudgetService
from app.schemas.usage import ProviderBudgetSnapshot

NOW = datetime(2026, 6, 28, 9, 0, 0, tzinfo=timezone.utc)

CLAUDE_USAGE_OUTPUT = """You are currently using your subscription to power your Claude Code usage

Current session: 22% used · resets Jun 28, 10:40am (UTC)
Current week (all models): 45% used · resets Jul 1, 8pm (UTC)
Current week (Sonnet only): 3% used · resets Jul 1, 8pm (UTC)

What's contributing to your limits usage?
Last 24h · 259 requests · 5 sessions
"""


# --------------------------------------------------------------------- Claude-Parser


def test_parse_claude_usage_extracts_both_windows() -> None:
    out = parse_claude_usage(CLAUDE_USAGE_OUTPUT, NOW)
    assert set(out) == {"5h", "week"}
    assert out["5h"].used_pct == 22.0
    assert out["week"].used_pct == 45.0
    assert out["5h"].source == "cli_live:claude_usage"


def test_parse_claude_usage_reset_times_utc() -> None:
    out = parse_claude_usage(CLAUDE_USAGE_OUTPUT, NOW)
    assert out["5h"].reset_at == datetime(2026, 6, 28, 10, 40, tzinfo=timezone.utc)
    # "8pm" ohne Minuten → 20:00 UTC.
    assert out["week"].reset_at == datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc)


def test_parse_claude_usage_ignores_sonnet_only_line() -> None:
    # "Current week (all models)" gewinnt; die Sonnet-only-Zeile darf week nicht überschreiben.
    out = parse_claude_usage(CLAUDE_USAGE_OUTPUT, NOW)
    assert out["week"].used_pct == 45.0


def test_parse_claude_usage_empty_on_garbage() -> None:
    assert parse_claude_usage("irgendein anderer Output ohne Quota", NOW) == {}


def test_parse_claude_reset_rolls_year_when_past() -> None:
    # Reset im Januar, jetzt Dezember → nächstes Jahr.
    dec = datetime(2026, 12, 31, 12, 0, tzinfo=timezone.utc)
    out = parse_claude_usage("Current session: 5% used · resets Jan 2, 1:00am (UTC)", dec)
    assert out["5h"].reset_at == datetime(2027, 1, 2, 1, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------- Codex-Parser

CODEX_RATE_LIMITS = {
    "limit_id": "codex",
    "primary": {"used_percent": 20.0, "window_minutes": 300, "resets_at": 1782648751},
    "secondary": {"used_percent": 55.5, "window_minutes": 10080, "resets_at": 1783105392},
    "plan_type": "plus",
}


def test_parse_codex_rate_limits_maps_windows() -> None:
    out = parse_codex_rate_limits(CODEX_RATE_LIMITS, NOW)
    assert out["5h"].used_pct == 20.0
    assert out["week"].used_pct == 55.5
    assert out["5h"].reset_at == datetime.fromtimestamp(1782648751, tz=timezone.utc)
    assert out["week"].source == "cli_live:codex_session"


def test_parse_codex_rate_limits_partial_slot() -> None:
    out = parse_codex_rate_limits({"primary": {"used_percent": 10.0, "window_minutes": 300}}, NOW)
    assert set(out) == {"5h"}
    assert out["5h"].reset_at is None  # kein resets_at → None


def test_read_codex_rate_limits_takes_last_event(tmp_path) -> None:
    f = tmp_path / "rollout-x.jsonl"
    older = {"type": "token_count", "payload": {"rate_limits": {"primary": {"used_percent": 1.0}}}}
    newer = {"type": "token_count", "info": {"rate_limits": {"primary": {"used_percent": 9.0}}}}
    f.write_text(
        json.dumps({"type": "session_meta"}) + "\n"
        + json.dumps(older) + "\n"
        + json.dumps(newer) + "\n",
        encoding="utf-8",
    )
    rl = read_codex_rate_limits(str(f))
    assert rl["primary"]["used_percent"] == 9.0


def test_latest_rollout_file_picks_newest(tmp_path) -> None:
    d = tmp_path / "2026" / "06" / "28"
    d.mkdir(parents=True)
    old = d / "rollout-old.jsonl"
    new = d / "rollout-new.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    new.write_text("{}\n", encoding="utf-8")
    import os

    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))
    assert latest_rollout_file(str(tmp_path)) == str(new)


def test_latest_rollout_file_none_when_empty(tmp_path) -> None:
    assert latest_rollout_file(str(tmp_path)) is None


@pytest.mark.asyncio
async def test_codex_probe_disabled_returns_empty(tmp_path) -> None:
    class _Cfg:
        provider_budget_codex_rollout_enabled = False
        codex_sessions_dir = str(tmp_path)

    assert await CodexRolloutProbe(cfg=_Cfg())(NOW) == {}


# ----------------------------------------------------------------- Service-Integration


class _FakeRepo:
    async def list_all(self) -> list[dict]:
        return []


class _FakeProfile:
    enabled = True
    kind = "engine"

    def availability(self) -> tuple[bool, str | None]:
        return True, None


class _FakeRegistry:
    def get(self, key, *, include_disabled=False):
        return _FakeProfile()


class _Cfg:
    provider_budget_refresh_minutes = 30
    provider_budget_timeout_seconds = 20.0
    provider_budget_force_refresh_min_seconds = 60
    provider_budget_claude_5h_tokens = 0
    provider_budget_claude_week_tokens = 0
    provider_budget_codex_5h_tokens = 0
    provider_budget_codex_week_tokens = 0
    provider_budget_opencode_5h_tokens = 0
    provider_budget_opencode_week_tokens = 0
    provider_budget_opencode_5h_usd = 12.0
    provider_budget_opencode_week_usd = 30.0


class _FixedClock(ProviderBudgetService):
    def _now(self) -> datetime:
        return NOW


def _probe(mapping):
    async def _call(now):
        return mapping
    return _call


@pytest.mark.asyncio
async def test_live_window_takes_precedence_and_is_marked_live() -> None:
    probes = {
        "claude": _probe(
            {
                "5h": LiveWindow(22.0, NOW + timedelta(hours=2), "cli_live:claude_usage"),
                "week": LiveWindow(45.0, NOW + timedelta(days=3), "cli_live:claude_usage"),
            }
        ),
    }
    svc = _FixedClock(_FakeRepo(), registry=_FakeRegistry(), cfg=_Cfg(), live_probes=probes)
    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    claude = next(p for p in snap.providers if p.provider == "claude")
    w5h = next(w for w in claude.windows if w.window == "5h")
    assert w5h.quality == "live"
    assert w5h.used_pct == 22.0
    assert w5h.source == "cli_live:claude_usage"


@pytest.mark.asyncio
async def test_live_window_past_reset_is_stale() -> None:
    probes = {"claude": _probe({"5h": LiveWindow(80.0, NOW - timedelta(minutes=1))})}
    svc = _FixedClock(_FakeRepo(), registry=_FakeRegistry(), cfg=_Cfg(), live_probes=probes)
    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    claude = next(p for p in snap.providers if p.provider == "claude")
    w5h = next(w for w in claude.windows if w.window == "5h")
    assert w5h.quality == "stale"


@pytest.mark.asyncio
async def test_partial_live_falls_back_for_other_window() -> None:
    # Nur 5h live → week ohne Limit/Store → n/v (kein erfundener Wert).
    probes = {"claude": _probe({"5h": LiveWindow(30.0, NOW + timedelta(hours=1))})}
    svc = _FixedClock(_FakeRepo(), registry=_FakeRegistry(), cfg=_Cfg(), live_probes=probes)
    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    claude = next(p for p in snap.providers if p.provider == "claude")
    w5h = next(w for w in claude.windows if w.window == "5h")
    week = next(w for w in claude.windows if w.window == "week")
    assert w5h.quality == "live"
    assert week.quality == "unavailable"


@pytest.mark.asyncio
async def test_failing_probe_degrades_to_fallback() -> None:
    async def _boom(now):
        raise RuntimeError("CLI kaputt")

    svc = _FixedClock(
        _FakeRepo(), registry=_FakeRegistry(), cfg=_Cfg(), live_probes={"claude": _boom}
    )
    # Darf nicht crashen; ohne Limit/Store → n/v.
    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    claude = next(p for p in snap.providers if p.provider == "claude")
    assert all(w.quality == "unavailable" for w in claude.windows)


# --------------------------------------------------------------------- QA-Edge-Cases


def test_parse_claude_usage_over_100_percent_not_truncated() -> None:
    # Acceptance: Überziehung muss als echter Wert > 100 % erscheinen, nicht bei 100 gekappt.
    out = parse_claude_usage("Current session: 105% used · resets Jun 28, 10:40am (UTC)", NOW)
    assert out["5h"].used_pct == 105.0


def test_parse_claude_usage_missing_reset_keeps_pct() -> None:
    # Unparsebarer/fehlender Reset darf den Prozentwert nicht verwerfen.
    out = parse_claude_usage("Current session: 12% used · resets irgendwann bald", NOW)
    assert out["5h"].used_pct == 12.0
    assert out["5h"].reset_at is None


def test_read_codex_rate_limits_skips_garbage_lines(tmp_path) -> None:
    f = tmp_path / "rollout-y.jsonl"
    f.write_text(
        'das ist "rate_limits" aber kein JSON\n'  # enthält Marker, ist aber kaputt → übersprungen
        + json.dumps({"info": {"rate_limits": {"primary": {"used_percent": 7.0}}}}) + "\n",
        encoding="utf-8",
    )
    rl = read_codex_rate_limits(str(f))
    assert rl["primary"]["used_percent"] == 7.0


def test_read_codex_rate_limits_none_when_no_event(tmp_path) -> None:
    f = tmp_path / "rollout-z.jsonl"
    f.write_text(json.dumps({"type": "session_meta"}) + "\n", encoding="utf-8")
    assert read_codex_rate_limits(str(f)) is None


def _row(**over) -> dict:
    base = {"session_id": "s", "engine": "claude", "created_at": NOW.isoformat(), "tokens_used": 0}
    base.update(over)
    return base


def test_endpoint_surfaces_live_values() -> None:
    """Acceptance: echte Live-Werte erscheinen über /usage/provider-budgets als quality=live."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes import usage as usage_route

    class _Repo:
        async def list_all(self):
            return [_row(tokens_used=1000)]

    probes = {"claude": _probe({"5h": LiveWindow(33.0, NOW + timedelta(hours=2), "cli_live:claude_usage")})}
    app = FastAPI()
    app.state.usage = object()
    app.state.provider_budgets = _FixedClock(
        _Repo(), registry=_FakeRegistry(), cfg=_Cfg(), live_probes=probes
    )
    app.include_router(usage_route.router)
    client = TestClient(app)

    body = ProviderBudgetSnapshot.model_validate(client.get("/usage/provider-budgets").json())
    claude = next(p for p in body.providers if p.provider == "claude")
    w5h = next(w for w in claude.windows if w.window == "5h")
    assert w5h.quality == "live"
    assert w5h.used_pct == 33.0


def test_live_window_exposes_no_secret_fields() -> None:
    # Red-Team: das Live-Fenster darf nur die Lagebild-Felder enthalten, keine Tokens/Plan/Keys.
    svc = _FixedClock(_FakeRepo(), registry=_FakeRegistry(), cfg=_Cfg())
    win = svc._live_window(  # noqa: SLF001 — gezielter Whitebox-Check
        type("S", (), {"key": "5h", "label": "5h", "duration": timedelta(hours=5)})(),
        NOW,
        LiveWindow(20.0, NOW + timedelta(hours=1), "cli_live:codex_session"),
    )
    assert set(win) == {
        "window", "label", "used_pct", "used_tokens", "limit_tokens",
        "reset_at", "quality", "source", "updated_at", "error",
    }
    assert win["used_tokens"] is None and win["limit_tokens"] is None


# ------------------------------------------------------------------- OpenCode Go


@pytest.mark.asyncio
async def test_opencode_go_budget_uses_local_turn_costs() -> None:
    class _Repo:
        async def list_all(self):
            return [
                {"engine": "opencode", "created_at": NOW.isoformat(), "total_cost_usd": 3.0},
                {
                    "engine": "opencode",
                    "created_at": (NOW - timedelta(hours=6)).isoformat(),
                    "total_cost_usd": 3.0,
                },
            ]

    svc = _FixedClock(_Repo(), registry=_FakeRegistry(), cfg=_Cfg())
    snap = ProviderBudgetSnapshot.model_validate(await svc.snapshot())
    opencode = next(p for p in snap.providers if p.provider == "opencode")
    w5h = next(w for w in opencode.windows if w.window == "5h")
    week = next(w for w in opencode.windows if w.window == "week")
    assert w5h.quality == "estimated"
    assert w5h.used_pct == 25.0  # 3 / 12 USD
    assert w5h.label == "5h"
    assert w5h.source == "local_cost_estimate:opencode_go"
    assert week.used_pct == 20.0  # 6 / 30 USD
    assert week.label == "Woche"
