"use client";

// Kontext-Füllstand als Balken (#25, PROJ-5). Zeigt „unbekannt" statt 0 %, solange
// der Treiber keine Token-Daten lieferte, färbt rot ab der wirksamen Schwelle und
// markiert die Schwelle als feine Linie.

import { cn } from "@/lib/utils";
import { contextLabel, gaugeColor } from "@/lib/status";

export function ContextGauge({
  pct,
  known,
  threshold,
  showLabel = true,
  className,
}: {
  pct: number;
  known: boolean;
  threshold: number;
  showLabel?: boolean;
  className?: string;
}) {
  const width = known ? Math.min(100, Math.max(2, pct)) : 0;
  return (
    <div className={className}>
      {showLabel && (
        <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
          <span className="tabular-nums">Kontext {contextLabel(pct, known)}</span>
          <span className="tabular-nums">Schwelle {threshold}%</span>
        </div>
      )}
      <div className="relative h-1 w-full overflow-hidden rounded-full bg-muted">
        {known ? (
          <div
            className={cn("h-full rounded-full transition-all", gaugeColor(pct, threshold))}
            style={{ width: `${width}%` }}
          />
        ) : (
          // „unbekannt": gestreifter, neutraler Balken statt irreführender 0-%-Füllung.
          <div className="h-full w-full bg-[repeating-linear-gradient(45deg,transparent,transparent_4px,var(--color-muted-foreground)_4px,var(--color-muted-foreground)_5px)] opacity-30" />
        )}
        {/* Schwellen-Markierung (nur sinnvoll bei bekannten Daten). */}
        {known && threshold < 100 && (
          <span
            className="absolute top-0 h-full w-px bg-foreground/40"
            style={{ left: `${threshold}%` }}
            aria-hidden
          />
        )}
      </div>
    </div>
  );
}
