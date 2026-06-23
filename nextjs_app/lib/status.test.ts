import { describe, expect, it } from "vitest";
import {
  columnFor,
  contextLabel,
  countStatuses,
  formatDuration,
  gaugeColor,
  modelLabel,
  projectName,
  railRank,
  statusMeta,
} from "./status";
import type { Session, SessionStatus } from "./types";

function session(overrides: Partial<Session> = {}): Session {
  return {
    session_id: "id",
    owner: "dev",
    project_path: "/home/dev/projects/jupiter",
    model: "haiku",
    permission_mode: "default",
    role: null,
    constitution_source: null,
    status: "running",
    created_at: "2026-06-22T10:00:00Z",
    last_activity: "2026-06-22T10:01:00Z",
    tokens_used: 0,
    context_fill_pct: 0,
    context_known: false,
    context_fill_threshold_pct: 85,
    threshold_warning: false,
    total_cost_usd: 0,
    num_turns: 0,
    error: null,
    rate_limit: null,
    parent_session_id: null,
    pending_decisions: [],
    ...overrides,
  };
}

const ALL: SessionStatus[] = [
  "starting",
  "running",
  "waiting",
  "awaiting_approval",
  "done",
  "error",
];

describe("statusMeta — Ampel-Mapping (AC: Ampel-Kacheln)", () => {
  it("startet/arbeitet → grün", () => {
    expect(statusMeta("starting").ampel).toBe("green");
    expect(statusMeta("running").ampel).toBe("green");
  });
  it("waiting → amber (stärkstes Signal)", () => {
    expect(statusMeta("waiting").ampel).toBe("amber");
    expect(statusMeta("waiting").label).toBe("Wartet auf dich");
  });
  it("awaiting_approval → orange (Freigabe nötig)", () => {
    expect(statusMeta("awaiting_approval").ampel).toBe("orange");
    expect(statusMeta("awaiting_approval").label).toBe("Freigabe nötig");
  });
  it("error → rot, done → grau", () => {
    expect(statusMeta("error").ampel).toBe("red");
    expect(statusMeta("done").ampel).toBe("gray");
  });
  it("liefert für jeden Status ein deutsches Label", () => {
    for (const s of ALL) expect(statusMeta(s).label.length).toBeGreaterThan(0);
  });
});

describe("columnFor — Kanban-Spalten (AC: 4 Spalten, Auto-Wandern)", () => {
  it("arbeitet: starting + running", () => {
    expect(columnFor("starting")).toBe("arbeitet");
    expect(columnFor("running")).toBe("arbeitet");
  });
  it("wartet: waiting UND error (Handlungsbedarf)", () => {
    expect(columnFor("waiting")).toBe("wartet");
    expect(columnFor("error")).toBe("wartet");
  });
  it("fertig: done", () => {
    expect(columnFor("done")).toBe("fertig");
  });
  it("review: awaiting_approval (PROJ-4 Decision Cards)", () => {
    expect(columnFor("awaiting_approval")).toBe("review");
  });
});

describe("countStatuses — Mission-Control-Zähler (AC: globaler Status)", () => {
  it("zählt aktiv/wartet/freigabe/fehler/fertig korrekt", () => {
    const c = countStatuses([
      session({ status: "running" }),
      session({ status: "starting" }),
      session({ status: "waiting" }),
      session({ status: "awaiting_approval" }),
      session({ status: "error" }),
      session({ status: "done" }),
      session({ status: "done" }),
    ]);
    expect(c).toEqual({ aktiv: 2, wartet: 1, freigabe: 1, fehler: 1, fertig: 2 });
  });
  it("leere Liste → alles 0", () => {
    expect(countStatuses([])).toEqual({
      aktiv: 0,
      wartet: 0,
      freigabe: 0,
      fehler: 0,
      fertig: 0,
    });
  });
});

describe("railRank — Rail/Board-Sortierung (AC: Handlungsbedarf zuoberst)", () => {
  it("awaiting_approval < waiting < error < running < done", () => {
    expect(railRank("awaiting_approval")).toBeLessThan(railRank("waiting"));
    expect(railRank("waiting")).toBeLessThan(railRank("error"));
    expect(railRank("error")).toBeLessThan(railRank("running"));
    expect(railRank("running")).toBeLessThan(railRank("done"));
  });
  it("sortiert eine gemischte Liste Freigabe→Wartet→Fehler→Aktiv→Fertig", () => {
    const order = (
      ["done", "running", "error", "waiting", "awaiting_approval"] as SessionStatus[]
    ).sort((a, b) => railRank(a) - railRank(b));
    expect(order).toEqual(["awaiting_approval", "waiting", "error", "running", "done"]);
  });
});

describe("modelLabel — auch aufgelöste IDs (Backend liefert volle ID nach Start)", () => {
  it("kürzt claude-haiku-4-5-… → Haiku", () => {
    expect(modelLabel("claude-haiku-4-5-20251001")).toBe("Haiku");
    expect(modelLabel("sonnet")).toBe("Sonnet");
    expect(modelLabel("claude-opus-4-8")).toBe("Opus");
  });
  it("unbekanntes Modell unverändert", () => {
    expect(modelLabel("gpt-foo")).toBe("gpt-foo");
  });
});

describe("projectName", () => {
  it("nimmt das letzte Pfadsegment", () => {
    expect(projectName("/home/dev/projects/jupiter")).toBe("jupiter");
    expect(projectName("/home/dev/projects/jupiter/")).toBe("jupiter");
  });
});

describe("formatDuration", () => {
  const base = Date.parse("2026-06-22T10:00:00Z");
  it("Sekunden/Minuten/Stunden", () => {
    expect(formatDuration("2026-06-22T10:00:00Z", base + 2_000)).toBe("gerade eben");
    expect(formatDuration("2026-06-22T10:00:00Z", base + 30_000)).toBe("30s");
    expect(formatDuration("2026-06-22T10:00:00Z", base + 5 * 60_000)).toBe("5m");
    expect(formatDuration("2026-06-22T10:00:00Z", base + 2 * 3_600_000)).toBe("2h 0m");
  });
  it("ungültiges Datum → —", () => {
    expect(formatDuration("nope", base)).toBe("—");
  });
});

describe("contextLabel — PROJ-5", () => {
  it("zeigt Prozent bei bekannten Daten", () => {
    expect(contextLabel(42.4, true)).toBe("42%");
  });
  it("zeigt unbekannt ohne Treiber-Daten (kein irreführendes 0 Prozent)", () => {
    expect(contextLabel(0, false)).toBe("unbekannt");
    expect(contextLabel(90, false)).toBe("unbekannt");
  });
});

describe("gaugeColor — PROJ-5", () => {
  it("rot ab der Schwelle", () => {
    expect(gaugeColor(85, 85)).toBe("bg-red-500");
    expect(gaugeColor(95, 85)).toBe("bg-red-500");
  });
  it("amber kurz vor der Schwelle", () => {
    expect(gaugeColor(70, 85)).toBe("bg-amber-400");
  });
  it("grün im grünen Bereich", () => {
    expect(gaugeColor(10, 85)).toBe("bg-emerald-500");
  });
});
