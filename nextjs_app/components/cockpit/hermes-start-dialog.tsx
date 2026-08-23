"use client";

// „Neu Hermes"-Dialog (PROJ-85/87): startet eine Hermes-Chat-Session fest im
// Bypass-Modus mit aktiviertem Token Savings (beides serverseitige Festwerte,
// hier weder sichtbar noch änderbar). Felder: Titel (optional), Projekt-Pfad
// (Pflicht), Profil (Pflicht, „default" vorausgewählt, PROJ-87) und Modell
// (Pflicht, Hermes-kompatibel aus GET /sessions/hermes/options; beim
// Profilwechsel auf dessen Standardmodell vorbelegt, danach frei änderbar).
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
import {
  ApiError,
  getHermesOptions,
  getHermesStartProfiles,
  startHermesSession,
} from "@/lib/api";
import { projectName } from "@/lib/status";
import type {
  HermesModelOption,
  HermesOptions,
  HermesProfileOption,
  HermesProfiles,
} from "@/lib/types";
import { useSessions } from "./sessions-provider";

const DEFAULT_PROFILE = "default";

export function HermesStartDialog({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { refresh } = useSessions();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Formularfelder.
  const [title, setTitle] = useState("");
  const [projectPath, setProjectPath] = useState("/home/dev/projects/");

  // Profil-Liste aus dem Backend (GET /sessions/hermes/profiles).
  const [profiles, setProfiles] = useState<HermesProfiles>({
    profiles: [],
    warning: null,
  });
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profilesError, setProfilesError] = useState<string | null>(null);
  const [profile, setProfile] = useState<string>(DEFAULT_PROFILE);

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

  // „default" ist serverseitig immer enthalten; falls doch nicht (Defensive),
  // ein synthetischer Eintrag einhängen, damit die Auswahl nie leer ist.
  const profileItems: HermesProfileOption[] = profiles.profiles.some(
    (p) => p.profile === DEFAULT_PROFILE,
  )
    ? profiles.profiles
    : [
        {
          profile: DEFAULT_PROFILE,
          label: "Standard (default)",
          engine: null,
          model: null,
        },
        ...profiles.profiles,
      ];

  const selectedProfile =
    profileItems.find((p) => p.profile === profile) ?? null;

  // Modell-Optionen: auf die Engine des gewählten Profils gefiltert (falls
  // bekannt), damit ein manuell gewähltes Modell stets zur Profil-Engine passt
  // (PROJ-87 Invariante G). Bei unaufgelöster Profil-Engine bleibt die volle
  // Liste wählbar.
  const modelOptions: HermesModelOption[] = selectedProfile?.engine
    ? options.models.filter((m) => m.engine === selectedProfile.engine)
    : options.models;

  const suggestedName = projectName(projectPath.trim()) || "jupiter";

  const selectedOption =
    modelOptions.find((m) => m.model === model) ?? null;

  // Profil startfähig? Defekte Profile (error != null) oder nicht mehr
  // erkannte Profile sind nicht wählbar.
  const profileValid =
    selectedProfile !== null && selectedProfile.error === null;

  const profilesReady = profileItems.length > 0 && profilesError === null;

  const valid =
    projectPath.trim().length > 0 &&
    profilesReady &&
    profileValid &&
    modelOptions.length > 0 &&
    selectedOption !== null;

  // Setzt das Modell auf das Standardmodell des genannten Profils (sofern
  // auflösbar), sonst zurück auf „keine Vorauswahl". Wird beim Profilwechsel
  // sowie beim erstmaligen Laden der Optionen aufgerufen.
  function applyProfileDefault(profileName: string, opts: { force: boolean }) {
    const p = profileItems.find((x) => x.profile === profileName);
    if (!opts.force && model) return; // manuelle Wahl nicht überschreiben
    if (p?.model && modelOptions.some((m) => m.model === p.model)) {
      setModel(p.model);
    } else if (p?.model) {
      // Standardmodell des Profils ist in der aktuellen Liste nicht (mehr) —
      // Vorauswahl zurücksetzen, der Nutzer wählt manuell.
      setModel("");
    } else {
      setModel("");
    }
  }

  // Optionen laden, sobald der Dialog geöffnet wird (nicht-blockierend).
  useEffect(() => {
    if (!open) return;
    const ctrlOptions = new AbortController();
    const ctrlProfiles = new AbortController();
    setOptionsLoading(true);
    setProfilesLoading(true);

    getHermesOptions(ctrlOptions.signal)
      .then((value) => {
        if (ctrlOptions.signal.aborted) return;
        setOptions(value);
        setOptionsError(null);
        // Modell vorbelegen: wenn noch nichts gewählt, Standardmodell des
        // aktuell gewählten Profils („default") übernehmen, sonst erstes.
        setModel((current) => {
          if (current && value.models.some((m) => m.model === current)) {
            return current;
          }
          const p = profileItems.find((x) => x.profile === profile);
          if (p?.model && value.models.some((m) => m.model === p.model)) {
            return p.model;
          }
          return value.models[0]?.model ?? "";
        });
      })
      .catch((err) => {
        if (ctrlOptions.signal.aborted) return;
        setOptions({ models: [], warning: null });
        setOptionsError(
          err instanceof ApiError
            ? err.message
            : "Hermes-Modellliste konnte nicht geladen werden",
        );
      })
      .finally(() => {
        if (!ctrlOptions.signal.aborted) setOptionsLoading(false);
      });

    getHermesStartProfiles(ctrlProfiles.signal)
      .then((value) => {
        if (ctrlProfiles.signal.aborted) return;
        setProfiles(value);
        setProfilesError(null);
        // „default" vorauswählen, falls noch kein bekanntes Profil gewählt.
        setProfile((current) =>
          current === DEFAULT_PROFILE ||
          value.profiles.some((p) => p.profile === current)
            ? current
            : DEFAULT_PROFILE,
        );
      })
      .catch((err) => {
        if (ctrlProfiles.signal.aborted) return;
        setProfiles({ profiles: [], warning: null });
        setProfilesError(
          err instanceof ApiError
            ? err.message
            : "Hermes-Profile konnten nicht geladen werden",
        );
      })
      .finally(() => {
        if (!ctrlProfiles.signal.aborted) setProfilesLoading(false);
      });

    return () => {
      ctrlOptions.abort();
      ctrlProfiles.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function resetForm() {
    setTitle("");
    setProjectPath("/home/dev/projects/");
    setProfiles({ profiles: [], warning: null });
    setProfilesLoading(false);
    setProfilesError(null);
    setProfile(DEFAULT_PROFILE);
    setOptions({ models: [], warning: null });
    setOptionsLoading(false);
    setOptionsError(null);
    setModel("");
    setSubmitError(null);
  }

  function handleProfileChange(name: string | null) {
    if (!name) return;
    setProfile(name);
    // Beim Profilwechsel das Modell auf dessen Standardmodell vorbelegen
    // (PROJ-87): eine danach manuell getroffene Wahl bleibt für dieses Profil
    // erhalten, bis ein anderes Profil gewählt wird.
    applyProfileDefault(name, { force: true });
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
        profile,
        engine: selected?.engine ?? "",
        model,
      });
      toast.success("Hermes-Session gestartet");
      setOpen(false);
      resetForm();
      refresh();
      router.push(`/sessions/${session.session_id}`);
    } catch (err) {
      // Dialog bleibt offen — der Nutzer kann Pfad/Profil/Modell korrigieren.
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
              <Label htmlFor="hermes_profile">Profil (Pflicht)</Label>
              <Select
                value={profile}
                onValueChange={handleProfileChange}
                disabled={!profilesReady}
              >
                <SelectTrigger id="hermes_profile" className="w-full">
                  <SelectValue
                    placeholder={
                      profilesLoading
                        ? "Lade Profile…"
                        : profileItems.length === 0
                          ? "Keine Profile verfügbar"
                          : "Profil wählen"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {profileItems.map((p) => (
                    <SelectItem
                      key={p.profile}
                      value={p.profile}
                      disabled={p.error !== null}
                    >
                      {p.label}
                      {p.error ? " (nicht startfähig)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {profilesLoading && (
                <p className="text-xs text-muted-foreground">
                  Hermes-Profile werden geladen…
                </p>
              )}
              {profilesError && (
                <p className="text-xs text-red-400">{profilesError}</p>
              )}
              {!profilesLoading && !profilesError && selectedProfile?.error && (
                <p className="text-xs text-red-400">
                  Profil &bdquo;{selectedProfile.label}&ldquo; ist nicht startfähig:{" "}
                  {selectedProfile.error}
                </p>
              )}
              {!profilesLoading &&
                !profilesError &&
                profiles.warning &&
                !selectedProfile?.error && (
                  <p className="text-xs text-amber-500">{profiles.warning}</p>
                )}
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
