"use client";

// PROJ-18 · Werkzeuge-Panel: listet die konfigurierten iFrame-Einbettungen (Tiefe 2)
// und Startknöpfe (Tiefe 3) aus GET /engines. Steuerbare Engines (Tiefe 1) erscheinen
// dagegen als vollwertige Sessions (Engine-Selector im „Neue Session"-Dialog).

import { useEffect, useState } from "react";
import { getEngines } from "@/lib/api";
import type { EngineRead } from "@/lib/types";
import { EmbedTab } from "./embed-tab";
import { LaunchButton } from "./launch-button";

export function ToolsPanel() {
  const [engines, setEngines] = useState<EngineRead[] | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getEngines(ctrl.signal)
      .then((o) => {
        setEngines(o.engines);
        setWarning(o.warning);
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return;
        setError(e instanceof Error ? e.message : "Fehler");
      });
    return () => ctrl.abort();
  }, []);

  if (error) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        Werkzeuge nicht verfügbar ({error}).
      </p>
    );
  }
  if (!engines) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Lädt…</p>;
  }

  const iframes = engines.filter((e) => e.kind === "iframe");
  const launches = engines.filter((e) => e.kind === "launch");

  if (iframes.length === 0 && launches.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        Keine eingebetteten Apps oder Startknöpfe konfiguriert — pflege sie in{" "}
        <span className="font-mono">config/engines.yaml</span>.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {warning && (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-500">
          Engine-Registry-Warnung: {warning}
        </p>
      )}

      {launches.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">Startknöpfe</h2>
          <div className="flex flex-wrap gap-2">
            {launches.map((e) => (
              <LaunchButton key={e.key} label={e.label} target={e.target ?? ""} />
            ))}
          </div>
        </section>
      )}

      {iframes.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium text-muted-foreground">Eingebettete Apps</h2>
          {iframes.map((e) => (
            <EmbedTab key={e.key} engine={e} />
          ))}
        </section>
      )}
    </div>
  );
}
