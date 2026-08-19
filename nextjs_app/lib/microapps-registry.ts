// PROJ-40: Frontend-Komponenten-Registry für NATIVE Micro-Apps (kind=native).
//
// Trennung Metadaten ↔ Code (siehe Tech-Design D):
//   • Metadaten (Label, Icon, group, Reihenfolge) leben in backend/config/engines.yaml
//     und kommen über GET /engines — einheitlich für iframe UND native.
//   • Der CODE einer nativen App liegt im Repo unter components/microapps/<key>/
//     und wird HIER per `key` registriert. YAML kann keinen Code tragen.
//
// Eingebettete Apps (kind=iframe, z. B. Excalidraw) brauchen KEINEN Eintrag hier —
// sie werden über die url + EmbedTab gerendert.
//
// Lazy-Import: Der App-Code wird erst beim Öffnen der Route /apps/[key] geladen
// (kein Aufblähen des Cockpit-Bundles). Neue native App ⇒ Ordner anlegen + eine
// Zeile hier + einen `kind: native`-Eintrag in engines.yaml. Kein Code-Wildwuchs.

import { lazy, type LazyExoticComponent, type ComponentType } from "react";

/** Props, die jede native Micro-App-Komponente erhält. Bewusst schlank gehalten. */
export interface MicroAppComponentProps {
  /** Registry-Key der App (= Routen-Parameter). */
  appKey: string;
}

type MicroAppComponent = LazyExoticComponent<
  ComponentType<MicroAppComponentProps>
>;

/**
 * key (aus engines.yaml, kind=native) → Lazy-geladene React-Komponente.
 *
 * Neue native App ⇒ Ordner unter components/microapps/<key>/ anlegen, hier eine
 * Zeile ergänzen und einen `kind: native`-Eintrag in engines.yaml pflegen.
 */
export const MICROAPP_REGISTRY: Record<string, MicroAppComponent> = {
  // PROJ-41: Video Summary — erste echte native Micro-App.
  video_summary: lazy(
    () => import("@/components/microapps/video_summary/video-summary-app"),
  ),
  // PROJ-42: VPS-Admin — Dashboard (Host-Metriken + systemd-Service-Health).
  vps_admin: lazy(
    () => import("@/components/microapps/vps_admin/vps-admin-app"),
  ),
  // PROJ-53: Buch-Nuggets — Buch (Upload/URL) → KI-Kurzform inkl. Contra → Hal.
  book_nuggets: lazy(
    () => import("@/components/microapps/book_nuggets/book-nuggets-app"),
  ),
  // PROJ-69: Clipboard — geräteübergreifender Datei-Puffer mit HAL-Inbox.
  clipboard: lazy(
    () => import("@/components/microapps/clipboard/clipboard-app"),
  ),
  // UI-Check PROJ-14: Website-Audit + Branding + Redesign-Artefakte.
  ui_check: lazy(
    () => import("@/components/microapps/ui_check/ui-check-app"),
  ),
  // PROJ-55: Session-Kondensierung — Wochen-Sweep alter Sessions → Hal-Knowledge.
  session_condense: lazy(
    () => import("@/components/microapps/session_condense/session-condense-app"),
  ),
  // PROJ-67: Peppermint Dashboard — Ticketspiegel + automatische Frontdesk-Triage.
  peppermint_dashboard: lazy(
    () => import("@/components/microapps/peppermint_dashboard/peppermint-dashboard-app"),
  ),
  // PROJ-82: Hermes Kanban — nativ in Jupiter (Board + Task-Detail, kein iFrame).
  // Nativer Eintrag in der Orchestration-Sektion (vgl. engines.yaml).
  hermes_kanban: lazy(
    () => import("@/components/microapps/hermes_kanban/hermes-kanban-app"),
  ),
};

/** Liefert die native Komponente zu einem key — oder null, wenn nicht registriert
 *  (die Route zeigt dann einen sauberen „App nicht verfügbar"-Hinweis). */
export function resolveMicroApp(key: string): MicroAppComponent | null {
  return MICROAPP_REGISTRY[key] ?? null;
}
