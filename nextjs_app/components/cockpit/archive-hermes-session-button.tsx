"use client";

// PROJ-88: Bewusster Hermes-Abschluss. Kleine Komposition auf Basis des
// vorhandenen ConfirmDialog, sonner, useSessions().refresh() und archiveSession.
// Beendet eine ruhende/aktive Hermes-Session und verschiebt sie ins Archiv
// (Status done) bzw. verschiebt eine Fehler-Session ohne Reanimation dorthin.
// Sichtbarkeit/Status-Logik liegt in SessionView — diese Komponente ist die
// reine Aktion. Während der Anfrage ist der Knopf gesperrt (kein Doppelklick).

import { useState } from "react";
import { ArchiveIcon } from "lucide-react";
import { toast } from "sonner";
import { ApiError, archiveSession } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "./confirm-dialog";
import { useSessions } from "./sessions-provider";

export function ArchiveHermesSessionButton({
  sessionId,
  projectName,
  mode,
  className,
}: {
  sessionId: string;
  projectName: string;
  /** "beenden" = ruhend/aktiv abschließen · "verschieben" = Fehler ins Archiv. */
  mode: "beenden" | "verschieben";
  className?: string;
}) {
  const { refresh } = useSessions();
  const [open, setOpen] = useState(false);
  const [archiving, setArchiving] = useState(false);

  const isMove = mode === "verschieben";
  const label = isMove ? "Ins Archiv verschieben" : "Beenden & archivieren";
  const title = isMove ? "Ins Archiv verschieben?" : "Beenden & archivieren?";

  function openDialog() {
    setOpen(true);
  }

  async function handleConfirm() {
    if (archiving) return;
    setArchiving(true);
    try {
      await archiveSession(sessionId);
      toast.success(
        isMove
          ? "Session ins Archiv verschoben."
          : "Session beendet und archiviert.",
      );
      setOpen(false);
      refresh();
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 404) {
        // In einem anderen Tab bereits gelöscht/verschoben → konsistent bleiben.
        toast.success("Session war bereits archiviert.");
        setOpen(false);
        refresh();
      } else if (status === 409) {
        toast.error(
          err instanceof ApiError
            ? err.message
            : "Diese Session kann nicht archiviert werden.",
        );
        refresh();
      } else if (status === 503) {
        toast.error(
          err instanceof ApiError
            ? err.message
            : "Turn ließ sich nicht sauber beenden — Session bleibt aktiv.",
        );
        refresh();
      } else {
        toast.error(
          err instanceof ApiError
            ? err.message
            : "Archivieren fehlgeschlagen — Backend nicht erreichbar.",
        );
        refresh();
      }
    } finally {
      setArchiving(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        aria-label={label}
        title={label}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          className,
        )}
      >
        <ArchiveIcon className="size-4" />
        {label}
      </button>
      <ConfirmDialog
        open={open}
        onOpenChange={(next) => !archiving && setOpen(next)}
        title={title}
        description={
          <div className="space-y-2">
            <p>
              <span className="font-medium text-foreground">{projectName}</span>{" "}
              {isMove
                ? "wird ohne erneuten Start ins Archiv verschoben (Status „Fertig“)."
                : "wird beendet und ins Archiv verschoben (Status „Fertig“)."}{" "}
              Die Session bleibt in der Detailansicht geöffnet, ist aber nicht
              mehr unter aktiven Sessions gelistet.
            </p>
            <p className="text-xs text-muted-foreground">
              Abbrechen ändert weder Status noch einen laufenden Hermes-Turn.
            </p>
          </div>
        }
        confirmLabel={label}
        cancelLabel="Abbrechen"
        loading={archiving}
        onConfirm={handleConfirm}
      />
    </>
  );
}
