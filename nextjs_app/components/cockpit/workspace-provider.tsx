"use client";

// PROJ-78: Flüchtiger Session-Arbeitsbereich (nur clientseitig, keine Backend-
// Änderung). Hält bis zu zwei geöffnete Session-Ansichten + die aktive Ansicht.
// Der zentrale open-/close-/focus-Vorgang verhindert Dubletten, nutzt den freien
// Platz und ersetzt sonst die aktive Ansicht. Entwürfe je Session überleben
// Wechsel, Schließen und Reload (localStorage) — nicht Gerät-übergreifend.

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

const MAX_VIEWS = 2;
const DRAFTS_KEY = "jupiter.sessionDrafts";

type Drafts = Record<string, string>;

interface WorkspaceContextValue {
  /** Geöffnete Session-IDs, maximal zwei, Reihenfolge = Anzeige-Reihenfolge. */
  openIds: string[];
  /** Aktive (fokussierte) Session-ID oder null. */
  activeId: string | null;
  /** Zentrale Öffnen-/Fokussieren-Regel (siehe open()). */
  open: (id: string) => void;
  /** Schließt nur die Ansicht — Session und Entwurf bleiben erhalten. */
  close: (id: string) => void;
  /** Setzt die aktive Ansicht ohne Duplikat. */
  focus: (id: string) => void;
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
  const [openIds, setOpenIds] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Drafts>(readStoredDrafts);

  // Entwürfe nach jedem Wechsel extern persistieren (localStorage = externer State).
  useEffect(() => {
    try {
      window.localStorage.setItem(DRAFTS_KEY, JSON.stringify(drafts));
    } catch {
      /* localStorage nicht verfügbar → Entwürfe nur für diese Sitzung. */
    }
  }, [drafts]);

  // open() braucht aktuellen activeId/pathname ohne Dependency-Loop → Ref-Spiegel,
  // der im Effect aktualisiert wird (Ref-Schreiben gehört nicht in den Render).
  const activeIdRef = useRef<string | null>(null);
  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);
  const pathnameRef = useRef(pathname);
  useEffect(() => {
    pathnameRef.current = pathname;
  }, [pathname]);

  // Zentrale Öffnen-/Fokussieren-Regel:
  // - bereits sichtbar → nur fokussieren (kein Duplikat);
  // - sonst freien Platz belegen; sind beide belegt, die aktive Ansicht ersetzen.
  const open = useCallback((id: string) => {
    setOpenIds((prev) => {
      if (prev.includes(id)) return prev;
      if (prev.length < MAX_VIEWS) return [...prev, id];
      return [...prev.filter((x) => x !== activeIdRef.current), id];
    });
    setActiveId(id);
  }, []);

  // BUG-1b-Fix: Der Rücksprung zu "/" beim Schließen der letzten Ansicht lief
  // vorher als passiver Effekt auf `openIds.length === 0` — das feuerte in
  // derselben Commit-Phase wie der `open(id)`-Effekt von `page.tsx` (Kind vor
  // Eltern), aber noch mit dem alten (leeren) State, weil State-Updates aus
  // Effekten nicht synchron in Geschwister-Effekten sichtbar sind. Ergebnis:
  // Deep-Link/Reload auf `/sessions/<id>` konnte zu "/" zurückspringen, bevor
  // `open(id)` überhaupt griff. Fix: Rücksprung nur noch als direkte Folge des
  // expliziten `close()`-Aufrufs (echte Nutzeraktion, keine Race mit Mount-Effekten).
  const close = useCallback(
    (id: string) => {
      setOpenIds((prev) => {
        const rest = prev.filter((x) => x !== id);
        // Wurde die AKTIVE Ansicht geschlossen und bleibt eine zweite offen,
        // wird diese aktiv; bei keiner verbleibenden Ansicht → null (Cockpit).
        if (id === activeIdRef.current && rest.length > 0) {
          setActiveId(rest[rest.length - 1]);
        } else if (id === activeIdRef.current) {
          setActiveId(null);
          if (pathnameRef.current.startsWith("/sessions/")) {
            router.replace("/", { scroll: false });
          }
        }
        return rest;
      });
    },
    [router],
  );

  const focus = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const draft = useCallback(
    (id: string) => drafts[id] ?? "",
    [drafts],
  );
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

  // Die kanonische URL folgt der aktiven Ansicht — aber nur, solange wir uns
  // im Session-Arbeitsbereich befinden (dann ersetzt das Fokussieren einer
  // zweiten Ansicht nicht versehentlich den Standort, z. B. das Board). Die
  // zweite Ansicht ist bewusst nicht routbar (Wiederherstellung nicht Teil des
  // Features). Der Rücksprung zu "/" bei leerem Workspace passiert NICHT hier
  // (Race mit dem open()-Effekt von page.tsx, siehe BUG-1b) — dafür ist close()
  // zuständig, das ihn nur bei echtem Schließen der letzten Ansicht auslöst.
  useEffect(() => {
    if (activeId && pathname.startsWith("/sessions/")) {
      router.replace(`/sessions/${activeId}`, { scroll: false });
    }
  }, [activeId, pathname, router]);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      openIds,
      activeId,
      open,
      close,
      focus,
      draft,
      setDraft,
      clearDraft,
    }),
    [openIds, activeId, open, close, focus, draft, setDraft, clearDraft],
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
