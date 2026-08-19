"use client";

// PROJ-82: Task-Detail-Panel. Lädt Detail (Läufe, Events, Kommentare, Summary)
// + Worker-Log-Snapshot (letzte 64 KB) und bietet die Einzeltask-Aktionen an.
// Kein Live-Streaming — der Log wird nur auf Knopfdruck bzw. beim Öffnen geholt.

import { useCallback, useEffect, useState } from "react";
import { RefreshCwIcon, XIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  getHermesKanbanTask,
  getHermesKanbanTaskLog,
} from "@/lib/api";
import type { HermesKanbanTaskDetail } from "@/lib/types";
import { TaskActions } from "./task-actions";

const STATUS_LABELS: Record<string, string> = {
  triage: "Triage",
  todo: "Todo",
  scheduled: "Scheduled",
  ready: "Ready",
  running: "Running",
  blocked: "Blocked",
  review: "Review",
  done: "Done",
  archived: "Archiviert",
};

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function outcomeBadge(outcome?: string | null) {
  if (!outcome) return <Badge variant="outline">—</Badge>;
  const map: Record<string, string> = {
    crashed: "bg-red-500/15 text-red-500",
    spawn_failed: "bg-red-500/15 text-red-500",
    protocol_violation: "bg-red-500/15 text-red-500",
    timeout: "bg-amber-500/15 text-amber-500",
    succeeded: "bg-green-500/15 text-green-500",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${map[outcome] ?? "bg-secondary text-secondary-foreground"}`}
    >
      {outcome}
    </span>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1">
      <span className="shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className="text-right text-xs">{value}</span>
    </div>
  );
}

interface TaskDetailPanelProps {
  taskId: string;
  board: string;
  onClose: () => void;
  onChanged: () => void;
}

export function TaskDetailPanel({
  taskId,
  board,
  onClose,
  onChanged,
}: TaskDetailPanelProps) {
  const [detail, setDetail] = useState<HermesKanbanTaskDetail | null>(null);
  const [log, setLog] = useState<string | null>(null);
  const [logLoading, setLogLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const d = await getHermesKanbanTask(taskId, board, signal);
        setDetail(d);
      } catch (err) {
        if (signal?.aborted) return;
        setError(err instanceof ApiError ? err.message : "Nicht erreichbar");
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [taskId, board],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    void refresh(ctrl.signal);
    return () => ctrl.abort();
  }, [refresh]);

  const loadLog = useCallback(async () => {
    setLogLoading(true);
    try {
      const r = await getHermesKanbanTaskLog(taskId, board);
      setLog(r.log);
    } catch (err) {
      setLog("Worker-Log nicht abrufbar.");
    } finally {
      setLogLoading(false);
    }
  }, [taskId, board]);

  useEffect(() => {
    void loadLog();
  }, [loadLog]);

  if (loading) {
    return (
      <aside className="flex h-full w-full flex-col gap-3 overflow-auto border-l border-border bg-card p-4 lg:w-[440px]">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </aside>
    );
  }

  if (error) {
    return (
      <aside className="flex h-full w-full flex-col border-l border-border bg-card p-4 lg:w-[440px]">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Task-Detail</h2>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Schließen">
            <XIcon className="size-4" />
          </Button>
        </div>
        <p className="mt-4 rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-6 text-sm text-red-500">
          Task nicht mehr verfügbar oder nicht erreichbar: {error}
        </p>
      </aside>
    );
  }

  const task = detail?.task;

  return (
    <aside className="flex h-full w-full flex-col overflow-hidden border-l border-border bg-card lg:w-[460px]">
      <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-2">
        <h2 className="truncate text-sm font-semibold">Task-Detail</h2>
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => void refresh()}
            aria-label="Aktualisieren"
          >
            <RefreshCwIcon className="size-4" />
          </Button>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Schließen">
            <XIcon className="size-4" />
          </Button>
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-5 overflow-auto p-4">
        {task && (
          <>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{STATUS_LABELS[task.status] ?? task.status}</Badge>
                {task.priority != null && (
                  <Badge variant="outline">Prio {task.priority}</Badge>
                )}
                {task.assignee && <Badge variant="secondary">{task.assignee}</Badge>}
              </div>
              <h1 className="text-base font-semibold leading-snug">{task.title}</h1>
              {task.body && (
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                  {task.body}
                </p>
              )}
            </div>

            <div className="rounded-lg border border-border p-3">
              <Row label="Status" value={STATUS_LABELS[task.status] ?? task.status} />
              <Row label="Workspace" value={task.workspace_kind ?? "—"} />
              {task.workspace_path && (
                <Row label="Pfad" value={<code>{task.workspace_path}</code>} />
              )}
              {task.branch_name && (
                <Row label="Branch" value={<code>{task.branch_name}</code>} />
              )}
              <Row label="Erstellt" value={fmtDate(task.created_at)} />
              {task.started_at && (
                <Row label="Gestartet" value={fmtDate(task.started_at)} />
              )}
              <Row label="Erstellt von" value={task.created_by ?? "—"} />
            </div>

            {(detail.parents.length > 0 || detail.children.length > 0) && (
              <div className="space-y-2">
                {detail.parents.length > 0 && (
                  <div>
                    <h3 className="text-xs font-medium text-muted-foreground">
                      Parent-Tasks
                    </h3>
                    <ul className="space-y-1 text-sm">
                      {detail.parents.map((p) => (
                        <li key={p.id}>
                          {p.title} <Badge variant="outline">{p.id}</Badge>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {detail.children.length > 0 && (
                  <div>
                    <h3 className="text-xs font-medium text-muted-foreground">
                      Children
                    </h3>
                    <ul className="space-y-1 text-sm">
                      {detail.children.map((c) => (
                        <li key={c.id}>
                          {c.title} <Badge variant="outline">{c.id}</Badge>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {detail.latest_summary && (
              <div className="rounded-lg border border-border p-3">
                <h3 className="mb-1 text-xs font-medium text-muted-foreground">
                  Letzte Zusammenfassung
                </h3>
                <p className="text-sm">{detail.latest_summary}</p>
              </div>
            )}

            <section>
              <h3 className="mb-2 text-xs font-medium text-muted-foreground">
                Run-History
              </h3>
              {detail.runs.length === 0 ? (
                <p className="text-sm text-muted-foreground">Noch keine Läufe.</p>
              ) : (
                <div className="space-y-2">
                  {detail.runs.map((r, i) => (
                    <div
                      key={r.id ?? i}
                      className="rounded-lg border border-border p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium">{r.profile ?? "—"}</span>
                        {outcomeBadge(r.outcome)}
                        {r.elapsed != null && (
                          <Badge variant="outline">{r.elapsed}s</Badge>
                        )}
                      </div>
                      {r.step_key && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          Schritt: {r.step_key}
                        </p>
                      )}
                      {r.summary && (
                        <p className="mt-1 text-sm text-muted-foreground">
                          {r.summary}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-xs font-medium text-muted-foreground">
                Events
              </h3>
              {detail.events.length === 0 ? (
                <p className="text-sm text-muted-foreground">Keine Events.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {detail.events.map((e, i) => (
                    <li key={e.id ?? i} className="text-xs text-muted-foreground">
                      <span className="text-foreground">{e.kind ?? "Event"}</span>{" "}
                      {e.summary ?? ""} · {fmtDate(e.created_at)}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-xs font-medium text-muted-foreground">
                Kommentare
              </h3>
              {detail.comments.length === 0 ? (
                <p className="text-sm text-muted-foreground">Keine Kommentare.</p>
              ) : (
                <ul className="space-y-2">
                  {detail.comments.map((c, i) => (
                    <li key={c.id ?? i} className="rounded-lg border border-border p-2">
                      <div className="text-xs text-muted-foreground">
                        {c.author ?? "—"} · {fmtDate(c.created_at)}
                      </div>
                      <p className="mt-1 text-sm">{c.text}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-medium text-muted-foreground">
                  Worker-Log
                </h3>
                <Button size="xs" variant="outline" onClick={() => void loadLog()}>
                  <RefreshCwIcon className="size-3" />
                  {logLoading ? "Lädt…" : "Aktualisieren"}
                </Button>
              </div>
              <pre className="max-h-72 overflow-auto rounded-lg border border-border bg-black/80 p-3 text-xs leading-relaxed text-green-400">
                {log ? log : "Noch kein Worker-Log vorhanden"}
              </pre>
            </section>

            <TaskActions
              taskId={task.id}
              board={board}
              archived={task.status === "archived"}
              onChanged={() => {
                void refresh();
                onChanged();
              }}
            />
          </>
        )}
      </div>
    </aside>
  );
}
