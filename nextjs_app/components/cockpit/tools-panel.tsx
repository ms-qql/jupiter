"use client";

// PROJ-18 · Werkzeuge-Panel: listet die konfigurierten iFrame-Einbettungen (Tiefe 2)
// und Startknöpfe (Tiefe 3) aus GET /engines. Steuerbare Engines (Tiefe 1) erscheinen
// dagegen als vollwertige Sessions (Engine-Selector im „Neue Session"-Dialog).

import { useEffect, useState } from "react";
import { getEngines } from "@/lib/api";
import type { EngineRead } from "@/lib/types";
import { EmbedTab } from "./embed-tab";
import { LaunchButton } from "./launch-button";
import { RagPreviewPanel } from "./rag-preview-panel";
import { ScoutPanel } from "./scout-panel";

// PROJ-19 (#23/#26): Effizienz-Werkzeuge — unabhängig von der Engine-Registry immer
// verfügbar (eigene Endpunkte), daher als eigener Block ganz oben.
function EfficiencyTools() {
  return (
    <section className="flex flex-col gap-6 rounded-lg border border-border bg-card/20 p-4">
      <RagPreviewPanel />
      <ScoutPanel />
    </section>
  );
}

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

  // PROJ-40: Micro-Apps (group=micro, z. B. Excalidraw) leben ausschließlich in der
  // Sidebar-Sektion „Micro-Apps" und erscheinen NICHT mehr im Werkzeuge-Tab — genau
  // eine Quelle pro App, keine Doppelregistrierung. Orchestration (PROJ-39) bleibt
  // hier bewusst mit gelistet.
  const iframes =
    engines?.filter((e) => e.kind === "iframe" && e.group !== "micro") ?? [];
  const launches = engines?.filter((e) => e.kind === "launch") ?? [];

  // Engine-abhängiger Block — eigene Lade-/Fehler-/Leer-Zustände, UNTER den
  // immer verfügbaren Effizienz-Werkzeugen (PROJ-19).
  let enginesContent: React.ReactNode;
  if (error) {
    enginesContent = (
      <p className="py-6 text-center text-sm text-muted-foreground">
        Werkzeuge nicht verfügbar ({error}).
      </p>
    );
  } else if (!engines) {
    enginesContent = (
      <p className="py-6 text-center text-sm text-muted-foreground">Lädt…</p>
    );
  } else if (iframes.length === 0 && launches.length === 0) {
    enginesContent = (
      <p className="py-6 text-center text-sm text-muted-foreground">
        Keine eingebetteten Apps oder Startknöpfe konfiguriert — pflege sie in{" "}
        <span className="font-mono">config/engines.yaml</span>.
      </p>
    );
  } else {
    enginesContent = (
      <>
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
      </>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <EfficiencyTools />
      {enginesContent}
    </div>
  );
}
