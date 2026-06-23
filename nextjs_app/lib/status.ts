// Verbindliches Mapping Status → Ampel → Kanban-Spalte (siehe PROJ-3 Tech-Design).

import type { Session, SessionStatus } from "./types";

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
