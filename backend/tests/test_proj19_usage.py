"""PROJ-19 (#28) — Token-/Kosten-Dashboard-Backend.

Deckt die reine Aggregations-Logik (Range-Filter, Gruppierung, Kosten-Lage) sowie
die beiden Endpunkte via FastAPI-TestClient mit einem Fake-Repo ab.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.engine.usage import (
    UsageService,
    aggregate_drilldown,
    aggregate_summary,
    engine_shows_cost,
    filter_by_range,
    range_start,
)
from app.routes import usage as usage_route
from app.schemas.usage import UsageDrilldown, UsageSummary

NOW = datetime(2026, 6, 24, 15, 0, 0, tzinfo=timezone.utc)


def _row(**over) -> dict:
    base = {
        "session_id": "s",
        "owner": "dev",
        "project_path": "/p/alpha",
        "project_name": None,
        "model": "sonnet",
        "engine": "claude",
        "role": None,
        "status": "done",
        "created_at": NOW.isoformat(),
        "tokens_used": 0,
        "total_cost_usd": 0.0,
        "abc_phase": None,
    }
    base.update(over)
    return base


# --- reine Logik ------------------------------------------------------------

def test_engine_shows_cost() -> None:
    assert engine_shows_cost("claude") is True
    assert engine_shows_cost(None) is True  # Default-Engine
    assert engine_shows_cost("openrouter") is False


def test_range_start() -> None:
    assert range_start("all", NOW) is None
    assert range_start("7d", NOW) == NOW - timedelta(days=7)
    assert range_start("today", NOW) == NOW.replace(hour=0, minute=0, second=0, microsecond=0)


def test_filter_by_range() -> None:
    rows = [
        _row(session_id="neu", created_at=NOW.isoformat()),
        _row(session_id="alt", created_at=(NOW - timedelta(days=20)).isoformat()),
    ]
    assert [r["session_id"] for r in filter_by_range(rows, "7d", NOW)] == ["neu"]
    assert len(filter_by_range(rows, "all", NOW)) == 2


def test_summary_groups_and_costs() -> None:
    rows = [
        _row(model="opus", tokens_used=1000, total_cost_usd=0.5),
        _row(model="opus", tokens_used=500, total_cost_usd=0.25),
        _row(model="haiku", tokens_used=200, total_cost_usd=0.01),
    ]
    s = aggregate_summary(rows, "all", NOW)
    assert s["total_tokens"] == 1700
    assert s["total_cost_usd"] == pytest.approx(0.76)
    assert s["cost_status"] == "complete"
    assert [g["label"] for g in s["by_model"]] == ["Opus", "Haiku"]  # nach Tokens
    assert s["by_model"][0]["tokens"] == 1500


def test_cost_status_none_and_partial() -> None:
    none = aggregate_summary([_row(engine="openrouter", tokens_used=100)], "all", NOW)
    assert none["cost_status"] == "none"
    assert none["total_cost_usd"] == 0.0

    mixed = aggregate_summary(
        [_row(engine="claude", total_cost_usd=0.1), _row(engine="openai")], "all", NOW
    )
    assert mixed["cost_status"] == "partial"


def test_project_grouping_label_fallback() -> None:
    rows = [
        _row(project_path="/p/alpha", project_name="Alpha", tokens_used=5),
        _row(project_path="/p/beta", project_name=None, tokens_used=7),
    ]
    s = aggregate_summary(rows, "all", NOW)
    assert s["by_project"][0]["label"] == "beta"  # 7 > 5, Basename-Fallback
    assert s["by_project"][1]["label"] == "Alpha"


def test_drilldown_sorted_and_filtered() -> None:
    rows = [
        _row(session_id="a", model="opus", tokens_used=10),
        _row(session_id="b", model="haiku", tokens_used=99),
        _row(session_id="c", model="opus", tokens_used=50),
    ]
    out = aggregate_drilldown(rows, "all", NOW)
    assert [r["session_id"] for r in out] == ["b", "c", "a"]  # Tokens desc
    only_opus = aggregate_drilldown(rows, "all", NOW, model="Opus")
    assert {r["session_id"] for r in only_opus} == {"a", "c"}


# --- Endpunkte (TestClient + Fake-Repo) -------------------------------------

class _FakeRepo:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def list_all(self) -> list[dict]:
        return list(self._rows)


@pytest.fixture
def client() -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.state.usage = UsageService(
        _FakeRepo(
            [
                _row(session_id="a", model="opus", tokens_used=1000, total_cost_usd=0.5),
                _row(session_id="b", engine="openrouter", model="hermes", tokens_used=200),
            ]
        )
    )
    app.include_router(usage_route.router)
    return TestClient(app)


def test_endpoint_summary(client: TestClient) -> None:
    resp = client.get("/usage/summary", params={"range": "all"})
    assert resp.status_code == 200
    data = UsageSummary.model_validate(resp.json())
    assert data.total_tokens == 1200
    assert data.cost_status == "partial"  # claude + openrouter gemischt


def test_endpoint_drilldown_default_range(client: TestClient) -> None:
    # Default range=today: beide Rows liegen auf NOW (heute relativ zur Testuhr ist
    # serverseitig „jetzt" — created_at = NOW, also evtl. nicht „heute" am Testtag).
    resp = client.get("/usage/drilldown", params={"range": "all"})
    assert resp.status_code == 200
    data = UsageDrilldown.model_validate(resp.json())
    assert [r.session_id for r in data.rows] == ["a", "b"]
    # Fremd-Engine → Kosten n/v
    assert data.rows[1].cost_status == "none"
