"use client";

// PROJ-82: Task-Aktionen (Einzeltask) — Blocken (Grund + Art), Entblocken
// (optionaler Grund), Archivieren (mit Bestätigung), Kommentieren. Jede Aktion
// ruft das Backend und meldet Erfolg/CLI-Fehler zurück; das Detail-Panel und
// die Board-Ansicht werden über `onChanged` aktualisiert.

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  archiveHermesKanbanTask,
  blockHermesKanbanTask,
  commentHermesKanbanTask,
  unblockHermesKanbanTask,
} from "@/lib/api";

type ActionKind = null | "block" | "unblock" | "archive" | "comment";

const BLOCK_KINDS = [
  { value: "", label: "Allgemein" },
  { value: "capability", label: "Capability" },
  { value: "dependency", label: "Dependency" },
  { value: "needs_input", label: "Needs Input" },
  { value: "transient", label: "Transient" },
];

interface TaskActionsProps {
  taskId: string;
  board: string;
  /** True, wenn der Task bereits archiviert ist (Archivieren-Button ausblenden). */
  archived?: boolean;
  onChanged: () => void;
}

export function TaskActions({ taskId, board, archived, onChanged }: TaskActionsProps) {
  const [kind, setKind] = useState<ActionKind>(null);
  const [reason, setReason] = useState("");
  const [blockKind, setBlockKind] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function open(next: ActionKind) {
    setReason("");
    setComment("");
    setBlockKind("");
    setError(null);
    setKind(next);
  }

  async function run(fn: () => Promise<void>, successMsg: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await fn();
      setKind(null);
      toast.success(successMsg);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Aktion fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" onClick={() => open("block")}>
        Blocken
      </Button>
      <Button size="sm" variant="outline" onClick={() => open("unblock")}>
        Entblocken
      </Button>
      {!archived && (
        <Button size="sm" variant="outline" onClick={() => open("archive")}>
          Archivieren
        </Button>
      )}
      <Button size="sm" variant="outline" onClick={() => open("comment")}>
        Kommentieren
      </Button>

      {/* Blocken */}
      <Dialog open={kind === "block"} onOpenChange={(o) => !o && setKind(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Task blocken</DialogTitle>
            <DialogDescription>Grund (optional) und Block-Art.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="hk_block_kind">Block-Art</Label>
              <select
                id="hk_block_kind"
                className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm"
                value={blockKind}
                onChange={(e) => setBlockKind(e.target.value)}
              >
                {BLOCK_KINDS.map((k) => (
                  <option key={k.value} value={k.value}>
                    {k.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="hk_block_reason">Grund</Label>
              <Input
                id="hk_block_reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
          </div>
          {error && (
            <p className="mt-2 rounded-lg border border-red-500/40 bg-red-500/5 px-3 py-2 text-sm text-red-500">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setKind(null)}>
              Abbrechen
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                void run(
                  () =>
                    blockHermesKanbanTask(
                      taskId,
                      board,
                      reason.trim() || null,
                      blockKind || null,
                    ),
                  "Task blockiert",
                )
              }
            >
              {busy ? "Blockt…" : "Blocken"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Entblocken */}
      <Dialog open={kind === "unblock"} onOpenChange={(o) => !o && setKind(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Task entblocken</DialogTitle>
            <DialogDescription>Optionaler Grund für das Entblocken.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="hk_unblock_reason">Grund</Label>
            <Input
              id="hk_unblock_reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          {error && (
            <p className="mt-2 rounded-lg border border-red-500/40 bg-red-500/5 px-3 py-2 text-sm text-red-500">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setKind(null)}>
              Abbrechen
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                void run(
                  () => unblockHermesKanbanTask(taskId, board, reason.trim() || null),
                  "Task entblockt",
                )
              }
            >
              {busy ? "Entblockt…" : "Entblocken"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Archivieren */}
      <Dialog open={kind === "archive"} onOpenChange={(o) => !o && setKind(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Task archivieren</DialogTitle>
            <DialogDescription>
              Der Task wird aus der aktiven Board-Ansicht entfernt.
            </DialogDescription>
          </DialogHeader>
          {error && (
            <p className="mt-2 rounded-lg border border-red-500/40 bg-red-500/5 px-3 py-2 text-sm text-red-500">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setKind(null)}>
              Abbrechen
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() =>
                void run(() => archiveHermesKanbanTask(taskId, board), "Task archiviert")
              }
            >
              {busy ? "Archiviert…" : "Archivieren"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Kommentieren */}
      <Dialog open={kind === "comment"} onOpenChange={(o) => !o && setKind(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Kommentar</DialogTitle>
            <DialogDescription>Autor ist fest `jupiter`.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="hk_comment">Text</Label>
            <Textarea
              id="hk_comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={4}
            />
          </div>
          {error && (
            <p className="mt-2 rounded-lg border border-red-500/40 bg-red-500/5 px-3 py-2 text-sm text-red-500">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setKind(null)}>
              Abbrechen
            </Button>
            <Button
              disabled={busy || !comment.trim()}
              onClick={() =>
                void run(
                  () => commentHermesKanbanTask(taskId, board, comment.trim()),
                  "Kommentar gesendet",
                )
              }
            >
              {busy ? "Sendet…" : "Senden"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
