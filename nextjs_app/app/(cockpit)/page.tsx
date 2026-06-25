"use client";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GlobalStatusBar } from "@/components/cockpit/global-status-bar";
import { RecoveryBanner } from "@/components/cockpit/recovery-banner";
import { CleanupButton } from "@/components/cockpit/cleanup-button";
import { SessionGrid } from "@/components/cockpit/session-grid";
import { KanbanBoard } from "@/components/cockpit/kanban-board";
import { CoordinatorPanel } from "@/components/cockpit/coordinator/coordinator-panel";
import { GanttChart } from "@/components/cockpit/gantt-chart";
import { ArchivedSection } from "@/components/cockpit/archived-section";
import { ToolsPanel } from "@/components/cockpit/tools-panel";
import { UsageDashboard } from "@/components/cockpit/usage-dashboard";
import { NewSessionDialog } from "@/components/cockpit/new-session-dialog";
import { SettingsDialog } from "@/components/cockpit/settings-dialog";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import {
  BoardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/cockpit/states";
import {
  useNow,
  useSessions,
} from "@/components/cockpit/sessions-provider";
import { countTerminal } from "@/lib/status";

export default function CockpitPage() {
  const { sessions, initialLoading, error } = useSessions();
  const now = useNow();
  const terminalCount = countTerminal(sessions);

  const showError = error && sessions.length === 0;
  // Beendete Sessions standardmäßig aus dem aktiven Board ausblenden (→ Archiv).
  // `error` bleibt aktiv sichtbar (Handlungsbedarf).
  const active = sessions.filter((s) => s.status !== "done");
  const archived = sessions.filter((s) => s.status === "done");

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Mission Control</h1>
          <p className="text-sm text-muted-foreground">
            Lagebild aller Sessions
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!initialLoading && <CleanupButton terminalCount={terminalCount} />}
          <SettingsDialog />
          <ThemeToggle />
          <NewSessionDialog>
            <button className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90">
              + Neue Session
            </button>
          </NewSessionDialog>
        </div>
      </header>

      {/* PROJ-17: Recovery-Hinweis nach Reboot/Crash — blendet sich selbst aus,
          wenn es keine wiederherstellbaren Stränge gibt. */}
      <RecoveryBanner />

      {!initialLoading && sessions.length > 0 && (
        <GlobalStatusBar sessions={sessions} />
      )}

      {initialLoading ? (
        <BoardSkeleton />
      ) : showError ? (
        <ErrorState message={error} />
      ) : (
        // PROJ-18 (BUG-3-Fix): Tabs IMMER rendern — der „Werkzeuge"-Tab (iFrame/Launch)
        // ist auch ohne laufende Session erreichbar; der Empty-State lebt im Kacheln-Tab.
        <Tabs defaultValue="kacheln" className="w-full">
          <TabsList>
            <TabsTrigger value="kacheln">Kacheln</TabsTrigger>
            <TabsTrigger value="kanban">Kanban</TabsTrigger>
            {/* PROJ-22: Multi-Agent-Dispatch — Verteilungsplan + Flotten-Sicht. */}
            <TabsTrigger value="koordinator">Koordinator</TabsTrigger>
            {/* PROJ-18: eingebettete Apps (iFrame) + externe Startknöpfe. */}
            <TabsTrigger value="werkzeuge">Werkzeuge</TabsTrigger>
            {/* PROJ-19 (#28): Token-/Kosten-Verbrauch je Modell/Projekt. */}
            <TabsTrigger value="verbrauch">Verbrauch</TabsTrigger>
          </TabsList>
          <TabsContent value="kacheln" className="mt-4">
            {sessions.length === 0 ? (
              <EmptyState />
            ) : (
              <>
                {active.length > 0 ? (
                  <SessionGrid sessions={active} now={now} />
                ) : (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    Keine aktiven Sessions.
                  </p>
                )}
                <ArchivedSection sessions={archived} now={now} />
              </>
            )}
          </TabsContent>
          <TabsContent value="kanban" className="mt-4">
            {sessions.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {`Noch keine Sessions — starte eine über „+ Neue Session“.`}
              </p>
            ) : (
              <>
                {/* Kanban = voller Pipeline-View inkl. „Fertig"-Spalte. */}
                <KanbanBoard sessions={sessions} now={now} />
                {/* PROJ-8: ABC-Fortschritt je Session direkt unter dem Kanban. */}
                <section className="mt-6">
                  <h2 className="mb-2 px-1 text-sm font-medium text-muted-foreground">
                    ABC-Fortschritt
                  </h2>
                  <GanttChart sessions={sessions} />
                </section>
              </>
            )}
          </TabsContent>
          <TabsContent value="koordinator" className="mt-4">
            <CoordinatorPanel />
          </TabsContent>
          <TabsContent value="werkzeuge" className="mt-4">
            <ToolsPanel />
          </TabsContent>
          <TabsContent value="verbrauch" className="mt-4">
            <UsageDashboard sessions={sessions} nowMs={now} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
