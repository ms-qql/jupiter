"use client";

// PROJ-12: „Verlinkt von" — zeigt die Notizen, die per [[…]] auf die aktuelle
// Datei zeigen (serverseitiger Reverse-Scan via GET /md/backlinks).

import { useEffect, useState } from "react";
import { Link2 } from "lucide-react";
import { ApiError, getMdBacklinks } from "@/lib/api";
import type { MdIndexEntry } from "@/lib/types";

export function BacklinksPanel({
  path,
  onNavigate,
}: {
  path: string;
  onNavigate: (path: string) => void;
}) {
  // Ergebnis trägt seinen Pfad mit → Loading wird abgeleitet (kein synchrones
  // setState im Effect, vgl. react-hooks/set-state-in-effect).
  const [loaded, setLoaded] = useState<{
    path: string;
    links: MdIndexEntry[] | null;
    error: string | null;
  }>({ path: "", links: null, error: null });

  useEffect(() => {
    let active = true;
    const ctrl = new AbortController();
    getMdBacklinks(path, ctrl.signal)
      .then((res) => active && setLoaded({ path, links: res, error: null }))
      .catch((e) => {
        if (!active || ctrl.signal.aborted) return;
        setLoaded({
          path,
          links: null,
          error: e instanceof ApiError ? e.message : "Backlinks nicht ladbar",
        });
      });
    return () => {
      active = false;
      ctrl.abort();
    };
  }, [path]);

  const ready = loaded.path === path;
  const links = ready ? loaded.links : null;
  const error = ready ? loaded.error : null;

  return (
    <section className="mt-8 border-t border-border pt-4">
      <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Link2 className="size-3.5" /> Verlinkt von
      </h2>
      {error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : links === null ? (
        <p className="text-xs text-muted-foreground">Lädt…</p>
      ) : links.length === 0 ? (
        <p className="text-xs text-muted-foreground">Keine Backlinks.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {links.map((l) => (
            <li key={l.path}>
              <button
                type="button"
                onClick={() => onNavigate(l.path)}
                className="text-left text-xs text-primary underline-offset-2 hover:underline"
                title={l.rel}
              >
                {l.name.replace(/\.md$/i, "")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
