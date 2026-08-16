"use client";

// PROJ-79: Feature-Verteilungsplan-Dialog (Human-in-the-Loop). Lädt den internen
// Plan für EIN Feature PROJ-X (POST /coordinator/feature-plan), zeigt die internen
// Arbeitspakete (Rolle/Skill/Engine + Schreibbereiche + Abschlussbeleg + Abhängigkeiten)
// und lässt pro Paket Engine/Modell überschreiben. Erst nach Freigabe dispatcht
// POST /coordinator/feature-dispatch die Feature-Ausführung.

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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  ApiError,
  dispatchFeature,
  getEngines,
  getFeaturePlan,
} from "@/lib/api";
import type { EngineRead, FeaturePlan, FeaturePlanItem } from "@/lib/types";

export function FeaturePlanDialog({
  open,
  onOpenChange,
  projectPath,
  featureId,
  onDispatched,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectPath: string;
  featureId: string;
  onDispatched: (featureId: string) => void;
}) {
  const [plan, setPlan] = useState<FeaturePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dispatching, setDispatching] = useState(false);
  const [engines, setEngines] = useState<EngineRead[]>([]);
  // Pro Paket editierte Engine/Modell (Key = package_id).
  const [overrides, setOverrides] = useState<
    Record<string, { engine: string; model: string | null }>
  >({});

  useEffect(() => {
    if (!open || !projectPath || !featureId) return;
    const ac = new AbortController();
    async function load() {
      setPlan(null);
      setError(null);
      setOverrides({});
      setLoading(true);
      try {
        const [p, e] = await Promise.all([
          getFeaturePlan(projectPath, featureId, ac.signal),
          getEngines(ac.signal).then((o) => o.engines).catch(() => [] as EngineRead[]),
        ]);
        if (ac.signal.aborted) return;
        setPlan(p);
        setEngines(e);
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
  }, [open, projectPath, featureId]);

  const dispatchable = plan?.items.filter((i) => !i.blocked) ?? [];
  const engineOptions = engines.filter((e) => e.kind === "engine" && e.available);

  function engineOf(item: FeaturePlanItem): string {
    return overrides[item.package_id]?.engine ?? item.engine;
  }
  function modelOf(item: FeaturePlanItem): string | null {
    return overrides[item.package_id]?.model ?? item.model;
  }

  async function dispatch() {
    if (!plan || dispatchable.length === 0 || dispatching) return;
    setDispatching(true);
    try {
      const items = plan.items.map((it) => ({
        ...it,
        engine: engineOf(it),
        model: modelOf(it),
      }));
      const run = await dispatchFeature(plan.project_path, plan.feature_id, items);
      toast.success(`Feature-Ausführung ${run.feature_id} gestartet`);
      onOpenChange(false);
      onDispatched(run.feature_id);
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
          <DialogTitle>Feature-Verteilungsplan</DialogTitle>
          <DialogDescription>
            Interne Arbeitspakete für{" "}
            <span className="font-mono">{featureId}</span> mit Rolle/Skill/Engine,
            Schreibbereich, Abschlussbeleg und Abhängigkeiten. Engine/Modell pro
            Paket überschreibbar. Erst nach Freigabe startet die Ausführung.
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
            Keine internen Arbeitspakete ableitbar (Feature ohne technische
            Teilbereiche?).
          </p>
        ) : (
          <div className="flex flex-col gap-3">
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
                  key={item.package_id}
                  className={cn(
                    "rounded-lg border bg-card p-2.5",
                    item.blocked ? "border-border opacity-60" : "border-border",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-6 shrink-0 text-center text-xs tabular-nums text-muted-foreground">
                      {item.order}.
                    </span>
                    <Badge variant="secondary" className="shrink-0 font-mono text-[10px]">
                      {item.package_id}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate text-sm" title={item.title}>
                      {item.title}
                    </span>
                    <Badge variant="outline" className="shrink-0 text-[10px]">
                      {item.required_proof}
                    </Badge>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 pl-8 text-[11px] text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      {item.role ?? "—"}
                      <ArrowRight className="size-3" />
                      {item.skill ?? "—"}
                    </span>
                    {item.dependencies.length > 0 && (
                      <>
                        <span aria-hidden>·</span>
                        <span>benötigt {item.dependencies.join(", ")}</span>
                      </>
                    )}
                    {item.write_scope.length > 0 && (
                      <>
                        <span aria-hidden>·</span>
                        <span title={item.write_scope.join(", ")}>
                          ✎ {item.write_scope.length} Bereich
                          {item.write_scope.length === 1 ? "" : "e"}
                        </span>
                      </>
                    )}
                  </div>
                  {!item.blocked && (
                    <div className="mt-2 flex flex-wrap items-end gap-2 pl-8">
                      <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
                        Engine
                        <Select
                          value={engineOf(item)}
                          onValueChange={(v) => {
                            if (!v) return;
                            setOverrides((o) => {
                              const next = { ...o };
                              const value: { engine: string; model: string | null } = {
                                engine: v,
                                model: modelOf(item),
                              };
                              next[item.package_id] = value;
                              return next;
                            });
                          }}
                        >
                          <SelectTrigger className="h-8 w-40">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {engineOptions.map((e) => (
                              <SelectItem key={e.key} value={e.key}>
                                {e.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </label>
                      <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
                        Modell
                        <Input
                          value={modelOf(item) ?? ""}
                          onChange={(e) =>
                            setOverrides((o) => {
                              const next = { ...o };
                              const value: { engine: string; model: string | null } = {
                                engine: engineOf(item),
                                model: e.target.value.trim() || null,
                              };
                              next[item.package_id] = value;
                              return next;
                            })
                          }
                          placeholder="—"
                          className="h-8 w-32 font-mono"
                        />
                      </label>
                    </div>
                  )}
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
              ? "Starte Ausführung …"
              : `Ausführung starten (${dispatchable.length})`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
