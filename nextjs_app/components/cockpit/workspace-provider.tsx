"use client";

// PROJ-78: Flüchtiger Session-Arbeitsbereich mit zwei Arbeitsflächen (zwei
// gleichberechtigte Pane-Slots, je Session- oder Datei-Inhalt) plus Dateivollansicht.
// Reine Client-Komponente, keine Backend-Änderung.
//
// Zentrale Öffnen-/Fokussieren-Regel (siehe open()):
//   - bereits sichtbar → nur fokussieren (kein Duplikat);
//   - sonst den freien Pane-Slot belegen;
//   - sonst den aktiven Pane ersetzen.
//
// Dateien („toggleFiles") folgen derselben Regel mit der Sonderbedingung, dass
// die jeweils aktive Session sichtbar bleibt: gibt es einen freien Slot, wird
// er benutzt; sonst ersetzt „Dateien" den nicht aktiven Pane. Damit ist die
// aktive Session nie versehentlich verdeckt.
//
// Entwürfe bleiben pro Session-ID (lokalStorage) erhalten — gleichgültig, in
// welchem Pane die Session liegt und ob sie geschlossen/regeöffnet wird.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";

const DRAFTS_KEY = "jupiter.sessionDrafts";
/** Harte Grenzen für die Trennlinien-Position, damit Composer und Dateiliste
 *  nie ganz zusammengequetscht werden. Werte in Bruchteilen (0..1). */
export const SPLIT_MIN = 0.2;
export const SPLIT_MAX = 0.8;
const SPLIT_DEFAULT = 0.5;

type Drafts = Record<string, string>;

export type PaneIndex = 0 | 1;
export type Pane =
  | { kind: "session"; id: string }
  | { kind: "files" }
  | null;

interface WorkspaceContextValue {
  /** Inhalt der zwei Pane-Slots (null = leer). */
  panes: [Pane, Pane];
  /** Welcher Pane gilt als aktiv (URL folgt ihm). */
  activeIndex: PaneIndex;
  /** Welcher Pane hält gerade die Dateivollansicht (überlagert beide Pane). */
  fileFullscreen: boolean;
  /** Position der Trennlinie (0 = linksbündig, 1 = rechtsbündig). */
  splitRatio: number;
  /** ID der aktiven Session (== panes[activeIndex]?.id, sofern es eine Session ist). */
  activeSessionId: string | null;
  /** Liste der aktuell eingeblendeten Session-IDs (Panes, die eine Session halten). */
  sessionIds: string[];
  /** Zentrale Öffnen-/Fokussieren-Regel. */
  open: (id: string) => void;
  /** Schließt nur die Ansicht; Session und Entwurf bleiben erhalten. */
  close: (id: string) => void;
  /** Macht genau diesen Pane zum aktiven Pane (URL folgt). */
  focus: (index: PaneIndex) => void;
  /** Aktiviert/deaktiviert die Datei-Arbeitsfläche (zweiter Pane). */
  toggleFiles: () => void;
  /** Wechselt in die Dateivollansicht (eine Datei ist zur Vorschau geöffnet). */
  openFileFullscreen: () => void;
  /** Zurück aus der Dateivollansicht in die Zwei-Pane-Sicht. */
  closeFileFullscreen: () => void;
  /** Setzt die Trennlinie (z. B. von der SplitDivider-Komponente). */
  setSplitRatio: (r: number) => void;
  /** Composer-Entwurf je Session. */
  draft: (id: string) => string;
  setDraft: (id: string, text: string) => void;
  clearDraft: (id: string) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function readStoredDrafts(): Drafts {
  try {
    if (typeof window === "undefined") return {};
    const raw = window.localStorage.getItem(DRAFTS_KEY);
    return raw ? (JSON.parse(raw) as Drafts) : {};
  } catch {
    return {};
  }
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [panes, setPanes] = useState<[Pane, Pane]>([null, null]);
  const [activeIndex, setActiveIndex] = useState<PaneIndex>(0);
  const [fileFullscreen, setFileFullscreen] = useState(false);
  const [splitRatio, _setSplitRatio] = useState(SPLIT_DEFAULT);
  const [drafts, setDrafts] = useState<Drafts>(readStoredDrafts);

  // Entwürfe nach jedem Wechsel extern persistieren (localStorage = externer State).
  useEffect(() => {
    try {
      window.localStorage.setItem(DRAFTS_KEY, JSON.stringify(drafts));
    } catch {
      /* localStorage nicht verfügbar → Entwürfe nur für diese Sitzung. */
    }
  }, [drafts]);

  // Ref-Spiegel, damit Callback-Implementierungen Stale-Closures vermeiden,
  // ohne dass jeder Callback neu erzeugt werden muss.
  const panesRef = useRef<[Pane, Pane]>(panes);
  const activeIndexRef = useRef<PaneIndex>(activeIndex);
  useEffect(() => {
    panesRef.current = panes;
  }, [panes]);
  useEffect(() => {
    activeIndexRef.current = activeIndex;
  }, [activeIndex]);
  const pathnameRef = useRef(pathname);
  useEffect(() => {
    pathnameRef.current = pathname;
  }, [pathname]);

  // setSplitRatio klemmt auf [SPLIT_MIN, SPLIT_MAX], damit Composer und
  // Dateiliste nie ganz zusammengequetscht werden.
  const setSplitRatio = useCallback((r: number) => {
    _setSplitRatio(Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, r)));
  }, []);

  // Pane <-> Session-ID Helfer werden jetzt als reine Funktionen unter
  // `computeOpenPanes` / `computeClosePanes` / `computeToggleFiles` definiert
  // und sind dort testbar.

  // Zentrale Öffnen-/Fokussieren-Regel.
  const open = useCallback((id: string) => {
    const result = computeOpenPanes(panesRef.current, activeIndexRef.current, id);
    if (result.activeIndex !== activeIndexRef.current) {
      setActiveIndex(result.activeIndex);
    }
    if (result.panes !== panesRef.current) {
      setPanes(result.panes);
    }
  }, []);

  // BUG-1b-Fix: Der Rücksprung zu "/" beim Schließen der letzten Ansicht lief
  // vorher als passiver Effekt auf `openIds.length === 0` — das feuerte in
  // derselben Commit-Phase wie der open(id)-Effekt von page.tsx (Kind vor
  // Eltern), aber noch mit dem altem (leeren) State, weil State-Updates aus
  // Effekten nicht synchron in Geschwister-Effekten sichtbar sind. Ergebnis:
  // Deep-Link/Reload auf /sessions/<id> konnte zu "/" zurückspringen, bevor
  // open(id) überhaupt griff. Fix: Rücksprung nur noch als direkte Folge des
  // expliziten close()-Aufrufs (echte Nutzeraktion, keine Race mit Mount-Effekten).
  //
  // BUG-3-Fix: setActiveId und router.replace liefen INNERHALB des
  // setOpenIds-Updaters. React sieht Updater als nicht-strikte Funktion und
  // doppel-aufruft sie in StrictMode; ein router.replace darin ist harmlos
  // (idempotent), aber riskant. Beide Seiteneffekte stehen jetzt im
  // close()-Body, der Updater ist rein.
  const close = useCallback(
    (id: string) => {
      const result = computeClosePanes(panesRef.current, activeIndexRef.current, id);
      if (result.panes === panesRef.current) return;
      setPanes(result.panes);
      // Datei-Vollansicht verlassen, falls die geschlossene Session dort
      // offen war — der Explorer selbst bleibt aber im Pane stehen.
      setFileFullscreen(false);
      if (result.activeIndex !== activeIndexRef.current) {
        setActiveIndex(result.activeIndex);
        if (result.activeIndex === 0 && result.bothClosed) {
          if (pathnameRef.current.startsWith("/sessions/")) {
            router.replace("/", { scroll: false });
          }
        }
      }
    },
    [router],
  );

  const focus = useCallback((index: PaneIndex) => {
    setActiveIndex(index);
  }, []);

  const toggleFiles = useCallback(() => {
    const result = computeToggleFiles(panesRef.current, activeIndexRef.current);
    if (result.panes !== panesRef.current) {
      setPanes(result.panes);
    }
    if (result.activeIndex !== activeIndexRef.current) {
      setActiveIndex(result.activeIndex);
      if (result.bothClosed && pathnameRef.current.startsWith("/sessions/")) {
        router.replace("/", { scroll: false });
      }
    }
    if (result.clearedFileFullscreen) {
      setFileFullscreen(false);
    }
  }, [router]);

  const openFileFullscreen = useCallback(() => {
    setFileFullscreen(true);
  }, []);
  const closeFileFullscreen = useCallback(() => {
    setFileFullscreen(false);
  }, []);

  const draft = useCallback((id: string) => drafts[id] ?? "", [drafts]);
  const setDraft = useCallback((id: string, text: string) => {
    setDrafts((prev) => ({ ...prev, [id]: text }));
  }, []);
  const clearDraft = useCallback((id: string) => {
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  // URL folgt der aktiven Session — aber nur im Session-Arbeitsbereich. Der
  // Rücksprung zu "/" bei leerem Workspace passiert ausschließlich in close()
  // (echte Nutzeraktion), nicht in einem Reaktiv-Effekt (Race mit open()-Mount
  // auf Deep Links, siehe BUG-1b).
  const activeSessionId = panes[activeIndex]?.kind === "session"
    ? (panes[activeIndex] as { kind: "session"; id: string }).id
    : null;
  useEffect(() => {
    if (activeSessionId && pathname.startsWith("/sessions/")) {
      router.replace(`/sessions/${activeSessionId}`, { scroll: false });
    }
  }, [activeSessionId, pathname, router]);

  const sessionIds = useMemo(() => {
    const ids: string[] = [];
    if (panes[0]?.kind === "session") ids.push(panes[0].id);
    if (panes[1]?.kind === "session") ids.push(panes[1].id);
    return ids;
  }, [panes]);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      panes,
      activeIndex,
      fileFullscreen,
      splitRatio,
      activeSessionId,
      sessionIds,
      open,
      close,
      focus,
      toggleFiles,
      openFileFullscreen,
      closeFileFullscreen,
      setSplitRatio,
      draft,
      setDraft,
      clearDraft,
    }),
    [
      panes,
      activeIndex,
      fileFullscreen,
      splitRatio,
      activeSessionId,
      sessionIds,
      open,
      close,
      focus,
      toggleFiles,
      openFileFullscreen,
      closeFileFullscreen,
      setSplitRatio,
      draft,
      setDraft,
      clearDraft,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace muss innerhalb von WorkspaceProvider stehen");
  return ctx;
}

/** Reine Selector-Helfer für Tests/UI: ist eine Pane sichtbar? */
export function isPaneFilled(p: Pane): p is Exclude<Pane, null> {
  return p !== null;
}

/** Reine Selector-Helfer: ist links/rechts eine Session? */
export function paneSessionId(p: Pane): string | null {
  return p?.kind === "session" ? p.id : null;
}

// === Reine Pane-Logik (testbar, ohne React-State) =========================

/**
 * Zentrale Öffnen-/Fokussieren-Regel: bereits sichtbar → nur fokussieren;
 * sonst den freien Pane-Slot belegen; sonst den aktiven Pane ersetzen.
 * Gibt { panes, activeIndex } zurück; bei unverändertem State dieselbe
 * Referenz, damit React-Renders ausbleiben.
 */
export function computeOpenPanes(
  panes: [Pane, Pane],
  activeIndex: PaneIndex,
  id: string,
): { panes: [Pane, Pane]; activeIndex: PaneIndex } {
  const existing = findSessionPaneIndex(panes, id);
  if (existing !== null) {
    return existing === activeIndex
      ? { panes, activeIndex }
      : { panes, activeIndex: existing };
  }
  const empty = findEmptyPane(panes);
  if (empty !== null) {
    const next: [Pane, Pane] = [...panes] as [Pane, Pane];
    next[empty] = { kind: "session", id };
    return { panes: next, activeIndex: empty };
  }
  const next: [Pane, Pane] = [...panes] as [Pane, Pane];
  next[activeIndex] = { kind: "session", id };
  return { panes: next, activeIndex };
}

/**
 * Schließt die Ansicht der genannten Session. Wird die aktive View
 * geschlossen, übernimmt die verbleibende View (oder der Cockpit fällt
 * leer zurück). Gibt { panes, activeIndex, bothClosed } zurück; wenn
 * `bothClosed` true ist, sollte der Konsument aus /sessions/* zu /
 * zurückspringen.
 */
export function computeClosePanes(
  panes: [Pane, Pane],
  activeIndex: PaneIndex,
  id: string,
): { panes: [Pane, Pane]; activeIndex: PaneIndex; bothClosed: boolean } {
  const idx = findSessionPaneIndex(panes, id);
  if (idx === null) {
    return { panes, activeIndex, bothClosed: false };
  }
  const next: [Pane, Pane] = [...panes] as [Pane, Pane];
  next[idx] = null;
  if (activeIndex !== idx) {
    return { panes: next, activeIndex, bothClosed: false };
  }
  const other = (idx === 0 ? 1 : 0) as PaneIndex;
  if (next[other] !== null) {
    return { panes: next, activeIndex: other, bothClosed: false };
  }
  return { panes: next, activeIndex: 0, bothClosed: true };
}

/**
 * Schaltet die Datei-Arbeitsfläche um: ist sie schon offen, wird der
 * Datei-Pane geleert; sonst wird sie entweder in den freien Slot gehängt
 * oder ersetzt den nicht-aktiven Pane (damit die aktive Session sichtbar
 * bleibt). Gibt { panes, activeIndex, bothClosed, clearedFileFullscreen }
 * zurück.
 */
export function computeToggleFiles(
  panes: [Pane, Pane],
  activeIndex: PaneIndex,
): {
  panes: [Pane, Pane];
  activeIndex: PaneIndex;
  bothClosed: boolean;
  clearedFileFullscreen: boolean;
} {
  // Schon offen → Datei-Pane leeren.
  if (panes[0]?.kind === "files") {
    const next: [Pane, Pane] = [...panes] as [Pane, Pane];
    next[0] = null;
    if (activeIndex === 0) {
      if (next[1] !== null) {
        return { panes: next, activeIndex: 1, bothClosed: false, clearedFileFullscreen: true };
      }
      return { panes: next, activeIndex: 0, bothClosed: true, clearedFileFullscreen: true };
    }
    return { panes: next, activeIndex, bothClosed: false, clearedFileFullscreen: true };
  }
  if (panes[1]?.kind === "files") {
    const next: [Pane, Pane] = [...panes] as [Pane, Pane];
    next[1] = null;
    if (activeIndex === 1) {
      if (next[0] !== null) {
        return { panes: next, activeIndex: 0, bothClosed: false, clearedFileFullscreen: true };
      }
      return { panes: next, activeIndex: 0, bothClosed: true, clearedFileFullscreen: true };
    }
    return { panes: next, activeIndex, bothClosed: false, clearedFileFullscreen: true };
  }
  // Noch nicht offen → in den freien Slot oder ersetze nicht-aktiven Pane.
  const empty = findEmptyPane(panes);
  if (empty !== null) {
    const next: [Pane, Pane] = [...panes] as [Pane, Pane];
    next[empty] = { kind: "files" };
    return { panes: next, activeIndex, bothClosed: false, clearedFileFullscreen: false };
  }
  const other = (activeIndex === 0 ? 1 : 0) as PaneIndex;
  const next: [Pane, Pane] = [...panes] as [Pane, Pane];
  next[other] = { kind: "files" };
  return { panes: next, activeIndex, bothClosed: false, clearedFileFullscreen: false };
}

function findSessionPaneIndex(panes: [Pane, Pane], id: string): PaneIndex | null {
  if (panes[0]?.kind === "session" && panes[0].id === id) return 0;
  if (panes[1]?.kind === "session" && panes[1].id === id) return 1;
  return null;
}

function findEmptyPane(panes: [Pane, Pane]): PaneIndex | null {
  if (panes[0] === null) return 0;
  if (panes[1] === null) return 1;
  return null;
}
