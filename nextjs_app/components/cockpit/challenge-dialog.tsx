"use client";

// PROJ-23 — Challenge-Aktion: startet auf einem Artefakt (Vault-Pointer) eine Reviewer-
// Session mit (möglichst) anderer Engine. Zweistufig: Eingabe (Artefakt + optionale
// Reviewer-Engine + Fokus) → Ergebnis (Reviewer-Session-Link + Diversitäts-Hinweis).

import { useState } from "react";
import Link from "next/link";
import { Swords } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, getEngines, startChallenge } from "@/lib/api";
import type { EngineRead, ReviewRead } from "@/lib/types";

const AUTO = "__auto__";

export function ChallengeDialog({
  sessionId,
  defaultPointer,
  variant = "outline",
  onStarted,
}: {
  sessionId: string;
  /** Vorbelegung des Artefakt-Pointers (z. B. der Vertrag-Pointer der Session). */
  defaultPointer?: string | null;
  variant?: "outline" | "default" | "ghost";
  /** Nach erfolgreichem Start (z. B. ReviewsPanel neu laden). */
  onStarted?: (review: ReviewRead) => void;
}) {
  const [open, setOpen] = useState(false);
  const [pointer, setPointer] = useState(defaultPointer ?? "");
  const [engine, setEngine] = useState<string>(AUTO);
  const [focus, setFocus] = useState("");
  const [engines, setEngines] = useState<EngineRead[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ReviewRead | null>(null);

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) return;
    // Beim Öffnen frisch initialisieren + Engine-Liste laden (kein Effekt → keine
    // kaskadierenden Renders; gleiches Muster wie HandoverDialog).
    setPointer(defaultPointer ?? "");
    setResult(null);
    setEngine(AUTO);
    getEngines()
      // Nur steuerbare, verfügbare Engines kommen als Reviewer infrage.
      .then((o) => setEngines(o.engines.filter((e) => e.kind === "engine" && e.available)))
      .catch(() => {
        /* Engine-Liste optional — „automatisch" funktioniert auch ohne. */
      });
  }

  async function handleStart() {
    if (!pointer.trim() || busy) return;
    setBusy(true);
    try {
      const review = await startChallenge(sessionId, {
        artifact_pointer: pointer.trim(),
        reviewer_engine: engine === AUTO ? null : engine,
        focus: focus.trim() || null,
      });
      setResult(review);
      onStarted?.(review);
      toast.success(
        review.same_engine
          ? "Challenge gestartet (gleiche Engine — eingeschränkte Diversität)"
          : `Challenge gestartet (Reviewer: ${review.reviewer_engine})`,
      );
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Challenge fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm" variant={variant}>
            <Swords className="size-3.5" /> Challenge
          </Button>
        }
      />
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Cross-Agent-Review starten</DialogTitle>
          <DialogDescription>
            Ein anderer Agent (möglichst andere Engine) prüft ein Artefakt adversariell.
            Der Reviewer ändert das Artefakt nie — er liefert nur Befunde.
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-3 text-sm">
            <p>
              Reviewer-Session gestartet mit{" "}
              <span className="font-medium">
                {result.reviewer_engine}/{result.reviewer_model}
              </span>
              {result.same_engine && (
                <span className="text-amber-600 dark:text-amber-400">
                  {" "}
                  — ⚠️ gleiche Engine wie der Autor (eingeschränkte Diversität)
                </span>
              )}
              .
            </p>
            <p className="text-xs text-muted-foreground">
              Runde {result.round} · Artefakt:{" "}
              <span className="font-mono">{result.artifact_pointer}</span>
            </p>
            <Link
              href={`/sessions/${result.review_id}`}
              className="inline-block text-sm text-indigo-600 hover:underline dark:text-indigo-400"
            >
              Zur Reviewer-Session →
            </Link>
            <p className="text-xs text-muted-foreground">
              Die Befunde erscheinen, sobald der Reviewer fertig ist — als Karten auf der
              Reviewer-Session und in der Review-Übersicht dieser Session.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="ch-pointer">Artefakt-Pointer (Vault-relativ)</Label>
              <Input
                id="ch-pointer"
                value={pointer}
                onChange={(e) => setPointer(e.target.value)}
                placeholder="z. B. Agentic OS/Jupiter/Knowledge/PROJ-22-vertrag.md"
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ch-engine">Reviewer-Engine</Label>
              <Select value={engine} onValueChange={(v) => v && setEngine(v)}>
                <SelectTrigger id="ch-engine">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={AUTO}>Automatisch (andere Engine bevorzugt)</SelectItem>
                  {engines.map((e) => (
                    <SelectItem key={e.key} value={e.key}>
                      {e.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ch-focus">Prüf-Fokus (optional)</Label>
              <Input
                id="ch-focus"
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                placeholder="z. B. Sicherheit, Skalierung, Konsistenz"
              />
            </div>
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button variant="outline" onClick={() => setOpen(false)}>
              Schließen
            </Button>
          ) : (
            <Button disabled={busy || !pointer.trim()} onClick={handleStart}>
              {busy ? "Startet…" : "Challenge starten"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
