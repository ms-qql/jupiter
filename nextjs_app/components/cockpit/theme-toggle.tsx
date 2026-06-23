"use client";

// Light/Dark-Umschalter (Sonne/Mond) — oben rechts. Brand-Default: Dark.

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { MoonIcon, SunIcon } from "lucide-react";

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  // setState aus dem synchronen Effect-Body heraushalten (Lint-konform).
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const isDark = (resolvedTheme ?? theme) === "dark";

  return (
    <button
      type="button"
      aria-label={isDark ? "Light Mode aktivieren" : "Dark Mode aktivieren"}
      title={isDark ? "Light Mode" : "Dark Mode"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="rounded-md border border-border p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
    >
      {/* Vor dem Mount Theme unbekannt → unsichtbares Icon, verhindert Hydration-Mismatch. */}
      {!mounted ? (
        <SunIcon className="size-4 opacity-0" />
      ) : isDark ? (
        <SunIcon className="size-4" />
      ) : (
        <MoonIcon className="size-4" />
      )}
    </button>
  );
}
