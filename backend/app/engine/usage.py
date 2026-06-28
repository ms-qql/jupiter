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

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..config import settings
from .registry import ENGINE, engine_registry

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


class BudgetRefreshRateLimited(RuntimeError):
    """Manueller Budget-Refresh wurde zu schnell wiederholt."""


@dataclass(frozen=True)
class _WindowSpec:
    key: str
    label: str
    duration: timedelta
    limit_tokens: int


class ProviderBudgetService:
    """Normalisiert providerseitige Claude-/Codex-Budgetfenster für die Sidebar.

    Es gibt aktuell keine verlässliche, einheitliche maschinenlesbare Quelle für die
    5h-/Wochenlimits beider Subscription-CLIs. Darum ist die Service-Regel bewusst
    konservativ: Live-Adapter können später echte Werte liefern; bis dahin gibt es nur
    markierte Schätzwerte, wenn Quoten explizit konfiguriert sind, sonst ``n/v``.
    """

    PROVIDERS = (
        ("claude", "Claude"),
        ("codex", "Codex"),
    )

    def __init__(self, repo, *, registry=engine_registry, cfg=settings, store=None) -> None:
        self._repo = repo
        self._registry = registry
        self._settings = cfg
        # Live-Quelle der Schätz-Quoten (UI-editierbar, PROJ-52). Ohne Store fallen die
        # Limits auf die env-Felder von ``cfg`` zurück (Rückwärtskompatibilität/Tests).
        self._store = store
        self._snapshot: dict | None = None
        self._snapshot_at: datetime | None = None
        self._last_force_at: datetime | None = None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @property
    def ttl_seconds(self) -> int:
        minutes = max(1, int(self._settings.provider_budget_refresh_minutes))
        return minutes * 60

    def _force_min_seconds(self) -> int:
        return max(0, int(self._settings.provider_budget_force_refresh_min_seconds))

    def _fresh(self, now: datetime) -> bool:
        if self._snapshot is None or self._snapshot_at is None:
            return False
        return (now - self._snapshot_at).total_seconds() < self.ttl_seconds

    def invalidate(self) -> None:
        """Cache verwerfen, damit der nächste Abruf frisch baut (z. B. nach Quoten-Änderung)."""
        self._snapshot = None
        self._snapshot_at = None

    async def snapshot(self) -> dict:
        now = self._now()
        if self._fresh(now):
            return dict(self._snapshot or {})
        return await self._build_snapshot(now)

    async def refresh(self) -> dict:
        now = self._now()
        if (
            self._last_force_at is not None
            and (now - self._last_force_at).total_seconds() < self._force_min_seconds()
        ):
            raise BudgetRefreshRateLimited("Budget wurde gerade aktualisiert.")
        self._last_force_at = now
        return await self._build_snapshot(now)

    async def _build_snapshot(self, now: datetime) -> dict:
        rows = await self._repo.list_all()
        providers = [self._provider_budget(key, label, rows, now) for key, label in self.PROVIDERS]
        warnings = [
            f"{p['label']}: {p['unavailable_reason']}"
            for p in providers
            if p.get("availability") != "available" and p.get("unavailable_reason")
        ]
        snapshot = {
            "updated_at": now.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "providers": providers,
            "warnings": warnings,
        }
        self._snapshot = snapshot
        self._snapshot_at = now
        return snapshot

    def _provider_budget(self, provider: str, label: str, rows: list[dict], now: datetime) -> dict:
        availability, reason = self._availability(provider)
        windows = [self._window_budget(provider, spec, rows, now, availability) for spec in self._windows(provider)]
        return {
            "provider": provider,
            "label": label,
            "availability": availability,
            "unavailable_reason": reason,
            "windows": windows,
        }

    def _availability(self, provider: str) -> tuple[str, str | None]:
        prof = self._registry.get(provider, include_disabled=True)
        if prof is None:
            return "unavailable", "Provider ist nicht konfiguriert."
        if not prof.enabled:
            return "disabled", "Provider ist deaktiviert."
        if prof.kind != ENGINE:
            return "unavailable", "Provider ist keine Session-Engine."
        available, reason = prof.availability()
        if not available:
            return "unavailable", reason or "Provider ist nicht verfügbar."
        return "available", None

    def _windows(self, provider: str) -> list[_WindowSpec]:
        limit_5h, limit_week = self._limits_for(provider)
        return [
            _WindowSpec("5h", "5h", timedelta(hours=5), limit_5h),
            _WindowSpec("week", "Woche", timedelta(days=7), limit_week),
        ]

    def _limits_for(self, provider: str) -> tuple[int, int]:
        """Token-Quoten für (5h, Woche) aus den env-Feldern (Legacy-Schätzpfad, ohne Store)."""
        prefix = f"provider_budget_{provider}"
        return (
            int(getattr(self._settings, f"{prefix}_5h_tokens", 0) or 0),
            int(getattr(self._settings, f"{prefix}_week_tokens", 0) or 0),
        )

    def _window_budget(
        self,
        provider: str,
        spec: _WindowSpec,
        rows: list[dict],
        now: datetime,
        availability: str,
    ) -> dict:
        if availability != "available":
            return self._unavailable_window(spec, now, "Provider nicht verfügbar.")
        # Produktivpfad (PROJ-52): vom Nutzer gepflegter Schnappschuss aus den Einstellungen.
        if self._store is not None:
            return self._manual_window(provider, spec, now)
        # Legacy-Schätzpfad (ohne Store): Verbrauch aus lokalen Tokens / konfigurierter Quote.
        if spec.limit_tokens <= 0:
            return self._unavailable_window(
                spec,
                now,
                "Kein providerseitiges Limit konfiguriert; Prozentwert nicht seriös bestimmbar.",
            )
        scoped = self._rows_for_provider_window(rows, provider, spec, now)
        used = _sum_tokens(scoped)
        used_pct = round(100.0 * used / spec.limit_tokens, 1)
        reset_at = self._reset_at(scoped, spec, now)
        return {
            "window": spec.key,
            "label": spec.label,
            "used_pct": used_pct,
            "used_tokens": used,
            "limit_tokens": spec.limit_tokens,
            "reset_at": reset_at.isoformat(),
            "quality": "estimated",
            "source": "local_usage_estimate",
            "updated_at": now.isoformat(),
            "error": None,
        }

    def _manual_window(self, provider: str, spec: _WindowSpec, now: datetime) -> dict:
        """Fenster aus dem nutzergepflegten Schnappschuss (Prozent + Reset) bauen.

        Leer ⇒ ``n/v`` (keine erfundenen Werte). Der überschrittene Reset wird im
        Frontend automatisch als *veraltet* markiert (resolveWindowQuality).
        """
        values = self._store.values()
        pct = values.get(f"{provider}_{spec.key}_pct")
        if pct is None:
            return self._unavailable_window(
                spec,
                now,
                "Kein Wert gepflegt - in den Einstellungen unter Budget eintragen.",
            )
        reset_raw = values.get(f"{provider}_{spec.key}_reset_at")
        # Python 3.10 fromisoformat kennt kein "Z" → vor dem Parsen normalisieren.
        reset_at = _parse_dt(str(reset_raw).replace("Z", "+00:00")) if reset_raw else None
        if reset_at is None:
            reset_at = now + spec.duration
        return {
            "window": spec.key,
            "label": spec.label,
            "used_pct": round(float(pct), 1),
            "used_tokens": None,
            "limit_tokens": None,
            "reset_at": reset_at.isoformat(),
            "quality": "live",
            "source": "manual_input",
            "updated_at": now.isoformat(),
            "error": None,
        }

    @staticmethod
    def _unavailable_window(spec: _WindowSpec, now: datetime, error: str) -> dict:
        return {
            "window": spec.key,
            "label": spec.label,
            "used_pct": None,
            "used_tokens": None,
            "limit_tokens": spec.limit_tokens if spec.limit_tokens > 0 else None,
            "reset_at": None,
            "quality": "unavailable",
            "source": "none",
            "updated_at": now.isoformat(),
            "error": error,
        }

    @staticmethod
    def _row_engine(row: dict) -> str:
        return str(row.get("engine") or "claude")

    def _rows_for_provider_window(
        self, rows: list[dict], provider: str, spec: _WindowSpec, now: datetime
    ) -> list[dict]:
        start = now - spec.duration
        out = []
        for row in rows:
            if self._row_engine(row) != provider:
                continue
            created_at = _parse_dt(row.get("created_at"))
            if created_at is not None and created_at >= start:
                out.append(row)
        return out

    @staticmethod
    def _reset_at(rows: list[dict], spec: _WindowSpec, now: datetime) -> datetime:
        starts = [_parse_dt(row.get("created_at")) for row in rows]
        starts = [dt for dt in starts if dt is not None]
        if not starts:
            return now + spec.duration
        return min(starts) + spec.duration
