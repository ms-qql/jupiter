"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { NewSessionDialog } from "./new-session-dialog";

export function BoardSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-28 rounded-lg" />
      ))}
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-border py-20 text-center">
      <div className="text-4xl">🛰️</div>
      <div>
        <h2 className="text-lg font-semibold">Noch keine Sessions</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Starte deine erste Claude-Code-Session, um das Cockpit zu füllen.
        </p>
      </div>
      <NewSessionDialog>
        <button className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90">
          + Neue Session
        </button>
      </NewSessionDialog>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-red-500/40 bg-red-500/5 py-20 text-center">
      <div className="text-3xl">⚠️</div>
      <h2 className="text-lg font-semibold text-red-400">
        Backend nicht erreichbar
      </h2>
      <p className="max-w-sm text-sm text-muted-foreground">{message}</p>
      <p className="text-xs text-muted-foreground/70">
        Erneuter Versuch automatisch alle paar Sekunden.
      </p>
    </div>
  );
}
