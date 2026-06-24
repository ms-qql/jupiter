// PROJ-19 (#28) — Token-/Kosten-Dashboard: reine Aggregations-Logik.
//
// Speist sich aus der bereits gepollten Session-Liste (sessions-provider) —
// KEIN Extra-Request, KEINE neue Erhebung (Acceptance Criterion „nutzt vorhandene
// Usage-Daten"). Alle Funktionen sind seiteneffektfrei und nehmen `nowMs` als
// Parameter, damit sie deterministisch testbar bleiben.

import { engineShowsCost, modelLabel, projectName } from "@/lib/status";
import type { Session } from "@/lib/types";

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

export interface UsageSummary {
  range: UsageRange;
  sessionCount: number;
  totalTokens: number;
  totalCostUsd: number;
  costStatus: CostStatus;
  byModel: UsageGroup[];
  byProject: UsageGroup[];
  /** Für die Drilldown-Tabelle: nach Tokens absteigend sortierte Sessions. */
  sessions: Session[];
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

  return {
    range,
    sessionCount: scoped.length,
    totalTokens,
    totalCostUsd,
    costStatus,
    byModel: groupBy(scoped, (s) => ({
      key: modelLabel(s.model),
      label: modelLabel(s.model),
    })),
    byProject: groupBy(scoped, (s) => {
      const label = s.project_name?.trim() || projectName(s.project_path);
      return { key: s.project_path, label };
    }),
    sessions: [...scoped].sort((a, b) => b.tokens_used - a.tokens_used),
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
