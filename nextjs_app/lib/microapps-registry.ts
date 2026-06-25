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
 * Noch leer: Es existiert derzeit keine native Micro-App (Excalidraw ist iframe).
 * Beispiel für eine künftige native App:
 *
 *   rechner: lazy(() => import("@/components/microapps/rechner/rechner-app")),
 */
export const MICROAPP_REGISTRY: Record<string, MicroAppComponent> = {};

/** Liefert die native Komponente zu einem key — oder null, wenn nicht registriert
 *  (die Route zeigt dann einen sauberen „App nicht verfügbar"-Hinweis). */
export function resolveMicroApp(key: string): MicroAppComponent | null {
  return MICROAPP_REGISTRY[key] ?? null;
}
