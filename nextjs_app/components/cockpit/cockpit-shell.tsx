"use client";

// Shell: Rail inline ab `md`, darunter (< 600/768px) als einklappbarer Drawer
// mit Menü-Button — verhindert das Beschneiden des Boards auf schmalen Screens.

import { useState } from "react";
import { MenuIcon, XIcon } from "lucide-react";
import { APP_VERSION } from "@/lib/version";
import { SessionRail } from "./session-rail";
import { ThemeToggle } from "./theme-toggle";

export function CockpitShell({ children }: { children: React.ReactNode }) {
  const [railOpen, setRailOpen] = useState(false);

  return (
    <div className="flex h-dvh overflow-hidden">
      {/* Desktop/Tablet: Rail dauerhaft sichtbar */}
      <div className="hidden md:flex">
        <SessionRail />
      </div>

      {/* Mobile: Rail als Overlay-Drawer */}
      {railOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setRailOpen(false)}
            aria-hidden
          />
          <div className="absolute left-0 top-0 h-full bg-background shadow-xl">
            <SessionRail onItemClick={() => setRailOpen(false)} />
            <button
              onClick={() => setRailOpen(false)}
              aria-label="Sessions schließen"
              className="absolute right-2 top-2 rounded-md p-1.5 text-muted-foreground hover:bg-accent"
            >
              <XIcon className="size-4" />
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile-Topbar mit Menü-Button + Theme-Toggle */}
        <div className="flex items-center gap-2 border-b border-border px-3 py-2 md:hidden">
          <button
            onClick={() => setRailOpen(true)}
            aria-label="Sessions öffnen"
            className="rounded-md border border-border p-2 text-muted-foreground hover:bg-accent"
          >
            <MenuIcon className="size-4" />
          </button>
          <span className="text-sm font-semibold tracking-tight">
            🛰️ Jupiter
            <span className="ml-1.5 align-middle text-[0.65rem] font-normal tabular-nums text-muted-foreground">
              v{APP_VERSION}
            </span>
          </span>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>

        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
