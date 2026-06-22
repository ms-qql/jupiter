"use client";

import { railRank } from "@/lib/status";
import type { Session } from "@/lib/types";
import { SessionTile } from "./session-tile";

export function SessionGrid({
  sessions,
  now,
}: {
  sessions: Session[];
  now: number;
}) {
  const sorted = [...sessions].sort((a, b) => {
    const r = railRank(a.status) - railRank(b.status);
    if (r !== 0) return r;
    return Date.parse(b.last_activity) - Date.parse(a.last_activity);
  });

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {sorted.map((s) => (
        <SessionTile key={s.session_id} session={s} now={now} />
      ))}
    </div>
  );
}
