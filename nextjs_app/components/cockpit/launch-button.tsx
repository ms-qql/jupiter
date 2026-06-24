"use client";

// PROJ-18 · Integrations-Tiefe 3: Startknopf. Für nicht integrierbare Werkzeuge —
// öffnet ein externes Ziel (Web-URL) in neuem Tab. Ist das Ziel ein lokaler Befehl
// (keine URL), kann der Browser ihn nicht ausführen → wir bieten ihn zum Kopieren an.

import { toast } from "sonner";

function isWebUrl(target: string): boolean {
  return /^https?:\/\//i.test(target.trim());
}

export function LaunchButton({ label, target }: { label: string; target: string }) {
  const cls =
    "inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium transition-colors hover:border-foreground/30";

  if (isWebUrl(target)) {
    return (
      <a href={target} target="_blank" rel="noopener noreferrer" className={cls}>
        {label}
        <span aria-hidden>↗</span>
      </a>
    );
  }

  // Lokaler Befehl/Absprung — im Browser nicht ausführbar → zum Kopieren anbieten.
  return (
    <button
      type="button"
      title={target}
      onClick={() =>
        navigator.clipboard?.writeText(target).then(
          () => toast.success("Befehl kopiert"),
          () => toast.error("Kopieren fehlgeschlagen"),
        )
      }
      className={cls}
    >
      {label}
      <span className="font-mono text-xs text-muted-foreground">Befehl kopieren</span>
    </button>
  );
}
