"use client";

// PROJ-40: Lädt die Micro-Apps aus der Engine-Registry (GET /engines, gefiltert
// auf group="micro") und meldet sie als dynamische Sidebar-Einträge beim
// Prefs-Provider an (Sichtbarkeit/Reihenfolge via Konfig-Panel, PROJ-38).
// Anders als Orchestration umfasst „Micro-Apps" BEIDE Naturen: eingebettet
// (kind=iframe, z. B. Excalidraw) und nativ in Jupiter (kind=native). Die
// Sidebar sieht nur Metadaten — erst die Route /apps/[key] verzweigt nach kind.

import { useEffect, useMemo, useState } from "react";
import { getEngines } from "@/lib/api";
import { microAppItemDef } from "@/lib/sidebar-config";
import type { EngineRead } from "@/lib/types";
import { useSidebarPrefs } from "./sidebar-prefs-provider";

export interface MicroAppsState {
  apps: EngineRead[];
  loading: boolean;
  error: string | null;
}

export function useMicroApps(): MicroAppsState {
  const { registerDynamicItems } = useSidebarPrefs();
  const [apps, setApps] = useState<EngineRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getEngines(ctrl.signal)
      .then((o) => {
        const micro = o.engines.filter(
          (e) =>
            e.group === "micro" &&
            (e.kind === "iframe" || e.kind === "native"),
        );
        setApps(micro);
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return;
        setError(e instanceof Error ? e.message : "Fehler");
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, []);

  // Registry-Reihenfolge als Default-Order; der Nutzer überschreibt sie im Panel.
  const items = useMemo(
    () => apps.map((e, i) => microAppItemDef(e, i)),
    [apps],
  );

  useEffect(() => {
    registerDynamicItems("micro", items);
  }, [items, registerDynamicItems]);

  return { apps, loading, error };
}
