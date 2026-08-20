"use client";

// PROJ-83 (Rework): Modellwahl je erkanntem abc-Hermes-Profil (Präfix `jupiter-`)
// als gekoppelte Engine→Modell-Auswahl. Engine- und Modellbestand stammen
// ausschließlich aus `GET /engines` (PROJ-51/PROJ-18) — keine eigene Liste.
// Speichern übersetzt Engine+Modell gemäß Tech-Design-Nachtrag in
// `model.default`/`model.provider` (serverseitig in `hermes_profiles.py`).
// Secrets/Credentials werden weder gelesen noch angezeigt — nur Engine/Modell.

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
import { ApiError, getEngines, getHermesProfiles, setHermesProfileModels } from "@/lib/api";
import type {
  EngineRead,
  HermesEngineKey,
  HermesProfileModel,
  HermesProfileModelPatch,
  HermesProfilesRead,
  HermesProfileSaveResult,
} from "@/lib/types";

/** Nur diese Engine-Keys sind für Hermes erlaubt (Tech-Design-Nachtrag). */
const ALLOWED_ENGINES = new Set<HermesEngineKey>(["claude", "codex", "opencode"]);

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

/** Lokal editierbarer Stand eines Profils: gewählte Engine + Modell + Unsaved-Flag. */
interface Draft {
  engine: HermesEngineKey | null;
  model: string | null;
  dirty: boolean;
}

// --- Loading / Empty / Error / Success: Zustände explizit ------------------

export function HermesProfileModelsControl() {
  const [data, setData] = useState<HermesProfilesRead | null>(null);
  const [engines, setEnginesState] = useState<EngineRead[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);

  // Steuerbare Hermes-Engines: kind=engine, verfügbar, erlaubter Key.
  const engineOptions = useMemo<EngineRead[]>(
    () =>
      engines.filter(
        (e) => e.kind === "engine" && e.available && e.key in ALLOWED_ENGINES,
      ),
    [engines],
  );
  const engineByKey = useMemo(() => {
    const m = new Map<string, EngineRead>();
    for (const e of engineOptions) m.set(e.key, e);
    return m;
  }, [engineOptions]);

  function modelsFor(engine: HermesEngineKey | null): string[] {
    if (!engine) return [];
    return engineByKey.get(engine)?.models ?? [];
  }

  function applyData(d: HermesProfilesRead) {
    setData(d);
    // Draft-Initialwert = aus der config.yaml rückübersetzte Engine/Modell-Kombination.
    const next: Record<string, Draft> = {};
    for (const p of d.profiles) {
      next[p.profile] = { engine: p.engine, model: p.model, dirty: false };
    }
    setDrafts(next);
    setLoadFailed(false);
  }

  async function reload() {
    setLoading(true);
    try {
      const [profiles, eng] = await Promise.all([
        getHermesProfiles(),
        getEngines().catch(() => null),
      ]);
      applyData(profiles);
      if (eng) setEnginesState(eng.engines);
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const ac = new AbortController();
    Promise.all([getHermesProfiles(ac.signal), getEngines(ac.signal).catch(() => null)])
      .then(([profiles, eng]) => {
        if (ac.signal.aborted) return;
        applyData(profiles);
        if (eng) setEnginesState(eng.engines);
      })
      .catch(() => {
        if (!ac.signal.aborted) setLoadFailed(true);
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, []);

  const profiles = useMemo(() => data?.profiles ?? [], [data]);
  const writableProfiles = useMemo(
    () => profiles.filter((p) => p.error === null),
    [profiles],
  );

  const dirtyDrafts = useMemo(
    () => Object.values(drafts).filter((d) => d.dirty),
    [drafts],
  );
  const dirtyCount = dirtyDrafts.length;
  // Unvollständige Änderung (Engine gewählt, aber noch kein Modell) → kein Speichern.
  const incomplete = dirtyDrafts.some((d) => !d.engine || !d.model);

  function setEngine(profile: string, engine: HermesEngineKey) {
    setDrafts((prev) => {
      const cur = prev[profile];
      if (!cur) return prev;
      // Engine-Wechsel verwirft eine bisherige, nicht mehr passende Modellauswahl.
      const engineChanged = cur.engine !== engine;
      return {
        ...prev,
        [profile]: { engine, model: engineChanged ? null : cur.model, dirty: true },
      };
    });
  }

  function setModel(profile: string, model: string) {
    setDrafts((prev) => {
      const cur = prev[profile];
      if (!cur) return prev;
      return { ...prev, [profile]: { ...cur, model, dirty: true } };
    });
  }

  function resetLocal() {
    if (!data) return;
    const next: Record<string, Draft> = {};
    for (const p of data.profiles) {
      next[p.profile] = { engine: p.engine, model: p.model, dirty: false };
    }
    setDrafts(next);
  }

  async function handleSave() {
    if (saving || dirtyCount === 0 || incomplete || !data) return;
    const payload: HermesProfileModelPatch[] = writableProfiles
      .filter((p) => drafts[p.profile]?.dirty)
      .map((p) => ({
        profile: p.profile,
        engine: drafts[p.profile].engine as HermesEngineKey,
        model: drafts[p.profile].model as string,
      }))
      .filter((e) => e.engine && e.model.length > 0);
    if (payload.length === 0) return;

    setSaving(true);
    try {
      const results: HermesProfileSaveResult[] = await setHermesProfileModels(payload);
      // Server-Antwort als neue Wahrheit übernehmen (kein lokaler Entwurf = gespeichert).
      const byProfile = new Map(results.map((r) => [r.profile, r]));
      const nextDrafts: Record<string, Draft> = { ...drafts };
      const failures: string[] = [];
      for (const p of data.profiles) {
        const res = byProfile.get(p.profile);
        if (!res) continue;
        if (res.ok && res.entry) {
          nextDrafts[p.profile] = {
            engine: res.entry.engine,
            model: res.entry.model,
            dirty: false,
          };
        } else {
          // Fehlgeschlagene Profile: letzten gültigen Stand behalten (dirty=false),
          // damit kein irreführender Erfolgszustand entsteht.
          nextDrafts[p.profile] = {
            engine: p.engine,
            model: p.model,
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
        toast.error(`Speichern fehlgeschlagen: ${failures[0] ?? "Unbekannter Fehler"}`);
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
            <span className="text-amber-600 dark:text-amber-400">{data.warning}</span>
          ) : (
            <>
              {writableProfiles.length} von {profiles.length} Profilen änderbar.
              Engine + Modell werden gespeichert — Provider, Secrets und weitere
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
            disabled={dirtyCount === 0 || incomplete || saving}
          >
            <SaveIcon />
            Speichern
            {dirtyCount > 0 ? ` (${dirtyCount})` : ""}
          </Button>
        </div>
      </div>

      {incomplete ? (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Bitte wähle für jedes geänderte Profil ein vollständiges Engine/Modell-Paar,
          bevor du speicherst.
        </p>
      ) : null}

      <ul className="grid gap-2">
        {profiles.map((p) => (
          <ProfileRow
            key={p.profile}
            profile={p}
            engineOptions={engineOptions}
            draft={drafts[p.profile]}
            disabled={saving}
            onSelectEngine={(engine) => setEngine(p.profile, engine)}
            onSelectModel={(model) => setModel(p.profile, model)}
          />
        ))}
      </ul>
    </div>
  );
}

function ProfileRow({
  profile,
  engineOptions,
  draft,
  disabled,
  onSelectEngine,
  onSelectModel,
}: {
  profile: HermesProfileModel;
  engineOptions: EngineRead[];
  draft: Draft | undefined;
  disabled: boolean;
  onSelectEngine: (engine: HermesEngineKey) => void;
  onSelectModel: (model: string) => void;
}) {
  const selectedEngine = draft?.engine ?? null;
  const selectedModel = draft?.model ?? null;
  const modelOptions = selectedEngine ? (engineOptions.find((e) => e.key === selectedEngine)?.models ?? []) : [];

  // Aktueller Bestand nicht mehr verfügbar: Engine/Modell steht in keiner
  // steuerbaren Registry-Engine (außerhalb Jupiters gesetzt).
  const engineAvailable =
    selectedEngine !== null && engineOptions.some((e) => e.key === selectedEngine);
  const modelAvailable =
    selectedModel !== null &&
    (modelOptions.includes(selectedModel) || profile.error !== null);
  const unavailable =
    !engineAvailable || (selectedModel !== null && !modelOptions.includes(selectedModel));

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
          <span className="font-mono">{profile.model ?? "—"}</span>
          {profile.provider ? <span className="ml-1">· {profile.provider}</span> : null}
          {selectedEngine && selectedModel &&
          (selectedEngine !== profile.engine || selectedModel !== profile.model) ? (
            <span className="ml-2 text-emerald-600 dark:text-emerald-400">geändert</span>
          ) : null}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {unavailable && profile.model ? (
          <Badge variant="outline" className="font-mono text-[11px]">
            {profile.model} (nicht verfügbar)
          </Badge>
        ) : null}
        <div className="grid gap-1.5">
          <Label htmlFor={`hpm-engine-${profile.profile}`} className="sr-only">
            Engine für {roleLabel(profile.profile)}
          </Label>
          <Select
            value={selectedEngine ?? undefined}
            onValueChange={(v) => v && onSelectEngine(v as HermesEngineKey)}
          >
            <SelectTrigger
              id={`hpm-engine-${profile.profile}`}
              size="sm"
              aria-label={`Engine für ${roleLabel(profile.profile)}`}
              className="w-44"
            >
              <SelectValue placeholder="Engine wählen" />
            </SelectTrigger>
            <SelectContent>
              {selectedEngine && !engineAvailable ? (
                <SelectItem value={selectedEngine}>{selectedEngine} (nicht verfügbar)</SelectItem>
              ) : null}
              {engineOptions.map((e) => (
                <SelectItem key={e.key} value={e.key}>
                  {e.label || e.key}
                </SelectItem>
              ))}
              {engineOptions.length === 0 ? (
                <SelectItem value="__none__" disabled>
                  Keine Engines verfügbar
                </SelectItem>
              ) : null}
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor={`hpm-model-${profile.profile}`} className="sr-only">
            Modell für {roleLabel(profile.profile)}
          </Label>
          <Select
            value={selectedModel ?? undefined}
            onValueChange={(v) => v && onSelectModel(v)}
            disabled={!selectedEngine || !engineAvailable}
          >
            <SelectTrigger
              id={`hpm-model-${profile.profile}`}
              size="sm"
              aria-label={`Modell für ${roleLabel(profile.profile)}`}
              className="w-56"
            >
              <SelectValue placeholder={selectedEngine ? "Modell wählen" : "zuerst Engine"} />
            </SelectTrigger>
            <SelectContent>
              {selectedModel && !modelAvailable ? (
                <SelectItem value={selectedModel}>{selectedModel} (nicht verfügbar)</SelectItem>
              ) : null}
              {modelOptions.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
              {selectedEngine && modelOptions.length === 0 ? (
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
