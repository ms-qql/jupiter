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
import { ApiError, listSessions } from "@/lib/api";
import type { Session } from "@/lib/types";

const POLL_MS = 4000;

interface SessionsContextValue {
  sessions: Session[];
  /** true nur beim allerersten Laden (für Skeletons). */
  initialLoading: boolean;
  /** gesetzt, wenn der letzte Poll fehlschlug. */
  error: string | null;
  refresh: () => void;
}

const SessionsContext = createContext<SessionsContextValue | null>(null);

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

  return (
    <SessionsContext.Provider
      value={{ sessions, initialLoading, error, refresh }}
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
