"use client";

// PROJ-39: Vollbild-Ansicht einer eingebetteten Orchestration-App (Paperclip,
// Wayland …). Lädt den Registry-Eintrag aus GET /engines (kind=iframe,
// group=orchestration) und bettet ihn vollhöhen über die wiederverwendete
// EmbedTab-Logik ein. Direkt per URL erreichbar — unabhängig davon, ob die
// Sidebar-Sektion gerade ein-/ausgeblendet ist (Edge Case der Spec).

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import { EmbedTab } from "@/components/cockpit/embed-tab";
import { LaunchButton } from "@/components/cockpit/launch-button";
import { getEngines } from "@/lib/api";
import type { EngineRead } from "@/lib/types";

// Ergebnis trägt den aufgelösten `key` mit → solange es noch nicht zum aktuellen
// Routen-Key passt, gilt „lädt" (abgeleitet, kein synchrones setState im Effect).
type LoadResult =
  | { key: string; phase: "error"; message: string }
  | { key: string; phase: "notfound" }
  | { key: string; phase: "ready"; engine: EngineRead };

export default function OrchestrationAppPage({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = use(params);
  const [result, setResult] = useState<LoadResult | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getEngines(ctrl.signal)
      .then((o) => {
        const engine = o.engines.find((e) => e.key === key && e.kind === "iframe");
        setResult(
          engine
            ? { key, phase: "ready", engine }
            : { key, phase: "notfound" },
        );
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return;
        setResult({
          key,
          phase: "error",
          message: e instanceof Error ? e.message : "Nicht erreichbar",
        });
      });
    return () => ctrl.abort();
  }, [key]);

  const back = (
    <Link
      href="/"
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
    >
      <ArrowLeftIcon className="size-3.5" /> Cockpit
    </Link>
  );

  // Stale-Ergebnis (anderer Key) während der Navigation = weiterhin „lädt".
  const state = result && result.key === key ? result : null;

  if (!state) {
    return (
      <div className="p-6">
        {back}
        <p className="mt-6 text-sm text-muted-foreground">Lädt App…</p>
      </div>
    );
  }

  if (state.phase === "error") {
    return (
      <div className="p-6">
        {back}
        <p className="mt-6 rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-6 text-sm text-red-400">
          Werkzeuge-Registry nicht erreichbar ({state.message}).
        </p>
      </div>
    );
  }

  if (state.phase === "notfound") {
    return (
      <div className="p-6">
        {back}
        <p className="mt-6 rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
          {`Unbekannte App „${key}“ — pflege sie in config/engines.yaml (kind: iframe, group: orchestration).`}
        </p>
      </div>
    );
  }

  const { engine } = state;

  // Mixed-Content-Schutz (Spec-Edge-Case): eine http-App lädt in der https-Seite
  // gar nicht — der Browser blockt vor jedem JS-Fallback. Statt eines stillen
  // Leer-Frames den klaren Hinweis + „In neuem Tab öffnen" zeigen.
  const isInsecure =
    typeof engine.url === "string" && /^http:\/\//i.test(engine.url);

  if (isInsecure && engine.url) {
    return (
      <div className="p-6">
        {back}
        <div className="mx-auto mt-8 max-w-xl rounded-lg border border-amber-500/40 bg-amber-500/10 p-5">
          <h1 className="text-base font-semibold">{engine.label}</h1>
          <p className="mt-2 text-sm text-amber-600 dark:text-amber-400">
            Einbettung blockiert: Die App wird über <code>http</code> ausgeliefert
            und kann in der verschlüsselten Seite nicht eingebettet werden
            (Mixed-Content). Über einen Reverse-Proxy unter <code>https</code>{" "}
            bereitstellen — oder in neuem Tab öffnen.
          </p>
          <div className="mt-4">
            <LaunchButton label="In neuem Tab öffnen" target={engine.url} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* PROJ-39 (QA Low #1): key=engine.key → bei App-Wechsel frischer Mount (kein
          übernommener Fehlerzustand). Back-Link sitzt im EmbedTab-Header (QA Low #2:
          keine zweite Kopfzeile). */}
      <EmbedTab key={engine.key} engine={engine} fullHeight headerLeading={back} />
    </div>
  );
}
