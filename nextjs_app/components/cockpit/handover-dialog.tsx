"use client";

// Handover-Dialog (PROJ-5): erzeugt einen verdichteten Staffelstab (Gerüst + optionale
// Anreicherung), zeigt ihn editierbar als Vorschau und schreibt ihn in den Vault.
// Zwei-Schritt-Flow (generieren → prüfen/editieren → schreiben), damit der Handover
// ein bewusst kuratiertes Dokument bleibt, kein Wegwerf-Log.

import { useState } from "react";
import Link from "next/link";
import { FileTextIcon } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, generateHandover, writeHandover } from "@/lib/api";

export function HandoverDialog({
  sessionId,
  variant = "outline",
}: {
  sessionId: string;
  variant?: "outline" | "default" | "ghost";
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [savedPath, setSavedPath] = useState<string | null>(null);

  async function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) return;
    // Beim Öffnen frisch generieren (Gerüst aus dem aktuellen Session-Zustand).
    setSavedPath(null);
    setLoading(true);
    try {
      const preview = await generateHandover(sessionId);
      setTitle(preview.title);
      setBody(preview.body);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Handover-Generierung fehlgeschlagen");
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }

  async function handleWrite() {
    if (!body.trim() || saving) return;
    setSaving(true);
    try {
      const result = await writeHandover(sessionId, body, title.trim() || undefined);
      setSavedPath(result.path);
      toast.success("Handover im Vault gespeichert");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Schreiben fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button variant={variant} size="sm">
            <FileTextIcon className="size-4" />
            Handover
          </Button>
        }
      />
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Handover erzeugen</DialogTitle>
          <DialogDescription>
            Verdichteter Staffelstab (Wo stehen wir? / Erledigt / Offen / Fallstricke /
            Pointer). Vor dem Schreiben prüf- und editierbar.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Generiere Handover…
          </p>
        ) : (
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="handover_title">Titel</Label>
              <Input
                id="handover_title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                spellCheck={false}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="handover_body">Inhalt (Markdown)</Label>
              <Textarea
                id="handover_body"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={14}
                className="font-mono text-xs"
              />
            </div>
            {savedPath && (
              <p className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-500">
                Gespeichert: <span className="font-mono">{savedPath}</span>
                {" · "}
                <Link
                  href={`/doku?source=vault&rel=${encodeURIComponent(savedPath)}`}
                  className="underline underline-offset-2 hover:no-underline"
                >
                  Im Reader öffnen →
                </Link>
              </p>
            )}
          </div>
        )}

        <DialogFooter showCloseButton>
          <Button onClick={handleWrite} disabled={loading || saving || !body.trim()}>
            {saving ? "Speichert…" : savedPath ? "Erneut speichern" : "In Vault schreiben"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
