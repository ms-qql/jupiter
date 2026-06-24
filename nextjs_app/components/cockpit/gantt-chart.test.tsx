// PROJ-8 QA: Render-Tests für den ABC-Workflow-Gantt ohne jsdom — die Komponente
// serverseitig zu statischem HTML rendern und Füllung/Hervorhebung/Labels prüfen.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { GanttChart } from "./gantt-chart";
import type { Session } from "@/lib/types";

function session(overrides: Partial<Session> = {}): Session {
  return {
    session_id: "id",
    owner: "dev",
    project_path: "/home/dev/projects/jupiter",
    model: "haiku",
    permission_mode: "default",
    engine: "claude",
    role: null,
    constitution_source: null,
    status: "running",
    created_at: "2026-06-22T10:00:00Z",
    last_activity: "2026-06-22T10:01:00Z",
    tokens_used: 0,
    cache_read_tokens: 0,
    cache_creation_tokens: 0,
    context_fill_pct: 0,
    context_known: false,
    context_fill_threshold_pct: 85,
    threshold_warning: false,
    total_cost_usd: 0,
    num_turns: 0,
    error: null,
    rate_limit: null,
    parent_session_id: null,
    child_session_id: null,
    project_name: null,
    abc_phase: null,
    abc_phase_reached: null,
    abc_feature: null,
    pending_decisions: [],
    liveness: "aktiv",
    liveness_auto_attempts: 0,
    liveness_last_result: null,
    ...overrides,
  };
}

const count = (html: string, needle: string) => html.split(needle).length - 1;

describe("GanttChart — PROJ-8", () => {
  it("0 Sessions → eigener Empty-State", () => {
    const html = renderToStaticMarkup(<GanttChart sessions={[]} />);
    expect(html).toContain("Noch keine Sessions mit ABC-Phase.");
  });

  it("füllt bis zur erreichten Phase und hebt die aktuelle hervor", () => {
    // backend = Index 4: Zellen 0–3 abgeschlossen, 4 aktuell, 5–7 offen.
    const html = renderToStaticMarkup(
      <GanttChart
        sessions={[
          session({
            project_name: "Jupiter",
            abc_feature: "8",
            abc_phase: "backend",
            abc_phase_reached: "backend",
          }),
        ]}
      />,
    );
    expect(html).toContain("Jupiter");
    expect(html).toContain("Feature 8");
    expect(count(html, "aktuelle Phase")).toBe(1);
    expect(count(html, ": abgeschlossen")).toBe(4);
    expect(count(html, ": offen")).toBe(3);
  });

  it("nicht-linear: Bar füllt bis reached, aktuelle Phase getrennt markiert", () => {
    // reached=document(7), aktuell zurück bei frontend(3): 0–7 gefüllt (7 abgeschlossen
    // + 1 aktuell), 0 offen; die aktuelle Markierung sitzt auf frontend.
    const html = renderToStaticMarkup(
      <GanttChart
        sessions={[
          session({ abc_phase: "frontend", abc_phase_reached: "document" }),
        ]}
      />,
    );
    expect(count(html, "aktuelle Phase")).toBe(1);
    expect(count(html, ": abgeschlossen")).toBe(7);
    expect(count(html, ": offen")).toBe(0);
  });

  it("Session ohne Phase → neutrale Zeile (alle 8 Zellen offen, keine Hervorhebung)", () => {
    const html = renderToStaticMarkup(
      <GanttChart sessions={[session({ project_name: "Ad-hoc" })]} />,
    );
    expect(html).toContain("Ad-hoc");
    expect(count(html, "aktuelle Phase")).toBe(0);
    expect(count(html, ": offen")).toBe(8);
  });

  it("beendete Session → eingefroren, aktuelle Phase NICHT mehr markiert", () => {
    const html = renderToStaticMarkup(
      <GanttChart
        sessions={[
          session({
            status: "done",
            abc_phase: "qa",
            abc_phase_reached: "qa",
            project_name: "Alt",
          }),
        ]}
      />,
    );
    expect(html).toContain("· beendet");
    expect(count(html, "aktuelle Phase")).toBe(0); // eingefroren
    expect(count(html, ": abgeschlossen")).toBe(6); // brainstorm…qa = 6 Zellen gefüllt
  });

  it("Fallback-Label: ohne project_name den Pfad-Basename zeigen", () => {
    const html = renderToStaticMarkup(
      <GanttChart sessions={[session({ project_path: "/home/dev/projects/apollo" })]} />,
    );
    expect(html).toContain("apollo");
  });
});
