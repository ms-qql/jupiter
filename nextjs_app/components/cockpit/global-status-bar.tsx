"use client";

import { cn } from "@/lib/utils";
import { countStatuses } from "@/lib/status";
import type { Session } from "@/lib/types";

export function GlobalStatusBar({ sessions }: { sessions: Session[] }) {
  const c = countStatuses(sessions);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Stat label="Aktiv" value={c.aktiv} dot="bg-emerald-500" />
      <Stat
        label="Wartet auf dich"
        value={c.wartet}
        dot="bg-amber-400"
        emphasis={c.wartet > 0}
      />
      <Stat
        label="Freigabe nötig"
        value={c.freigabe}
        dot="bg-orange-500"
        emphasis={c.freigabe > 0}
      />
      <Stat
        label="Fehler"
        value={c.fehler}
        dot="bg-red-500"
        emphasis={c.fehler > 0}
      />
      <Stat label="Fertig" value={c.fertig} dot="bg-zinc-500" />
    </div>
  );
}

function Stat({
  label,
  value,
  dot,
  emphasis = false,
}: {
  label: string;
  value: number;
  dot: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm",
        emphasis
          ? "border-amber-400/40 bg-amber-400/5"
          : "border-border bg-card",
      )}
    >
      <span className={cn("h-2 w-2 rounded-full", dot)} />
      <span className="tabular-nums font-semibold">{value}</span>
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}
