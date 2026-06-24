"use client";

// PROJ-19 (#28) — Token-/Kosten-Dashboard. Verdichtet die bereits gepollte
// Session-Liste (kein Extra-Request) zu Kennzahlen + Verteilungen je Modell/Projekt
// + Drilldown-Tabelle. Kosten degradieren sauber zu „n/v"/„~" bei Subscription-/
// Fremd-Engines (kein echter Betrag verfügbar).

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { phaseLabel } from "@/lib/status";
import {
  aggregateUsage,
  formatCost,
  formatTokens,
  USAGE_RANGES,
  type UsageGroup,
  type UsageRange,
} from "@/lib/usage";
import type { Session } from "@/lib/types";

export function UsageDashboard({
  sessions,
  nowMs,
}: {
  sessions: Session[];
  nowMs: number;
}) {
  const [range, setRange] = useState<UsageRange>("today");
  const summary = useMemo(
    () => aggregateUsage(sessions, range, nowMs),
    [sessions, range, nowMs],
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Zeitraum-Filter */}
      <div
        className="inline-flex w-fit rounded-md border border-border p-0.5"
        role="tablist"
        aria-label="Zeitraum"
      >
        {USAGE_RANGES.map((r) => (
          <button
            key={r.key}
            role="tab"
            aria-selected={range === r.key}
            onClick={() => setRange(r.key)}
            className={cn(
              "rounded px-3 py-1.5 text-sm font-medium transition-colors",
              range === r.key
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent",
            )}
          >
            {r.label}
          </button>
        ))}
      </div>

      {summary.sessionCount === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card/20 px-4 py-12 text-center text-sm text-muted-foreground">
          Noch keine Verbrauchsdaten in diesem Zeitraum.
        </div>
      ) : (
        <>
          {/* Kennzahlen-Leiste */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <MetricCard label="Tokens" value={formatTokens(summary.totalTokens)} />
            <MetricCard
              label="Kosten (geschätzt)"
              value={formatCost(summary.totalCostUsd, summary.costStatus)}
              note={
                summary.costStatus !== "complete"
                  ? "teilweise ohne echte Kosten (Subscription)"
                  : undefined
              }
            />
            <MetricCard label="Sessions" value={String(summary.sessionCount)} />
          </div>

          {/* Verteilungen */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <DistributionCard title="Tokens je Modell" groups={summary.byModel} />
            <DistributionCard
              title="Tokens je Projekt"
              groups={summary.byProject}
            />
          </div>

          {/* Drilldown */}
          <DrilldownTable sessions={summary.sessions} />
        </>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        {note && <p className="mt-1 text-xs text-muted-foreground">{note}</p>}
      </CardContent>
    </Card>
  );
}

function DistributionCard({
  title,
  groups,
}: {
  title: string;
  groups: UsageGroup[];
}) {
  const max = Math.max(1, ...groups.map((g) => g.tokens));
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2.5">
        {groups.map((g) => (
          <div key={g.key} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="truncate font-medium" title={g.label}>
                {g.label}
              </span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {formatTokens(g.tokens)} · {formatCost(g.costUsd, g.costStatus)}
              </span>
            </div>
            {/* Reiner DOM-Balken — konsistent mit gantt-chart.tsx, keine Chart-Lib. */}
            <div className="h-2 w-full overflow-hidden rounded-sm bg-muted/40">
              <div
                className="h-full rounded-sm bg-primary/60"
                style={{ width: `${(g.tokens / max) * 100}%` }}
                aria-hidden
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function DrilldownTable({ sessions }: { sessions: Session[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">
          Sessions (nach Tokens)
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2 font-medium">Projekt</th>
              <th className="px-4 py-2 font-medium">Rolle / Phase</th>
              <th className="px-4 py-2 font-medium">Modell</th>
              <th className="px-4 py-2 text-right font-medium">Tokens</th>
              <th className="px-4 py-2 text-right font-medium">Kosten</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => {
              const project =
                s.project_name?.trim() ||
                s.project_path.replace(/\/+$/, "").split("/").pop() ||
                s.project_path;
              const roleOrPhase =
                s.role?.trim() ||
                (s.abc_phase ? phaseLabel(s.abc_phase) : null) ||
                "—";
              return (
                <tr
                  key={s.session_id}
                  className="border-b border-border/50 last:border-b-0"
                >
                  <td className="max-w-[14rem] truncate px-4 py-2" title={project}>
                    {project}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{roleOrPhase}</td>
                  <td className="px-4 py-2">
                    <Badge variant="outline">{s.model}</Badge>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {formatTokens(s.tokens_used)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                    {formatCost(
                      s.total_cost_usd,
                      s.engine === "claude" ? "complete" : "none",
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
