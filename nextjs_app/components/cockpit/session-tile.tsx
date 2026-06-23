"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { contextLabel, formatDuration, modelLabel, projectName, statusMeta } from "@/lib/status";
import type { Session } from "@/lib/types";
import { Ampel } from "./ampel";
import { ContextGauge } from "./context-gauge";
import { ThresholdBadge } from "./threshold-badge";

export function SessionTile({
  session,
  now,
  compact = false,
}: {
  session: Session;
  now: number;
  compact?: boolean;
}) {
  const meta = statusMeta(session.status);
  const isWaiting = session.status === "waiting";
  const isAwaiting = session.status === "awaiting_approval";
  const isError = session.status === "error";
  const pendingCount = session.pending_decisions?.length ?? 0;

  return (
    <Link
      href={`/sessions/${session.session_id}`}
      className={cn(
        "block rounded-lg border bg-card p-3 transition-colors hover:border-foreground/30",
        isWaiting && "border-amber-400/60 ring-1 ring-amber-400/30",
        isAwaiting && "border-orange-500/60 ring-1 ring-orange-500/30",
        isError && "border-red-500/60 ring-1 ring-red-500/20",
        !isWaiting && !isAwaiting && !isError && "border-border",
      )}
    >
      <div className="flex items-center gap-2">
        <Ampel color={meta.ampel} />
        <span className="min-w-0 flex-1 truncate font-medium">
          {projectName(session.project_path)}
        </span>
        <Badge variant="secondary" className="shrink-0 text-[10px]">
          {modelLabel(session.model)}
        </Badge>
      </div>

      <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
        <span
          className={cn(
            isWaiting && "font-medium text-amber-500",
            isAwaiting && "font-medium text-orange-500",
          )}
        >
          {isAwaiting && pendingCount > 0
            ? `⚠ ${pendingCount} Freigabe${pendingCount > 1 ? "n" : ""} nötig`
            : meta.label}
        </span>
        {session.role && (
          <>
            <span aria-hidden>·</span>
            <span className="truncate">{session.role}</span>
          </>
        )}
        <span aria-hidden>·</span>
        <span className="tabular-nums">
          {formatDuration(session.created_at, now)}
        </span>
      </div>

      {isError && session.error && (
        <p className="mt-2 line-clamp-2 rounded bg-red-500/10 px-2 py-1 text-xs text-red-400">
          {session.error}
        </p>
      )}

      {!compact && (
        <>
          <div className="mt-2.5 flex items-center justify-between text-[11px] text-muted-foreground">
            <span className="tabular-nums">
              Kontext {contextLabel(session.context_fill_pct, session.context_known)}
            </span>
            {session.threshold_warning ? (
              <ThresholdBadge thresholdPct={session.context_fill_threshold_pct} compact />
            ) : (
              <span className="tabular-nums">${session.total_cost_usd.toFixed(3)}</span>
            )}
          </div>
          <ContextGauge
            pct={session.context_fill_pct}
            known={session.context_known}
            threshold={session.context_fill_threshold_pct}
            showLabel={false}
            className="mt-1"
          />
        </>
      )}
    </Link>
  );
}
