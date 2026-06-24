// PROJ-19 (#28) — Token-/Kosten-Dashboard: reine Aggregations-Logik.
//
// Speist sich aus der bereits gepollten Session-Liste (sessions-provider) —
// KEIN Extra-Request, KEINE neue Erhebung (Acceptance Criterion „nutzt vorhandene
// Usage-Daten"). Alle Funktionen sind seiteneffektfrei und nehmen `nowMs` als
// Parameter, damit sie deterministisch testbar bleiben.

import { engineShowsCost, modelLabel, phaseLabel, projectName } from "@/lib/status";
import type { Session, UsageDrilldownRead, UsageSummaryRead } from "@/lib/types";

export type UsageRange = "today" | "7d" | "30d" | "all";

export const USAGE_RANGES: { key: UsageRange; label: string }[] = [
  { key: "today", label: "Heute" },
  { key: "7d", label: "7 Tage" },
  { key: "30d", label: "30 Tage" },
  { key: "all", label: "Gesamt" },
];

/** Kosten-Lage eines Aggregats:
 *  - complete: alle Sessions liefern echte Kosten (nur Claude).
 *  - partial:  einige Sessions liefern Kosten, andere nicht (Subscription/Fremd-Engine).
 *  - none:     keine Session liefert Kosten → Anzeige „n/v". */
export type CostStatus = "complete" | "partial" | "none";

export interface UsageGroup {
  key: string;
  label: string;
  tokens: number;
  costUsd: number;
  costStatus: CostStatus;
  sessionCount: number;
}

/** Eine Drilldown-Zeile — gemeinsame Sicht für Client-Aggregation UND Backend-Antwort. */
export interface UsageRow {
  sessionId: string;
  project: string;
  roleOrPhase: string;
  model: string;
  tokens: number;
  costUsd: number;
  costStatus: CostStatus;
}

export interface UsageSummary {
  range: UsageRange;
  sessionCount: number;
  totalTokens: number;
  totalCostUsd: number;
  costStatus: CostStatus;
  /** PROJ-19 (#27): Prompt-Cache-Sichtbarkeit. */
  cacheReadTokens: number;
  cacheCreationTokens: number;
  cacheHitRatio: number; // % (read / (read+creation))
  byModel: UsageGroup[];
  byProject: UsageGroup[];
  /** Für die Drilldown-Tabelle: nach Tokens absteigend. */
  rows: UsageRow[];
}

function roleOrPhase(role: string | null, phase: string | null): string {
  return role?.trim() || (phase ? phaseLabel(phase) : null) || "—";
}

function sessionToRow(s: Session): UsageRow {
  return {
    sessionId: s.session_id,
    project: s.project_name?.trim() || projectName(s.project_path),
    roleOrPhase: roleOrPhase(s.role, s.abc_phase),
    model: s.model,
    tokens: s.tokens_used,
    costUsd: s.total_cost_usd,
    costStatus: engineShowsCost(s.engine) ? "complete" : "none",
  };
}

/** Untergrenze (ms) des gewählten Zeitraums. „today" = ab lokaler Mitternacht. */
export function rangeStartMs(range: UsageRange, nowMs: number): number {
  if (range === "all") return Number.NEGATIVE_INFINITY;
  if (range === "today") {
    const d = new Date(nowMs);
    d.setHours(0, 0, 0, 0);
    return d.getTime();
  }
  const days = range === "7d" ? 7 : 30;
  return nowMs - days * 86_400_000;
}

/** Sessions auf den Zeitraum eingrenzen (nach `created_at`). */
export function filterByRange(
  sessions: Session[],
  range: UsageRange,
  nowMs: number,
): Session[] {
  const start = rangeStartMs(range, nowMs);
  if (start === Number.NEGATIVE_INFINITY) return sessions;
  return sessions.filter((s) => {
    const t = Date.parse(s.created_at);
    return !Number.isNaN(t) && t >= start;
  });
}

/** Verdichtet eine Session-Gruppe zu einer Zeile (Tokens-Summe + Kosten-Lage). */
function summarizeGroup(
  key: string,
  label: string,
  sessions: Session[],
): UsageGroup {
  const tokens = sessions.reduce((sum, s) => sum + (s.tokens_used || 0), 0);
  const withCost = sessions.filter((s) => engineShowsCost(s.engine));
  const costUsd = withCost.reduce((sum, s) => sum + (s.total_cost_usd || 0), 0);
  const costStatus: CostStatus =
    withCost.length === 0
      ? "none"
      : withCost.length === sessions.length
        ? "complete"
        : "partial";
  return { key, label, tokens, costUsd, costStatus, sessionCount: sessions.length };
}

function groupBy(
  sessions: Session[],
  keyOf: (s: Session) => { key: string; label: string },
): UsageGroup[] {
  const buckets = new Map<string, { label: string; items: Session[] }>();
  for (const s of sessions) {
    const { key, label } = keyOf(s);
    const bucket = buckets.get(key) ?? { label, items: [] };
    bucket.items.push(s);
    buckets.set(key, bucket);
  }
  return Array.from(buckets.entries())
    .map(([key, { label, items }]) => summarizeGroup(key, label, items))
    .sort((a, b) => b.tokens - a.tokens);
}

/** Voll-Aggregat für den gewählten Zeitraum. */
export function aggregateUsage(
  sessions: Session[],
  range: UsageRange,
  nowMs: number,
): UsageSummary {
  const scoped = filterByRange(sessions, range, nowMs);
  const totalTokens = scoped.reduce((sum, s) => sum + (s.tokens_used || 0), 0);
  const withCost = scoped.filter((s) => engineShowsCost(s.engine));
  const totalCostUsd = withCost.reduce(
    (sum, s) => sum + (s.total_cost_usd || 0),
    0,
  );
  const costStatus: CostStatus =
    withCost.length === 0
      ? "none"
      : withCost.length === scoped.length
        ? "complete"
        : "partial";

  const cacheReadTokens = scoped.reduce((sum, s) => sum + (s.cache_read_tokens || 0), 0);
  const cacheCreationTokens = scoped.reduce((sum, s) => sum + (s.cache_creation_tokens || 0), 0);
  const cacheTotal = cacheReadTokens + cacheCreationTokens;

  return {
    range,
    sessionCount: scoped.length,
    totalTokens,
    totalCostUsd,
    costStatus,
    cacheReadTokens,
    cacheCreationTokens,
    cacheHitRatio: cacheTotal > 0 ? round1((100 * cacheReadTokens) / cacheTotal) : 0,
    byModel: groupBy(scoped, (s) => ({
      key: modelLabel(s.model),
      label: modelLabel(s.model),
    })),
    byProject: groupBy(scoped, (s) => {
      const label = s.project_name?.trim() || projectName(s.project_path);
      return { key: s.project_path, label };
    }),
    rows: [...scoped].sort((a, b) => b.tokens_used - a.tokens_used).map(sessionToRow),
  };
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

/** Adaptiert die Backend-Antworten (`/usage/summary` + `/usage/drilldown`, snake_case)
 *  auf dieselbe `UsageSummary`-Sicht wie die Client-Aggregation. So rendert das
 *  Dashboard quellen-unabhängig; der Backend-Pfad liefert zusätzlich die echte
 *  historische Summe + die Cache-Quote. */
export function summaryFromBackend(
  summary: UsageSummaryRead,
  drilldown: UsageDrilldownRead,
): UsageSummary {
  const mapGroup = (g: UsageSummaryRead["by_model"][number]): UsageGroup => ({
    key: g.key,
    label: g.label,
    tokens: g.tokens,
    costUsd: g.cost_usd,
    costStatus: g.cost_status,
    sessionCount: g.session_count,
  });
  return {
    range: summary.range,
    sessionCount: summary.session_count,
    totalTokens: summary.total_tokens,
    totalCostUsd: summary.total_cost_usd,
    costStatus: summary.cost_status,
    cacheReadTokens: summary.cache_read_tokens,
    cacheCreationTokens: summary.cache_creation_tokens,
    cacheHitRatio: summary.cache_hit_ratio,
    byModel: summary.by_model.map(mapGroup),
    byProject: summary.by_project.map(mapGroup),
    rows: drilldown.rows.map((r) => ({
      sessionId: r.session_id,
      project: r.project_name?.trim() || projectName(r.project_path),
      roleOrPhase: roleOrPhase(r.role, r.abc_phase),
      model: r.model,
      tokens: r.tokens_used,
      costUsd: r.total_cost_usd,
      costStatus: r.cost_status,
    })),
  };
}

// --- Formatierung -----------------------------------------------------------

const NUM = new Intl.NumberFormat("de-DE");

export function formatTokens(n: number): string {
  return NUM.format(Math.round(n));
}

/** Kosten-Label je nach Lage: echter Betrag, „~Betrag" (teilweise) oder „n/v". */
export function formatCost(costUsd: number, status: CostStatus): string {
  if (status === "none") return "n/v";
  const prefix = status === "partial" ? "~" : "";
  return `${prefix}$${costUsd.toFixed(2)}`;
}
