"""Token-/Kosten-Aggregation (PROJ-19 #28).

Verdichtet den **persistenten Session-Live-Index** (PROJ-14) zu Verbrauchs-
Kennzahlen je Modell/Projekt sowie einem Session-Drilldown. Bewusst read-only und
ohne neue Erhebung: es werden ausschließlich die bereits erfassten Felder
``tokens_used`` / ``total_cost_usd`` / ``model`` / ``engine`` / ``project_*`` /
``created_at`` aus dem Index gelesen (Acceptance Criterion „nutzt vorhandene
Usage-Daten").

Kosten-Degradation: nur die Claude-Engine liefert echte Kosten (vgl. Frontend
``engineShowsCost``). Subscription-/Fremd-Engines → ``cost_status`` „none"/„partial",
das Frontend zeigt dann „n/v"/„~$…" statt falscher Nullen.

Zeitbezug: ``created_at`` ist tz-aware UTC; die Zeitfenster werden in UTC gebildet
(„today" = ab UTC-Mitternacht). Die Aggregation ist seiteneffektfrei und nimmt
``now`` als Parameter, damit sie deterministisch testbar bleibt.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

UsageRange = str  # "today" | "7d" | "30d" | "all"
CostStatus = str  # "complete" | "partial" | "none"


def engine_shows_cost(engine: str | None) -> bool:
    """Nur der Claude-Treiber liefert echte Kosten (PROJ-18-Konvention)."""
    return (engine or "claude") == "claude"


def range_start(range_: UsageRange, now: datetime) -> datetime | None:
    """Untergrenze des Zeitfensters (None = unbegrenzt/„all")."""
    if range_ == "all":
        return None
    if range_ == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = 7 if range_ == "7d" else 30
    return now - timedelta(days=days)


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    # Naive Altdaten defensiv als UTC interpretieren.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def filter_by_range(rows: list[dict], range_: UsageRange, now: datetime) -> list[dict]:
    start = range_start(range_, now)
    if start is None:
        return list(rows)
    out = []
    for r in rows:
        dt = _parse_dt(r.get("created_at"))
        if dt is not None and dt >= start:
            out.append(r)
    return out


def _cost_status(rows: list[dict]) -> CostStatus:
    if not rows:
        return "none"
    with_cost = sum(1 for r in rows if engine_shows_cost(r.get("engine")))
    if with_cost == 0:
        return "none"
    return "complete" if with_cost == len(rows) else "partial"


def _sum_tokens(rows: list[dict]) -> int:
    return sum(int(r.get("tokens_used") or 0) for r in rows)


def _sum_cost(rows: list[dict]) -> float:
    return sum(
        float(r.get("total_cost_usd") or 0.0)
        for r in rows
        if engine_shows_cost(r.get("engine"))
    )


def _group(rows: list[dict], key_of, label_of) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    labels: dict[str, str] = {}
    for r in rows:
        k = key_of(r)
        buckets.setdefault(k, []).append(r)
        labels.setdefault(k, label_of(r))
    groups = [
        {
            "key": k,
            "label": labels[k],
            "tokens": _sum_tokens(items),
            "cost_usd": round(_sum_cost(items), 4),
            "cost_status": _cost_status(items),
            "session_count": len(items),
        }
        for k, items in buckets.items()
    ]
    groups.sort(key=lambda g: g["tokens"], reverse=True)
    return groups


def _project_label(row: dict) -> str:
    name = (row.get("project_name") or "").strip()
    if name:
        return name
    path = (row.get("project_path") or "").rstrip("/")
    return path.rsplit("/", 1)[-1] or path or "—"


def _model_label(model: str | None) -> str:
    m = (model or "").lower()
    if "haiku" in m:
        return "Haiku"
    if "sonnet" in m:
        return "Sonnet"
    if "opus" in m:
        return "Opus"
    return model or "—"


def _sum_cache(rows: list[dict]) -> tuple[int, int]:
    read = sum(int(r.get("cache_read_tokens") or 0) for r in rows)
    creation = sum(int(r.get("cache_creation_tokens") or 0) for r in rows)
    return read, creation


def aggregate_summary(rows: list[dict], range_: UsageRange, now: datetime) -> dict:
    scoped = filter_by_range(rows, range_, now)
    cache_read, cache_creation = _sum_cache(scoped)
    cache_total = cache_read + cache_creation
    # Cache-Treffer-Quote: Anteil des cachefähigen Prompts, der aus dem Cache kam
    # (read) statt neu geschrieben wurde (creation). Sichtbarkeit der Treffer (#27).
    cache_hit_ratio = round(100.0 * cache_read / cache_total, 1) if cache_total > 0 else 0.0
    return {
        "range": range_,
        "session_count": len(scoped),
        "total_tokens": _sum_tokens(scoped),
        "total_cost_usd": round(_sum_cost(scoped), 4),
        "cost_status": _cost_status(scoped),
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "cache_hit_ratio": cache_hit_ratio,
        "by_model": _group(
            scoped, lambda r: _model_label(r.get("model")), lambda r: _model_label(r.get("model"))
        ),
        "by_project": _group(
            scoped, lambda r: r.get("project_path") or "—", _project_label
        ),
    }


def aggregate_drilldown(
    rows: list[dict],
    range_: UsageRange,
    now: datetime,
    *,
    model: str | None = None,
    project: str | None = None,
) -> list[dict]:
    scoped = filter_by_range(rows, range_, now)
    if model:
        scoped = [r for r in scoped if _model_label(r.get("model")) == model]
    if project:
        scoped = [r for r in scoped if (r.get("project_path") or "") == project]
    scoped.sort(key=lambda r: int(r.get("tokens_used") or 0), reverse=True)
    return [
        {
            "session_id": r.get("session_id"),
            "project_path": r.get("project_path") or "",
            "project_name": r.get("project_name"),
            "model": r.get("model") or "",
            "engine": r.get("engine") or "claude",
            "role": r.get("role"),
            "abc_phase": r.get("abc_phase"),
            "tokens_used": int(r.get("tokens_used") or 0),
            "total_cost_usd": round(float(r.get("total_cost_usd") or 0.0), 4),
            "cost_status": "complete" if engine_shows_cost(r.get("engine")) else "none",
            "created_at": r.get("created_at"),
        }
        for r in scoped
    ]


class UsageService:
    """Liest den persistenten Live-Index und liefert Verbrauchs-Aggregate.

    Quelle ist absichtlich der Index (überlebt Neustart, enthält auch beendete
    Sessions), nicht die In-Memory-Registry. Für laufende Sessions kann der
    Token-Stand minimal nachhängen (Persist bei Zustandswechsel) — fürs
    Kosten-/Verbrauchs-Lagebild unkritisch.
    """

    def __init__(self, repo) -> None:
        self._repo = repo

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def summary(self, range_: UsageRange) -> dict:
        rows = await self._repo.list_all()
        return aggregate_summary(rows, range_, self._now())

    async def drilldown(
        self, range_: UsageRange, *, model: str | None = None, project: str | None = None
    ) -> list[dict]:
        rows = await self._repo.list_all()
        return aggregate_drilldown(rows, range_, self._now(), model=model, project=project)
