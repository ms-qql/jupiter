"use client";

// PROJ-8 — ABC-Workflow-Gantt: eine horizontale Bar pro Session unter dem Kanban.
// Rein additive, gepollte Lese-Ansicht (dieselbe Session-Liste wie Board/Rail —
// kein Extra-Request). Links Projekt + Feature, rechts die 8 festen ABC-Phasen;
// gefüllt bis zur weitesten erreichten Phase, die aktuelle Phase hervorgehoben.

import { cn } from "@/lib/utils";
import { ABC_PHASES, phaseIndex, projectName } from "@/lib/status";
import type { Session } from "@/lib/types";

// Beendete/abgebrochene Sessions: Track eingefroren + dezent ausgegraut.
const ENDED = new Set(["done", "error"]);

// Label-Spalte + 8 gleich breite Phasen-Spalten. Auf schmalen Screens schmaler,
// der Container scrollt horizontal (AC: horizontal scrollbar).
const COLS =
  "grid-cols-[9rem_repeat(8,minmax(3rem,1fr))] sm:grid-cols-[14rem_repeat(8,minmax(4rem,1fr))]";

export function GanttChart({ sessions }: { sessions: Session[] }) {
  if (sessions.length === 0) return <GanttEmpty />;

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card/30">
      <div className="min-w-[34rem]">
        {/* Phasen-Kopf */}
        <div className={cn("grid items-stretch border-b border-border", COLS)}>
          <div className="sticky left-0 z-10 bg-card/80 px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground backdrop-blur">
            Projekt · Feature
          </div>
          {ABC_PHASES.map((p) => (
            <div
              key={p.key}
              className="border-l border-border px-1 py-2 text-center text-[0.7rem] font-medium text-muted-foreground"
              title={p.label}
            >
              <span className="hidden sm:inline">{p.label}</span>
              <span className="sm:hidden">{p.short}</span>
            </div>
          ))}
        </div>

        {/* Zeilen (eine pro Session). Viele Sessions → vertikal scrollbar. */}
        <div className="max-h-[24rem] overflow-y-auto">
          {sessions.map((s) => (
            <GanttRow key={s.session_id} session={s} />
          ))}
        </div>
      </div>
    </div>
  );
}

function GanttRow({ session }: { session: Session }) {
  const ended = ENDED.has(session.status);
  const reachedIdx = phaseIndex(session.abc_phase_reached);
  const currentIdx = phaseIndex(session.abc_phase);

  const name = session.project_name?.trim() || projectName(session.project_path);
  const role = session.role?.trim();
  // Untertitel: Feature, sonst Rolle, sonst Platzhalter; bei Ende „· beendet".
  const sub = session.abc_feature
    ? `Feature ${session.abc_feature}`
    : role || "—";

  return (
    <div
      className={cn(
        "grid items-stretch border-b border-border/60 last:border-b-0",
        COLS,
        ended && "opacity-60",
      )}
    >
      <div className="sticky left-0 z-10 flex flex-col justify-center gap-0.5 bg-card/80 px-3 py-2.5 backdrop-blur">
        <span className="truncate text-sm font-medium leading-tight" title={name}>
          {name}
        </span>
        <span className="truncate text-xs text-muted-foreground">
          {sub}
          {ended && " · beendet"}
        </span>
      </div>

      {ABC_PHASES.map((p, i) => {
        const filled = reachedIdx >= 0 && i <= reachedIdx;
        const current = !ended && currentIdx >= 0 && i === currentIdx;
        return (
          <div
            key={p.key}
            className="flex items-center border-l border-border/60 px-1 py-3"
            aria-label={
              current
                ? `${p.label}: aktuelle Phase`
                : filled
                  ? `${p.label}: abgeschlossen`
                  : `${p.label}: offen`
            }
          >
            <div
              className={cn(
                "h-2.5 w-full rounded-sm transition-colors",
                current
                  ? "bg-primary ring-2 ring-primary/40"
                  : filled
                    ? ended
                      ? "bg-muted-foreground/40"
                      : "bg-primary/50"
                    : "bg-muted/40",
              )}
            />
          </div>
        );
      })}
    </div>
  );
}

function GanttEmpty() {
  return (
    <div className="rounded-lg border border-dashed border-border bg-card/20 px-4 py-10 text-center text-sm text-muted-foreground">
      Noch keine Sessions mit ABC-Phase.
    </div>
  );
}
