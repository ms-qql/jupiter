"use client";

// Einzel-Lösch-Button für terminale Sessions (PROJ-21). Sitzt als Overlay in einer
// Kachel/Rail-Zeile, die selbst ein <Link> ist — Klick darf daher NICHT navigieren
// (preventDefault + stopPropagation). Bestätigung via ConfirmDialog, Erfolg/Fehler
// als deutscher Toast, danach Provider-Refetch, damit der Eintrag sofort verschwindet.

import { useState } from "react";
import { Trash2Icon } from "lucide-react";
import { toast } from "sonner";
import { ApiError, deleteSession } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "./confirm-dialog";
import { useSessions } from "./sessions-provider";

export function DeleteSessionButton({
  sessionId,
  projectName,
  className,
}: {
  sessionId: string;
  projectName: string;
  className?: string;
}) {
  const { refresh } = useSessions();
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  function openDialog(e: React.MouseEvent) {
    // Eltern-Link nicht auslösen.
    e.preventDefault();
    e.stopPropagation();
    setOpen(true);
  }

  async function handleConfirm() {
    if (deleting) return;
    setDeleting(true);
    try {
      await deleteSession(sessionId);
      toast.success("Session gelöscht.");
      setOpen(false);
      refresh();
    } catch (err) {
      // 409 = inzwischen wieder aktiv; 404 = schon weg → beides ist „verschwunden".
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 404) {
        toast.success("Session war bereits gelöscht.");
        setOpen(false);
        refresh();
      } else {
        toast.error(
          err instanceof ApiError
            ? err.message
            : "Löschen fehlgeschlagen — Backend nicht erreichbar.",
        );
        refresh();
      }
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        aria-label="Session löschen"
        title="Session löschen"
        className={cn(
          "inline-flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive/40",
          className,
        )}
      >
        <Trash2Icon className="size-3.5" />
      </button>
      <ConfirmDialog
        open={open}
        onOpenChange={(next) => !deleting && setOpen(next)}
        title="Session löschen?"
        description={
          <>
            <span className="font-medium text-foreground">{projectName}</span> wird
            aus dem Cockpit entfernt. Das Session-Log im Vault bleibt erhalten. Aktive
            Sessions lassen sich nicht löschen.
          </>
        }
        loading={deleting}
        onConfirm={handleConfirm}
      />
    </>
  );
}
