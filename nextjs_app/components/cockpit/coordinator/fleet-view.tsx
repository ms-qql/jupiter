"use client";

// PROJ-22: Eine Koordinator-Flotte als zusammengehörige Gruppe — Eltern-Kachel
// (Koordinator + Aggregat + Steuerung) über den eingerückten Kind-Sessions. Die
// Kinder werden über die bestehende SessionTile gerendert (Klick = „Kind
// übernehmen" = Direktzugriff auf die Detailroute). Daten kommen aus dem globalen
// /sessions-Poll (sessions-provider); nur Mutationen rufen /coordinator/*.

import { useState } from "react";
import { Pause, Play, FileText, Shuffle } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
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
import { ApiError, reassignTicket, setCoordinatorPaused } from "@/lib/api";
import { displayName, statusMeta } from "@/lib/status";
import type { EngineRead, Session } from "@/lib/types";
import { Ampel } from "../ampel";
import { SessionTile } from "../session-tile";

export function FleetView({
  coordinator,
  childSessions,
  now,
  paused: pausedProp,
  engines,
}: {
  coordinator: Session;
  childSessions: Session[];
  now: number;
  /** Aus dem letzten /coordinator/{id}/fleet — sonst aus dem Session-Status abgeleitet. */
  paused?: boolean;
  /** Verfügbare Engines für die Umverteilung (kind=engine). */
  engines: EngineRead[];
}) {
  const [paused, setPaused] = useState(pausedProp ?? false);
  const [busy, setBusy] = useState(false);
  const [reassignFor, setReassignFor] = useState<string | null>(null);

  async function togglePause() {
    if (busy) return;
    setBusy(true);
    try {
      const fleet = await setCoordinatorPaused(coordinator.session_id, !paused);
      setPaused(fleet.paused);
      toast.success(fleet.paused ? "Dispatch pausiert" : "Dispatch fortgesetzt");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  const meta = statusMeta(coordinator.status);
  const queued = coordinator.queued_ticket_ids ?? [];
  const openCards = childSessions.reduce(
    (n, c) => n + (c.pending_decisions?.length ?? 0),
    coordinator.pending_decisions?.length ?? 0,
  );

  return (
    <section className="rounded-xl border border-indigo-500/40 bg-indigo-500/[0.03] p-3">
      {/* Eltern-Kachel: Koordinator */}
      <header className="flex flex-wrap items-center gap-2">
        <Ampel color={meta.ampel} />
        <Link
          href={`/sessions/${coordinator.session_id}`}
          className="font-medium hover:underline"
          title={displayName(coordinator)}
        >
          🧭 {displayName(coordinator)}
        </Link>
        <Badge variant="secondary" className="text-[10px]">
          Koordinator
        </Badge>
        <Badge variant="outline" className="text-[10px] tabular-nums">
          {childSessions.length} Spezialist{childSessions.length === 1 ? "" : "en"}
        </Badge>
        {paused && (
          <Badge
            variant="outline"
            className="border-amber-500/50 text-[10px] text-amber-600 dark:text-amber-400"
          >
            pausiert
          </Badge>
        )}
        {queued.length > 0 && (
          <Badge
            variant="outline"
            className="border-sky-500/50 text-[10px] text-sky-600 dark:text-sky-400"
            title={`Eingereiht (rücken nach, sobald ein Slot frei wird): ${queued.join(", ")}`}
          >
            {queued.length} eingereiht
          </Badge>
        )}
        {openCards > 0 && (
          <Badge
            variant="outline"
            className="border-orange-500/50 text-[10px] text-orange-600 dark:text-orange-400"
          >
            ⚠ {openCards} Freigabe{openCards === 1 ? "" : "n"}
          </Badge>
        )}

        <div className="ml-auto flex items-center gap-1.5">
          {coordinator.contract_pointer && (
            <Button
              variant="outline"
              size="sm"
              render={
                <Link
                  href={`/doku?source=vault&path=${encodeURIComponent(coordinator.contract_pointer)}`}
                />
              }
            >
              <FileText className="size-3.5" />
              Vertrag
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={togglePause} disabled={busy}>
            {paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}
            {paused ? "Fortsetzen" : "Pausieren"}
          </Button>
        </div>
      </header>

      {/* Kind-Sessions: eingerückt, je mit Ticket-Badge + Umverteilen */}
      <div className="mt-3 flex flex-col gap-2 border-l-2 border-indigo-500/20 pl-3">
        {childSessions.length === 0 ? (
          <p className="py-2 text-xs text-muted-foreground">
            Noch keine Spezialisten-Sessions gestartet.
          </p>
        ) : (
          childSessions.map((child) => (
            <div key={child.session_id} className="flex flex-col gap-1">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <SessionTile session={child} now={now} compact />
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1 pt-1">
                  {child.ticket_id && (
                    <Badge variant="secondary" className="font-mono text-[10px]">
                      {child.ticket_id}
                    </Badge>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setReassignFor((id) =>
                        id === child.session_id ? null : child.session_id,
                      )
                    }
                    title="Ticket umverteilen"
                  >
                    <Shuffle className="size-3.5" />
                  </Button>
                </div>
              </div>
              {reassignFor === child.session_id && child.ticket_id && (
                <ReassignForm
                  coordinatorId={coordinator.session_id}
                  ticketId={child.ticket_id}
                  currentRole={child.role}
                  currentEngine={child.engine}
                  engines={engines}
                  onDone={() => setReassignFor(null)}
                />
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

/** Inline-Mini-Formular: Ticket auf andere Rolle/Engine umverteilen. */
function ReassignForm({
  coordinatorId,
  ticketId,
  currentRole,
  currentEngine,
  engines,
  onDone,
}: {
  coordinatorId: string;
  ticketId: string;
  currentRole: string | null;
  currentEngine: string;
  engines: EngineRead[];
  onDone: () => void;
}) {
  const [role, setRole] = useState(currentRole ?? "");
  const [engine, setEngine] = useState(currentEngine);
  const [busy, setBusy] = useState(false);
  const options = engines.filter((e) => e.kind === "engine" && e.available);

  async function submit() {
    if (busy) return;
    setBusy(true);
    try {
      await reassignTicket(coordinatorId, ticketId, {
        role: role.trim() || undefined,
        engine,
      });
      toast.success(`${ticketId} umverteilt`);
      onDone();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Umverteilen fehlgeschlagen");
      setBusy(false);
    }
  }

  return (
    <div className="ml-1 flex flex-wrap items-end gap-2 rounded-md border border-border bg-card/60 p-2">
      <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
        Rolle
        <Input
          value={role}
          onChange={(e) => setRole(e.target.value)}
          placeholder="z. B. backend"
          className="h-8 w-40"
        />
      </label>
      <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
        Engine
        <Select value={engine} onValueChange={(v) => v && setEngine(v)}>
          <SelectTrigger className={cn("h-8 w-40")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options.map((e) => (
              <SelectItem key={e.key} value={e.key}>
                {e.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </label>
      <Button size="sm" onClick={submit} disabled={busy}>
        {busy ? "…" : "Umverteilen"}
      </Button>
      <Button variant="ghost" size="sm" onClick={onDone} disabled={busy}>
        Abbrechen
      </Button>
    </div>
  );
}
