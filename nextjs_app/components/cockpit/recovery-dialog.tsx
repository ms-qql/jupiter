"use client";

// Recovery-Dialog (PROJ-17): listet nach Reboot/Crash wiederherstellbare Stränge.
// Pro Kandidat: letzter Stand (Projekt/Phase/Zeitpunkt), „Hier ging's weiter"-
// Vorschlag und die Aktionen Wiederherstellen (Kind-Session mit Seed) / Verwerfen
// (raus aus der Ansicht, Vault-Eintrag bleibt — Audit). Deutsche UI.

import { useState } from "react";
import { AlertTriangleIcon, LifeBuoyIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ApiError, dismissRecovery, restoreRecovery } from "@/lib/api";
import type { RecoveryCandidate, RecoverySource } from "@/lib/types";
import { ABC_PHASES, formatDuration, projectName } from "@/lib/status";

const SOURCE_META: Record<
  RecoverySource,
  { label: string; variant: "default" | "secondary" | "outline" }
> = {
  handover: { label: "Handover", variant: "default" },
  log: { label: "Session-Log", variant: "secondary" },
  incomplete: { label: "unvollständig", variant: "outline" },
};

function phaseLabel(phase: RecoveryCandidate["abc_phase"]): string | null {
  if (!phase) return null;
  return ABC_PHASES.find((p) => p.key === phase)?.label ?? phase;
}

export function RecoveryDialog({
  open,
  onOpenChange,
  candidates,
  nowMs,
  onChanged,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  candidates: RecoveryCandidate[];
  nowMs: number;
  /** Nach Wiederherstellen/Verwerfen: Recovery-Liste UND Sessions neu laden. */
  onChanged: () => void;
}) {
  // session_id des gerade in Bearbeitung befindlichen Kandidaten (+ Aktion).
  const [busy, setBusy] = useState<{ id: string; action: "restore" | "dismiss" } | null>(
    null,
  );

  async function handleRestore(c: RecoveryCandidate) {
    if (busy) return;
    setBusy({ id: c.session_id, action: "restore" });
    try {
      await restoreRecovery(c.session_id);
      toast.success(`Session wiederhergestellt — ${projectName(c.project_path)} läuft weiter`);
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Wiederherstellen fehlgeschlagen");
    } finally {
      setBusy(null);
    }
  }

  async function handleDismiss(c: RecoveryCandidate) {
    if (busy) return;
    setBusy({ id: c.session_id, action: "dismiss" });
    try {
      await dismissRecovery(c.session_id);
      toast.success("Kandidat verworfen (Vault-Eintrag bleibt erhalten)");
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Verwerfen fehlgeschlagen");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <LifeBuoyIcon className="size-4" />
            Sessions wiederherstellen
          </DialogTitle>
          <DialogDescription>
            Nach einem Neustart aus dem Vault rekonstruierte Stränge bis zum letzten
            Handover. Wiederherstellen startet eine Nachfolge-Session mit dem letzten
            Stand als Kontext.
          </DialogDescription>
        </DialogHeader>

        {candidates.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Keine wiederherstellbaren Sessions.
          </p>
        ) : (
          <ScrollArea className="max-h-[60vh] pr-3">
            <ul className="flex flex-col gap-3 py-1">
              {candidates.map((c) => {
                const src = SOURCE_META[c.source];
                const phase = phaseLabel(c.abc_phase);
                const isBusy = busy?.id === c.session_id;
                return (
                  <li
                    key={c.session_id}
                    className="rounded-lg border border-border bg-card p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="min-w-0 flex-1 truncate font-medium">
                        {c.project_name || projectName(c.project_path)}
                      </span>
                      {phase && (
                        <Badge variant="outline" className="shrink-0">
                          {phase}
                        </Badge>
                      )}
                      <Badge variant={src.variant} className="shrink-0">
                        {src.label}
                      </Badge>
                    </div>

                    <p className="mt-1 text-xs text-muted-foreground">
                      {c.last_handover_at
                        ? `Letzter Stand vor ${formatDuration(c.last_handover_at, nowMs)}`
                        : "Zeitpunkt unbekannt"}
                      {" · "}
                      <span className="font-mono break-all">{c.project_path}</span>
                    </p>

                    <div className="mt-2 rounded-md bg-muted/50 px-3 py-2">
                      <p className="mb-0.5 text-xs font-medium text-muted-foreground">
                        Hier ging&apos;s weiter
                      </p>
                      <p className="whitespace-pre-wrap text-sm">
                        {c.suggestion?.trim() || "Kein verdichteter Stand verfügbar."}
                      </p>
                    </div>

                    {c.warning && (
                      <p className="mt-2 flex items-start gap-1.5 text-xs text-amber-500">
                        <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
                        <span>{c.warning}</span>
                      </p>
                    )}

                    {c.restore_blocked && c.blocked_reason && (
                      <p className="mt-2 flex items-start gap-1.5 text-xs text-destructive">
                        <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
                        <span>{c.blocked_reason}</span>
                      </p>
                    )}

                    <div className="mt-3 flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDismiss(c)}
                        disabled={isBusy}
                      >
                        <Trash2Icon className="size-4" />
                        {isBusy && busy?.action === "dismiss" ? "Verwirft…" : "Verwerfen"}
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleRestore(c)}
                        disabled={isBusy || c.restore_blocked}
                        title={c.restore_blocked ? c.blocked_reason ?? undefined : undefined}
                      >
                        {isBusy && busy?.action === "restore"
                          ? "Stellt wieder her…"
                          : "Wiederherstellen"}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </ScrollArea>
        )}

        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  );
}
