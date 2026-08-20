"use client";

// PROJ-83: Modellwahl je erkanntem abc-Hermes-Profil (Präfix `jupiter-`).
// Konsumiert GET/PATCH /settings/hermes-profiles. Die UI bietet pro Profil ein
// Dropdown mit den aus Jupiters bestehender Modellverwaltung (PROJ-51) stammenden
// Modellen; der Nutzer wählt, ändert mehrere und speichert explizit. Secrets/
// Credentials werden weder gelesen noch angezeigt — nur das Modell.

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangleIcon,
  RefreshCwIcon,
  RotateCcwIcon,
  SaveIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ApiError,
  getHermesProfiles,
  setHermesProfileModels,
} from "@/lib/api";
import type {
  HermesProfilesRead,
  HermesProfileModel,
  HermesProfileSaveResult,
} from "@/lib/types";

/** Mapping Profilschlüssel → kurzer Rollenanzeigename (nur für Optik). */
const ROLE_LABELS: Record<string, string> = {
  "jupiter-requirements": "Requirements",
  "jupiter-architecture": "Architecture",
  "jupiter-frontend": "Frontend",
  "jupiter-backend": "Backend",
  "jupiter-qa": "QA",
  "jupiter-coordinator": "Koordinator",
  "jupiter-deploy": "Deploy",
  "jupiter-document": "Dokumentation",
  "jupiter-brainstorm": "Brainstorm",
  "jupiter-backoffice": "Backoffice",
  "jupiter-predeploy": "Pre-Deploy",
  "jupiter-review-architecture": "Review-Architecture",
};

function roleLabel(profile: string): string {
  return ROLE_LABELS[profile] ?? profile;
}

/** Lokal editierbarer Stand eines Profils: gewähltes Modell + Unsaved-Flag. */
interface Draft {
  model: string | null;
  dirty: boolean;
}

// --- Loading / Empty / Error / Success: Zustände explizit ------------------

export function HermesProfileModelsControl() {
  const [data, setData] = useState<HermesProfilesRead | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);

  function applyData(d: HermesProfilesRead) {
    setData(d);
    // Draft-Initialwert = aktuell wirksames Modell (auch wenn nicht in `models`).
    const next: Record<string, Draft> = {};
    for (const p of d.profiles) {
      next[p.profile] = { model: p.current_model, dirty: false };
    }
    setDrafts(next);
    setLoadFailed(false);
  }

  async function reload() {
    setLoading(true);
    try {
      applyData(await getHermesProfiles());
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const ac = new AbortController();
    getHermesProfiles(ac.signal)
      .then((d) => {
        if (!ac.signal.aborted) applyData(d);
      })
      .catch(() => {
        if (!ac.signal.aborted) setLoadFailed(true);
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, []);

  const models = useMemo(() => data?.models ?? [], [data]);
  const profiles = useMemo(() => data?.profiles ?? [], [data]);
  const writableProfiles = useMemo(
    () => profiles.filter((p) => p.error === null),
    [profiles],
  );

  const dirtyCount = useMemo(
    () => Object.values(drafts).filter((d) => d.dirty).length,
    [drafts],
  );

  function setDraft(profile: string, model: string) {
    setDrafts((prev) => ({
      ...prev,
      [profile]: { model, dirty: true },
    }));
  }

  function resetLocal() {
    if (!data) return;
    const next: Record<string, Draft> = {};
    for (const p of data.profiles) {
      next[p.profile] = { model: p.current_model, dirty: false };
    }
    setDrafts(next);
  }

  async function handleSave() {
    if (saving || dirtyCount === 0 || !data) return;
    const payload = writableProfiles
      .filter((p) => drafts[p.profile]?.dirty)
      .map((p) => ({ profile: p.profile, model: drafts[p.profile].model ?? "" }))
      .filter((e) => e.model.length > 0);
    if (payload.length === 0) return;

    setSaving(true);
    try {
      const results: HermesProfileSaveResult[] = await setHermesProfileModels(
        payload,
      );
      // Server-Antwort als neue Wahrheit übernehmen (kein lokaler Entwurf = gespeichert).
      const savedByProfile = new Map(results.map((r) => [r.profile, r]));
      const nextDrafts: Record<string, Draft> = { ...drafts };
      const failures: string[] = [];
      for (const p of data.profiles) {
        const res = savedByProfile.get(p.profile);
        if (!res) continue;
        if (res.ok) {
          nextDrafts[p.profile] = { model: res.saved_model, dirty: false };
        } else {
          // Fehlgeschlagene Profile: letzten gültigen Stand behalten (dirty=false),
          // damit kein irreführender Erfolgszustand entsteht.
          nextDrafts[p.profile] = {
            model: p.current_model,
            dirty: false,
          };
          failures.push(`${roleLabel(p.profile)}: ${res.error ?? "Fehler"}`);
        }
      }
      setDrafts(nextDrafts);

      if (failures.length === 0) {
        toast.success("Modellzuordnung gespeichert");
      } else if (failures.length < payload.length) {
        toast.error(
          `${payload.length - failures.length} Profil(e) gespeichert, ${failures.length} fehlgeschlagen`,
        );
        failures.forEach((f) => console.warn("PROJ-83 Speichern:", f));
      } else {
        toast.error(
          `Speichern fehlgeschlagen: ${failures[0] ?? "Unbekannter Fehler"}`,
        );
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  // --- Load-Fehler-Zustand ---
  if (loadFailed) {
    return (
      <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
        <div className="flex items-center gap-2 font-medium">
          <AlertTriangleIcon className="size-4" />
          Hermes-Profile nicht erreichbar
        </div>
        <p className="mt-1 text-xs">
          Backend offline oder Endpunkt <code>/settings/hermes-profiles</code> nicht
          verfügbar.
        </p>
        <Button
          size="sm"
          variant="outline"
          className="mt-2"
          onClick={() => void reload()}
        >
          <RefreshCwIcon />
          Wiederholen
        </Button>
      </div>
    );
  }

  // --- Lade-Zustand ---
  if (loading || !data) {
    return <p className="text-xs text-muted-foreground">Lädt Hermes-Profile…</p>;
  }

  // --- Leer-Zustand ---
  if (profiles.length === 0) {
    return (
      <div className="rounded-md border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
        Keine abc-Profile gefunden.
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-muted-foreground">
          {data.warning ? (
            <span className="text-amber-600 dark:text-amber-400">
              {data.warning}
            </span>
          ) : (
            <>
              {writableProfiles.length} von {profiles.length} Profilen änderbar.
              Nur das Modell wird gespeichert — Provider, Secrets und weitere
              Einstellungen bleiben unberührt.
            </>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => void reload()}
            disabled={saving}
          >
            <RefreshCwIcon />
            Neu laden
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={resetLocal}
            disabled={dirtyCount === 0 || saving}
          >
            <RotateCcwIcon />
            Verwerfen
          </Button>
          <Button
            size="sm"
            onClick={() => void handleSave()}
            disabled={dirtyCount === 0 || saving}
          >
            <SaveIcon />
            Speichern
            {dirtyCount > 0 ? ` (${dirtyCount})` : ""}
          </Button>
        </div>
      </div>

      <ul className="grid gap-2">
        {profiles.map((p) => (
          <ProfileRow
            key={p.profile}
            profile={p}
            models={models}
            draft={drafts[p.profile]}
            disabled={saving}
            onSelect={(model) => setDraft(p.profile, model)}
          />
        ))}
      </ul>
    </div>
  );
}

function ProfileRow({
  profile,
  models,
  draft,
  disabled,
  onSelect,
}: {
  profile: HermesProfileModel;
  models: string[];
  draft: Draft | undefined;
  disabled: boolean;
  onSelect: (model: string) => void;
}) {
  const selected = draft?.model ?? null;
  // Aktueller Wert nicht mehr in der verfügbaren Liste → als nicht verfügbar markieren.
  const selectedAvailable =
    selected !== null && (models.includes(selected) || profile.error !== null);

  if (profile.error !== null) {
    return (
      <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{roleLabel(profile.profile)}</span>
            <Badge variant="outline" className="font-mono text-[11px]">
              {profile.profile}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
            {profile.error}
          </p>
        </div>
        <Badge variant="destructive">nicht verfügbar</Badge>
      </li>
    );
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{roleLabel(profile.profile)}</span>
          <Badge variant="outline" className="font-mono text-[11px]">
            {profile.profile}
          </Badge>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Aktuell:{" "}
          <span className="font-mono">{profile.current_model ?? "—"}</span>
          {profile.provider ? (
            <span className="ml-1">· {profile.provider}</span>
          ) : null}
          {selected !== null && selected !== profile.current_model ? (
            <span className="ml-2 text-emerald-600 dark:text-emerald-400">
              geändert
            </span>
          ) : null}
        </p>
      </div>

      <div className="flex items-center gap-2">
        {!selectedAvailable && selected ? (
          <Badge variant="outline" className="font-mono text-[11px]">
            {selected} (nicht verfügbar)
          </Badge>
        ) : null}
        <div className="grid gap-1.5">
          <Label htmlFor={`hpm-${profile.profile}`} className="sr-only">
            Modell für {roleLabel(profile.profile)}
          </Label>
          <Select
            value={selected ?? undefined}
            onValueChange={(v) => v && onSelect(v)}
          >
            <SelectTrigger
              id={`hpm-${profile.profile}`}
              size="sm"
              aria-label={`Modell für ${roleLabel(profile.profile)}`}
              className="w-56"
            >
              <SelectValue placeholder="Modell wählen" />
            </SelectTrigger>
            <SelectContent>
              {selectedAvailable && selected ? (
                <SelectItem value={selected}>{selected}</SelectItem>
              ) : null}
              {models.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
              {models.length === 0 ? (
                <SelectItem value="__none__" disabled>
                  Keine Modelle verfügbar
                </SelectItem>
              ) : null}
            </SelectContent>
          </Select>
        </div>
        {draft?.dirty ? (
          <span className="text-[11px] text-amber-600 dark:text-amber-400">*</span>
        ) : null}
      </div>
    </li>
  );
}
