"use client";

// Einklappbarer „Archiv"-Bereich: beendete (done) Sessions, standardmäßig
// ausgeblendet. Bleiben anklickbar → Detail → fortsetzbar.

import { useState } from "react";
import { ArchiveIcon, ChevronDownIcon, ChevronRightIcon } from "lucide-react";
import type { Session } from "@/lib/types";
import { SessionTile } from "./session-tile";

export function ArchivedSection({
  sessions,
  now,
}: {
  sessions: Session[];
  now: number;
}) {
  const [open, setOpen] = useState(false);
  if (sessions.length === 0) return null;

  return (
    <section className="mt-6 border-t border-border pt-4">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        {open ? (
          <ChevronDownIcon className="size-4" />
        ) : (
          <ChevronRightIcon className="size-4" />
        )}
        <ArchiveIcon className="size-4" />
        <span>
          Archiv ({sessions.length}) — beendete Sessions
        </span>
      </button>

      {open && (
        <div className="mt-4 grid grid-cols-1 gap-3 opacity-90 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {sessions.map((s) => (
            <SessionTile key={s.session_id} session={s} now={now} />
          ))}
        </div>
      )}
    </section>
  );
}
