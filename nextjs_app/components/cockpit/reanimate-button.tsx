"use client";

// PROJ-27: manueller „Reaktivieren"-Knopf für hängende/tote Sessions. Löst denselben
// Resume-Pfad wie die Automatik aus (POST /sessions/{id}/reanimate). Zwei Varianten:
// „icon" (kompakt, in der Kachel — die selbst ein <Link> ist, daher preventDefault/
// stopPropagation) und „full" (Beschriftung, im Session-Detail). Erfolg/Fehler als
// deutscher Toast; danach Provider-Refetch. 409 = lief bereits, 429 = Session-Limit.

import { useState } from "react";
import { HeartPulseIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ApiError, reanimateSession } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useSessions } from "./sessions-provider";

export function ReanimateButton({
  sessionId,
  variant = "icon",
  className,
  onDone,
}: {
  sessionId: string;
  variant?: "icon" | "full";
  className?: string;
  onDone?: () => void;
}) {
  const { refresh } = useSessions();
  const [busy, setBusy] = useState(false);

  async function handle(e: React.MouseEvent) {
    // In der Kachel sitzt der Knopf in einem <Link> — Navigation unterbinden.
    e.preventDefault();
    e.stopPropagation();
    if (busy) return;
    setBusy(true);
    try {
      await reanimateSession(sessionId);
      toast.success("Reaktiviert — Session läuft wieder.");
      refresh();
      onDone?.();
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 409) {
        toast.info("Session läuft bereits — keine Reanimierung nötig.");
        refresh();
      } else if (status === 429) {
        toast.error(
          err instanceof ApiError
            ? err.message
            : "Session-Limit erreicht — zuerst eine laufende Session beenden.",
        );
      } else {
        toast.error(
          err instanceof ApiError
            ? err.message
            : "Reanimierung fehlgeschlagen — Backend nicht erreichbar.",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  if (variant === "full") {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={handle}
        disabled={busy}
        className={cn("gap-1.5", className)}
      >
        <HeartPulseIcon className="size-3.5" />
        {busy ? "Reaktiviert…" : "Reaktivieren"}
      </Button>
    );
  }

  return (
    <button
      type="button"
      onClick={handle}
      disabled={busy}
      aria-label="Session reaktivieren"
      title="Session reaktivieren"
      className={cn(
        "inline-flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-emerald-500/10 hover:text-emerald-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40 disabled:opacity-50",
        className,
      )}
    >
      <HeartPulseIcon className="size-3.5" />
    </button>
  );
}
