"use client";

// Cockpit-Einstellungen als eigene Seite (statt eines zu kleinen Modals, dessen
// Inhalt rechts/unten aus dem Dialog lief). Alle globalen Regler liegen hier als
// vertikal gestapelte Sektionen — die Seite scrollt natürlich, nichts wird beschnitten.
//  - Allgemein (PROJ-5): Kontext-Schwelle für Warnung + Handover-Vorschlag.
//  - Trust-Policy (PROJ-10): abgestuftes Vertrauen + Phasen-Übergangs-Gate.
//  - Watchdog (PROJ-16): Reißleine — Token-/Zeit-/Wiederholungs-/Schreib-Limits.
//  - Liveness (PROJ-27): verifizierter Heartbeat + Auto-Reanimierung hängender Sessions.
//  - Budget (PROJ-52): Schätz-Quoten für den Sidebar-Token-Budget-Monitor.
//  - Sprache (PROJ-20): Quelle der Push-to-Talk-Transkription (lokal/Groq).
//  - Modelle / Registry: Engine- und Modellverwaltung (PROJ-51).

import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThresholdControl } from "@/components/cockpit/threshold-control";
import { HermesKanbanControl } from "@/components/cockpit/hermes-kanban-control";
import { PolicyControl } from "@/components/cockpit/policy-control";
import { WatchdogControl } from "@/components/cockpit/watchdog-control";
import { LivenessControl } from "@/components/cockpit/liveness-control";
import { TranscriptionControl } from "@/components/cockpit/transcription-control";
import { RegistryControl } from "@/components/cockpit/registry-control";
import { EngineModelsControl } from "@/components/cockpit/engine-models-control";
import { ProviderBudgetControl } from "@/components/cockpit/provider-budget-control";
import { TokenSavingsControl } from "@/components/cockpit/token-savings-control";

type Section = {
  id: string;
  title: string;
  description?: string;
  control: React.ReactNode;
};

const SECTIONS: Section[] = [
  { id: "allgemein", title: "Allgemein", control: <ThresholdControl /> },
  { id: "policy", title: "Trust-Policy", control: <PolicyControl /> },
  { id: "watchdog", title: "Watchdog", control: <WatchdogControl /> },
  { id: "liveness", title: "Liveness", control: <LivenessControl /> },
  { id: "budget", title: "Budget", control: <ProviderBudgetControl /> },
  { id: "token-savings", title: "Token Savings", control: <TokenSavingsControl /> },
  { id: "sprache", title: "Sprache", control: <TranscriptionControl /> },
  { id: "hermes-kanban", title: "Hermes-Kanban", control: <HermesKanbanControl /> },
  { id: "modelle", title: "Modelle", control: <EngineModelsControl /> },
  { id: "registry", title: "Registry", control: <RegistryControl /> },
];

export default function SettingsPage() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Einstellungen</h1>
          <p className="text-sm text-muted-foreground">
            Globale Defaults für alle Sessions. Pro Session überschreibbar.
          </p>
        </div>
        <Button variant="outline" size="sm" render={<Link href="/" />}>
          <ArrowLeftIcon className="size-4" />
          Zurück
        </Button>
      </header>

      {SECTIONS.map((s) => (
        <section
          key={s.id}
          className="rounded-lg border border-border bg-card p-4 md:p-5"
        >
          <h2 className="mb-3 text-sm font-medium tracking-tight">{s.title}</h2>
          {s.control}
        </section>
      ))}
    </div>
  );
}
