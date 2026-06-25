"use client";

// PROJ-40: Vollbild-Ansicht einer Micro-App. Lädt den Registry-Eintrag aus
// GET /engines (group=micro) und VERZWEIGT nach `kind`:
//   • kind=iframe  → eingebettete App (z. B. Excalidraw) über die wiederverwendete
//                    EmbedTab-Logik (Sandbox + „In neuem Tab öffnen"-Fallback).
//   • kind=native  → nativ in Jupiter programmierte Komponente aus der Frontend-
//                    Komponenten-Registry (microapps-registry.ts), kein iFrame.
// Direkt per URL erreichbar — unabhängig davon, ob die Sidebar-Sektion gerade
// ein-/ausgeblendet ist (Edge Case der Spec).

import { Suspense, createElement, use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import { EmbedTab } from "@/components/cockpit/embed-tab";
import { LaunchButton } from "@/components/cockpit/launch-button";
import { getEngines } from "@/lib/api";
import { resolveMicroApp } from "@/lib/microapps-registry";
import type { EngineRead } from "@/lib/types";

// Ergebnis trägt den aufgelösten `key` mit → solange es noch nicht zum aktuellen
// Routen-Key passt, gilt „lädt" (abgeleitet, kein synchrones setState im Effect —
// Muster wie die Orchestration-Route).
type LoadResult =
  | { key: string; phase: "error"; message: string }
  | { key: string; phase: "notfound" }
  | { key: string; phase: "ready"; engine: EngineRead };

export default function MicroAppPage({
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
        const engine = o.engines.find(
          (e) =>
            e.key === key &&
            e.group === "micro" &&
            (e.kind === "iframe" || e.kind === "native"),
        );
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
          {`Unbekannte Micro-App „${key}“ — pflege sie in config/engines.yaml (group: micro).`}
        </p>
      </div>
    );
  }

  const { engine } = state;

  const header = (
    <header className="flex items-center gap-3 border-b border-border px-4 py-2">
      {back}
      <h1 className="truncate text-sm font-semibold tracking-tight">
        {engine.label}
      </h1>
    </header>
  );

  // --- Native Micro-App (kind=native) ----------------------------------------
  if (engine.kind === "native") {
    return (
      <div className="flex h-full flex-col">
        {header}
        <div className="min-h-0 flex-1 overflow-auto">
          <NativeMicroAppHost appKey={engine.key} back={back} />
        </div>
      </div>
    );
  }

  // --- Eingebettete Micro-App (kind=iframe) -----------------------------------
  // Mixed-Content-Schutz (wie Orchestration): eine http-App lädt in der https-Seite
  // gar nicht — der Browser blockt vor jedem JS-Fallback. Excalidraw ist https, daher
  // greift das hier nicht; der Schutz gilt für künftige eingebettete Micro-Apps.
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
      {header}
      <div className="min-h-0 flex-1">
        <EmbedTab engine={engine} fullHeight />
      </div>
    </div>
  );
}

// Eigene Komponente (Modul-Scope, nicht im Render erzeugt) für die native App:
// löst den `key` über die stabile Komponenten-Registry auf und rendert die
// Lazy-Komponente in <Suspense>. Fehlt der key → sauberer Hinweis statt Crash.
function NativeMicroAppHost({
  appKey,
  back,
}: {
  appKey: string;
  back: React.ReactNode;
}) {
  // Stabile Lazy-Komponente aus der Modul-Registry (NICHT im Render erzeugt).
  // `createElement` statt JSX, damit der static-components-Lint die call-abgeleitete
  // Komponente nicht fälschlich als „im Render erzeugt" markiert.
  const nativeApp = resolveMicroApp(appKey);
  if (!nativeApp) {
    return (
      <div className="p-6">
        {back}
        <p className="mt-6 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-6 text-sm text-amber-600 dark:text-amber-400">
          {`Native Micro-App „${appKey}“ ist nicht verfügbar — sie ist in lib/microapps-registry.ts (noch) nicht registriert.`}
        </p>
      </div>
    );
  }
  return (
    <Suspense
      fallback={<p className="p-6 text-sm text-muted-foreground">Lädt App…</p>}
    >
      {createElement(nativeApp, { appKey })}
    </Suspense>
  );
}
