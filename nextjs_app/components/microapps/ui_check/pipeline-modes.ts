// PROJ-21: Fachliches Modusmodell für das Dashboard. Spiegelt die Skill-Commands
// aus docs/pipeline.md (UI-Check-Projekt) — kein neuer Workflow, nur eine
// verständliche Übersetzung der bestehenden Commands in Auswahlfelder.

import type { UiCheckRunDetail } from "@/lib/types";

export type PipelineModeId =
  | "complete"
  | "audit_only"
  | "redesign"
  | "images"
  | "mockup_export"
  | "assembler"
  | "recycle";

export interface PipelineModeDef {
  id: PipelineModeId;
  label: string;
  description: string;
  /** Modus braucht eine URL-Eingabe (Neuer Lauf). */
  requiresUrl: boolean;
  /** Modus wirkt auf einen bestehenden, ausgewählten Lauf. */
  requiresRun: boolean;
  /** Springt nur zu einem anderen Tab, statt selbst einen Lauf zu starten. */
  jumpsToTab?: "assembler";
  commandLines: string[];
}

export const PIPELINE_MODES: PipelineModeDef[] = [
  {
    id: "complete",
    label: "Komplette Pipeline",
    description: "Kompletter Lauf von der URL bis zur teilbaren mockup.html.",
    requiresUrl: true,
    requiresRun: false,
    commandLines: [
      "/ui-check <url>",
      "/ui-redesign <run-dir>",
      "/ui-images-fill <run-dir>",
      "/ui-mockup-export <run-dir>",
      "# äquivalent zum Shortcut: /ui-pipeline <url>",
    ],
  },
  {
    id: "audit_only",
    label: "Audit-only",
    description: "Nur Stufe-1-Audit: Screenshots, Lighthouse, Branding, Design-Score.",
    requiresUrl: true,
    requiresRun: false,
    commandLines: ["/ui-check <url>"],
  },
  {
    id: "redesign",
    label: "Redesign nachziehen",
    description: "Safe- und Bold-Variante für einen bestehenden Audit-Lauf erzeugen.",
    requiresUrl: false,
    requiresRun: true,
    commandLines: ["/ui-redesign <run-dir>"],
  },
  {
    id: "images",
    label: "Bilder füllen",
    description: "Bild-Slots eines Redesign-Laufs befüllen (Stock → Website → KI-Generierung).",
    requiresUrl: false,
    requiresRun: true,
    commandLines: ["/ui-images-fill <run-dir>"],
  },
  {
    id: "mockup_export",
    label: "Mockup exportieren",
    description: "Self-contained mockup.html aus dem Redesign-Ergebnis bauen.",
    requiresUrl: false,
    requiresRun: true,
    commandLines: ["/ui-mockup-export <run-dir>"],
  },
  {
    id: "assembler",
    label: "Portfolio-Assembler",
    description: "Neue Website aus Branding-Profil × Registry-Komponenten bauen.",
    requiresUrl: false,
    requiresRun: false,
    jumpsToTab: "assembler",
    commandLines: [
      '/ui-assemble --branding <slug> --industry <tag> --sections <liste> --prompt "<Briefing>"',
    ],
  },
  {
    id: "recycle",
    label: "Registry-Recycling",
    description: "Portfoliowürdige Sektionen eines Redesign-Laufs in die Registry übernehmen.",
    requiresUrl: false,
    requiresRun: true,
    commandLines: ["/ui-recycle <run-dir>"],
  },
];

export interface PrerequisiteItem {
  label: string;
  satisfied: boolean;
}

export function hasRedesignArtifacts(detail: UiCheckRunDetail | null): boolean {
  if (!detail) return false;
  if (detail.mockup_status) {
    return Boolean(detail.mockup_status.safe_ready || detail.mockup_status.bold_ready);
  }
  return typeof detail.redesign_score === "number";
}

/** true, sobald mindestens ein Bild-Slot bekannt ist und keiner davon mehr ein
 *  Platzhalter ist. Ohne bekannte Slots (images-fill.json fehlt noch) gilt die
 *  Befüllung defensiv als nicht abgeschlossen. */
export function hasImagesFilled(detail: UiCheckRunDetail | null): boolean {
  const images = detail?.mockup_status?.images;
  if (!images) return false;
  return images.total_slots > 0 && images.placeholder_slots === 0;
}

export function hasMockupExisting(detail: UiCheckRunDetail | null): boolean {
  return Boolean(detail?.mockup_status?.exported ?? detail?.artifacts?.mockup);
}

export function computePrerequisites(
  modeId: PipelineModeId,
  detail: UiCheckRunDetail | null,
  url: string,
): PrerequisiteItem[] {
  switch (modeId) {
    case "complete":
    case "audit_only":
      return [{ label: "Website-URL ist angegeben", satisfied: url.trim().length > 0 }];
    case "redesign":
      return [
        { label: "Ein Lauf ist ausgewählt", satisfied: Boolean(detail?.run_id) },
        {
          label: "Audit für den Lauf ist abgeschlossen (scores.json vorhanden)",
          satisfied: Boolean(detail?.run_id) && typeof detail?.score_total === "number",
        },
      ];
    case "images":
      return [
        { label: "Ein Lauf ist ausgewählt", satisfied: Boolean(detail?.run_id) },
        {
          label: "Redesign-Ordner mit Safe/Bold-Varianten ist vorhanden",
          satisfied: hasRedesignArtifacts(detail),
        },
      ];
    case "mockup_export":
      return [
        { label: "Ein Lauf ist ausgewählt", satisfied: Boolean(detail?.run_id) },
        {
          label: "Redesign-Ordner mit Safe/Bold-Varianten ist vorhanden",
          satisfied: hasRedesignArtifacts(detail),
        },
      ];
    case "recycle":
      return [
        { label: "Ein Lauf ist ausgewählt", satisfied: Boolean(detail?.run_id) },
        {
          label: "Redesign-Ordner mit Safe/Bold-Varianten ist vorhanden",
          satisfied: hasRedesignArtifacts(detail),
        },
      ];
    case "assembler":
      return [];
    default:
      return [];
  }
}
