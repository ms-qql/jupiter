"use client";

import { cn } from "@/lib/utils";
import { COLUMNS, columnFor, railRank, type ColumnKey } from "@/lib/status";
import type { Session } from "@/lib/types";
import { SessionTile } from "./session-tile";

export function KanbanBoard({
  sessions,
  now,
}: {
  sessions: Session[];
  now: number;
}) {
  const byColumn: Record<ColumnKey, Session[]> = {
    arbeitet: [],
    wartet: [],
    review: [],
    fertig: [],
  };
  for (const s of sessions) byColumn[columnFor(s.status)].push(s);
  for (const key of Object.keys(byColumn) as ColumnKey[]) {
    byColumn[key].sort((a, b) => {
      const r = railRank(a.status) - railRank(b.status);
      if (r !== 0) return r;
      return Date.parse(b.last_activity) - Date.parse(a.last_activity);
    });
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      {COLUMNS.map((col) => {
        const items = byColumn[col.key];
        return (
          <div
            key={col.key}
            className={cn(
              "flex min-h-[8rem] flex-col rounded-lg border bg-card/30 p-2",
              col.emphasis
                ? "border-amber-400/40"
                : "border-border",
            )}
          >
            <div className="flex items-center justify-between px-1 py-1.5">
              <span
                className={cn(
                  "text-sm font-medium",
                  col.emphasis && "text-amber-500",
                )}
              >
                {col.title}
              </span>
              <span className="rounded-full bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">
                {items.length}
              </span>
            </div>
            <div className="flex flex-1 flex-col gap-2 pt-1">
              {items.length === 0 ? (
                <p className="px-1 py-3 text-xs text-muted-foreground/60">
                  {col.key === "review"
                    ? "Folgt mit Decision Cards (PROJ-4)"
                    : "—"}
                </p>
              ) : (
                items.map((s) => (
                  <SessionTile key={s.session_id} session={s} now={now} compact />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
