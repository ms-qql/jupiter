"use client";

// Decision Card (PROJ-4) — die 5-Sekunden-Entscheidung: Was, Ausschnitt, Warum,
// Kontext + Freigeben / Ablehnen / Mit Kommentar zurück / In Session springen.

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { ApiError, resolveDecision } from "@/lib/api";
import { projectName } from "@/lib/status";
import type { PendingDecision } from "@/lib/types";

export function DecisionCard({
  decision,
  showJump = true,
  className,
}: {
  decision: PendingDecision;
  /** „In Session springen" zeigen (auf der Detailseite überflüssig). */
  showJump?: boolean;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [commentOpen, setCommentOpen] = useState(false);
  const [comment, setComment] = useState("");

  const obsolete = decision.state === "obsolete";

  async function decide(verdict: "approve" | "deny", withComment?: string) {
    if (busy) return;
    setBusy(true);
    try {
      await resolveDecision(decision.session_id, decision.decision_id, verdict, withComment);
      toast.success(
        verdict === "approve" ? "Freigegeben" : withComment ? "Mit Kommentar zurückgegeben" : "Abgelehnt",
      );
      // Board-Polling / WS blendet die Card danach automatisch aus.
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Entscheidung fehlgeschlagen");
      setBusy(false);
    }
  }

  const proj = decision.context?.project_path ? projectName(decision.context.project_path) : null;
  const phase = decision.context?.phase;
  const role = decision.context?.role;

  return (
    <div
      className={cn(
        "rounded-lg border border-orange-500/50 bg-orange-500/5 p-3 ring-1 ring-orange-500/20",
        obsolete && "border-border bg-muted/30 opacity-60 ring-0",
        className,
      )}
    >
      {/* Was + Kontext */}
      <div className="flex items-start gap-2">
        <Badge
          variant="secondary"
          className="shrink-0 border-orange-500/40 bg-orange-500/10 text-orange-600 dark:text-orange-400"
        >
          {decision.tool_name}
        </Badge>
        <span className="min-w-0 flex-1 break-words text-sm font-medium">{decision.action}</span>
      </div>

      <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
        {proj && <span className="font-mono">{proj}</span>}
        {role && <span>· {role}</span>}
        {phase && <span>· {phase}</span>}
      </div>

      {/* Relevanter Ausschnitt (Befehl/Diff) — NICHT das ganze Log. */}
      <pre className="mt-2 max-h-44 overflow-auto rounded-md border border-border bg-background/60 p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words">
        {decision.excerpt}
      </pre>

      {/* Warum */}
      {decision.rationale && (
        <p className="mt-2 line-clamp-4 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/70">Warum: </span>
          {decision.rationale}
        </p>
      )}

      {obsolete ? (
        <p className="mt-3 text-xs italic text-muted-foreground">
          Obsolet — die Session wurde beendet.
        </p>
      ) : (
        <>
          {/* Aktionen */}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={busy} onClick={() => decide("approve")}>
              Freigeben
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => decide("deny")}
            >
              Ablehnen
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => setCommentOpen((v) => !v)}
            >
              Mit Kommentar zurück
            </Button>
            {showJump && (
              <Link
                href={`/sessions/${decision.session_id}`}
                className="ml-auto text-xs text-muted-foreground hover:text-foreground"
              >
                In Session springen →
              </Link>
            )}
          </div>

          {/* Kommentar-Eingabe (eingeklappt) */}
          {commentOpen && (
            <div className="mt-2">
              <Textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                placeholder="Begründung — Claude sieht sie und passt die Aktion an…"
                className="text-sm"
                autoFocus
              />
              <div className="mt-1.5 flex justify-end">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || !comment.trim()}
                  onClick={() => decide("deny", comment.trim())}
                >
                  Mit Kommentar ablehnen
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
