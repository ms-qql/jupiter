"use client";

// PROJ-22: Verteilungsplan-Dialog (Human-in-the-Loop). Lädt den Plan aus
// features/INDEX.md des Projekts (POST /coordinator/plan), zeigt Ticket → Rolle/
// Skill/Engine + topologische Reihenfolge + Abhängigkeits-Warnungen und dispatcht
// erst nach ausdrücklicher Freigabe (POST /coordinator/dispatch).

import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ApiError, dispatchCoordinator, getCoordinatorPlan } from "@/lib/api";
import type { CoordinatorPlan } from "@/lib/types";

export function DispatchPlanDialog({
  open,
  onOpenChange,
  projectPath,
  onDispatched,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectPath: string;
  onDispatched: (coordinatorId: string) => void;
}) {
  const [plan, setPlan] = useState<CoordinatorPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dispatching, setDispatching] = useState(false);

  // Plan laden, sobald der Dialog mit einem Projektpfad öffnet. setState lebt in
  // der async-Funktion (nicht synchron im Effect-Body) — vgl. RecoveryBanner.
  useEffect(() => {
    if (!open || !projectPath) return;
    const ac = new AbortController();
    async function load() {
      setPlan(null);
      setError(null);
      setLoading(true);
      try {
        const p = await getCoordinatorPlan(projectPath, ac.signal);
        if (!ac.signal.aborted) setPlan(p);
      } catch (e) {
        if (ac.signal.aborted) return;
        setError(
          e instanceof ApiError ? e.message : "Plan konnte nicht erstellt werden",
        );
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => ac.abort();
  }, [open, projectPath]);

  const dispatchable = plan?.items.filter((i) => !i.blocked) ?? [];

  async function dispatch() {
    if (!plan || dispatchable.length === 0 || dispatching) return;
    setDispatching(true);
    try {
      const fleet = await dispatchCoordinator(plan.project_path, dispatchable);
      toast.success(
        `Flotte gestartet — ${fleet.children.length} Spezialisten-Session${
          fleet.children.length === 1 ? "" : "s"
        }`,
      );
      onOpenChange(false);
      onDispatched(fleet.coordinator.session_id);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Dispatch fehlgeschlagen",
      );
      setDispatching(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Verteilungsplan</DialogTitle>
          <DialogDescription>
            Offene Tickets aus <span className="font-mono">features/INDEX.md</span>{" "}
            mit abgeleiteter Rolle/Engine. Reihenfolge folgt der Spalte
            {" "}
            <span className="font-mono">Abhängigkeiten</span>. Erst nach Freigabe
            werden Sessions gestartet.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Plan wird erstellt …
          </p>
        ) : error ? (
          <p className="rounded-md border border-red-500/40 bg-red-500/5 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        ) : !plan || plan.items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Keine verteilbaren Tickets gefunden (alle Deployed/Approved?).
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {/* Warnungen: zirkuläre/fehlende Abhängigkeiten — nur auflösbarer Teilgraph. */}
            {plan.warnings.length > 0 && (
              <div className="flex flex-col gap-1 rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2">
                {plan.warnings.map((w, i) => (
                  <p
                    key={i}
                    className="flex items-start gap-1.5 text-xs text-amber-600 dark:text-amber-400"
                  >
                    <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                    {w}
                  </p>
                ))}
              </div>
            )}

            <ul className="flex max-h-[50vh] flex-col gap-1.5 overflow-y-auto">
              {plan.items.map((item) => (
                <li
                  key={item.ticket_id}
                  className={cn(
                    "rounded-lg border bg-card p-2.5",
                    item.blocked
                      ? "border-border opacity-60"
                      : "border-border",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-6 shrink-0 text-center text-xs tabular-nums text-muted-foreground">
                      {item.order}.
                    </span>
                    <Badge variant="secondary" className="shrink-0 font-mono text-[10px]">
                      {item.ticket_id}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate text-sm" title={item.title}>
                      {item.title}
                    </span>
                    <Badge variant="outline" className="shrink-0 text-[10px]">
                      {item.status}
                    </Badge>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 pl-8 text-[11px] text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      {item.role ?? "—"}
                      <ArrowRight className="size-3" />
                      {item.skill ?? "—"}
                    </span>
                    <span aria-hidden>·</span>
                    <span className="uppercase">{item.engine}</span>
                    {item.model && (
                      <>
                        <span aria-hidden>·</span>
                        <span>{item.model}</span>
                      </>
                    )}
                    {item.dependencies.length > 0 && (
                      <>
                        <span aria-hidden>·</span>
                        <span>benötigt {item.dependencies.join(", ")}</span>
                      </>
                    )}
                  </div>
                  {item.blocked && item.blocked_reason && (
                    <p className="mt-1 pl-8 text-[11px] text-amber-600 dark:text-amber-400">
                      ⏸ {item.blocked_reason}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Abbrechen
          </Button>
          <Button
            onClick={dispatch}
            disabled={dispatching || dispatchable.length === 0}
          >
            {dispatching
              ? "Starte Flotte …"
              : `Flotte starten (${dispatchable.length})`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
