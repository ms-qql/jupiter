"use client";

// PROJ-14/21: Kleine, tab-übergreifende Bausteine der UI-Check-Micro-App
// (Formatierung, Status-Badge, authentifizierter Artefakt-Button). Ausgelagert,
// damit Mockup-/Portfolio-/Assembler-Tab sie ohne Zirkelimport auf
// ui-check-app.tsx nutzen können.

import { useState } from "react";
import { ExternalLinkIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError, openUiCheckArtifact } from "@/lib/api";
import type { UiCheckFinding, UiCheckRunStatus } from "@/lib/types";

export const STATUS_LABEL: Record<UiCheckRunStatus, string> = {
  queued: "Wartend",
  running: "Läuft",
  done: "Fertig",
  error: "Fehler",
  cancelled: "Abgebrochen",
};

export function fmtDate(iso: string | null): string {
  if (!iso) return "unbekannt";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unbekannt";
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtScore(score: number | null | undefined): string {
  return typeof score === "number" ? `${Math.round(score)}` : "n/v";
}

export function statusTone(status: UiCheckRunStatus): string {
  if (status === "done") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-500";
  if (status === "error") return "border-red-500/40 bg-red-500/10 text-red-500";
  if (status === "cancelled") return "border-amber-500/40 bg-amber-500/10 text-amber-500";
  if (status === "running") return "border-sky-500/40 bg-sky-500/10 text-sky-500";
  return "";
}

export function StatusBadge({ status }: { status: UiCheckRunStatus }) {
  const tone = statusTone(status);
  return tone ? (
    <Badge className={tone}>{STATUS_LABEL[status]}</Badge>
  ) : (
    <Badge variant="secondary">{STATUS_LABEL[status]}</Badge>
  );
}

export function SeverityBadge({ severity }: { severity: UiCheckFinding["severity"] }) {
  if (severity === "high") return <Badge variant="destructive">Hoch</Badge>;
  if (severity === "medium")
    return <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-500">Mittel</Badge>;
  return <Badge variant="outline">Niedrig</Badge>;
}

export function ArtifactButton({
  runId,
  kind,
  label,
}: {
  runId: string;
  kind: string;
  label: string;
}) {
  const [loading, setLoading] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      disabled={loading}
      onClick={async () => {
        setLoading(true);
        try {
          await openUiCheckArtifact(runId, kind);
        } catch (err) {
          toast.error(
            err instanceof ApiError ? err.message : "Artefakt konnte nicht geöffnet werden.",
          );
        } finally {
          setLoading(false);
        }
      }}
    >
      <ExternalLinkIcon className="size-3.5" />
      {label}
    </Button>
  );
}
