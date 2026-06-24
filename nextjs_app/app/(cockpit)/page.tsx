"use client";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GlobalStatusBar } from "@/components/cockpit/global-status-bar";
import { CleanupButton } from "@/components/cockpit/cleanup-button";
import { SessionGrid } from "@/components/cockpit/session-grid";
import { KanbanBoard } from "@/components/cockpit/kanban-board";
import { GanttChart } from "@/components/cockpit/gantt-chart";
import { ArchivedSection } from "@/components/cockpit/archived-section";
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

      {!initialLoading && sessions.length > 0 && (
        <GlobalStatusBar sessions={sessions} />
      )}

      {initialLoading ? (
        <BoardSkeleton />
      ) : showError ? (
        <ErrorState message={error} />
      ) : sessions.length === 0 ? (
        <EmptyState />
      ) : (
        <Tabs defaultValue="kacheln" className="w-full">
          <TabsList>
            <TabsTrigger value="kacheln">Kacheln</TabsTrigger>
            <TabsTrigger value="kanban">Kanban</TabsTrigger>
          </TabsList>
          <TabsContent value="kacheln" className="mt-4">
            {active.length > 0 ? (
              <SessionGrid sessions={active} now={now} />
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Keine aktiven Sessions.
              </p>
            )}
            <ArchivedSection sessions={archived} now={now} />
          </TabsContent>
          <TabsContent value="kanban" className="mt-4">
            {/* Kanban = voller Pipeline-View inkl. „Fertig"-Spalte. */}
            <KanbanBoard sessions={sessions} now={now} />
            {/* PROJ-8: ABC-Fortschritt je Session direkt unter dem Kanban. */}
            <section className="mt-6">
              <h2 className="mb-2 px-1 text-sm font-medium text-muted-foreground">
                ABC-Fortschritt
              </h2>
              <GanttChart sessions={sessions} />
            </section>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
