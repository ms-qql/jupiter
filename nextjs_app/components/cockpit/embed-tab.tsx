"use client";

// PROJ-18 · Integrations-Tiefe 2: iFrame-Einbettung. Eine konfigurierte Web-App
// wird eingebettet angezeigt. Verweigert die Fremdseite die Einbettung
// (X-Frame-Options/CSP — das kontrollieren wir nicht), bleibt der „In neuem Tab
// öffnen"-Knopf als verlässlicher Fallback (Edge-Case der Spec).

import { useState } from "react";
import type { EngineRead } from "@/lib/types";
import { LaunchButton } from "./launch-button";

export function EmbedTab({ engine }: { engine: EngineRead }) {
  const [failed, setFailed] = useState(false);
  if (!engine.url) return null;

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="truncate text-sm font-medium">{engine.label}</span>
        <LaunchButton label="In neuem Tab öffnen" target={engine.url} />
      </div>

      {failed ? (
        <p className="px-3 py-8 text-center text-sm text-muted-foreground">
          {`„${engine.label}“ verweigert die Einbettung (X-Frame-Options/CSP). Nutze „In neuem Tab öffnen“.`}
        </p>
      ) : (
        <iframe
          src={engine.url}
          title={engine.label}
          sandbox={engine.sandbox ?? undefined}
          onError={() => setFailed(true)}
          className="h-[60vh] w-full"
        />
      )}

      <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
        {`Lädt die App hier nicht? Manche Seiten verbieten die Einbettung — dann „In neuem Tab öffnen“.`}
      </p>
    </div>
  );
}
