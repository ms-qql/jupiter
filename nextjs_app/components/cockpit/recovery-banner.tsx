"use client";

// Recovery-Banner (PROJ-17): erkennt nach Reboot/Crash wiederherstellbare Stränge
// (GET /recovery) und blendet — nur wenn es welche gibt — einen prominenten Hinweis
// über dem Board ein. Öffnet den Recovery-Dialog. Lädt einmal beim Mount sowie nach
// jeder Wiederherstellung/Verwerfung neu; aktualisiert dabei auch die Session-Liste,
// damit eine wiederhergestellte Kind-Session sofort im Cockpit erscheint.

import { useCallback, useEffect, useRef, useState } from "react";
import { LifeBuoyIcon } from "lucide-react";
import { listRecovery } from "@/lib/api";
import type { RecoveryCandidate } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { RecoveryDialog } from "./recovery-dialog";
import { useNow, useSessions } from "./sessions-provider";

export function RecoveryBanner() {
  const { refresh: refreshSessions } = useSessions();
  const nowMs = useNow();
  const [candidates, setCandidates] = useState<RecoveryCandidate[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);
  // Zeigt auf die aktuelle Lade-Funktion des laufenden Effects (manueller Refresh
  // nach einer Aktion) — vermeidet setState direkt im Effect-Body (vgl. SessionsProvider).
  const reloadRef = useRef<() => void>(() => {});

  useEffect(() => {
    const ac = new AbortController();

    async function tick() {
      try {
        const res = await listRecovery(ac.signal);
        if (ac.signal.aborted) return;
        setCandidates(res.candidates);
      } catch {
        // Recovery ist additiv: schlägt der Abruf fehl, zeigen wir einfach keinen
        // Banner (das Cockpit bleibt nutzbar). Kein Fehler-Toast beim Hintergrund-Load.
      } finally {
        if (!ac.signal.aborted) setLoaded(true);
      }
    }

    reloadRef.current = () => void tick();
    void tick();
    return () => ac.abort();
  }, []);

  // Nach Aktion: Recovery-Liste neu laden UND Sessions auffrischen (Kind-Session).
  const handleChanged = useCallback(() => {
    reloadRef.current();
    refreshSessions();
  }, [refreshSessions]);

  if (!loaded || candidates.length === 0) return null;

  const n = candidates.length;

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
        <LifeBuoyIcon className="size-5 shrink-0 text-amber-500" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">
            {n === 1
              ? "1 Session aus dem Vault wiederherstellbar"
              : `${n} Sessions aus dem Vault wiederherstellbar`}
          </p>
          <p className="text-xs text-muted-foreground">
            Nach einem Neustart unterbrochene Stränge können bis zum letzten Handover
            fortgesetzt werden.
          </p>
        </div>
        <Button size="sm" onClick={() => setOpen(true)}>
          Ansehen
        </Button>
      </div>

      <RecoveryDialog
        open={open}
        onOpenChange={setOpen}
        candidates={candidates}
        nowMs={nowMs}
        onChanged={handleChanged}
      />
    </>
  );
}
