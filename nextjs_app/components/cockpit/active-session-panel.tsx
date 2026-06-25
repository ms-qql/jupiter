"use client";

// PROJ-37: Rechte „Ansicht"-Spalte des Fileexplorers, solange KEINE Datei mit
// Vorschau gewählt ist. Statt eines leeren Platzhalters bleibt hier das aktive
// Fenster — eine kompakte Übersicht der zuletzt fokussierten (bzw. dringlichsten
// laufenden) Session. Speist sich ausschließlich aus dem bereits pollenden
// SessionsProvider → keine zweite WebSocket-Instanz, kein Reconnect, kein
// Doppel-Mount. Voll-Live + Eingabe bleibt einen Klick entfernt (/sessions/<id>).

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  contextLabel,
  displayName,
  formatDuration,
  phaseLabel,
  pickActiveSession,
  statusMeta,
} from "@/lib/status";
import { Ampel } from "./ampel";
import { useNow, useSessions } from "./sessions-provider";

export function ActiveSessionPanel() {
  const { sessions, initialLoading, focusedSessionId } = useSessions();
  const now = useNow();

  const session = pickActiveSession(sessions, focusedSessionId);

  // Sonderfall: keine laufende Session → neutraler Hinweis (kein Leer-Bug, kein
  // Fehler). Während des allerersten Polls nicht vorschnell „keine" behaupten.
  if (!session) {
    return (
      <p className="py-20 text-center text-sm text-muted-foreground">
        {initialLoading
          ? "Lädt…"
          : "Keine aktive Session — wähle links eine Datei für die Vorschau."}
      </p>
    );
  }

  const meta = statusMeta(session.status);
  const role = session.role?.trim();
  const phase = phaseLabel(session.abc_phase);
  const pending = session.pending_decisions.length;

  return (
    <section className="flex flex-col gap-4">
      <p className="text-xs uppercase tracking-wider text-muted-foreground">
        Aktive Session
      </p>

      <div className="rounded-lg border border-border bg-card/40 p-4">
        <div className="flex items-start gap-3">
          <Ampel color={meta.ampel} className="mt-1 shrink-0" />
          <div className="min-w-0 flex-1">
            <h2
              className="truncate text-base font-semibold"
              title={displayName(session)}
            >
              {displayName(session)}
            </h2>
            <p className="truncate text-sm text-muted-foreground">
              {role ? `${role} · ${meta.label}` : meta.label}
            </p>
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          {phase && (
            <div className="min-w-0">
              <dt className="text-xs text-muted-foreground">Phase</dt>
              <dd className="truncate">{phase}</dd>
            </div>
          )}
          <div className="min-w-0">
            <dt className="text-xs text-muted-foreground">Kontext</dt>
            <dd className="truncate">
              {contextLabel(session.context_fill_pct, session.context_known)}
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="text-xs text-muted-foreground">Aktiv seit</dt>
            <dd className="truncate tabular-nums">
              {formatDuration(session.created_at, now)}
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="text-xs text-muted-foreground">Letzte Aktivität</dt>
            <dd className="truncate tabular-nums">
              {formatDuration(session.last_activity, now)}
            </dd>
          </div>
        </dl>

        {pending > 0 && (
          <p className="mt-4 rounded-md border border-orange-500/40 bg-orange-500/10 px-3 py-2 text-xs text-orange-600 dark:text-orange-400">
            {pending === 1
              ? "1 Freigabe wartet auf dich."
              : `${pending} Freigaben warten auf dich.`}
          </p>
        )}

        <Link href={`/sessions/${session.session_id}`} className="mt-4 block">
          <Button size="sm" className="w-full">
            Session öffnen <ArrowRight className="size-4" />
          </Button>
        </Link>
      </div>

      <p className="text-center text-xs text-muted-foreground">
        Wähle links eine Datei, um sie hier in der Vorschau zu öffnen.
      </p>
    </section>
  );
}
