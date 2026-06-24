// Verbindliches Mapping Status → Ampel → Kanban-Spalte (siehe PROJ-3 Tech-Design).

import type { AbcPhase, Liveness, Session, SessionStatus } from "./types";

export type Ampel = "green" | "amber" | "orange" | "red" | "gray";

export interface StatusMeta {
  ampel: Ampel;
  label: string; // deutscher Klartext
}

export const STATUS_META: Record<SessionStatus, StatusMeta> = {
  starting: { ampel: "green", label: "Startet" },
  running: { ampel: "green", label: "Arbeitet" },
  waiting: { ampel: "amber", label: "Wartet auf dich" },
  awaiting_approval: { ampel: "orange", label: "Freigabe nötig" },
  done: { ampel: "gray", label: "Fertig" },
  error: { ampel: "red", label: "Fehler" },
};

export function statusMeta(status: SessionStatus): StatusMeta {
  return STATUS_META[status] ?? { ampel: "gray", label: status };
}

/**
 * Terminal = löschbar (PROJ-21): `done`, `error` und verwaiste Sessions (kommen
 * vom Backend i. d. R. als `error` an). Aktive Stati bleiben unlöschbar.
 * Der Server bleibt autoritativ — diese Hilfe steuert nur die UI-Sichtbarkeit.
 */
export function isTerminalStatus(status: SessionStatus): boolean {
  return status === "done" || status === "error";
}

/** Anzahl terminaler (= löschbarer) Sessions — für den „Aufräumen (N)"-Button. */
export function countTerminal(sessions: Session[]): number {
  return sessions.filter((s) => isTerminalStatus(s.status)).length;
}

// PROJ-27: Liveness (verifizierter Heartbeat) ---------------------------------

export interface LivenessMeta {
  label: string; // deutscher Klartext
  color: "emerald" | "amber" | "zinc";
  pulse: boolean; // pulsiert nur, wenn wirklich aktiv
}

export const LIVENESS_META: Record<Liveness, LivenessMeta> = {
  aktiv: { label: "Aktiv", color: "emerald", pulse: true },
  hängt: { label: "Hängt", color: "amber", pulse: false },
  tot: { label: "Beendet", color: "zinc", pulse: false },
};

export function livenessMeta(liveness: Liveness): LivenessMeta {
  return LIVENESS_META[liveness] ?? LIVENESS_META.tot;
}

/** Reanimierungs-Kandidat (Reaktivieren-Knopf zeigen): nur „hängt"/„tot". */
export function canReanimate(liveness: Liveness | null | undefined): boolean {
  return liveness === "hängt" || liveness === "tot";
}

// Kanban-Spalten (AC: Arbeitet / Wartet auf dich / Review/Approval / Fertig).
export type ColumnKey = "arbeitet" | "wartet" | "review" | "fertig";

export interface ColumnDef {
  key: ColumnKey;
  title: string;
  /** „Wartet auf dich" ist das stärkste Signal. */
  emphasis?: boolean;
}

export const COLUMNS: ColumnDef[] = [
  { key: "arbeitet", title: "Arbeitet" },
  { key: "wartet", title: "Wartet auf dich", emphasis: true },
  { key: "review", title: "Review/Approval" },
  { key: "fertig", title: "Fertig" },
];

/**
 * Spalte je Status. „Review/Approval" trägt seit PROJ-4 die Sessions mit offener
 * Decision Card (`awaiting_approval`). Fehler-Sessions landen in „Wartet auf dich"
 * (Handlungsbedarf), rot markiert.
 */
export function columnFor(status: SessionStatus): ColumnKey {
  switch (status) {
    case "starting":
    case "running":
      return "arbeitet";
    case "waiting":
    case "error":
      return "wartet";
    case "awaiting_approval":
      return "review";
    case "done":
      return "fertig";
  }
}

/** Mission-Control-Zähler — client-seitig aus der Liste. */
export interface StatusCounts {
  aktiv: number;
  wartet: number;
  freigabe: number;
  fehler: number;
  fertig: number;
}

export function countStatuses(sessions: Session[]): StatusCounts {
  const c: StatusCounts = { aktiv: 0, wartet: 0, freigabe: 0, fehler: 0, fertig: 0 };
  for (const s of sessions) {
    if (s.status === "starting" || s.status === "running") c.aktiv++;
    else if (s.status === "waiting") c.wartet++;
    else if (s.status === "awaiting_approval") c.freigabe++;
    else if (s.status === "error") c.fehler++;
    else if (s.status === "done") c.fertig++;
  }
  return c;
}

/** Sortier-Rang für die Rail: Freigabe/Wartet/Fehler zuerst, dann nach Aktivität. */
export function railRank(status: SessionStatus): number {
  switch (status) {
    case "awaiting_approval":
      return 0; // braucht dich JETZT (blockiert mitten im Turn)
    case "waiting":
      return 1;
    case "error":
      return 2;
    case "running":
    case "starting":
      return 3;
    case "done":
      return 4;
  }
}

// ABC-Workflow-Gantt (PROJ-8) -------------------------------------------------

export interface AbcPhaseMeta {
  key: AbcPhase;
  label: string; // volle Spaltenüberschrift
  short: string; // Kürzel für schmale Spalten (mobile/horizontal scroll)
}

/**
 * Kanonische ABC-Phasen in fester Reihenfolge — spiegelt backend
 * `app/engine/abc_phases.py` (ABC_PHASES). EINE Quelle der Wahrheit fürs Frontend.
 */
export const ABC_PHASES: AbcPhaseMeta[] = [
  { key: "brainstorm", label: "Brainstorm", short: "BS" },
  { key: "requirements", label: "Requirements", short: "Req" },
  { key: "architecture", label: "Architecture", short: "Arch" },
  { key: "frontend", label: "Frontend", short: "FE" },
  { key: "backend", label: "Backend", short: "BE" },
  { key: "qa", label: "QA", short: "QA" },
  { key: "deploy", label: "Deploy", short: "Dep" },
  { key: "document", label: "Document", short: "Doc" },
];

/** Position einer Phase in der kanonischen Reihenfolge; -1 für null/unbekannt. */
export function phaseIndex(phase: string | null | undefined): number {
  if (!phase) return -1;
  return ABC_PHASES.findIndex((p) => p.key === phase);
}

// Hilfen ----------------------------------------------------------------------

/** Kurzlabel fürs Modell — auch wenn das Backend die volle ID auflöst
 *  (z. B. „claude-haiku-4-5-20251001" → „Haiku"). */
export function modelLabel(model: string): string {
  const m = model.toLowerCase();
  if (m.includes("haiku")) return "Haiku";
  if (m.includes("sonnet")) return "Sonnet";
  if (m.includes("opus")) return "Opus";
  return model;
}

/** Füllstand-Label: „unbekannt", solange der Treiber keine Token-Daten lieferte (PROJ-5). */
export function contextLabel(pct: number, known: boolean): string {
  return known ? `${Math.round(pct)}%` : "unbekannt";
}

/** PROJ-18: Nur der Claude-Treiber liefert echte Kosten; andere Engines (OpenAI/CLI)
 *  haben keine Kosten-Extraktion → die Anzeige degradiert sauber zu „n/v". */
export function engineShowsCost(engine: string): boolean {
  return engine === "claude";
}

/** Kosten-Label der Kachel: „$x.xxx" für Claude, sonst „n/v" (engine-agnostische Degradation). */
export function costLabel(engine: string, totalCostUsd: number): string {
  return engineShowsCost(engine) ? `$${totalCostUsd.toFixed(3)}` : "n/v";
}

/** Farbklasse des Kontext-Balkens: rot ab Schwelle, amber kurz davor, sonst grün (PROJ-5). */
export function gaugeColor(pct: number, threshold: number): string {
  if (pct >= threshold) return "bg-red-500";
  if (pct >= threshold * 0.7) return "bg-amber-400";
  return "bg-emerald-500";
}

export function projectName(path: string): string {
  const parts = path.replace(/\/+$/, "").split("/");
  return parts[parts.length - 1] || path;
}

/** Kompakte Laufzeit/Relativzeit, z. B. „4m", „2h", „gerade eben". */
export function formatDuration(fromIso: string, nowMs: number): string {
  const start = Date.parse(fromIso);
  if (Number.isNaN(start)) return "—";
  const secs = Math.max(0, Math.round((nowMs - start) / 1000));
  if (secs < 5) return "gerade eben";
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ${mins % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}
