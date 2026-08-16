"use client";

// PROJ-22 / PROJ-79: Koordinator-Tab. Start (Projektpfad → Plan → Dispatch) plus
// Live-Sicht aller laufenden Flotten. PROJ-79 ergänzt einen Modus-Umschalter:
// „Feature" startet eine Feature-Ausführung (interne Arbeitspakete statt allgemeiner
// Ticket-Flotte), „Flotte" ist der bestehende PROJ-22-Pfad. Feature-Läufe werden
// aus dem globalen /sessions-Poll abgeleitet (is_feature_run) und als FeatureRunView
// gerendert; nur Mutationen rufen /coordinator/features/*.

import { useEffect, useMemo, useState } from "react";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getEngines, readFileText } from "@/lib/api";
import type { EngineRead, Session } from "@/lib/types";
import { useNow, useSessions } from "../sessions-provider";
import { DispatchPlanDialog } from "./dispatch-plan-dialog";
import { FeaturePlanDialog } from "./feature-plan-dialog";
import { FeatureRunView } from "./feature-run-view";
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
  const [mode, setMode] = useState<"feature" | "fleet">("fleet");
  const [featureId, setFeatureId] = useState("");
  const [featureOpen, setFeatureOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [engines, setEngines] = useState<EngineRead[]>([]);
  const [featureHints, setFeatureHints] = useState<string[]>([]);

  useEffect(() => {
    const ac = new AbortController();
    getEngines(ac.signal)
      .then((o) => setEngines(o.engines))
      .catch(() => setEngines([]));
    return () => ac.abort();
  }, []);

  // Autocomplete für Feature-ID gegen features/INDEX.md des Projekts.
  useEffect(() => {
    if (!projectPath.trim()) return;
    const ac = new AbortController();
    readFileText(`${projectPath.trim()}/features/INDEX.md`, ac.signal)
      .then((f) => {
        if (ac.signal.aborted) return;
        const ids = new Set<string>();
        for (const line of f.content.split("\n")) {
          const m = line.match(/PROJ-(\d+)/i);
          if (m) ids.add(`PROJ-${m[1]}`);
        }
        setFeatureHints([...ids]);
      })
      .catch(() => {
        if (!ac.signal.aborted) setFeatureHints([]);
      });
    return () => ac.abort();
  }, [projectPath]);

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

  function openFeaturePlan() {
    const p = projectPath.trim();
    const f = featureId.trim().toUpperCase();
    if (!p || !f) return;
    try {
      window.localStorage.setItem(PROJECT_KEY, p);
    } catch {
      /* ignore */
    }
    setFeatureOpen(true);
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Modus-Umschalter */}
      <div className="flex items-center gap-1 self-start rounded-lg border border-border bg-card/40 p-1">
        <Button
          size="sm"
          variant={mode === "feature" ? "default" : "ghost"}
          onClick={() => setMode("feature")}
        >
          Feature
        </Button>
        <Button
          size="sm"
          variant={mode === "fleet" ? "default" : "ghost"}
          onClick={() => setMode("fleet")}
        >
          Flotte (bestehend)
        </Button>
      </div>

      {/* Einstieg */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card/40 p-3">
        {mode === "feature" ? (
          <>
            <div className="flex items-center gap-2 text-sm font-medium">
              <Compass className="size-4 text-emerald-500" />
              Feature-Ausführung starten
            </div>
            <p className="text-xs text-muted-foreground">
              Jupiter leitet aus der Spezifikation von{" "}
              <span className="font-mono">PROJ-X</span> die nötigen internen
              Arbeitspakete ab und führt sie abhängigkeitsgerecht aus — erst nach
              deiner Freigabe.
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-1 flex-col gap-1 text-[11px] text-muted-foreground">
                Projektpfad
                <Input
                  value={projectPath}
                  onChange={(e) => setProjectPath(e.target.value)}
                  placeholder="/home/dev/projects/…"
                  className="h-9 font-mono"
                />
              </label>
              <label className="flex flex-1 flex-col gap-1 text-[11px] text-muted-foreground">
                Feature-ID
                <Input
                  list="feature-id-hints"
                  value={featureId}
                  onChange={(e) => setFeatureId(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") openFeaturePlan();
                  }}
                  placeholder="PROJ-101"
                  className="h-9 font-mono"
                />
                <datalist id="feature-id-hints">
                  {featureHints.map((h) => (
                    <option key={h} value={h} />
                  ))}
                </datalist>
              </label>
              <Button
                onClick={openFeaturePlan}
                disabled={!projectPath.trim() || !featureId.trim()}
                className="h-9"
              >
                Plan erstellen
              </Button>
            </div>
          </>
        ) : (
          <>
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
          </>
        )}
      </div>

      {/* Laufende Flotten / Feature-Läufe */}
      {fleets.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Keine aktive Flotte. Dispatche oben eine neue.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {fleets.map((f) =>
            f.coordinator.is_feature_run && f.coordinator.feature_id ? (
              <FeatureRunView
                key={f.coordinator.session_id}
                featureId={f.coordinator.feature_id}
                coordinator={f.coordinator}
              />
            ) : (
              <FleetView
                key={f.coordinator.session_id}
                coordinator={f.coordinator}
                childSessions={f.children}
                now={now}
                paused={f.coordinator.status === "waiting"}
                engines={engines}
              />
            ),
          )}
        </div>
      )}

      <DispatchPlanDialog
        open={planOpen}
        onOpenChange={setPlanOpen}
        projectPath={projectPath.trim()}
        onDispatched={() => setPlanOpen(false)}
      />
      <FeaturePlanDialog
        open={featureOpen}
        onOpenChange={setFeatureOpen}
        projectPath={projectPath.trim()}
        featureId={featureId.trim().toUpperCase()}
        onDispatched={() => {
          setFeatureOpen(false);
        }}
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
