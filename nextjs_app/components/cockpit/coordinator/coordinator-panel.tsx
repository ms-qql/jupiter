"use client";

// PROJ-22: Koordinator-Tab. Einstieg (Projektpfad → Verteilungsplan → Dispatch)
// plus Live-Sicht aller laufenden Flotten. Die Flotten werden aus dem globalen
// /sessions-Poll (sessions-provider) abgeleitet: Koordinator = role "coordinator";
// Kinder = Sessions mit parent_coordinator_id === Koordinator-ID. So braucht der
// Tab keinen zweiten Poll; nur Mutationen rufen /coordinator/*.

import { useEffect, useMemo, useState } from "react";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getEngines } from "@/lib/api";
import type { EngineRead, Session } from "@/lib/types";
import { useNow, useSessions } from "../sessions-provider";
import { DispatchPlanDialog } from "./dispatch-plan-dialog";
import { FleetView } from "./fleet-view";

/** localStorage-Key für den zuletzt genutzten Projektpfad (Komfort). */
const PROJECT_KEY = "jupiter.coordinator.project";

/** Zuletzt genutzten Projektpfad lesen (SSR-sicher, als Lazy-Initializer). */
function readStoredProject(): string {
  try {
    return typeof window !== "undefined"
      ? (window.localStorage.getItem(PROJECT_KEY) ?? "")
      : "";
  } catch {
    return "";
  }
}

export function CoordinatorPanel() {
  const { sessions } = useSessions();
  const now = useNow();
  const [projectPath, setProjectPath] = useState(readStoredProject);
  const [planOpen, setPlanOpen] = useState(false);
  const [engines, setEngines] = useState<EngineRead[]>([]);

  // Engines einmalig für die Umverteilung laden (nicht-blockierend).
  useEffect(() => {
    const ac = new AbortController();
    getEngines(ac.signal)
      .then((o) => setEngines(o.engines))
      .catch(() => setEngines([]));
    return () => ac.abort();
  }, []);

  // Flotten aus dem globalen Session-Stand ableiten.
  const fleets = useMemo(() => groupFleets(sessions), [sessions]);

  function openPlan() {
    const p = projectPath.trim();
    if (!p) return;
    try {
      window.localStorage.setItem(PROJECT_KEY, p);
    } catch {
      /* ignore */
    }
    setPlanOpen(true);
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Einstieg */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card/40 p-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Compass className="size-4 text-indigo-500" />
          Neue Flotte dispatchen
        </div>
        <p className="text-xs text-muted-foreground">
          Der Koordinator liest offene Tickets aus{" "}
          <span className="font-mono">features/INDEX.md</span> des Projekts und
          schlägt einen Verteilungsplan vor — gestartet wird erst nach deiner
          Freigabe.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-1 flex-col gap-1 text-[11px] text-muted-foreground">
            Projektpfad
            <Input
              value={projectPath}
              onChange={(e) => setProjectPath(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") openPlan();
              }}
              placeholder="/home/dev/projects/…"
              className="h-9 font-mono"
            />
          </label>
          <Button onClick={openPlan} disabled={!projectPath.trim()} className="h-9">
            Verteilungsplan erstellen
          </Button>
        </div>
      </div>

      {/* Laufende Flotten */}
      {fleets.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Keine aktive Flotte. Dispatche oben eine neue.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {fleets.map((f) => (
            <FleetView
              key={f.coordinator.session_id}
              coordinator={f.coordinator}
              childSessions={f.children}
              now={now}
              paused={f.coordinator.status === "waiting"}
              engines={engines}
            />
          ))}
        </div>
      )}

      <DispatchPlanDialog
        open={planOpen}
        onOpenChange={setPlanOpen}
        projectPath={projectPath.trim()}
        onDispatched={() => setPlanOpen(false)}
      />
    </div>
  );
}

interface Fleet {
  coordinator: Session;
  children: Session[];
}

/** Aus der flachen Session-Liste die Koordinator-Flotten bauen. */
function groupFleets(sessions: Session[]): Fleet[] {
  const coordinators = sessions.filter((s) => s.role === "coordinator");
  const byParent = new Map<string, Session[]>();
  for (const s of sessions) {
    if (s.parent_coordinator_id) {
      const arr = byParent.get(s.parent_coordinator_id) ?? [];
      arr.push(s);
      byParent.set(s.parent_coordinator_id, arr);
    }
  }
  return coordinators
    .map((coordinator) => ({
      coordinator,
      children: (byParent.get(coordinator.session_id) ?? []).sort((a, b) =>
        (a.ticket_id ?? "").localeCompare(b.ticket_id ?? ""),
      ),
    }))
    // Jüngste Flotte zuerst.
    .sort(
      (a, b) =>
        Date.parse(b.coordinator.created_at) -
        Date.parse(a.coordinator.created_at),
    );
}
