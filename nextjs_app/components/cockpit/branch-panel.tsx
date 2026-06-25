"use client";

// PROJ-13: in-App Git-Branch-Handling — Ein-Klick-UI für die abc-Git-Logik.
// Ein `BranchBadge` im Header zeigt je Projekt (= aktueller Explorer-Pfad) den
// Branch + clean/dirty + ahead/behind und öffnet ein `BranchPanel` (Dialog) zum
// Wechseln (main ↔ dev), Feature-Branch anlegen (specs/PROJ-X-<slug>) und
// Promoten (dev → main). Git ist die Quelle der Wahrheit — der Status wird live
// gepollt, nichts lokal gespiegelt. Deutsche UI; gefährliche Operationen (Force)
// gibt es bewusst nicht. Alle Calls scoped das Backend gegen die erlaubten Roots.

import { useCallback, useEffect, useState } from "react";
import { GitBranch, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ApiError,
  createFeatureBranch,
  getBranchStatus,
  gitInit,
  promoteBranch,
  stashChanges,
  switchBranch,
} from "@/lib/api";
import type { BranchStatus } from "@/lib/types";

/** Reine Darstellungs-Logik des Badges (ohne Netz/State) — separat testbar. */
export function describeBranch(status: BranchStatus | null): {
  label: string;
  variant: "default" | "secondary" | "destructive" | "outline";
  title: string;
} {
  if (!status) return { label: "Git…", variant: "outline", title: "Branch-Status wird geladen" };
  if (!status.is_repo)
    return { label: "Kein Git-Repo", variant: "outline", title: "Dieses Verzeichnis ist kein Git-Repository" };
  if (status.detached)
    return {
      label: `detached @${status.branch ?? "?"}`,
      variant: "destructive",
      title: "Detached HEAD — auf keinem Branch",
    };
  const ab = [
    status.ahead ? `↑${status.ahead}` : "",
    status.behind ? `↓${status.behind}` : "",
  ]
    .filter(Boolean)
    .join(" ");
  return {
    label: `${status.branch ?? "?"}${status.dirty ? " •" : ""}${ab ? ` ${ab}` : ""}`,
    variant: status.dirty ? "secondary" : "default",
    title: status.dirty ? "Uncommittete Änderungen vorhanden" : "Working Tree sauber",
  };
}

/** Badge + Panel für den Branch-Status eines Projektpfads. */
export function BranchBadge({ path }: { path: string | null }) {
  const [status, setStatus] = useState<BranchStatus | null>(null);
  const [open, setOpen] = useState(false);

  // Manueller Refresh (Button im Panel) — kein Effect, daher freier setState.
  const reload = useCallback(() => {
    if (!path) return;
    getBranchStatus(path)
      .then(setStatus)
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 0)) setStatus(null);
      });
  }, [path]);

  // Status bei Pfadwechsel laden (read-only, günstig). setState nur in den
  // Promise-Callbacks (akzeptiertes Muster wie im FileExplorer).
  useEffect(() => {
    if (!path) return;
    const ac = new AbortController();
    getBranchStatus(path, ac.signal)
      .then((s) => setStatus(s))
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 0)) setStatus(null);
      });
    return () => ac.abort();
  }, [path]);

  if (!path) return null;
  const { label, variant, title } = describeBranch(status);

  return (
    <>
      <Badge
        variant={variant}
        title={title}
        className="cursor-pointer gap-1 px-2"
        render={<button type="button" onClick={() => setOpen(true)} />}
      >
        <GitBranch className="size-3" />
        <span className="max-w-[12rem] truncate font-mono">{label}</span>
      </Badge>
      <BranchPanel
        open={open}
        onOpenChange={setOpen}
        path={path}
        status={status}
        onChanged={(s) => setStatus(s)}
        onReload={() => void reload()}
      />
    </>
  );
}

function BranchPanel({
  open,
  onOpenChange,
  path,
  status,
  onChanged,
  onReload,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  path: string;
  status: BranchStatus | null;
  onChanged: (s: BranchStatus) => void;
  onReload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [featureId, setFeatureId] = useState("");
  const [slug, setSlug] = useState("");
  const [base, setBase] = useState("main");

  // Generische Aktion: 409 (dirty/Konflikt/kein-Repo) als bedienbaren Hinweis
  // zeigen, Erfolg spiegelt den frischen Status zurück. Kein stiller Verlust.
  async function run(
    fn: () => Promise<BranchStatus>,
    ok: string,
  ): Promise<boolean> {
    setBusy(true);
    try {
      onChanged(await fn());
      toast.success(ok);
      return true;
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Git-Operation fehlgeschlagen");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const isRepo = status?.is_repo ?? false;
  const branches = status?.branches ?? [];
  const current = status?.branch ?? null;

  async function doFeatureBranch() {
    const id = Number(featureId);
    if (!Number.isInteger(id) || id < 1) {
      toast.error("Bitte eine gültige PROJ-Nummer angeben.");
      return;
    }
    if (!slug.trim()) {
      toast.error("Bitte einen Kurz-Titel (Slug) angeben.");
      return;
    }
    if (await run(() => createFeatureBranch(path, id, slug.trim(), base), "Feature-Branch bereit")) {
      setFeatureId("");
      setSlug("");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitBranch className="size-4" /> Branch-Verwaltung
          </DialogTitle>
          <DialogDescription className="truncate font-mono text-xs">{path}</DialogDescription>
        </DialogHeader>

        {!isRepo ? (
          // Kein Git-Repo → Aktionen ausgegraut, Angebot „git init".
          <div className="space-y-3 py-2 text-sm">
            <p className="text-muted-foreground">
              Dieses Verzeichnis ist kein Git-Repository.
            </p>
            <Button
              size="sm"
              disabled={busy}
              onClick={() => void run(() => gitInit(path), "Repository initialisiert")}
            >
              git init ausführen
            </Button>
          </div>
        ) : (
          <div className="space-y-4 py-1 text-sm">
            {/* Status-Kopf */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-muted-foreground">Aktuell:</span>
              <Badge variant={status?.detached ? "destructive" : "default"} className="font-mono">
                {status?.detached ? `detached @${current}` : current}
              </Badge>
              <Badge variant={status?.dirty ? "secondary" : "outline"}>
                {status?.dirty ? "dirty" : "clean"}
              </Badge>
              {(status?.ahead || status?.behind) ? (
                <Badge variant="outline" className="font-mono">
                  ↑{status?.ahead ?? 0} ↓{status?.behind ?? 0}
                </Badge>
              ) : null}
              <Button
                size="icon-sm"
                variant="ghost"
                className="ml-auto"
                title="Status neu laden"
                disabled={busy}
                onClick={onReload}
              >
                <RefreshCw className="size-4" />
              </Button>
            </div>

            {/* Dirty-Warnung + expliziter Stash (Optionen statt Zwang) */}
            {status?.dirty && (
              <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs">
                <p className="mb-2">
                  Uncommittete Änderungen vorhanden — ein Wechsel/Promote wird blockiert.
                  Erst committen oder stashen.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => void run(() => stashChanges(path), "Änderungen gestasht")}
                >
                  Änderungen stashen
                </Button>
              </div>
            )}

            {/* Branch wechseln */}
            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                Branch wechseln
              </h3>
              <div className="flex flex-wrap gap-2">
                {branches.map((b) => (
                  <Button
                    key={b}
                    size="sm"
                    variant={b === current ? "default" : "outline"}
                    disabled={busy || b === current}
                    className="font-mono"
                    onClick={() => void run(() => switchBranch(path, b), `Auf ${b} gewechselt`)}
                  >
                    {b}
                  </Button>
                ))}
              </div>
            </section>

            {/* Feature-Branch anlegen */}
            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                Feature-Branch anlegen
              </h3>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-muted-foreground">specs/PROJ-</span>
                <Input
                  value={featureId}
                  onChange={(e) => setFeatureId(e.target.value.replace(/\D/g, ""))}
                  placeholder="13"
                  inputMode="numeric"
                  className="w-16"
                />
                <span className="font-mono text-muted-foreground">-</span>
                <Input
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="kurz-titel"
                  className="flex-1 min-w-[8rem] font-mono"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">von</span>
                {["main", "dev"].map((b) => (
                  <Button
                    key={b}
                    size="sm"
                    variant={base === b ? "secondary" : "ghost"}
                    className="font-mono"
                    disabled={busy}
                    onClick={() => setBase(b)}
                  >
                    {b}
                  </Button>
                ))}
                <Button size="sm" className="ml-auto" disabled={busy} onClick={doFeatureBranch}>
                  Anlegen
                </Button>
              </div>
            </section>

            {/* Promote (dev → main) */}
            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                Promote (Merge --no-ff)
              </h3>
              <p className="text-xs text-muted-foreground">
                Vorab-Check (sauber, Ziel ⊆ Quelle); bei Konflikt wird abgebrochen.
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  className="font-mono"
                  onClick={() =>
                    void run(() => promoteBranch(path, "dev", "main"), "dev → main promotet")
                  }
                >
                  dev → main
                </Button>
                {current && current !== "dev" && current !== "main" && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    className="font-mono"
                    onClick={() =>
                      void run(
                        () => promoteBranch(path, current, "dev"),
                        `${current} → dev promotet`,
                      )
                    }
                  >
                    {current} → dev
                  </Button>
                )}
              </div>
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
