// PROJ-42: Generischer Status-Provider je Micro-App-Key für die Sidebar-Ampel.
//
// Bewusst NICHT hart auf VPS-Admin verdrahtet: jede native Micro-App, die einen
// leichtgewichtigen Gesamtstatus anbietet, registriert hier EINE Zeile (Key →
// Fetcher, der eine Ampel-Farbe liefert). Die Sidebar (`use-microapp-status`)
// pollt nur Keys mit registriertem Fetcher — alle übrigen Einträge bleiben ohne
// Ampel. So kann später z. B. eine weitere App ebenfalls ein Statuslicht zeigen,
// ohne die Rail-Komponente anzufassen.

import type { Ampel } from "./status";
import { getMetricsStatus } from "./api";

/** Liefert die Sidebar-Ampelfarbe einer App (oder wirft bei Nichterreichbarkeit —
 *  der Aufrufer degradiert dann sauber zu „unbekannt"/grau). */
export type MicroAppStatusFetcher = (signal?: AbortSignal) => Promise<Ampel>;

/** appKey (= engines.yaml-Key, kind=native) → Status-Fetcher. */
export const MICROAPP_STATUS_PROVIDERS: Record<string, MicroAppStatusFetcher> = {
  // VPS-Admin: leichter Gesamt-Ampel-Endpoint (green/amber/red ⊂ Ampel).
  vps_admin: async (signal) => (await getMetricsStatus(signal)).status,
};

export function microAppStatusFetcher(
  appKey: string,
): MicroAppStatusFetcher | null {
  return MICROAPP_STATUS_PROVIDERS[appKey] ?? null;
}
