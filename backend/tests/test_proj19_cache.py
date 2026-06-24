"""PROJ-19 (#27) — Prompt-Caching.

Deckt den CacheManager (cache-freundliche Assemblierung, Inhalts-Hash/Invalidierung,
No-op-Fallback bei deaktiviertem Feature) sowie die kumulative Cache-Token-Sichtbarkeit
im Usage-Aggregat ab.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.engine.cache_manager import CacheManager
from app.engine.constitution import combine_with_extra
from app.engine.usage import aggregate_summary

NOW = datetime(2026, 6, 24, 15, 0, 0, tzinfo=timezone.utc)


# --- CacheManager -----------------------------------------------------------

def test_plan_assembly_matches_combine_with_extra() -> None:
    """Verhalten unverändert: gleicher Prompt wie der bisherige combine_with_extra."""
    cm = CacheManager(enabled=True)
    stable, extra = "KONSTITUTION", "Seed-Kontext"
    assert cm.plan(stable, extra).prompt == combine_with_extra(stable, extra)
    assert cm.plan(stable, None).prompt == combine_with_extra(stable, None)
    # Stabiles Präfix kommt zuerst (cache-freundlich).
    assert cm.plan(stable, extra).prompt.startswith(stable)


def test_plan_key_is_content_hash_and_invalidates() -> None:
    cm = CacheManager(enabled=True)
    a = cm.plan("Rolle A Konstitution", "seed")
    b = cm.plan("Rolle A Konstitution", "anderer seed")  # nur variabler Teil ändert sich
    c = cm.plan("Rolle B Konstitution", "seed")  # stabiler Teil ändert sich → Invalidierung
    assert a.cache_key == b.cache_key  # Key hängt NUR am stabilen Präfix
    assert a.cache_key != c.cache_key
    assert a.cache_key is not None and len(a.cache_key) == 16


def test_plan_disabled_is_noop_fallback() -> None:
    off = CacheManager(enabled=False)
    plan = off.plan("KONSTITUTION", "seed")
    assert plan.enabled is False
    assert plan.cache_key is None
    # Prompt bleibt identisch — kein Hard-Fail, nur ohne Cache-Key.
    assert plan.prompt == combine_with_extra("KONSTITUTION", "seed")


def test_plan_empty_stable_no_key() -> None:
    cm = CacheManager(enabled=True)
    plan = cm.plan("", "nur variabel")
    assert plan.cache_key is None
    assert plan.prompt == "nur variabel"


# --- Cache-Sichtbarkeit im Usage-Aggregat -----------------------------------

def _row(**over) -> dict:
    base = {
        "session_id": "s",
        "engine": "claude",
        "model": "sonnet",
        "project_path": "/p/a",
        "created_at": NOW.isoformat(),
        "tokens_used": 100,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "total_cost_usd": 0.0,
    }
    base.update(over)
    return base


def test_summary_exposes_cache_hit_ratio() -> None:
    rows = [
        _row(cache_read_tokens=900, cache_creation_tokens=100),
        _row(cache_read_tokens=0, cache_creation_tokens=0),
    ]
    s = aggregate_summary(rows, "all", NOW)
    assert s["cache_read_tokens"] == 900
    assert s["cache_creation_tokens"] == 100
    assert s["cache_hit_ratio"] == 90.0  # 900 / (900+100)


def test_summary_cache_ratio_zero_without_cache() -> None:
    s = aggregate_summary([_row()], "all", NOW)
    assert s["cache_hit_ratio"] == 0.0


# --- Manager: Cache-Tokens werden über result-Events akkumuliert ------------

import pytest  # noqa: E402

from app.engine.events import StreamEvent  # noqa: E402
from app.engine.manager import SessionManager  # noqa: E402

from .fakes import FakeDriver  # noqa: E402

PROJECT = "/home/dev/projects/jupiter"


def _result(cache_read: int, cache_creation: int) -> StreamEvent:
    return StreamEvent("result", "success", {"is_error": False, "num_turns": 1, "usage": {
        "input_tokens": 30, "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation, "output_tokens": 15},
        "modelUsage": {"m": {"contextWindow": 200_000}}})


@pytest.mark.asyncio
async def test_manager_accumulates_cache_tokens() -> None:
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    await rt.handle_event(_result(cache_read=1000, cache_creation=200))
    await rt.handle_event(_result(cache_read=500, cache_creation=0))
    assert rt.state.cache_read_tokens == 1500
    assert rt.state.cache_creation_tokens == 200
    # Caching ist per Default an → stabiles Präfix erzeugt einen Cache-Key.
    assert rt.state.cache_key is not None
