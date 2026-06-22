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
  const loadedOnce = useRef(false);

  const poll = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await listSessions(signal);
      if (signal?.aborted) return;
      setSessions(data);
      setError(null);
    } catch (e) {
      if (signal?.aborted) return;
      const msg =
        e instanceof ApiError ? e.message : "Backend nicht erreichbar";
      setError(msg);
    } finally {
      if (!signal?.aborted && !loadedOnce.current) {
        loadedOnce.current = true;
        setInitialLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    poll(ac.signal);
    const id = setInterval(() => poll(ac.signal), POLL_MS);
    return () => {
      ac.abort();
      clearInterval(id);
    };
  }, [poll]);

  const refresh = useCallback(() => {
    poll();
  }, [poll]);

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
