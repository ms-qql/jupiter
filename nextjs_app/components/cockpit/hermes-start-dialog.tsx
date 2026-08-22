"use client";

// „Neu Hermes"-Dialog (PROJ-85): startet eine Hermes-Chat-Session fest im
// Bypass-Modus mit aktiviertem Token Savings (beides serverseitige Festwerte,
// hier weder sichtbar noch änderbar). Felder: Titel (optional), Projekt-Pfad
// (Pflicht), Modell (Pflicht, Hermes-kompatibel aus GET /sessions/hermes/options).
// Nach dem Start erscheint die Session unter „Aktive Sessions" und öffnet die
// bekannte Session-Ansicht (engine="hermes").

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, getHermesOptions, startHermesSession } from "@/lib/api";
import { projectName } from "@/lib/status";
import type { HermesModelOption, HermesOptions } from "@/lib/types";
import { useSessions } from "./sessions-provider";

export function HermesStartDialog({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { refresh } = useSessions();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Formularfelder.
  const [title, setTitle] = useState("");
  const [projectPath, setProjectPath] = useState("/home/dev/projects/");

  // Modell-Optionen aus dem Backend (GET /sessions/hermes/options).
  const [options, setOptions] = useState<HermesOptions>({
    models: [],
    warning: null,
  });
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [model, setModel] = useState<string>("");

  // Fehlerzustand nach Submit (Dialog bleibt offen für Korrektur).
  const [submitError, setSubmitError] = useState<string | null>(null);

  const modelOptions: HermesModelOption[] = options.models;

  const suggestedName = projectName(projectPath.trim()) || "jupiter";

  const selectedOption = modelOptions.find((m) => m.model === model) ?? null;

  const valid =
    projectPath.trim().length > 0 &&
    modelOptions.length > 0 &&
    selectedOption !== null;

  // Modell auf das erste verfügbare zurücksetzen, sobald die Liste (neu) da ist.
  function onOptionsChanged(next: HermesOptions) {
    setOptions(next);
    setOptionsError(null);
    const first = next.models[0]?.model;
    setModel((current) => current || first || "");
  }

  // Optionen laden, sobald der Dialog geöffnet wird (nicht-blockierend).
  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    setOptionsLoading(true);
    getHermesOptions(ctrl.signal)
      .then((value) => {
        if (ctrl.signal.aborted) return;
        onOptionsChanged(value);
      })
      .catch((err) => {
        if (ctrl.signal.aborted) return;
        setOptions({ models: [], warning: null });
        setOptionsError(
          err instanceof ApiError
            ? err.message
            : "Hermes-Modellliste konnte nicht geladen werden",
        );
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setOptionsLoading(false);
      });
    return () => ctrl.abort();
  }, [open]);

  function resetForm() {
    setTitle("");
    setProjectPath("/home/dev/projects/");
    setOptions({ models: [], warning: null });
    setOptionsLoading(false);
    setOptionsError(null);
    setModel("");
    setSubmitError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const selected = modelOptions.find((m) => m.model === model);
      const session = await startHermesSession({
        title: title.trim() || null,
        project_path: projectPath.trim(),
        engine: selected?.engine ?? "",
        model,
      });
      toast.success("Hermes-Session gestartet");
      setOpen(false);
      resetForm();
      refresh();
      router.push(`/sessions/${session.session_id}`);
    } catch (err) {
      // Dialog bleibt offen — der Nutzer kann Pfad/Modell korrigieren.
      setSubmitError(
        err instanceof ApiError
          ? err.message
          : "Hermes-Session konnte nicht gestartet werden",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {/* Base UI: eigenes Element via render (kein asChild wie bei Radix). */}
      <DialogTrigger render={children as React.ReactElement} />
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-hidden sm:max-w-lg">
        <form
          onSubmit={handleSubmit}
          className="flex max-h-[calc(100dvh-4rem)] min-h-0 flex-col"
        >
          <DialogHeader className="shrink-0">
            <DialogTitle>Neue Hermes-Session</DialogTitle>
            <DialogDescription>
              Startet eine Hermes-Chat-Session — Bypass und Token Savings sind
              fest aktiviert.
            </DialogDescription>
          </DialogHeader>

          <div className="grid min-h-0 gap-4 overflow-y-auto py-4 pr-1">
            <div className="grid gap-2">
              <Label htmlFor="hermes_title">Titel (optional)</Label>
              <Input
                id="hermes_title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={suggestedName}
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="hermes_path">Projekt-Pfad (Pflicht)</Label>
              <Input
                id="hermes_path"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                placeholder="/home/dev/projects/jupiter"
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="hermes_model">Modell (Pflicht)</Label>
              <Select value={model} onValueChange={(v) => v && setModel(v)}>
                <SelectTrigger id="hermes_model" className="w-full">
                  <SelectValue
                    placeholder={
                      optionsLoading
                        ? "Lade Modelle…"
                        : modelOptions.length === 0
                          ? "Keine Modelle verfügbar"
                          : "Modell wählen"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {modelOptions.map((m) => (
                    <SelectItem key={m.model} value={m.model}>
                      {m.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {optionsLoading && (
                <p className="text-xs text-muted-foreground">
                  Hermes-Modellliste wird geladen…
                </p>
              )}
              {optionsError && (
                <p className="text-xs text-red-400">{optionsError}</p>
              )}
              {options.warning && !optionsError && (
                <p className="text-xs text-amber-500">{options.warning}</p>
              )}
              {!optionsLoading &&
                !optionsError &&
                modelOptions.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    Keine Hermes-kompatiblen Modelle verfügbar.
                  </p>
                )}
            </div>

            {submitError && (
              <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-400">
                {submitError}
              </p>
            )}
          </div>

          <DialogFooter className="shrink-0">
            <Button
              type="submit"
              disabled={!valid || submitting}
              className="w-full sm:w-auto"
            >
              {submitting ? "Startet…" : "Hermes-Session starten"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
