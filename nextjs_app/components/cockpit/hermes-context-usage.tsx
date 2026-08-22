"use client";

// Hermes-Kontextverbrauch (PROJ-85): absolute Werte + zugänglicher Balken mit
// Prozent. Drei Zustände: (1) Daten verfügbar → „18.600 / 256.000 Token · 7 %",
// Balken visuell höchstens 100 %. (2) Nur verbrauchte Tokens bekannt → absoluter
// Wert, Balken/Prozent als „n/v". (3) Gar keine Daten → klarer deutscher
// Nichtverfügbarkeits-Hinweis (ADR-85-3: keine erfundenen Zahlen).

import { cn } from "@/lib/utils";

interface HermesContextUsageProps {
  available: boolean;
  used: number | null;
  window: number | null;
  className?: string;
}

const nf = new Intl.NumberFormat("de-DE");

function pctUsed(used: number, window: number): number {
  if (window <= 0) return 0;
  // Prozent für die Anzeige — geklemmt, Rohwerte bleiben unverfälscht.
  return Math.min(100, Math.round((used / window) * 100));
}

export function HermesContextUsage({
  available,
  used,
  window,
  className,
}: HermesContextUsageProps) {
  // Zustand 3: keine Daten → nur Hinweis.
  if (!available || (used == null && window == null)) {
    return (
      <div className={cn("text-xs text-muted-foreground", className)}>
        Kontextverbrauch nicht verfügbar.
      </div>
    );
  }

  // Zustand 2: nur verbraucht bekannt → absoluter Wert ohne Balken.
  const hasWindow = typeof window === "number" && window > 0;
  if (!hasWindow) {
    return (
      <div className={cn("text-xs text-muted-foreground", className)}>
        <span className="tabular-nums">
          {nf.format(used ?? 0)} Token verbraucht
        </span>
        <span className="ml-1">· Fenster n/v</span>
      </div>
    );
  }

  // Zustand 1: vollständige Werte → absolute Angabe + Balken + Prozent.
  const usedVal = used ?? 0;
  const windowVal = window as number;
  const pct = pctUsed(usedVal, windowVal);
  const width = Math.max(2, pct); // min. sichtbare Füllung, nie > 100

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="tabular-nums">
          {nf.format(usedVal)} / {nf.format(windowVal)} Token
        </span>
        <span className="tabular-nums">{pct} %</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Hermes-Kontextverbrauch"
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full bg-emerald-500 transition-all"
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}
