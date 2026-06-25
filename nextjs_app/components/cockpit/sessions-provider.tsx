"use client";

// Pollt GET /sessions (~4s) EINMAL und versorgt Rail + Board konsistent
// über React Context — kein doppelter Request (PROJ-3 Tech-Design).

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { usePathname } from "next/navigation";
import { ApiError, listSessions } from "@/lib/api";
import type { Session } from "@/lib/types";

const POLL_MS = 4000;
// PROJ-37: zuletzt fokussierte Session (Reload-fest), damit der Fileexplorer
// rechts „das aktive Fenster" deterministisch wählen kann.
const FOCUS_KEY = "jupiter.focusedSessionId";

interface SessionsContextValue {
  sessions: Session[];
  /** true nur beim allerersten Laden (für Skeletons). */
  initialLoading: boolean;
  /** gesetzt, wenn der letzte Poll fehlschlug. */
  error: string | null;
  refresh: () => void;
  /** PROJ-37: ID der zuletzt geöffneten Session-Detailroute (oder null). */
  focusedSessionId: string | null;
}

const SessionsContext = createContext<SessionsContextValue | null>(null);

/** Persistierten Fokus lesen (SSR-sicher, Reload-Stabilität für PROJ-37). */
function readStoredFocus(): string | null {
  try {
    return typeof window !== "undefined"
      ? window.localStorage.getItem(FOCUS_KEY)
      : null;
  } catch {
    return null;
  }
}

export function SessionsProvider({ children }: { children: React.ReactNode }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Manueller Refresh (z. B. nach Session-Erstellung): zeigt auf die aktuelle
  // tick-Funktion des laufenden Effects — vermeidet setState direkt im Effect-Body.
  const refreshRef = useRef<() => void>(() => {});

  useEffect(() => {
    const ac = new AbortController();
    let loadedOnce = false;

    async function tick() {
      try {
        const data = await listSessions(ac.signal);
        if (ac.signal.aborted) return;
        setSessions(data);
        setError(null);
      } catch (e) {
        if (ac.signal.aborted) return;
        setError(e instanceof ApiError ? e.message : "Backend nicht erreichbar");
      } finally {
        if (!ac.signal.aborted && !loadedOnce) {
          loadedOnce = true;
          setInitialLoading(false);
        }
      }
    }

    refreshRef.current = () => void tick();
    void tick();
    const id = setInterval(() => void tick(), POLL_MS);
    return () => {
      ac.abort();
      clearInterval(id);
    };
  }, []);

  const refresh = useCallback(() => refreshRef.current(), []);

  // PROJ-37: Fokus aus der Route ableiten — betritt der Nutzer /sessions/<id>,
  // merken wir diese ID. Kein Eingriff in die Detailroute, keine zweite
  // Session-Instanz; der Fileexplorer liest die ID nur aus. Die Aktualisierung
  // läuft über das React-Muster „State beim Prop-Wechsel anpassen" (setState
  // während des Renders, nicht im Effect) → kein kaskadierendes Re-Rendern.
  const pathname = usePathname();
  const [focusedSessionId, setFocusedSessionId] = useState<string | null>(
    readStoredFocus,
  );
  const [seenPath, setSeenPath] = useState(pathname);
  if (pathname !== seenPath) {
    setSeenPath(pathname);
    const m = /^\/sessions\/([^/]+)/.exec(pathname);
    if (m) setFocusedSessionId(decodeURIComponent(m[1]));
  }

  // localStorage ist externer State → im Effect schreiben ist erlaubt.
  useEffect(() => {
    if (!focusedSessionId) return;
    try {
      window.localStorage.setItem(FOCUS_KEY, focusedSessionId);
    } catch {
      /* localStorage nicht verfügbar → Fokus nur für diese Sitzung. */
    }
  }, [focusedSessionId]);

  return (
    <SessionsContext.Provider
      value={{ sessions, initialLoading, error, refresh, focusedSessionId }}
    >
      {children}
    </SessionsContext.Provider>
  );
}

export function useSessions(): SessionsContextValue {
  const ctx = useContext(SessionsContext);
  if (!ctx) {
    throw new Error("useSessions muss innerhalb von SessionsProvider stehen");
  }
  return ctx;
}

/** Tickt jede Sekunde — für laufende Relativzeiten ohne Re-Fetch. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
