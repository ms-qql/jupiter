"use client";

// PROJ-38: Hält Sichtbarkeit + Reihenfolge der Sidebar-Einträge, persistiert
// nach localStorage (versionierter Key) und merged beim Laden über die zentrale
// Definition — neue Sektionen (PROJ-39/40) erscheinen sichtbar, veraltete Keys
// werden ignoriert, bestehende Nutzerwünsche bleiben. Muster analog Theme:
// `mounted`-Flag verhindert Hydration-Mismatch; blockierter Storage → Defaults.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  SIDEBAR_ITEMS,
  type SidebarItemDef,
  type SidebarSectionId,
} from "@/lib/sidebar-config";

const STORAGE_KEY = "jupiter.sidebar.v1";

export interface ItemPref {
  visible: boolean;
  order: number;
}
export type PrefsMap = Record<string, ItemPref>;

/** Eintrag-Definition + aufgelöste Präferenz. */
export interface ResolvedItem extends SidebarItemDef, ItemPref {}

interface SidebarPrefsContextValue {
  /** Sichtbare Einträge einer Sektion, nach Reihenfolge sortiert. */
  visibleItems: (section: SidebarSectionId) => ResolvedItem[];
  /** ALLE Einträge einer Sektion (für das Konfig-Panel), sortiert. */
  allItems: (section: SidebarSectionId) => ResolvedItem[];
  toggleVisible: (key: string) => void;
  /** Innerhalb der Sektion eine Position nach oben (-1) / unten (+1). */
  move: (key: string, dir: -1 | 1) => void;
  /** Drag-and-Drop: `fromKey` vor `beforeKey` einsortieren (gleiche Sektion). */
  reorder: (fromKey: string, beforeKey: string) => void;
  reset: () => void;
  /** false bis localStorage gelesen wurde (Hydration-Sicherheit). */
  mounted: boolean;
}

const SidebarPrefsContext = createContext<SidebarPrefsContextValue | null>(null);

// --- Pure Logik (ohne React/DOM, daher unit-testbar) ---------------------

export function buildDefaults(): PrefsMap {
  const m: PrefsMap = {};
  for (const it of SIDEBAR_ITEMS) {
    m[it.key] = { visible: it.defaultVisible, order: it.defaultOrder };
  }
  return m;
}

/** Sektion eines Keys laut Definition (oder null, wenn unbekannt). */
function sectionOf(key: string): SidebarSectionId | null {
  return SIDEBAR_ITEMS.find((it) => it.key === key)?.section ?? null;
}

/** Geschwister-Keys einer Sektion, nach aktueller Reihenfolge sortiert. */
function siblingKeysSorted(prefs: PrefsMap, section: SidebarSectionId): string[] {
  return SIDEBAR_ITEMS.filter((it) => it.section === section)
    .map((it) => it.key)
    .sort((a, b) => prefs[a].order - prefs[b].order);
}

/** Reihenfolge-Werte für die übergebene Key-Folge neu vergeben (0..n). */
function applyOrder(prefs: PrefsMap, orderedKeys: string[]): PrefsMap {
  const next = { ...prefs };
  orderedKeys.forEach((k, i) => {
    next[k] = { ...next[k], order: i };
  });
  return next;
}

export function togglePref(prefs: PrefsMap, key: string): PrefsMap {
  if (!prefs[key]) return prefs;
  return { ...prefs, [key]: { ...prefs[key], visible: !prefs[key].visible } };
}

/** Eine Position nach oben (-1) / unten (+1), Grenzen sind no-ops. */
export function movePref(prefs: PrefsMap, key: string, dir: -1 | 1): PrefsMap {
  const section = sectionOf(key);
  if (!section) return prefs;
  const keys = siblingKeysSorted(prefs, section);
  const i = keys.indexOf(key);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= keys.length) return prefs;
  [keys[i], keys[j]] = [keys[j], keys[i]];
  return applyOrder(prefs, keys);
}

/** Drag-and-Drop: `fromKey` direkt vor `beforeKey` einsortieren (gleiche Sektion). */
export function reorderPref(
  prefs: PrefsMap,
  fromKey: string,
  beforeKey: string,
): PrefsMap {
  const section = sectionOf(fromKey);
  if (!section || fromKey === beforeKey || sectionOf(beforeKey) !== section)
    return prefs;
  const keys = siblingKeysSorted(prefs, section).filter((k) => k !== fromKey);
  const at = keys.indexOf(beforeKey);
  if (at < 0) return prefs;
  keys.splice(at, 0, fromKey);
  return applyOrder(prefs, keys);
}

/** Gespeicherte Map über die Definition mergen (Defaults für unbekannte Keys). */
export function mergeStored(stored: unknown): PrefsMap {
  const m = buildDefaults();
  if (stored && typeof stored === "object") {
    const s = stored as Record<string, Partial<ItemPref>>;
    for (const it of SIDEBAR_ITEMS) {
      const p = s[it.key];
      if (p && typeof p.visible === "boolean" && typeof p.order === "number") {
        m[it.key] = { visible: p.visible, order: p.order };
      }
    }
  }
  return m;
}

export function SidebarPrefsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [prefs, setPrefs] = useState<PrefsMap>(buildDefaults);
  const [mounted, setMounted] = useState(false);

  // Einmalig aus localStorage laden + mergen. setState aus dem synchronen
  // Effect-Body heraushalten (Lint-konform, Muster wie theme-toggle).
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (raw) setPrefs(mergeStored(JSON.parse(raw)));
      } catch {
        // Privatmodus / blockiert → bei Defaults bleiben.
      }
      setMounted(true);
    });
    return () => cancelAnimationFrame(id);
  }, []);

  // Persistieren (erst nach dem initialen Laden, sonst Defaults überschreiben).
  useEffect(() => {
    if (!mounted) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      // Storage nicht verfügbar → Änderung gilt nur für diese Session.
    }
  }, [prefs, mounted]);

  const resolve = useCallback(
    (section: SidebarSectionId): ResolvedItem[] =>
      SIDEBAR_ITEMS.filter((it) => it.section === section)
        .map((it) => ({ ...it, ...prefs[it.key] }))
        .sort((a, b) => a.order - b.order),
    [prefs],
  );

  const visibleItems = useCallback(
    (section: SidebarSectionId) => resolve(section).filter((it) => it.visible),
    [resolve],
  );

  const toggleVisible = useCallback((key: string) => {
    setPrefs((prev) => togglePref(prev, key));
  }, []);

  const move = useCallback((key: string, dir: -1 | 1) => {
    setPrefs((prev) => movePref(prev, key, dir));
  }, []);

  const reorder = useCallback((fromKey: string, beforeKey: string) => {
    setPrefs((prev) => reorderPref(prev, fromKey, beforeKey));
  }, []);

  const reset = useCallback(() => setPrefs(buildDefaults()), []);

  const value = useMemo<SidebarPrefsContextValue>(
    () => ({
      visibleItems,
      allItems: resolve,
      toggleVisible,
      move,
      reorder,
      reset,
      mounted,
    }),
    [visibleItems, resolve, toggleVisible, move, reorder, reset, mounted],
  );

  return (
    <SidebarPrefsContext.Provider value={value}>
      {children}
    </SidebarPrefsContext.Provider>
  );
}

export function useSidebarPrefs(): SidebarPrefsContextValue {
  const ctx = useContext(SidebarPrefsContext);
  if (!ctx)
    throw new Error("useSidebarPrefs must be used within SidebarPrefsProvider");
  return ctx;
}
