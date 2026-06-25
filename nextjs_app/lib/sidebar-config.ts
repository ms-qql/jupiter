// PROJ-38: Zentrale Definition der konfigurierbaren Sidebar-Einträge.
// EINZIGE Stelle, an der Sektionen/Einträge registriert werden — PROJ-39
// (Orchestration) und PROJ-40 (Micro-Apps) fügen hier künftig nur Zeilen hinzu.
// Die Nutzer-Präferenz (Sichtbarkeit + Reihenfolge) lebt getrennt im
// SidebarPrefsProvider (localStorage). Siehe Tech-Design PROJ-38.

import {
  AppWindowIcon,
  BotIcon,
  FileTextIcon,
  FolderIcon,
  LayoutDashboardIcon,
  PaperclipIcon,
  PenToolIcon,
  RadioIcon,
  ServerIcon,
  WavesIcon,
  type LucideIcon,
} from "lucide-react";

export type SidebarSectionId =
  | "workspace"
  | "sessions"
  | "orchestration"
  | "micro";

export interface SidebarSectionDef {
  id: SidebarSectionId;
  /** Überschrift (uppercase, gedämpft) wie bei „Aktive Sessions". */
  label: string;
}

export interface SidebarItemDef {
  /** Stabile ID — Schlüssel für die persistierte Präferenz. */
  key: string;
  label: string;
  icon: LucideIcon;
  /** Navigationsziel; fehlt bei strukturellen Einträgen (z. B. Session-Liste). */
  href?: string;
  section: SidebarSectionId;
  defaultVisible: boolean;
  /** Default-Position innerhalb der Sektion. */
  defaultOrder: number;
}

/** Reihenfolge der Sektionen in der Sidebar (Überschriften). */
export const SIDEBAR_SECTIONS: SidebarSectionDef[] = [
  { id: "workspace", label: "Workspace" },
  { id: "sessions", label: "Aktive Sessions" },
  // PROJ-39: „Orchestration" sitzt unter „Aktive Sessions". Ihre Einträge sind
  // NICHT statisch hier, sondern kommen aus der Engine-Registry (group=orchestration)
  // und werden zur Laufzeit über `registerDynamicItems` im Prefs-Provider angemeldet.
  { id: "orchestration", label: "Orchestration" },
  // PROJ-40: „Micro-Apps" sitzt UNTER „Orchestration". Einträge kommen ebenfalls
  // dynamisch aus der Engine-Registry (group=micro) — als eingebettete (kind=iframe)
  // ODER nativ in Jupiter programmierte App (kind=native, Render via
  // microapps-registry.ts). Excalidraw ist die erste (eingebettete) Micro-App.
  { id: "micro", label: "Micro-Apps" },
];

/**
 * Alle konfigurierbaren Einträge. Die „Aktive Sessions"-Liste ist als EIN
 * Eintrag modelliert (als Ganzes togglebar; einzelne Sessions sind bewusst
 * nicht konfigurierbar — siehe Spec).
 */
export const SIDEBAR_ITEMS: SidebarItemDef[] = [
  {
    key: "doku",
    label: "Doku",
    icon: FileTextIcon,
    href: "/doku",
    section: "workspace",
    defaultVisible: true,
    defaultOrder: 0,
  },
  {
    key: "dateien",
    label: "Dateien",
    icon: FolderIcon,
    href: "/dateien",
    section: "workspace",
    defaultVisible: true,
    defaultOrder: 1,
  },
  {
    key: "sessions",
    label: "Aktive Sessions",
    icon: LayoutDashboardIcon,
    section: "sessions",
    defaultVisible: true,
    defaultOrder: 0,
  },
];

export function sectionLabel(id: SidebarSectionId): string {
  return SIDEBAR_SECTIONS.find((s) => s.id === id)?.label ?? id;
}

// --- PROJ-39: Orchestration-Einträge aus der Engine-Registry ----------------

/** Bekannte lucide-Icons für Registry-Einträge (Name aus `engines.yaml`). */
const ORCHESTRATION_ICONS: Record<string, LucideIcon> = {
  paperclip: PaperclipIcon,
  waves: WavesIcon,
  radio: RadioIcon,
  bot: BotIcon,
  appwindow: AppWindowIcon,
  pentool: PenToolIcon,
  server: ServerIcon, // PROJ-42: VPS-Admin
};

/** Icon-Name (aus der Registry) → Komponente; Fallback ist ein neutrales App-Icon. */
export function resolveOrchestrationIcon(name: string | null | undefined): LucideIcon {
  if (!name) return AppWindowIcon;
  return ORCHESTRATION_ICONS[name.toLowerCase()] ?? AppWindowIcon;
}

/** Persistenz-Schlüssel eines Orchestration-Eintrags — eigener Namensraum, damit
 *  Registry-Keys nie mit statischen Einträgen (oder PROJ-40) kollidieren. */
export function orchestrationItemKey(engineKey: string): string {
  return `orch:${engineKey}`;
}

/** Baut aus einem Registry-Eintrag (key/label/icon) eine Sidebar-Item-Definition.
 *  `order` = Position laut Registry-Reihenfolge (Nutzer kann sie im Panel ändern). */
export function orchestrationItemDef(
  engine: { key: string; label: string; icon: string | null },
  order: number,
): SidebarItemDef {
  return {
    key: orchestrationItemKey(engine.key),
    label: engine.label,
    icon: resolveOrchestrationIcon(engine.icon),
    href: `/orchestration/${engine.key}`,
    section: "orchestration",
    defaultVisible: true,
    defaultOrder: order,
  };
}

// --- PROJ-40: Micro-Apps aus der Engine-Registry (group=micro) --------------

/** Persistenz-Schlüssel eines Micro-App-Eintrags — eigener Namensraum, damit
 *  Registry-Keys nie mit statischen Einträgen oder Orchestration kollidieren. */
export function microAppItemKey(engineKey: string): string {
  return `micro:${engineKey}`;
}

/** Umkehr von `microAppItemKey`: holt den Registry-Key (engines.yaml) aus einem
 *  Sidebar-Item-Key zurück (für die Status-Ampel-Auflösung, PROJ-42). */
export function microAppEngineKey(itemKey: string): string {
  return itemKey.startsWith("micro:") ? itemKey.slice("micro:".length) : itemKey;
}

/** Baut aus einem Registry-Eintrag (key/label/icon) eine Sidebar-Item-Definition.
 *  Ziel ist die Vollbild-Route `/apps/[key]` — sie verzweigt selbst nach `kind`
 *  (iframe ⇒ EmbedTab, native ⇒ microapps-registry). Icon-Auflösung teilt sich
 *  die Tabelle mit Orchestration. */
export function microAppItemDef(
  engine: { key: string; label: string; icon: string | null },
  order: number,
): SidebarItemDef {
  return {
    key: microAppItemKey(engine.key),
    label: engine.label,
    icon: resolveOrchestrationIcon(engine.icon),
    href: `/apps/${engine.key}`,
    section: "micro",
    defaultVisible: true,
    defaultOrder: order,
  };
}
