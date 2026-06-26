"use client";

// PROJ-25: kompakte Identitäts-Zeile im Rail-Footer — zeigt den angemeldeten
// Nutzer und bietet „Abmelden". Rendert nichts im anonymen/Lade-Zustand.

import { LogOutIcon } from "lucide-react";
import { useAuth } from "./auth-provider";

export function UserMenu() {
  const { status, user, signOut } = useAuth();
  if (status !== "authed" || !user) return null;

  return (
    <div className="flex items-center justify-between gap-2">
      <span
        className="min-w-0 truncate text-xs text-muted-foreground"
        title={user.username}
      >
        {user.username}
      </span>
      <button
        onClick={() => void signOut()}
        className="flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        aria-label="Abmelden"
      >
        <LogOutIcon className="size-3.5" />
        Abmelden
      </button>
    </div>
  );
}
