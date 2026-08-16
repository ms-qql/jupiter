"use client";

// PROJ-78: Host für den Session-Arbeitsbereich. Liest die kanonische ID aus der
// URL und führt sie über denselben zentralen Öffnen-/Fokussieren-Vorgang wie
// Sidebar, Vorgänger-/Nachfolger- und Deep-Link-Einstiege in den Arbeitsbereich
// über. Rendert 1–2 Session-Ansichten: auf Desktop nebeneinander, darunter nur
// die aktive mit Tab-Umschalter.

import { use, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/components/cockpit/workspace-provider";
import { SessionView } from "@/components/cockpit/session-view";
import { useSessions } from "@/components/cockpit/sessions-provider";
import { displayName } from "@/lib/status";

export default function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { openIds, activeId, open, focus } = useWorkspace();
  const { sessions } = useSessions();

  // Zentrale Regel: beim direkten Aufruf (Deep Link, Reload) die ID in den
  // Arbeitsbereich übernehmen — füllt den freien Platz, sonst ersetzt sie die
  // aktive Ansicht; bereits sichtbar → nur fokussieren (kein Duplikat).
  useEffect(() => {
    open(id);
  }, [id, open]);

  // Die aktive Ansicht folgt der URL nur beim allerersten Aufruf bzw. wenn die
  // Seite selbst den Arbeitsbereich geöffnet hat. Vor dem ersten open()-Effect
  // rendern wir bereits die URL-Session, um keinen Leer-Blitz zu zeigen.
  const twoViews = openIds.length === 2;
  const active = activeId ?? id;
  const views = twoViews ? openIds : [active];

  return (
    <div className="flex h-dvh flex-col">
      {/* Mobile-Tab-Leiste (unterhalb Desktop): wechselt zwischen offenen Sessions. */}
      {twoViews && (
        <div
          role="tablist"
          aria-label="Offene Session-Ansichten"
          className="flex shrink-0 items-center gap-1 border-b border-border px-2 py-1.5 md:hidden"
        >
          {openIds.map((sid) => {
            const s = sessions.find((x) => x.session_id === sid);
            return (
              <button
                key={sid}
                role="tab"
                aria-selected={sid === active}
                onClick={() => focus(sid)}
                className={cn(
                  "min-w-0 flex-1 truncate rounded-md px-3 py-1.5 text-sm transition-colors",
                  sid === active
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50",
                )}
              >
                {s ? displayName(s) : sid}
              </button>
            );
          })}
        </div>
      )}

      {/* Alle offenen Ansichten, jeweils EINMAL gemountet. Auf Desktop stehen
          zwei gleichwertig nebeneinander; unterhalb (md) ist nur die aktive
          sichtbar (die zweite bleibt via CSS verborgen, ohne Zustandsverlust
          oder Duplikat-WebSocket). Einzel-Ansicht bleibt zentriert begrenzt. */}
      <div className="flex min-h-0 flex-1">
        {views.map((sid) => (
          <div
            key={sid}
            className={cn(
              "min-w-0 flex-1",
              twoViews && "border-r border-border last:border-r-0",
              // Einzel-Ansicht: bewährte zentrierte Breite beibehalten.
              !twoViews && "mx-auto max-w-4xl",
              // Mobil mit zwei Ansichten: nur die aktive zeigen.
              twoViews && sid !== active && "hidden md:block",
            )}
          >
            <SessionView id={sid} />
          </div>
        ))}
      </div>
    </div>
  );
}
