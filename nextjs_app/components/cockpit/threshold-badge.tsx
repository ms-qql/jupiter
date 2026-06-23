"use client";

// Warn-Chip (PROJ-5): erscheint, sobald der Kontext-Füllstand die Schwelle erreicht.
// Rein präsentational — die Handover-Aktion liegt daneben (HandoverDialog).

import { AlertTriangleIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function ThresholdBadge({
  thresholdPct,
  compact = false,
  className,
}: {
  thresholdPct: number;
  compact?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-red-500/50 bg-red-500/10 font-medium text-red-500",
        compact ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs",
        className,
      )}
      title={`Kontext-Schwelle (${thresholdPct}%) erreicht — Handover empfohlen`}
    >
      <AlertTriangleIcon className={compact ? "size-3" : "size-3.5"} />
      {compact ? "Schwelle" : `Schwelle ${thresholdPct}% erreicht`}
    </span>
  );
}
