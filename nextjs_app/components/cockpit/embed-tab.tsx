"use client";

// PROJ-18 · Integrations-Tiefe 2: iFrame-Einbettung. Eine konfigurierte Web-App
// wird eingebettet angezeigt. Verweigert die Fremdseite die Einbettung
// (X-Frame-Options/CSP — das kontrollieren wir nicht), bleibt der „In neuem Tab
// öffnen"-Knopf als verlässlicher Fallback (Edge-Case der Spec).

import { useState } from "react";
import { RotateCwIcon } from "lucide-react";
import type { EngineRead } from "@/lib/types";
import { cn } from "@/lib/utils";
import { LaunchButton } from "./launch-button";

// `fullHeight` (PROJ-39): Vollbild-Variante für die Orchestration-Route — der
// iFrame füllt die verfügbare Höhe statt fester 60vh. Default bleibt die kompakte
// Karte im Werkzeuge-Panel (PROJ-18).
export function EmbedTab({
  engine,
  fullHeight = false,
  headerLeading,
}: {
  engine: EngineRead;
  fullHeight?: boolean;
  /** PROJ-39: optionaler Slot links im Header (z. B. „← Cockpit" der Route) —
   *  vermeidet eine zweite, redundante Kopfzeile über der Einbettung. */
  headerLeading?: React.ReactNode;
}) {
  const [failed, setFailed] = useState(false);
  // Erhöhen → iFrame wird neu gemountet (Retry, z. B. App war offline/Tailscale getrennt).
  const [reloadKey, setReloadKey] = useState(0);

  // QA Low #1 (Stale-Fehlerzustand beim App-Wechsel) ist über `key={engine.key}`
  // an der Aufrufstelle (Route) gelöst — die EmbedTab wird dann frisch gemountet,
  // sodass `failed` automatisch zurückgesetzt ist.
  if (!engine.url) return null;

  const retry = () => {
    setFailed(false);
    setReloadKey((k) => k + 1);
  };

  return (
    <div
      className={cn(
        "overflow-hidden border border-border bg-card",
        fullHeight ? "flex h-full flex-col rounded-none border-x-0" : "rounded-lg",
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="flex min-w-0 items-center gap-3">
          {headerLeading}
          <span className="truncate text-sm font-medium">{engine.label}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={retry}
            title="Erneut laden"
            aria-label="App erneut laden"
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-2 text-sm font-medium transition-colors hover:border-foreground/30"
          >
            <RotateCwIcon className="size-3.5" />
            Erneut laden
          </button>
          <LaunchButton label="In neuem Tab öffnen" target={engine.url} />
        </div>
      </div>

      {failed ? (
        <p
          className={cn(
            "px-3 text-center text-sm text-muted-foreground",
            fullHeight ? "flex flex-1 items-center justify-center" : "py-8",
          )}
        >
          {`„${engine.label}“ verweigert die Einbettung (X-Frame-Options/CSP). Nutze „In neuem Tab öffnen“.`}
        </p>
      ) : (
        <iframe
          key={reloadKey}
          src={engine.url}
          title={engine.label}
          sandbox={engine.sandbox ?? undefined}
          onError={() => setFailed(true)}
          className={cn("w-full", fullHeight ? "min-h-0 flex-1" : "h-[60vh]")}
        />
      )}

      <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
        {`Lädt die App hier nicht? Manche Apps verbieten die Einbettung oder sind offline (Tailscale getrennt?) — dann „Erneut laden“ oder „In neuem Tab öffnen“.`}
      </p>
    </div>
  );
}
