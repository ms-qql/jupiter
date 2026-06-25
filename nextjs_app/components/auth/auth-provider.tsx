"use client";

// PROJ-25: hält die angemeldete Identität für die ganze App. Beim Laden wird
// EINMAL versucht, über den httpOnly-Refresh-Cookie einen Access-Token zu
// ziehen (`/auth/refresh`) und damit `/auth/me` aufzulösen — so überlebt der
// Login einen Reload, ohne den Access-Token persistent (XSS-anfällig) zu lagern.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  bootstrap as apiBootstrap,
  getAuthStatus,
  getMe,
  login as apiLogin,
  logout as apiLogout,
  refreshAccessToken,
} from "@/lib/api";
import type { AuthUser } from "@/lib/types";

export type AuthStatusValue = "loading" | "authed" | "anon";

interface AuthContextValue {
  status: AuthStatusValue;
  user: AuthUser | null;
  /** true → Login-Seite zeigt den Bootstrap-Modus (erster Account). */
  bootstrapNeeded: boolean;
  /** Wirft ApiError bei falschen Daten. */
  signIn: (username: string, password: string) => Promise<void>;
  /** Ersten Account anlegen (nur bei leerer Nutzerbasis). */
  signUpFirst: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatusValue>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [bootstrapNeeded, setBootstrapNeeded] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      // 1) Versuch: bestehenden Login per Refresh-Cookie wiederherstellen.
      if (await refreshAccessToken()) {
        try {
          const me = await getMe(ac.signal);
          if (!ac.signal.aborted) {
            setUser(me);
            setStatus("authed");
          }
          return;
        } catch {
          /* Refresh ok, aber /me fehlgeschlagen → als anonym behandeln. */
        }
      }
      // 2) Anonym: für die Login-Seite klären, ob ein Bootstrap nötig ist.
      try {
        const st = await getAuthStatus(ac.signal);
        if (!ac.signal.aborted) setBootstrapNeeded(!st.has_users);
      } catch {
        /* Status unbekannt → normaler Login-Modus. */
      }
      if (!ac.signal.aborted) setStatus("anon");
    })();
    return () => ac.abort();
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const u = await apiLogin(username, password);
    setUser(u);
    setStatus("authed");
  }, []);

  const signUpFirst = useCallback(async (username: string, password: string) => {
    const u = await apiBootstrap(username, password);
    setBootstrapNeeded(false);
    setUser(u);
    setStatus("authed");
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setStatus("anon");
  }, []);

  return (
    <AuthContext.Provider
      value={{ status, user, bootstrapNeeded, signIn, signUpFirst, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth muss innerhalb von AuthProvider stehen");
  return ctx;
}
