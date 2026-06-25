"use client";

// Persistente „Recents"-Liste aktiver Sessions (Vorbild: Referenz-Sidebar).
// Klickbare Zeilen → Session-Detailroute. Speist sich aus dem geteilten Poll.

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArchiveIcon, ChevronDownIcon, ChevronRightIcon } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import {
  displayName,
  formatDuration,
  isTerminalStatus,
  railRank,
  statusMeta,
} from "@/lib/status";
import type { Session } from "@/lib/types";
import { APP_VERSION } from "@/lib/version";
import { microAppEngineKey, sectionLabel } from "@/lib/sidebar-config";
import { Ampel } from "./ampel";
import { DeleteSessionButton } from "./delete-session-button";
import { NewSessionDialog } from "./new-session-dialog";
import { SidebarConfigButton } from "./sidebar-config-panel";
import { useSidebarPrefs } from "./sidebar-prefs-provider";
import { useOrchestrationApps } from "./use-orchestration-apps";
import { useMicroApps } from "./use-microapps";
import { useMicroAppStatuses } from "./use-microapp-status";
import { useNow, useSessions } from "./sessions-provider";

const RAIL_LIMIT = 10;

function sortForRail(sessions: Session[]): Session[] {
  return [...sessions].sort((a, b) => {
    const r = railRank(a.status) - railRank(b.status);
    if (r !== 0) return r;
    return Date.parse(b.last_activity) - Date.parse(a.last_activity);
  });
}

export function SessionRail({ onItemClick }: { onItemClick?: () => void }) {
  const { sessions, initialLoading, error } = useSessions();
  const pathname = usePathname();
  const now = useNow();
  const [showArchived, setShowArchived] = useState(false);
  const { visibleItems } = useSidebarPrefs();
  // PROJ-39: lädt die Orchestration-Apps aus der Registry und meldet sie als
  // dynamische Sidebar-Einträge an (auch wenn die Sektion gerade ausgeblendet ist —
  // sonst fehlten sie im Konfig-Panel zum Wieder-Einblenden).
  useOrchestrationApps();
  // PROJ-40: dito für Micro-Apps (group=micro; eingebettet ODER nativ).
  useMicroApps();

  // PROJ-38: Workspace-Einträge + ob die Session-Sektion sichtbar ist —
  // beides aus der Nutzer-Präferenz (localStorage), Reihenfolge inklusive.
  const workspaceItems = visibleItems("workspace");
  const sessionsVisible = visibleItems("sessions").length > 0;
  // PROJ-39: sichtbare Orchestration-Einträge (group=orchestration aus der Registry).
  const orchestrationItems = visibleItems("orchestration");
  // PROJ-40: sichtbare Micro-App-Einträge (group=micro aus der Registry).
  const microAppItems = visibleItems("micro");
  // PROJ-42: Gesamtstatus-Ampel je Micro-App (nur Apps mit Status-Endpoint, z. B.
  // VPS-Admin) — pollt unabhängig davon, ob die App geöffnet ist.
  const microAppStatuses = useMicroAppStatuses(
    microAppItems.map((item) => microAppEngineKey(item.key)),
  );

  // Aktive Sessions in der Rail; beendete (done) wandern ins ausklappbare Archiv.
  const activeSorted = sortForRail(sessions.filter((s) => s.status !== "done"));
  const archived = sortForRail(sessions.filter((s) => s.status === "done"));
  const shown = activeSorted.slice(0, RAIL_LIMIT);
  const hiddenCount = activeSorted.length - shown.length;

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-border bg-card/40">
      <div className="flex items-center justify-between px-4 py-3">
        <Link
          href="/"
          onClick={onItemClick}
          className="text-sm font-semibold tracking-tight"
        >
          🛰️ Jupiter
          <span className="ml-1.5 align-middle text-[0.65rem] font-normal tabular-nums text-muted-foreground">
            v{APP_VERSION}
          </span>
        </Link>
        <NewSessionDialog>
          <button className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
            + Neu
          </button>
        </NewSessionDialog>
      </div>

      {/* PROJ-38: Workspace-Sektion. Überschrift + Einstellungs-Icon sind
          IMMER sichtbar (auch wenn alle Einträge ausgeblendet sind) — der
          Panel-Zugang darf nie verloren gehen. */}
      <div className="flex items-center justify-between px-4 pb-1 pt-1">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {sectionLabel("workspace")}
        </span>
        <SidebarConfigButton />
      </div>
      {workspaceItems.length > 0 && (
        <div className="px-2 pb-1">
          {workspaceItems.map((item) => {
            const Icon = item.icon;
            const href = item.href ?? "/";
            return (
              <Link
                key={item.key}
                href={href}
                onClick={onItemClick}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
                  pathname.startsWith(href)
                    ? "bg-accent text-accent-foreground"
                    : "text-foreground/90 hover:bg-accent/50",
                )}
              >
                <Icon className="size-4 shrink-0 text-muted-foreground" />
                {item.label}
              </Link>
            );
          })}
        </div>
      )}

      {/* PROJ-39: Orchestration-Sektion. Nach oben gezogen (direkt unter Workspace),
          damit alle kompakten Link-Sektionen oben gebündelt sind; die lange
          Sessions-Liste füllt darunter den Rest. Etwas Abstand (mt-2) + Trennlinie
          (border-t) trennen die Bereiche sauber. */}
      {orchestrationItems.length > 0 && (
        <div className="mt-3 border-t border-border pt-3">
          <div className="px-4 pb-1 pt-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {sectionLabel("orchestration")}
          </div>
          <div className="px-2 pb-1">
            {orchestrationItems.map((item) => {
              const Icon = item.icon;
              const href = item.href ?? "/";
              return (
                <Link
                  key={item.key}
                  href={href}
                  onClick={onItemClick}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
                    pathname.startsWith(href)
                      ? "bg-accent text-accent-foreground"
                      : "text-foreground/90 hover:bg-accent/50",
                  )}
                >
                  <Icon className="size-4 shrink-0 text-muted-foreground" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* PROJ-40: Micro-Apps-Sektion (UNTER „Orchestration"). Ebenfalls oben
          gebündelt; Klick öffnet die Vollbild-Route /apps/[key]. */}
      {microAppItems.length > 0 && (
        <div className="mt-3 border-t border-border pt-3">
          <div className="px-4 pb-1 pt-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {sectionLabel("micro")}
          </div>
          <div className="px-2 pb-1">
            {microAppItems.map((item) => {
              const Icon = item.icon;
              const href = item.href ?? "/";
              // PROJ-42: Status-Ampel, falls die App einen Status-Endpoint hat.
              const statusColor = microAppStatuses[microAppEngineKey(item.key)];
              return (
                <Link
                  key={item.key}
                  href={href}
                  onClick={onItemClick}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
                    pathname.startsWith(href)
                      ? "bg-accent text-accent-foreground"
                      : "text-foreground/90 hover:bg-accent/50",
                  )}
                >
                  <Icon className="size-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{item.label}</span>
                  {statusColor && (
                    <Ampel
                      color={statusColor}
                      size="sm"
                      className="ml-auto shrink-0"
                    />
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Sessions-Sektion: als Ganzes über das Panel ausblendbar. Abstand (mt-2)
          + Trennlinie (border-t) grenzen die Liste von den Minipunkten oben ab;
          flex-1 + min-h-0 lassen sie den restlichen Platz füllen und scrollen. */}
      {sessionsVisible ? (
        <div className="mt-3 flex min-h-0 flex-1 flex-col border-t border-border pt-3">
          <div className="px-4 pb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {sectionLabel("sessions")}
          </div>

          <ScrollArea className="flex-1">
            <div className="flex flex-col gap-0.5 px-2 py-1">
              {initialLoading ? (
                <RailSkeleton />
              ) : activeSorted.length === 0 ? (
                <p className="px-2 py-6 text-center text-xs text-muted-foreground">
                  {error && sessions.length === 0
                    ? error
                    : "Keine aktiven Sessions."}
                </p>
              ) : (
                shown.map((s) => (
                  <RailItem
                    key={s.session_id}
                    session={s}
                    now={now}
                    active={pathname === `/sessions/${s.session_id}`}
                    onNavigate={onItemClick}
                  />
                ))
              )}

              {/* Archiv: beendete Sessions, einklappbar, weiterhin fortsetzbar. */}
              {archived.length > 0 && (
                <div className="mt-1">
                  <button
                    type="button"
                    onClick={() => setShowArchived((v) => !v)}
                    className="flex w-full items-center gap-1.5 rounded-md px-2 py-2 text-xs text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"
                  >
                    {showArchived ? (
                      <ChevronDownIcon className="size-3.5" />
                    ) : (
                      <ChevronRightIcon className="size-3.5" />
                    )}
                    <ArchiveIcon className="size-3.5" />
                    Archiv ({archived.length})
                  </button>
                  {showArchived &&
                    archived.map((s) => (
                      <RailItem
                        key={s.session_id}
                        session={s}
                        now={now}
                        active={pathname === `/sessions/${s.session_id}`}
                        onNavigate={onItemClick}
                      />
                    ))}
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      ) : (
        // Sessions ausgeblendet → Platzhalter, damit der Footer unten bleibt.
        <div className="flex-1" />
      )}

      <div className="border-t border-border px-4 py-2">
        <Link
          href="/"
          onClick={onItemClick}
          className="text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          {hiddenCount > 0 ? `Alle anzeigen (+${hiddenCount}) →` : "Zum Board →"}
        </Link>
      </div>
    </aside>
  );
}

function RailItem({
  session,
  now,
  active,
  onNavigate,
}: {
  session: Session;
  now: number;
  active: boolean;
  onNavigate?: () => void;
}) {
  const meta = statusMeta(session.status);
  const role = session.role?.trim();
  const isTerminal = isTerminalStatus(session.status);
  return (
    <Link
      href={`/sessions/${session.session_id}`}
      onClick={onNavigate}
      className={cn(
        "group flex items-center gap-2.5 rounded-md px-2 py-2 text-sm transition-colors",
        active ? "bg-accent text-accent-foreground" : "hover:bg-accent/50",
      )}
    >
      <Ampel color={meta.ampel} size="sm" className="shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium leading-tight" title={displayName(session)}>
          {displayName(session)}
        </div>
        <div className="truncate text-xs text-muted-foreground">
          {role ? `${role} · ${meta.label}` : meta.label}
        </div>
      </div>
      {isTerminal ? (
        <DeleteSessionButton
          sessionId={session.session_id}
          projectName={displayName(session)}
          className="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
        />
      ) : (
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
          {formatDuration(session.created_at, now)}
        </span>
      )}
    </Link>
  );
}

function RailSkeleton() {
  return (
    <div className="flex flex-col gap-1 px-2 py-1">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="h-11 animate-pulse rounded-md bg-muted/50"
          style={{ opacity: 1 - i * 0.15 }}
        />
      ))}
    </div>
  );
}
