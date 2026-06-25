"use client";

// PROJ-42: pollt den Gesamtstatus (Ampel) der Micro-Apps, die einen
// leichtgewichtigen Status-Endpoint anbieten (Registry `microapp-status.ts`),
// für das Farb-Icon am Sidebar-Eintrag. Niederfrequent (15 s) — der Status läuft
// unabhängig davon, ob die App geöffnet ist, und der Server liefert ihn aus dem
// gecachten Worker-Stand (keine Neuberechnung pro Request). Nicht erreichbar →
// „grau" (unbekannt), nie ein Crash der Sidebar.

import { useEffect, useState } from "react";
import type { Ampel } from "@/lib/status";
import { microAppStatusFetcher } from "@/lib/microapp-status";

const STATUS_POLL_MS = 15000;

/** appKey → Ampelfarbe. Nur Keys mit registriertem Fetcher erscheinen. */
export function useMicroAppStatuses(appKeys: string[]): Record<string, Ampel> {
  const [statuses, setStatuses] = useState<Record<string, Ampel>>({});
  // Stabile Signatur der zu pollenden Keys (sortiert), damit der Effect nicht bei
  // jeder Render-Identität neu aufsetzt.
  const keysSig = [...appKeys].sort().join(",");

  useEffect(() => {
    const keys = keysSig ? keysSig.split(",") : [];
    const provided = keys.filter((k) => microAppStatusFetcher(k));
    // Keine App mit Status-Endpoint → nichts zu pollen. (Verbliebene Einträge im
    // State schaden nicht: die Rail liest nur Keys aktuell sichtbarer Apps.)
    if (provided.length === 0) return;
    const ctrl = new AbortController();
    const tick = () => {
      provided.forEach((k) => {
        const fetcher = microAppStatusFetcher(k);
        if (!fetcher) return;
        fetcher(ctrl.signal)
          .then((color) =>
            setStatuses((s) => (s[k] === color ? s : { ...s, [k]: color })),
          )
          .catch(() => {
            if (ctrl.signal.aborted) return;
            // Degradiert sauber zu „grau"/unbekannt statt veraltet grün zu zeigen.
            setStatuses((s) => (s[k] === "gray" ? s : { ...s, [k]: "gray" }));
          });
      });
    };
    tick();
    const t = setInterval(tick, STATUS_POLL_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, [keysSig]);

  return statuses;
}
