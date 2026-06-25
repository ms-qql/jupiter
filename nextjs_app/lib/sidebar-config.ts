// PROJ-38: Zentrale Definition der konfigurierbaren Sidebar-Einträge.
// EINZIGE Stelle, an der Sektionen/Einträge registriert werden — PROJ-39
// (Orchestration) und PROJ-40 (Micro-Apps) fügen hier künftig nur Zeilen hinzu.
// Die Nutzer-Präferenz (Sichtbarkeit + Reihenfolge) lebt getrennt im
// SidebarPrefsProvider (localStorage). Siehe Tech-Design PROJ-38.

import {
  FileTextIcon,
  FolderIcon,
  LayoutDashboardIcon,
  type LucideIcon,
} from "lucide-react";

export type SidebarSectionId = "workspace" | "sessions";

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
