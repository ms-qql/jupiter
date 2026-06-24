"use client";

// Globale Aktion „Erledigte aufräumen (N)" (PROJ-21): löscht alle terminalen
// Sessions auf einmal. Nur sichtbar, wenn ≥ 1 terminale Session existiert. Aktive
// Sessions überspringt der Server still — wir zeigen die zurückgemeldete Anzahl.

import { useState } from "react";
import { Trash2Icon } from "lucide-react";
import { toast } from "sonner";
import { ApiError, cleanupSessions } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "./confirm-dialog";
import { useSessions } from "./sessions-provider";

export function CleanupButton({ terminalCount }: { terminalCount: number }) {
  const { refresh } = useSessions();
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);

  if (terminalCount < 1) return null;

  async function handleConfirm() {
    if (running) return;
    setRunning(true);
    try {
      const { deleted } = await cleanupSessions();
      toast.success(
        deleted === 1 ? "1 Session aufgeräumt." : `${deleted} Sessions aufgeräumt.`,
      );
      setOpen(false);
      refresh();
    } catch (err) {
      toast.error(
        err instanceof ApiError
          ? err.message
          : "Aufräumen fehlgeschlagen — Backend nicht erreichbar.",
      );
      refresh();
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        aria-label="Erledigte Sessions aufräumen"
      >
        <Trash2Icon className="size-3.5" />
        Erledigte aufräumen ({terminalCount})
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={(next) => !running && setOpen(next)}
        title="Erledigte Sessions aufräumen?"
        description={
          <>
            Entfernt alle{" "}
            <span className="font-medium text-foreground">{terminalCount}</span>{" "}
            erledigten und fehlgeschlagenen Sessions aus dem Cockpit. Aktive Sessions
            bleiben unberührt; die Session-Logs im Vault bleiben erhalten.
          </>
        }
        confirmLabel="Aufräumen"
        loading={running}
        onConfirm={handleConfirm}
      />
    </>
  );
}
