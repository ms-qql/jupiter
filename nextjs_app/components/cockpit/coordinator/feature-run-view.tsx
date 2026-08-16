"use client";

// PROJ-79: Feature-Ausführung als zusammengehörige Gruppe — Elternkopf (Feature-ID +
// Gesamtzustand + Fortschritt + Pausieren/Abbrechen) über der Paketliste. Die Pakete
// kommen aus GET /coordinator/features/{id} (eigener Poll, unabhängig vom
// Session-Poll); Mutationen rufen /coordinator/features/{id}/*.

import { useEffect, useState } from "react";
import { Pause, Play, CheckCircle2, XCircle, RotateCcw, Hand, Trash2 } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, completePackage, deleteFeatureRun, featureDecision, getFeatureRun, setFeaturePaused } from "@/lib/api";
import { statusMeta } from "@/lib/status";
import type { FeaturePackageRead, FeatureRun } from "@/lib/types";
import { Ampel } from "../ampel";
import { ConfirmDialog } from "../confirm-dialog";

/** Gesamtzustand der Feature-Ausführung → Ampelfarbe. */
function runMeta(status: FeatureRun["status"]): { ampel: "green" | "amber" | "red"; label: string } {
  switch (status) {
    case "fertig":
      return { ampel: "green", label: "Fertig" };
    case "läuft":
      return { ampel: "green", label: "Läuft" };
    case "pausiert":
      return { ampel: "amber", label: "Pausiert" };
    case "blockiert":
      return { ampel: "amber", label: "Blockiert" };
    case "abgebrochen":
      return { ampel: "red", label: "Abgebrochen" };
    default:
      return { ampel: "amber", label: "Planung" };
  }
}

export function FeatureRunView({
  featureId,
  coordinator,
  onDeleted,
}: {
  featureId: string;
  /** Die Koordinator-Session aus dem globalen Poll (für Name/Link). */
  coordinator: FeatureRun["coordinator"];
  onDeleted?: () => void;
}) {
  const [run, setRun] = useState<FeatureRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [completeFor, setCompleteFor] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useEffect(() => {
    if (!featureId) return;
    const ac = new AbortController();
    async function load() {
      try {
        const r = await getFeatureRun(featureId, ac.signal);
        if (!ac.signal.aborted) setRun(r);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return;
      }
    }
    void load();
    const t = setInterval(() => void load(), 4000);
    return () => {
      ac.abort();
      clearInterval(t);
    };
  }, [featureId]);

  async function togglePause() {
    if (busy || !run) return;
    setBusy(true);
    try {
      const r = await setFeaturePaused(featureId, !run.paused);
      setRun(r);
      toast.success(r.paused ? "Schwarm pausiert" : "Fortgesetzt");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Aktion fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function decide(action: "retry" | "manual" | "abort", packageId?: string) {
    if (busy) return;
    setBusy(true);
    try {
      const r = await featureDecision(featureId, action, packageId);
      setRun(r);
      toast.success(
        action === "abort"
          ? "Schwarm abgebrochen"
          : action === "manual"
            ? "Manuell übernommen"
            : "Erneut versucht",
      );
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Entscheidung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function removeRun() {
    if (busy) return;
    setBusy(true);
    try {
      await deleteFeatureRun(coordinator.session_id);
      toast.success("Schwarm gelöscht.");
      setDeleteOpen(false);
      onDeleted?.();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Löschen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  const meta = run ? runMeta(run.status) : { ampel: "amber" as const, label: "…" };
  const done = run?.packages.filter((p) => p.status === "erfolgreich").length ?? 0;
  const total = run?.packages.length ?? 0;

  return (
    <section className="rounded-xl border border-emerald-500/40 bg-emerald-500/[0.03] p-3">
      <header className="flex flex-wrap items-center gap-2">
        <Ampel color={meta.ampel} />
        <Link
          href={`/sessions/${coordinator.session_id}`}
          className="font-medium hover:underline"
          title={coordinator.project_name ?? coordinator.session_id}
        >
          🐝 Schwarm {featureId}
        </Link>
        <Badge variant="secondary" className="text-[10px]">
          Schwarm
        </Badge>
        <Badge variant="outline" className="text-[10px]">
          {meta.label}
        </Badge>
        {total > 0 && (
          <Badge
            variant="outline"
            className="text-[10px] tabular-nums"
            title={`${done}/${total} Pakete erfolgreich`}
          >
            {done}/{total} Pakete
          </Badge>
        )}
        {run?.paused && (
          <Badge variant="outline" className="border-amber-500/50 text-[10px] text-amber-600 dark:text-amber-400">
            pausiert
          </Badge>
        )}

        <div className="ml-auto flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={togglePause} disabled={busy || (run?.status === "fertig" || run?.status === "abgebrochen")}>
            {run?.paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}
            {run?.paused ? "Fortsetzen" : "Pausieren"}
          </Button>
          <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)} disabled={busy}>
            <Trash2 className="size-3.5" />
            Löschen
          </Button>
        </div>
      </header>

      {/* Genau eine Blockierungs-Decision-Card */}
      {run?.blocker && (
        <div className="mt-3 rounded-lg border border-orange-500/50 bg-orange-500/5 p-3">
          <p className="flex items-center gap-1.5 text-sm font-medium text-orange-600 dark:text-orange-400">
            <XCircle className="size-4" />
            Entscheidung nötig — Paket {run.blocker.package_id}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{run.blocker.cause}</p>
          {run.blocker.last_safe_state && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              Letzter sicherer Stand: {run.blocker.last_safe_state}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Button size="sm" variant="outline" onClick={() => decide("retry", run.blocker!.package_id)} disabled={busy}>
              <RotateCcw className="size-3.5" />
              Erneut versuchen
            </Button>
            <Button size="sm" variant="outline" onClick={() => decide("manual", run.blocker!.package_id)} disabled={busy}>
              <Hand className="size-3.5" />
              Manuell übernehmen
            </Button>
            <Button size="sm" variant="destructive" onClick={() => decide("abort")} disabled={busy}>
              <XCircle className="size-3.5" />
              Schwarm abbrechen
            </Button>
          </div>
        </div>
      )}

      {/* Paketliste */}
      <div className="mt-3 flex flex-col gap-2 border-l-2 border-emerald-500/20 pl-3">
        {!run ? (
          <p className="py-2 text-xs text-muted-foreground">Lade Schwarm …</p>
        ) : run.packages.length === 0 ? (
          <p className="py-2 text-xs text-muted-foreground">Noch keine Arbeitspakete.</p>
        ) : (
          run.packages.map((pkg) => (
            <PackageRow
              key={pkg.package_id}
              pkg={pkg}
              onCompleteClick={() => setCompleteFor((id) => (id === pkg.package_id ? null : pkg.package_id))}
              completeOpen={completeFor === pkg.package_id}
              onComplete={(proof) => completePackage(featureId, pkg.package_id, proof).then(setRun).catch((e) => toast.error(e instanceof ApiError ? e.message : "Beleg fehlgeschlagen"))}
            />
          ))
        )}
      </div>
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={(next) => !busy && setDeleteOpen(next)}
        title="Schwarm löschen?"
        description="Der Koordinator und alle Paket-Sessions werden gestoppt und aus dem Cockpit entfernt. Session-Logs im Vault bleiben erhalten."
        loading={busy}
        onConfirm={() => void removeRun()}
      />
    </section>
  );
}

function PackageRow({
  pkg,
  onCompleteClick,
  completeOpen,
  onComplete,
}: {
  pkg: FeaturePackageRead;
  onCompleteClick: () => void;
  completeOpen: boolean;
  onComplete: (proof: Parameters<typeof completePackage>[2]) => void;
}) {
  const meta = statusMeta(pkg.status === "läuft" ? "running" : pkg.status === "erfolgreich" ? "done" : pkg.status === "fehlgeschlagen" ? "error" : "waiting");
  const [busy, setBusy] = useState(false);
  const [resultState, setResultState] = useState<"success" | "failed">("success");
  const [artifacts, setArtifacts] = useState("");
  const [checkResult, setCheckResult] = useState("");
  const [limitations, setLimitations] = useState("");

  // BUG-2-Fix: Backend verlangt bei "success" mind. 1 Artefakt + 1 Check mit Ergebnis
  // (sonst 400 "Abschlussbeleg unvollständig"). Vorher gab es dafür kein Formularfeld.
  const successIncomplete =
    resultState === "success" && (!artifacts.trim() || !checkResult.trim());

  async function submit() {
    if (successIncomplete) return;
    setBusy(true);
    try {
      await onComplete({
        package_id: pkg.package_id,
        role: pkg.role,
        result_state: resultState,
        artifacts: artifacts.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean),
        checks: checkResult.trim() ? [{ name: "Abschlussprüfung", result: checkResult.trim() }] : [],
        open_limitations: limitations.trim() || null,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Ampel color={meta.ampel} />
            <Badge variant="secondary" className="shrink-0 font-mono text-[10px]">
              {pkg.package_id}
            </Badge>
            <span className="min-w-0 flex-1 truncate text-sm" title={pkg.title}>
              {pkg.title}
            </span>
            {pkg.session_id && (
              <Link href={`/sessions/${pkg.session_id}`} className="shrink-0 text-[11px] text-indigo-500 hover:underline">
                Session
              </Link>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 pl-8 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              {pkg.role ?? "—"}
            </span>
            <span aria-hidden>·</span>
            <span className="uppercase">{pkg.engine}</span>
            {pkg.model && (
              <>
                <span aria-hidden>·</span>
                <span>{pkg.model}</span>
              </>
            )}
            {pkg.required_proof !== "other" && (
              <>
                <span aria-hidden>·</span>
                <span>Beleg: {pkg.required_proof}</span>
              </>
            )}
            {pkg.resume_attempts > 0 && (
              <>
                <span aria-hidden>·</span>
                <span>{pkg.resume_attempts}× wiederaufgenommen</span>
              </>
            )}
          </div>
          {pkg.proof && (
            <p className="mt-1 pl-8 text-[11px] text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="mr-1 inline size-3" />
              Beleg: {pkg.proof.result_state}
              {pkg.proof.artifacts.length > 0 && ` · ${pkg.proof.artifacts.length} Artefakt(e)`}
            </p>
          )}
        </div>
        {(pkg.status === "wartet" || pkg.status === "bereit" || pkg.status === "fehlgeschlagen" || pkg.status === "läuft") && (
          <Button variant="ghost" size="sm" onClick={onCompleteClick} title="Abschluss manuell melden" disabled={busy}>
            <CheckCircle2 className="size-3.5" />
          </Button>
        )}
      </div>

      {completeOpen && (
        <div className="ml-1 flex flex-col gap-2 rounded-md border border-border bg-card/60 p-2">
          <p className="text-[11px] text-muted-foreground">
            Strukturierter Abschlussbeleg für {pkg.package_id} (ersetzt alleinigen
            Session-Endstatus).
          </p>
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
            Ergebnis
            <Select value={resultState} onValueChange={(v) => v && setResultState(v as "success" | "failed")}>
              <SelectTrigger className="h-8 w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="success">erfolgreich</SelectItem>
                <SelectItem value="failed">fehlgeschlagen</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
            Artefakte (Pfad pro Zeile){resultState === "success" && " · Pflicht"}
            <Textarea
              value={artifacts}
              onChange={(e) => setArtifacts(e.target.value)}
              placeholder="src/…/datei.ts"
              className="h-16 font-mono text-[11px]"
            />
          </label>
          {resultState === "success" && (
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
              Durchgeführte Prüfung + Ergebnis · Pflicht
              <Input
                value={checkResult}
                onChange={(e) => setCheckResult(e.target.value)}
                placeholder="z. B. pytest grün / manuell verifiziert"
                className="h-8"
              />
            </label>
          )}
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
            Offene Einschränkungen
            <Input
              value={limitations}
              onChange={(e) => setLimitations(e.target.value)}
              placeholder="—"
              className="h-8"
            />
          </label>
          <div className="flex gap-2">
            <Button size="sm" onClick={submit} disabled={busy || successIncomplete}>
              {busy ? "…" : "Beleg einspielen"}
            </Button>
            <Button variant="ghost" size="sm" onClick={onCompleteClick} disabled={busy}>
              Abbrechen
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
