// PROJ-46: Live-Aktivitäts-Ticker — zeigt transient, WAS der Agent gerade tut.
// Ergänzt den Heartbeat (PROJ-27): „lebt/hängt/tot" wird zu „lebt + tut gerade X".
// Quelle ist der `kind:"activity"`-Broadcast (jüngster Tool-Start, serverseitig gekürzt)
// plus der jüngste Assistenten-Text-Schnipsel. Bewusst flüchtig: nichts wird persistiert,
// eine neu verbundene Ansicht sieht ab dann die Live-Aktionen (keine Historie nachgeladen).

"use client";

import { useState } from "react";
import { ActivityIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LiveActivity } from "@/hooks/use-session-stream";

/** Letzten Assistenten-Schnipsel auf eine kurze, einzeilige Vorschau kürzen. */
function lastSnippet(liveText: string, max = 120): string {
  const collapsed = liveText.replace(/\s+/g, " ").trim();
  if (!collapsed) return "";
  // Nur das Ende zeigen (jüngster Gedanke), vorne mit Ellipse abschneiden.
  return collapsed.length > max ? "…" + collapsed.slice(-(max - 1)) : collapsed;
}

function ToolChip({ activity }: { activity: LiveActivity }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-muted px-2 py-0.5 font-mono text-xs">
      <ActivityIcon className="size-3 text-emerald-500" />
      <span className="font-medium">{activity.tool}</span>
      {activity.target && (
        <>
          <span className="text-muted-foreground">·</span>
          <span className="text-muted-foreground" title={activity.target}>
            {activity.target}
          </span>
        </>
      )}
    </span>
  );
}

export function ActivityTicker({
  lastActivity,
  liveText,
  className,
}: {
  /** Jüngste Tool-Start-Aktion (transient); `null` = noch keine / Session terminal. */
  lastActivity: LiveActivity | null;
  /** Live gestreamter Assistenten-Text (jüngster Schnipsel wird angezeigt). */
  liveText: string;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  // Kurze Ring-Historie der letzten ~5 Aktionen — rein clientseitig aus den
  // aufeinanderfolgenden `lastActivity`-Ständen abgeleitet (transient, nicht geladen).
  // Anpassen-während-Render statt Effekt (React-empfohlenes Derived-State-Muster):
  // ändert sich der Zeitstempel, wird die Historie beim selben Render aktualisiert.
  const [history, setHistory] = useState<LiveActivity[]>([]);
  const [seenTs, setSeenTs] = useState<string | null>(null);
  const ts = lastActivity?.ts ?? null;
  if (ts !== seenTs) {
    setSeenTs(ts);
    // Session terminal / geleert (lastActivity === null) → Historie zurücksetzen.
    setHistory(lastActivity ? [lastActivity, ...history].slice(0, 5) : []);
  }

  const snippet = lastSnippet(liveText);

  // Nichts zu zeigen (noch keine Aktion und kein Text) → Ticker einklappen.
  if (!lastActivity && !snippet) return null;

  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-md border border-border bg-card/50 px-3 py-1.5 text-xs",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        {lastActivity ? (
          <ToolChip activity={lastActivity} />
        ) : (
          <span className="shrink-0 text-muted-foreground">Agent arbeitet…</span>
        )}
        {snippet && (
          <span className="truncate text-muted-foreground" title={snippet}>
            {snippet}
          </span>
        )}
        {history.length > 1 && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="ml-auto inline-flex shrink-0 items-center gap-0.5 text-muted-foreground hover:text-foreground"
            aria-expanded={expanded}
            aria-label={expanded ? "Verlauf einklappen" : "Verlauf anzeigen"}
          >
            {expanded ? (
              <ChevronUpIcon className="size-3.5" />
            ) : (
              <ChevronDownIcon className="size-3.5" />
            )}
            <span>{history.length}</span>
          </button>
        )}
      </div>

      {expanded && history.length > 1 && (
        <ul className="flex flex-col gap-1 border-t border-border pt-1">
          {history.slice(1).map((a, i) => (
            <li key={`${a.ts}-${i}`} className="flex items-center gap-2 opacity-70">
              <ToolChip activity={a} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
