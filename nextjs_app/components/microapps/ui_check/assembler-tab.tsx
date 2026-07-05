"use client";

// PROJ-21 (BUG-3 Fix): Portfolio-Assembler-Tab. Baut aus Branding-Profil ×
// Industrie × Sektionsplan einen POST /ui-check/assemble-Request. Keine eigene
// Assembler-/Registry-Logik — nur Auswahl, clientseitige Vorprüfung und Start.
//
// Vertrag (backend/app/schemas/ui_check.py UiCheckAssembleRequest): `sections`
// ist der VOLLSTÄNDIGE Rollenplan (auch ausgeschlossene Rollen bleiben drin),
// `overrides` markiert nur die Rollen, die vom Default "auto" abweichen
// (block/generate/exclude). Der Backend-Selector kanonisiert Section-Typen
// über Aliase (scripts/registry-select.mjs); die Alias-Liste unten ist eine
// bewusst unvollständige Teilmenge nur für die elf Sektionsrollen aus der
// PROJ-21-Spec — sie dient ausschließlich der clientseitigen Vorwarnung, die
// serverseitige 409-Antwort bleibt die Wahrheit.

import { useMemo, useState } from "react";
import { AlertTriangleIcon, CheckCircle2Icon, PuzzleIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import type {
  UiCheckAssembleOutcome,
  UiCheckAssembleRequest,
  UiCheckAssembleSectionOverride,
  UiCheckRegistryItem,
  UiCheckSectionOverrideDecision,
} from "@/lib/types";
import { isGalleryItem, useUiCheckBrandingProfiles, useUiCheckRegistry } from "./registry-data";

interface SectionRole {
  id: string;
  label: string;
  sectionMatches: string[];
}

const SECTION_ROLES: SectionRole[] = [
  { id: "nav", label: "Navigation", sectionMatches: ["nav"] },
  { id: "hero", label: "Hero", sectionMatches: ["hero"] },
  { id: "trust", label: "Trust / Vertrauen", sectionMatches: ["trust"] },
  { id: "features", label: "Features / Leistungen", sectionMatches: ["services", "features"] },
  { id: "process", label: "Prozess / Ablauf", sectionMatches: ["process", "steps"] },
  { id: "pricing", label: "Preise", sectionMatches: ["pricing"] },
  {
    id: "social-proof",
    label: "Social Proof / Testimonials",
    sectionMatches: ["social-proof", "testimonials"],
  },
  { id: "faq", label: "FAQ", sectionMatches: ["faq"] },
  { id: "cta", label: "CTA / Kontakt", sectionMatches: ["cta", "contact"] },
  { id: "footer", label: "Footer", sectionMatches: ["footer"] },
];

const MODE_LABEL: Record<UiCheckSectionOverrideDecision, string> = {
  auto: "Auto",
  block: "Konkreter Block",
  generate: "Generieren",
  exclude: "Ausschließen",
};

interface SectionPlanEntry {
  mode: UiCheckSectionOverrideDecision;
  blockName: string | null;
}

function initialPlan(): Record<string, SectionPlanEntry> {
  const plan: Record<string, SectionPlanEntry> = {};
  for (const role of SECTION_ROLES) plan[role.id] = { mode: "auto", blockName: null };
  return plan;
}

function candidatesForRole(role: SectionRole, items: UiCheckRegistryItem[]): UiCheckRegistryItem[] {
  return items.filter((item) => isGalleryItem(item) && item.section && role.sectionMatches.includes(item.section));
}

function matchesIndustry(item: UiCheckRegistryItem, industry: string): boolean {
  if (!industry.trim()) return true;
  return item.industry.some((tag) => industry.includes(tag) || tag.includes(industry));
}

export function AssemblerTab({
  onAssemble,
}: {
  onAssemble: (payload: UiCheckAssembleRequest) => Promise<UiCheckAssembleOutcome>;
}) {
  const { profiles, loading: profilesLoading, error: profilesError } = useUiCheckBrandingProfiles();
  const { items: registryItems, error: registryError } = useUiCheckRegistry();

  const [brandingSlug, setBrandingSlug] = useState<string | null>(null);
  const [industry, setIndustry] = useState("");
  const [prompt, setPrompt] = useState("");
  const [registryOnly, setRegistryOnly] = useState(false);
  const [plan, setPlan] = useState<Record<string, SectionPlanEntry>>(() => initialPlan());
  const [submitting, setSubmitting] = useState(false);
  const [lastConflict, setLastConflict] = useState<{
    message: string;
    missingSections?: string[];
    missingProfileParts?: string[];
  } | null>(null);

  const selectedProfile = profiles.find((p) => p.slug === brandingSlug) ?? null;

  function setRoleMode(roleId: string, mode: UiCheckSectionOverrideDecision) {
    setPlan((prev) => ({
      ...prev,
      [roleId]: { mode, blockName: mode === "block" ? (prev[roleId]?.blockName ?? null) : null },
    }));
  }

  function setRoleBlock(roleId: string, blockName: string) {
    setPlan((prev) => ({ ...prev, [roleId]: { mode: "block", blockName } }));
  }

  const roleCandidates = useMemo(() => {
    const map = new Map<string, UiCheckRegistryItem[]>();
    for (const role of SECTION_ROLES) {
      const candidates = candidatesForRole(role, registryItems).filter((item) =>
        matchesIndustry(item, industry),
      );
      map.set(role.id, candidates);
    }
    return map;
  }, [registryItems, industry]);

  const blockingIssues: string[] = [];
  const infoIssues: string[] = [];

  if (!brandingSlug) {
    blockingIssues.push("Kein Branding-Profil ausgewählt.");
  } else if (selectedProfile) {
    if (!selectedProfile.complete) {
      const parts = selectedProfile.missing.length > 0 ? selectedProfile.missing.join(", ") : "Tokens/Theme";
      blockingIssues.push(
        `Branding-Profil "${selectedProfile.name ?? selectedProfile.slug}" ist unvollständig — es fehlen: ${parts}.`,
      );
    }
    if (!selectedProfile.has_logo) {
      infoIssues.push(`Logo fehlt bei "${selectedProfile.name ?? selectedProfile.slug}" (optional je Contract).`);
    }
  }

  if (!industry.trim()) {
    blockingIssues.push("Kein Industrie-Tag angegeben.");
  }

  const missingRegistryRoles: string[] = [];
  if (registryOnly) {
    for (const role of SECTION_ROLES) {
      const entry = plan[role.id];
      if (entry.mode === "generate" || entry.mode === "exclude") continue;
      const candidates = roleCandidates.get(role.id) ?? [];
      if (candidates.length === 0) missingRegistryRoles.push(role.label);
    }
    if (missingRegistryRoles.length > 0) {
      blockingIssues.push(
        `"Nur existierende Komponenten" ist aktiv, aber es gibt keine passenden Blocks für: ${missingRegistryRoles.join(", ")}.`,
      );
    }
  }

  for (const role of SECTION_ROLES) {
    const entry = plan[role.id];
    if (entry.mode === "block" && !entry.blockName) {
      blockingIssues.push(`Für "${role.label}" ist der Modus "Konkreter Block" gewählt, aber kein Block ausgewählt.`);
    }
  }

  const allExcluded = SECTION_ROLES.every((role) => plan[role.id].mode === "exclude");
  if (allExcluded) {
    blockingIssues.push("Alle Sektionen sind ausgeschlossen — der Sektionsplan wäre leer.");
  }

  const generatedFallbackRoles = SECTION_ROLES.filter((role) => {
    const entry = plan[role.id];
    if (entry.mode !== "auto") return false;
    return (roleCandidates.get(role.id) ?? []).length === 0;
  });

  async function handleStart() {
    if (submitting || blockingIssues.length > 0) return;
    setSubmitting(true);
    setLastConflict(null);
    try {
      const overrides: UiCheckAssembleSectionOverride[] = SECTION_ROLES.filter(
        (role) => plan[role.id].mode !== "auto",
      ).map((role) => ({
        section: role.id,
        decision: plan[role.id].mode,
        block: plan[role.id].mode === "block" ? (plan[role.id].blockName ?? undefined) : undefined,
      }));
      const outcome = await onAssemble({
        branding: brandingSlug as string,
        industry: industry.trim(),
        sections: SECTION_ROLES.map((role) => role.id),
        registry_only: registryOnly,
        overrides,
        prompt: prompt.trim() || undefined,
      });
      if (!outcome.ok) {
        setLastConflict({
          message: outcome.conflict.message,
          missingSections: outcome.conflict.missing_sections,
          missingProfileParts: outcome.conflict.missing_profile_parts,
        });
        toast.error(outcome.conflict.message);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Assembler-Start fehlgeschlagen");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Briefing</CardTitle>
            <CardDescription>Branding-Profil, Industrie und optionales Kunden-Briefing.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Branding-Profil</Label>
                <Select value={brandingSlug ?? undefined} onValueChange={(v) => v && setBrandingSlug(v)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={profilesLoading ? "Lädt…" : "Profil wählen"} />
                  </SelectTrigger>
                  <SelectContent>
                    {profiles.map((p) => (
                      <SelectItem key={p.slug} value={p.slug}>
                        {p.name ?? p.slug}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {profilesError && (
                  <p className="text-xs text-amber-600 dark:text-amber-400">{profilesError}</p>
                )}
                {selectedProfile && selectedProfile.colors.length > 0 && (
                  <div className="flex gap-1 pt-1">
                    {selectedProfile.colors.slice(0, 8).map((c) => (
                      <div
                        key={c}
                        className="size-4 rounded-full border border-border"
                        style={{ backgroundColor: c }}
                        title={c}
                      />
                    ))}
                  </div>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="assemble-industry">Industrie-Tag</Label>
                <Input
                  id="assemble-industry"
                  placeholder="z. B. saas, legal, agency"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="assemble-prompt">Prompt / Briefing</Label>
              <Textarea
                id="assemble-prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Kurzes Kunden-Briefing, z. B. Zielgruppe, Tonalität, Schwerpunkt."
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={registryOnly}
                onChange={(e) => setRegistryOnly(e.target.checked)}
                className="size-4"
              />
              Nur existierende Komponenten (registry-only, kein Generierungs-Fallback)
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sektionsplan</CardTitle>
            <CardDescription>
              Je Sektion: Auto (Registry mit sichtbarem Fallback), konkreter Block, Generieren oder
              Ausschließen.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {registryError && (
              <p className="text-xs text-amber-600 dark:text-amber-400">{registryError}</p>
            )}
            {SECTION_ROLES.map((role) => {
              const entry = plan[role.id];
              const candidates = roleCandidates.get(role.id) ?? [];
              const isFallback = generatedFallbackRoles.some((r) => r.id === role.id);
              return (
                <div
                  key={role.id}
                  className="grid gap-2 rounded-lg border border-border p-3 sm:grid-cols-[minmax(140px,1fr)_160px_minmax(160px,1fr)]"
                >
                  <div className="flex items-center gap-2 text-sm font-medium">
                    {role.label}
                    {isFallback && (
                      <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-500">
                        Generierung
                      </Badge>
                    )}
                  </div>
                  <Select
                    value={entry.mode}
                    onValueChange={(v) => v && setRoleMode(role.id, v as UiCheckSectionOverrideDecision)}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(MODE_LABEL) as UiCheckSectionOverrideDecision[]).map((m) => (
                        <SelectItem key={m} value={m}>
                          {MODE_LABEL[m]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {entry.mode === "block" ? (
                    <Select
                      value={entry.blockName ?? undefined}
                      onValueChange={(v) => v && setRoleBlock(role.id, v)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue
                          placeholder={candidates.length === 0 ? "Keine Blocks passend" : "Block wählen"}
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {candidates.map((c) => (
                          <SelectItem key={c.name} value={c.name}>
                            {c.title ?? c.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div className="self-center text-xs text-muted-foreground">
                      {candidates.length} passende Blocks in der Registry
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PuzzleIcon className="size-4" />
              Validierung
            </CardTitle>
            <CardDescription>Blockiert den Start, bis alle Punkte erfüllt sind.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {blockingIssues.length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-emerald-500">
                <CheckCircle2Icon className="size-4" />
                Start ist möglich.
              </div>
            ) : (
              blockingIssues.map((issue) => (
                <div key={issue} className="flex items-start gap-2 text-sm text-red-500">
                  <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" />
                  <span>{issue}</span>
                </div>
              ))
            )}
            {infoIssues.map((issue) => (
              <div key={issue} className="flex items-start gap-2 text-sm text-muted-foreground">
                <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" />
                <span>{issue}</span>
              </div>
            ))}
            {lastConflict && (
              <div className="mt-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-500">
                <div className="font-medium">Backend meldet einen Konflikt</div>
                <div className="mt-1">{lastConflict.message}</div>
                {lastConflict.missingSections && lastConflict.missingSections.length > 0 && (
                  <div className="mt-1">
                    Fehlende Sektionen: {lastConflict.missingSections.join(", ")}
                  </div>
                )}
                {lastConflict.missingProfileParts && lastConflict.missingProfileParts.length > 0 && (
                  <div className="mt-1">
                    Fehlende Profilteile: {lastConflict.missingProfileParts.join(", ")}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Assembler starten</CardTitle>
            <CardDescription>
              Erzeugt einen synthetischen Run vom Typ „assemble&quot; und führt anschließend zum
              Mockup-Tab.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              type="button"
              className="w-full"
              onClick={handleStart}
              disabled={submitting || blockingIssues.length > 0}
            >
              <PuzzleIcon className="size-3.5" />
              Portfolio-Assembler starten
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
