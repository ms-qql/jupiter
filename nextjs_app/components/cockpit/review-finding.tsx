"use client";

// PROJ-23 — gemeinsame Bausteine für Cross-Agent-Review-Befunde: Schweregrad-Badge +
// die drei Aktionen (Übernehmen / Verwerfen / Mit Kommentar zurück). Wiederverwendet
// von der ReviewFindingCard (auf der Reviewer-Session) und vom ReviewsPanel (auf der
// Autor-Session) — eine Stelle für Aktions-Logik und Farbgebung.

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { ApiError, resolveFinding } from "@/lib/api";
import type { FindingAction, Severity } from "@/lib/types";

const SEVERITY_META: Record<Severity, { label: string; className: string }> = {
  hoch: {
    label: "hoch",
    className: "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
  },
  mittel: {
    label: "mittel",
    className: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  },
  niedrig: {
    label: "niedrig",
    className: "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400",
  },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const meta = SEVERITY_META[severity] ?? SEVERITY_META.mittel;
  return (
    <Badge variant="secondary" className={cn("shrink-0", meta.className)}>
      {meta.label}
    </Badge>
  );
}

/** Die drei Befund-Aktionen. ``resolved`` blendet sie aus (zeigt das Ergebnis).
 *  Optimistisches UI: nach Erfolg ruft ``onResolved`` den Eltern-Refresh. */
export function FindingActions({
  reviewId,
  findingId,
  resolution,
  onResolved,
}: {
  reviewId: string;
  findingId: string;
  resolution?: FindingAction | null;
  onResolved?: (action: FindingAction) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [commentOpen, setCommentOpen] = useState(false);
  const [comment, setComment] = useState("");

  if (resolution) {
    const label =
      resolution === "übernehmen"
        ? "Übernommen → an Autor-Session"
        : resolution === "zurück"
          ? "Mit Kommentar an Autor-Session zurück"
          : "Verworfen";
    return <p className="mt-2 text-xs italic text-muted-foreground">{label}</p>;
  }

  async function act(action: FindingAction, withComment?: string) {
    if (busy) return;
    setBusy(true);
    try {
      await resolveFinding(reviewId, findingId, action, withComment);
      toast.success(
        action === "übernehmen"
          ? "Übernommen — Gegenvorschlag an die Autor-Session"
          : action === "zurück"
            ? "Mit Kommentar an die Autor-Session zurück"
            : "Befund verworfen",
      );
      onResolved?.(action);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Aktion fehlgeschlagen");
      setBusy(false);
    }
  }

  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={busy} onClick={() => act("übernehmen")}>
          Übernehmen
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => act("verwerfen")}
          className="border-red-500/40 text-red-600 hover:bg-red-500/10 dark:text-red-400"
        >
          Verwerfen
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={busy}
          onClick={() => setCommentOpen((v) => !v)}
        >
          Mit Kommentar zurück
        </Button>
      </div>
      {commentOpen && (
        <div className="mt-2">
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            placeholder="Kommentar — geht mit dem Befund an die Autor-Session zurück…"
            className="text-sm"
            autoFocus
          />
          <div className="mt-1.5 flex justify-end">
            <Button
              size="sm"
              variant="outline"
              disabled={busy || !comment.trim()}
              onClick={() => act("zurück", comment.trim())}
            >
              Zurück an Autor-Session
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
