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
};

/** Liefert die native Komponente zu einem key — oder null, wenn nicht registriert
 *  (die Route zeigt dann einen sauberen „App nicht verfügbar"-Hinweis). */
export function resolveMicroApp(key: string): MicroAppComponent | null {
  return MICROAPP_REGISTRY[key] ?? null;
}
