"use client";

// PROJ-39: Lädt die Orchestration-Apps aus der Engine-Registry (GET /engines,
// gefiltert auf group="orchestration") und meldet sie als dynamische Sidebar-
// Einträge beim Prefs-Provider an (Sichtbarkeit/Reihenfolge via Konfig-Panel,
// PROJ-38). Liefert die Liste zugleich für die Vollbild-Route zurück.

import { useEffect, useMemo, useState } from "react";
import { getEngines } from "@/lib/api";
import { orchestrationItemDef } from "@/lib/sidebar-config";
import type { EngineRead } from "@/lib/types";
import { useSidebarPrefs } from "./sidebar-prefs-provider";

export interface OrchestrationAppsState {
  apps: EngineRead[];
  loading: boolean;
  error: string | null;
}

export function useOrchestrationApps(): OrchestrationAppsState {
  const { registerDynamicItems } = useSidebarPrefs();
  const [apps, setApps] = useState<EngineRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getEngines(ctrl.signal)
      .then((o) => {
        const orch = o.engines.filter(
          (e) => e.kind === "iframe" && e.group === "orchestration",
        );
        setApps(orch);
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
    () => apps.map((e, i) => orchestrationItemDef(e, i)),
    [apps],
  );

  useEffect(() => {
    registerDynamicItems("orchestration", items);
  }, [items, registerDynamicItems]);

  return { apps, loading, error };
}
