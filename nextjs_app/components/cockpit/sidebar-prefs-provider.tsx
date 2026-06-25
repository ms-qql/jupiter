"use client";

// PROJ-38: Hält Sichtbarkeit + Reihenfolge der Sidebar-Einträge, persistiert
// nach localStorage (versionierter Key) und merged beim Laden über die zentrale
// Definition — neue Sektionen (PROJ-39/40) erscheinen sichtbar, veraltete Keys
// werden ignoriert, bestehende Nutzerwünsche bleiben. Muster analog Theme:
// `mounted`-Flag verhindert Hydration-Mismatch; blockierter Storage → Defaults.
//
// PROJ-39: Neben den statischen `SIDEBAR_ITEMS` kennt der Provider zur Laufzeit
// angemeldete DYNAMISCHE Einträge (Orchestration-Apps aus der Engine-Registry).
// `registerDynamicItems` meldet sie an; die persistierten Präferenzen werden dann
// aus dem Roh-Storage nach-gemerged, sobald die Einträge bekannt sind.

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
  /** PROJ-39/40: Registry-getriebene Einträge zur Laufzeit anmelden. `namespace`
   *  trennt die Quellen (z. B. „orchestration", „micro"), damit sich mehrere
   *  Hooks nicht gegenseitig überschreiben. */
  registerDynamicItems: (namespace: string, items: SidebarItemDef[]) => void;
  /** false bis localStorage gelesen wurde (Hydration-Sicherheit). */
  mounted: boolean;
}

const SidebarPrefsContext = createContext<SidebarPrefsContextValue | null>(null);

// --- Pure Logik (ohne React/DOM, daher unit-testbar) ---------------------
// Alle Helfer nehmen optional die Definitionsliste entgegen (Default =
// statische SIDEBAR_ITEMS), damit der Provider die um dynamische Einträge
// erweiterte Liste durchreichen kann — ohne die bestehenden Tests zu brechen.

export function buildDefaults(defs: SidebarItemDef[] = SIDEBAR_ITEMS): PrefsMap {
  const m: PrefsMap = {};
  for (const it of defs) {
    m[it.key] = { visible: it.defaultVisible, order: it.defaultOrder };
  }
  return m;
}

/** Sektion eines Keys laut Definition (oder null, wenn unbekannt). */
function sectionOf(
  key: string,
  defs: SidebarItemDef[] = SIDEBAR_ITEMS,
): SidebarSectionId | null {
  return defs.find((it) => it.key === key)?.section ?? null;
}

/** Effektive Order eines Keys — Fallback auf den Default, falls (noch) nicht
 *  in der Präferenz-Map (dynamische Einträge vor dem Reconcile). */
function orderOf(prefs: PrefsMap, key: string, defs: SidebarItemDef[]): number {
  if (prefs[key]) return prefs[key].order;
  return defs.find((it) => it.key === key)?.defaultOrder ?? 0;
}

/** Geschwister-Keys einer Sektion, nach aktueller Reihenfolge sortiert. */
function siblingKeysSorted(
  prefs: PrefsMap,
  section: SidebarSectionId,
  defs: SidebarItemDef[] = SIDEBAR_ITEMS,
): string[] {
  return defs
    .filter((it) => it.section === section)
    .map((it) => it.key)
    .sort((a, b) => orderOf(prefs, a, defs) - orderOf(prefs, b, defs));
}

/** Reihenfolge-Werte für die übergebene Key-Folge neu vergeben (0..n). */
function applyOrder(prefs: PrefsMap, orderedKeys: string[]): PrefsMap {
  const next = { ...prefs };
  orderedKeys.forEach((k, i) => {
    next[k] = { ...next[k], order: i, visible: next[k]?.visible ?? true };
  });
  return next;
}

export function togglePref(prefs: PrefsMap, key: string): PrefsMap {
  if (!prefs[key]) return prefs;
  return { ...prefs, [key]: { ...prefs[key], visible: !prefs[key].visible } };
}

/** Eine Position nach oben (-1) / unten (+1), Grenzen sind no-ops. */
export function movePref(
  prefs: PrefsMap,
  key: string,
  dir: -1 | 1,
  defs: SidebarItemDef[] = SIDEBAR_ITEMS,
): PrefsMap {
  const section = sectionOf(key, defs);
  if (!section) return prefs;
  const keys = siblingKeysSorted(prefs, section, defs);
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
  defs: SidebarItemDef[] = SIDEBAR_ITEMS,
): PrefsMap {
  const section = sectionOf(fromKey, defs);
  if (!section || fromKey === beforeKey || sectionOf(beforeKey, defs) !== section)
    return prefs;
  const keys = siblingKeysSorted(prefs, section, defs).filter((k) => k !== fromKey);
  const at = keys.indexOf(beforeKey);
  if (at < 0) return prefs;
  keys.splice(at, 0, fromKey);
  return applyOrder(prefs, keys);
}

/** Gespeicherte Map über die Definition mergen (Defaults für unbekannte Keys). */
export function mergeStored(
  stored: unknown,
  defs: SidebarItemDef[] = SIDEBAR_ITEMS,
): PrefsMap {
  const m = buildDefaults(defs);
  if (stored && typeof stored === "object") {
    const s = stored as Record<string, Partial<ItemPref>>;
    for (const it of defs) {
      const p = s[it.key];
      if (p && typeof p.visible === "boolean" && typeof p.order === "number") {
        m[it.key] = { visible: p.visible, order: p.order };
      }
    }
  }
  return m;
}

/** Signatur einer Item-Liste (Key+Sektion+Reihenfolge) — erkennt echte
 *  Änderungen, ohne Objekt-Referenzen (Icon-Komponenten) zu vergleichen. */
function itemsSignature(items: SidebarItemDef[]): string {
  return items.map((it) => `${it.key}@${it.section}#${it.defaultOrder}`).join("|");
}

export function SidebarPrefsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [prefs, setPrefs] = useState<PrefsMap>(() => buildDefaults());
  // PROJ-39/40: dynamische Einträge pro Namespace (orchestration, micro …), damit
  // sich die anmeldenden Hooks nicht gegenseitig überschreiben.
  const [dynamicGroups, setDynamicGroups] = useState<
    Record<string, SidebarItemDef[]>
  >({});
  const dynamicItems = useMemo(
    () => Object.values(dynamicGroups).flat(),
    [dynamicGroups],
  );
  const [mounted, setMounted] = useState(false);
  // Roh-Storage merken → beim Anmelden dynamischer Einträge deren persistierte
  // Präferenz nach-mergen (mergeStored verwirft sonst noch-unbekannte Keys).
  const storedRef = useRef<unknown>(null);

  const allDefs = useMemo(
    () => [...SIDEBAR_ITEMS, ...dynamicItems],
    [dynamicItems],
  );

  // Einmalig aus localStorage laden + mergen. setState aus dem synchronen
  // Effect-Body heraushalten (Lint-konform, Muster wie theme-toggle).
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          storedRef.current = parsed;
          setPrefs(mergeStored(parsed));
        }
      } catch {
        // Privatmodus / blockiert → bei Defaults bleiben.
      }
      setMounted(true);
    });
    return () => cancelAnimationFrame(id);
  }, []);

  // PROJ-39: Sobald dynamische Einträge bekannt sind, deren persistierte Präferenz
  // aus dem Roh-Storage nach-mergen — laufende Änderungen (prev) gewinnen, dynamische
  // Keys kommen aus dem Storage, fehlende erhalten ihren Default.
  useEffect(() => {
    if (!mounted || dynamicItems.length === 0) return;
    setPrefs((prev) => {
      const base =
        storedRef.current && typeof storedRef.current === "object"
          ? { ...(storedRef.current as object), ...prev }
          : prev;
      return mergeStored(base, allDefs);
    });
  }, [allDefs, dynamicItems.length, mounted]);

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
      allDefs
        .filter((it) => it.section === section)
        .map((it) => ({
          ...it,
          ...(prefs[it.key] ?? { visible: it.defaultVisible, order: it.defaultOrder }),
        }))
        .sort((a, b) => a.order - b.order),
    [prefs, allDefs],
  );

  const visibleItems = useCallback(
    (section: SidebarSectionId) => resolve(section).filter((it) => it.visible),
    [resolve],
  );

  const toggleVisible = useCallback((key: string) => {
    setPrefs((prev) => togglePref(prev, key));
  }, []);

  const move = useCallback(
    (key: string, dir: -1 | 1) => {
      setPrefs((prev) => movePref(prev, key, dir, allDefs));
    },
    [allDefs],
  );

  const reorder = useCallback(
    (fromKey: string, beforeKey: string) => {
      setPrefs((prev) => reorderPref(prev, fromKey, beforeKey, allDefs));
    },
    [allDefs],
  );

  const reset = useCallback(() => setPrefs(buildDefaults(allDefs)), [allDefs]);

  const registerDynamicItems = useCallback(
    (namespace: string, items: SidebarItemDef[]) => {
      setDynamicGroups((prev) =>
        itemsSignature(prev[namespace] ?? []) === itemsSignature(items)
          ? prev
          : { ...prev, [namespace]: items },
      );
    },
    [],
  );

  const value = useMemo<SidebarPrefsContextValue>(
    () => ({
      visibleItems,
      allItems: resolve,
      toggleVisible,
      move,
      reorder,
      reset,
      registerDynamicItems,
      mounted,
    }),
    [
      visibleItems,
      resolve,
      toggleVisible,
      move,
      reorder,
      reset,
      registerDynamicItems,
      mounted,
    ],
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
