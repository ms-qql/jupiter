"use client";

// PROJ-82/84: Native Hermes-Kanban-Ansicht in Jupiter (kein iFrame).
// Board-Übersicht (gruppiert nach Status), lokaler Phasenfilter, Assignee-Filter,
// Schnell-Anlage (Kurzsyntax), Dispatch-Button, Mehrfachauswahl + Bulk-Archiv
// und angedocktes Task-Detail-Panel (Desktop neben dem Board, mobil darunter).
// Aktualisiert sich per Polling laut Settings-Intervall.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ColumnsIcon,
  PlusIcon,
  RefreshCwIcon,
  SlidersHorizontalIcon,
  XIcon,
  ZapIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ApiError,
  archiveBulkHermesKanbanTasks,
  dispatchHermesKanban,
  getHermesKanbanAssignees,
  getHermesKanbanBoards,
  getHermesKanbanSettings,
  getHermesKanbanTasks,
} from "@/lib/api";
import type { HermesKanbanBoard, HermesKanbanTask } from "@/lib/types";
import {
  NewTaskDialog,
  parseQuickAdd,
  quickAddBody,
  quickAddTitle,
  type QuickAddPrefill,
} from "./new-task-dialog";
import { TaskDetailPanel } from "./task-detail-panel";

const COLUMNS: { status: string; label: string }[] = [
  { status: "triage", label: "Triage" },
  { status: "todo", label: "Todo" },
  { status: "scheduled", label: "Scheduled" },
  { status: "ready", label: "Ready" },
  { status: "running", label: "Running" },
  { status: "blocked", label: "Blocked" },
  { status: "review", label: "Review" },
  { status: "done", label: "Done" },
];

const PRIORITY_COLORS: Record<string, string> = {
  "1": "text-red-500",
  "2": "text-amber-500",
  "3": "text-sky-500",
};

function fmtTime(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
}

function workspaceKindLabel(t: HermesKanbanTask): string {
  return t.workspace_kind ?? "scratch";
}

export default function HermesKanbanApp() {
  const [boards, setBoards] = useState<HermesKanbanBoard[]>([]);
  const [board, setBoard] = useState<string>("");
  const [assignees, setAssignees] = useState<string[]>([]);
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [tasks, setTasks] = useState<HermesKanbanTask[]>([]);
  const [pollInterval, setPollInterval] = useState(10);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [quickInput, setQuickInput] = useState("");
  const [newTaskOpen, setNewTaskOpen] = useState(false);
  const [prefill, setPrefill] = useState<QuickAddPrefill | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [dispatchBusy, setDispatchBusy] = useState(false);

  // PROJ-84 A: lokaler Phasenfilter — alle 8 regulären Phasen sind sichtbar.
  // Kein Persistenz-, kein Request-Auslöser; filtert nur den geladenen Bestand.
  const [visiblePhases, setVisiblePhases] = useState<Set<string>>(
    () => new Set(COLUMNS.map((c) => c.status)),
  );

  // --- Initial: Boards + Settings -----------------------------------------
  useEffect(() => {
    const ctrl = new AbortController();
    void Promise.all([
      getHermesKanbanBoards(ctrl.signal),
      getHermesKanbanSettings(ctrl.signal),
    ])
      .then(([b, s]) => {
        setBoards(b);
        setPollInterval(s.poll_interval_seconds);
        const current = b.find((x) => x.is_current);
        setBoard(current?.slug ?? b[0]?.slug ?? "");
      })
      .catch((err) => {
        if (ctrl.signal.aborted) return;
        setLoadError(
          err instanceof ApiError ? err.message : "Hermes nicht erreichbar",
        );
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, []);

  // Assignees hängen am Board.
  useEffect(() => {
    if (!board) return;
    const ctrl = new AbortController();
    getHermesKanbanAssignees(board, ctrl.signal)
      .then(setAssignees)
      .catch(() => {
        /* Dropdown bleibt leer — kein Blocker. */
      });
    return () => ctrl.abort();
  }, [board]);

  const refreshTasks = useCallback(
    async (signal?: AbortSignal) => {
      if (!board) return;
      setLoading(true);
      try {
        const r = await getHermesKanbanTasks(
          board,
          assigneeFilter || null,
          false,
          signal,
        );
        setTasks(r.tasks ?? []);
        setLoadError(null);
      } catch (err) {
        if (signal?.aborted) return;
        setLoadError(
          err instanceof ApiError ? err.message : "Hermes nicht erreichbar",
        );
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [board, assigneeFilter],
  );

  // Tasks beim Laden + bei Filter-/Board-Wechsel.
  useEffect(() => {
    const ctrl = new AbortController();
    void refreshTasks(ctrl.signal);
    return () => ctrl.abort();
  }, [refreshTasks]);

  // Polling laut Settings-Intervall.
  useEffect(() => {
    const t = setInterval(
      () => void refreshTasks(),
      Math.max(5, pollInterval) * 1000,
    );
    return () => clearInterval(t);
  }, [refreshTasks, pollInterval]);

  const grouped = useMemo(() => {
    const map = new Map<string, HermesKanbanTask[]>();
    for (const c of COLUMNS) map.set(c.status, []);
    for (const t of tasks) {
      const list = map.get(t.status);
      if (list) list.push(t);
    }
    return map;
  }, [tasks]);

  const visibleCols = useMemo(
    () => COLUMNS.filter((c) => visiblePhases.has(c.status)),
    [visiblePhases],
  );

  const selectedTasks = useMemo(
    () => tasks.filter((t) => selectedIds.has(t.id)),
    [tasks, selectedIds],
  );

  function togglePhase(status: string) {
    setVisiblePhases((cur) => {
      const next = new Set(cur);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }

  function toggleSelect(id: string) {
    setSelectedIds((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function openNewTask() {
    setPrefill(null);
    setNewTaskOpen(true);
  }

  function submitQuickAdd() {
    const parsed = parseQuickAdd(quickInput);
    if (parsed) {
      setPrefill({
        ...parsed,
        title: quickAddTitle(parsed),
        body: quickAddBody(parsed),
      });
    } else {
      setPrefill(null);
    }
    setQuickInput("");
    setNewTaskOpen(true);
  }

  async function runDispatch() {
    if (!board || dispatchBusy) return;
    setDispatchBusy(true);
    try {
      const r = await dispatchHermesKanban(board);
      toast.success(
        `Dispatch: ${r.reclaimed ?? 0} reclaimed, ${r.spawned ?? 0} spawned, ${r.crashed ?? 0} crashed`,
      );
      await refreshTasks();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Dispatch fehlgeschlagen");
    } finally {
      setDispatchBusy(false);
    }
  }

  async function confirmBulkArchive() {
    if (selectedIds.size === 0) return;
    try {
      const r = await archiveBulkHermesKanbanTasks(
        Array.from(selectedIds),
        board,
      );
      const failed = r.failed ?? {};
      const failedCount = Object.keys(failed).length;
      if (failedCount > 0) {
        toast.error(
          `${selectedIds.size - failedCount} archiviert; ${failedCount} fehlgeschlagen: ${Object.keys(failed).join(", ")}`,
        );
      } else {
        toast.success(`${selectedIds.size} Tasks archiviert`);
      }
      setBulkConfirmOpen(false);
      setSelectedIds(new Set());
      setSelectedTaskId(null);
      await refreshTasks();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Archivieren fehlgeschlagen",
      );
    }
  }

  const bulkTitles = selectedTasks.slice(0, 10).map((t) => t.title);

  return (
    <div className="flex h-full flex-col">
      {/* Kopfzeile */}
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2">
        {boards.length > 0 && (
          <select
            className="h-8 max-w-44 rounded-lg border border-input bg-transparent px-2 text-sm"
            value={board}
            onChange={(e) => {
              setBoard(e.target.value);
              setSelectedTaskId(null);
            }}
            aria-label="Board"
          >
            {boards.map((b) => (
              <option key={b.slug} value={b.slug}>
                {b.name || b.slug}
              </option>
            ))}
          </select>
        )}

        <select
          className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
          value={assigneeFilter}
          onChange={(e) => {
            setAssigneeFilter(e.target.value);
            setSelectedTaskId(null);
          }}
          aria-label="Assignee-Filter"
        >
          <option value="">Alle Assignees</option>
          {assignees.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>

        {/* PROJ-84 A: Phasenfilter ersetzt den bisherigen Archived-Toggle. */}
        <Popover>
          <PopoverTrigger className="inline-flex h-7 items-center gap-1.5 rounded-[min(var(--radius-md),12px)] border border-border bg-background px-2.5 text-[0.8rem] hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:border-input dark:bg-input/30 dark:hover:bg-input/50">
            <SlidersHorizontalIcon className="size-3.5" />
            Phasen
            <Badge variant="secondary">
              {visiblePhases.size}/{COLUMNS.length}
            </Badge>
          </PopoverTrigger>
          <PopoverContent className="w-56 space-y-1">
            <p className="px-1 pb-1 text-xs font-medium text-muted-foreground">
              Sichtbare Phasen
            </p>
            {COLUMNS.map((col) => (
              <label
                key={col.status}
                className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1 text-sm hover:bg-secondary/50"
              >
                <input
                  type="checkbox"
                  checked={visiblePhases.has(col.status)}
                  onChange={() => togglePhase(col.status)}
                  aria-label={`Phase ${col.label} umschalten`}
                />
                {col.label}
              </label>
            ))}
          </PopoverContent>
        </Popover>

        <Input
          value={quickInput}
          onChange={(e) => setQuickInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitQuickAdd()}
          placeholder="Schnell anlegen: requirements 82"
          className="h-8 w-56"
        />

        <div className="ml-auto flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => void refreshTasks()}
          >
            <RefreshCwIcon className="size-3.5" />
          </Button>
          <Button size="sm" variant="outline" onClick={() => void runDispatch()}>
            <ZapIcon className="size-3.5" />
            {dispatchBusy ? "Dispatched…" : "Dispatch jetzt"}
          </Button>
          <Button size="sm" onClick={openNewTask}>
            <PlusIcon className="size-3.5" />
            Neuer Task
          </Button>
        </div>
      </header>

      {loadError && (
        <p className="mx-4 mt-3 rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-3 text-sm text-red-500">
          {loadError}
        </p>
      )}

      {/* Bulk-Aktionsleiste */}
      {selectedIds.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-secondary/40 px-4 py-2">
          <span className="text-sm font-medium">{selectedIds.size} ausgewählt</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setSelectedIds(new Set());
              setSelectedTaskId(null);
            }}
          >
            <XIcon className="size-3.5" />
            Auswahl aufheben
          </Button>
          <div className="ml-auto">
            <Button
              size="sm"
              onClick={() => setBulkConfirmOpen(true)}
            >
              <ColumnsIcon className="size-3.5" />
              Archivieren ({selectedIds.size})
            </Button>
          </div>
        </div>
      )}

      {/* Board + angedocktes Detail (Desktop nebeneinander, mobil gestapelt). */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden">
        <div className="min-h-0 flex-1">
          {loading ? (
            <div className="flex h-full items-center justify-center px-4 py-3 text-sm text-muted-foreground">
              Lädt…
            </div>
          ) : (
            <div className="min-h-0 flex-1 overflow-x-auto px-4 py-3">
              {visibleCols.length === 0 ? (
                <div className="flex h-full items-center justify-center">
                  <p className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
                    Keine Phase ausgewählt. Oben rechts mindestens eine Phase
                    wählen.
                  </p>
                </div>
              ) : (
                <div className="flex h-full items-stretch gap-3">
                  {visibleCols.map((col) => {
                    const items = grouped.get(col.status) ?? [];
                    return (
                      <Column
                        key={col.status}
                        label={col.label}
                        count={items.length}
                        items={items}
                        selectionMode={selectedIds.size > 0}
                        selectedIds={selectedIds}
                        onToggleSelect={toggleSelect}
                        onOpen={(id) => setSelectedTaskId(id)}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Detail-Panel (rechts angedockt auf Desktop). */}
        {selectedTaskId && (
          <TaskDetailPanel
            taskId={selectedTaskId}
            board={board}
            onClose={() => setSelectedTaskId(null)}
            onChanged={() => void refreshTasks()}
          />
        )}
      </div>

      {/* Neuer Task */}
      <NewTaskDialog
        open={newTaskOpen}
        onOpenChange={setNewTaskOpen}
        board={board}
        assignees={assignees}
        parents={tasks.filter((t) => t.status !== "archived")}
        prefill={prefill}
        onCreated={() => void refreshTasks()}
      />

      {/* Bulk-Archiv-Bestätigung */}
      <Dialog
        open={bulkConfirmOpen}
        onOpenChange={(o) => !o && setBulkConfirmOpen(false)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedIds.size} Task{selectedIds.size === 1 ? "" : "s"} archivieren?
            </DialogTitle>
            <DialogDescription>
              Die ausgewählten Tasks werden aus der aktiven Ansicht entfernt.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-48 space-y-1 overflow-y-auto text-sm">
            {bulkTitles.map((t, i) => (
              <p key={i} className="truncate">
                {t}
              </p>
            ))}
            {selectedIds.size > 10 && (
              <p className="text-xs text-muted-foreground">
                +{selectedIds.size - 10} weitere
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkConfirmOpen(false)}>
              Abbrechen
            </Button>
            <Button
              variant="destructive"
              onClick={() => void confirmBulkArchive()}
            >
              <ColumnsIcon className="size-4" />
              Archivieren ({selectedIds.size})
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Column({
  label,
  count,
  items,
  selectionMode,
  selectedIds,
  onToggleSelect,
  onOpen,
}: {
  label: string;
  count: number;
  items: HermesKanbanTask[];
  selectionMode: boolean;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onOpen: (id: string) => void;
}) {
  return (
    <section className="flex w-64 shrink-0 flex-col rounded-xl border border-border bg-card min-h-[33dvh]">
      <header className="flex items-center gap-2 border-b border-border px-3 py-2">
        <ColumnsIcon className="size-3.5 text-muted-foreground" />
        <h3 className="text-xs font-semibold uppercase tracking-wide">{label}</h3>
        <Badge variant="secondary">{count}</Badge>
      </header>
      <div className="flex-1 min-h-0 space-y-2 overflow-y-auto p-2">
        {items.length === 0 ? (
          <p className="px-1 py-6 text-center text-xs text-muted-foreground">
            Keine Tasks
          </p>
        ) : (
          items.map((t) => {
            const selected = selectedIds.has(t.id);
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  if (selectionMode) onToggleSelect(t.id);
                  else onOpen(t.id);
                }}
                className={`flex w-full flex-col gap-1 rounded-lg border p-2 text-left transition-colors ${
                  selected
                    ? "border-primary bg-primary/10"
                    : "border-border bg-background hover:border-primary/50"
                }`}
              >
                <div className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggleSelect(t.id)}
                    onClick={(e) => e.stopPropagation()}
                    aria-label="Task auswählen"
                    className="mt-0.5 shrink-0"
                  />
                  <span className="line-clamp-2 text-sm font-medium">{t.title}</span>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 pl-6">
                  {t.assignee && (
                    <Badge variant="outline" className="text-[10px]">
                      {t.assignee}
                    </Badge>
                  )}
                  {t.priority != null && (
                    <span
                      className={`text-xs font-semibold ${PRIORITY_COLORS[String(t.priority)] ?? ""}`}
                    >
                      P{t.priority}
                    </span>
                  )}
                  <span className="text-[10px] text-muted-foreground">
                    {workspaceKindLabel(t)}
                  </span>
                  {fmtTime(t.created_at) && (
                    <span className="ml-auto text-[10px] text-muted-foreground">
                      {fmtTime(t.created_at)}
                    </span>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>
    </section>
  );
}
