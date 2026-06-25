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
  useRef,
  useState,
} from "react";
import {
  SIDEBAR_ITEMS,
  type SidebarItemDef,
  type SidebarSectionId,
} from "@/lib/sidebar-config";

const STORAGE_KEY = "jupiter.sidebar.v1";

interface ItemPref {
  visible: boolean;
  order: number;
}
type PrefsMap = Record<string, ItemPref>;

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

function buildDefaults(): PrefsMap {
  const m: PrefsMap = {};
  for (const it of SIDEBAR_ITEMS) {
    m[it.key] = { visible: it.defaultVisible, order: it.defaultOrder };
  }
  return m;
}

/** Gespeicherte Map über die Definition mergen (Defaults für unbekannte Keys). */
function mergeStored(stored: unknown): PrefsMap {
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

  // Stabile Sektions-Zugehörigkeit (Definition ist konstant zur Laufzeit).
  const sectionOf = useRef<Map<string, SidebarSectionId>>(
    new Map(SIDEBAR_ITEMS.map((it) => [it.key, it.section])),
  ).current;

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
    setPrefs((prev) => ({
      ...prev,
      [key]: { ...prev[key], visible: !prev[key].visible },
    }));
  }, []);

  // Reihenfolge-Werte innerhalb der Sektion neu vergeben (0..n).
  const applyOrder = useCallback(
    (prev: PrefsMap, orderedKeys: string[]): PrefsMap => {
      const next = { ...prev };
      orderedKeys.forEach((k, i) => {
        next[k] = { ...next[k], order: i };
      });
      return next;
    },
    [],
  );

  const siblingKeysSorted = useCallback(
    (prev: PrefsMap, section: SidebarSectionId): string[] =>
      SIDEBAR_ITEMS.filter((it) => it.section === section)
        .map((it) => it.key)
        .sort((a, b) => prev[a].order - prev[b].order),
    [],
  );

  const move = useCallback(
    (key: string, dir: -1 | 1) => {
      const section = sectionOf.get(key);
      if (!section) return;
      setPrefs((prev) => {
        const keys = siblingKeysSorted(prev, section);
        const i = keys.indexOf(key);
        const j = i + dir;
        if (i < 0 || j < 0 || j >= keys.length) return prev;
        [keys[i], keys[j]] = [keys[j], keys[i]];
        return applyOrder(prev, keys);
      });
    },
    [applyOrder, siblingKeysSorted, sectionOf],
  );

  const reorder = useCallback(
    (fromKey: string, beforeKey: string) => {
      const section = sectionOf.get(fromKey);
      if (!section || fromKey === beforeKey || sectionOf.get(beforeKey) !== section)
        return;
      setPrefs((prev) => {
        const keys = siblingKeysSorted(prev, section).filter((k) => k !== fromKey);
        const at = keys.indexOf(beforeKey);
        if (at < 0) return prev;
        keys.splice(at, 0, fromKey);
        return applyOrder(prev, keys);
      });
    },
    [applyOrder, siblingKeysSorted, sectionOf],
  );

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
