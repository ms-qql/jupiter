"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatDuration, modelLabel, projectName, statusMeta } from "@/lib/status";
import type { Session } from "@/lib/types";
import { Ampel } from "./ampel";

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
  const isError = session.status === "error";

  return (
    <Link
      href={`/sessions/${session.session_id}`}
      className={cn(
        "block rounded-lg border bg-card p-3 transition-colors hover:border-foreground/30",
        isWaiting && "border-amber-400/60 ring-1 ring-amber-400/30",
        isError && "border-red-500/60 ring-1 ring-red-500/20",
        !isWaiting && !isError && "border-border",
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
        <span className={cn(isWaiting && "font-medium text-amber-500")}>
          {meta.label}
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
        <div className="mt-2.5 flex items-center justify-between text-[11px] text-muted-foreground">
          <span className="tabular-nums">
            Kontext {Math.round(session.context_fill_pct)}%
          </span>
          <span className="tabular-nums">
            ${session.total_cost_usd.toFixed(3)}
          </span>
        </div>
      )}
      {!compact && (
        <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              session.context_fill_pct > 85
                ? "bg-red-500"
                : session.context_fill_pct > 60
                  ? "bg-amber-400"
                  : "bg-emerald-500",
            )}
            style={{
              width: `${Math.min(100, Math.max(2, session.context_fill_pct))}%`,
            }}
          />
        </div>
      )}
    </Link>
  );
}
