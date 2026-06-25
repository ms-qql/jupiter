// PROJ-37 QA: Kernlogik der Auswahl „welche Session ist das aktive Fenster" im
// Fileexplorer. Reine Funktion → deterministisch ohne DOM/Context testbar.
// Deckt die Acceptance Criteria zur deterministischen Wahl + den neutralen
// Sonderfall (keine laufende Session → null) ab.

import { describe, expect, it } from "vitest";
import { pickActiveSession } from "./status";
import type { Session, SessionStatus } from "./types";

function session(id: string, status: SessionStatus, lastActivity: string): Session {
  return {
    session_id: id,
    owner: "dev",
    project_path: `/home/dev/projects/${id}`,
    model: "sonnet",
    permission_mode: "default",
    engine: "claude",
    role: null,
    constitution_source: null,
    status,
    created_at: "2026-06-25T10:00:00Z",
    last_activity: lastActivity,
    tokens_used: 0,
    cache_read_tokens: 0,
    cache_creation_tokens: 0,
    context_fill_pct: 0,
    context_known: true,
    context_fill_threshold_pct: 80,
    threshold_warning: false,
    total_cost_usd: 0,
    num_turns: 0,
    error: null,
    rate_limit: null,
    parent_session_id: null,
    child_session_id: null,
    project_name: id,
    abc_phase: null,
    abc_phase_reached: null,
    abc_feature: null,
    pending_decisions: [],
    liveness: "aktiv",
    liveness_auto_attempts: 0,
    liveness_last_result: null,
  };
}

describe("pickActiveSession (PROJ-37)", () => {
  it("bevorzugt die fokussierte laufende Session, auch wenn eine andere dringlicher ist", () => {
    const sessions = [
      session("a", "awaiting_approval", "2026-06-25T11:00:00Z"), // dringlicher
      session("b", "running", "2026-06-25T10:30:00Z"), // fokussiert
    ];
    expect(pickActiveSession(sessions, "b")?.session_id).toBe("b");
  });

  it("ignoriert eine fokussierte terminale Session und fällt auf die dringlichste laufende zurück", () => {
    const sessions = [
      session("done", "done", "2026-06-25T12:00:00Z"), // fokussiert, aber terminal
      session("run", "running", "2026-06-25T10:30:00Z"),
    ];
    expect(pickActiveSession(sessions, "done")?.session_id).toBe("run");
  });

  it("fällt zurück, wenn die fokussierte ID nicht (mehr) existiert", () => {
    const sessions = [session("run", "running", "2026-06-25T10:30:00Z")];
    expect(pickActiveSession(sessions, "weg")?.session_id).toBe("run");
  });

  it("liefert null, wenn keine laufende Session existiert (neutraler Hinweis)", () => {
    const sessions = [
      session("d", "done", "2026-06-25T11:00:00Z"),
      session("e", "error", "2026-06-25T11:30:00Z"),
    ];
    expect(pickActiveSession(sessions, "d")).toBeNull();
  });

  it("liefert null bei leerer Liste", () => {
    expect(pickActiveSession([], "x")).toBeNull();
    expect(pickActiveSession([], null)).toBeNull();
  });

  it("ohne Fokus: dringlichste zuerst (awaiting_approval vor running)", () => {
    const sessions = [
      session("run", "running", "2026-06-25T12:00:00Z"),
      session("appr", "awaiting_approval", "2026-06-25T10:00:00Z"),
    ];
    expect(pickActiveSession(sessions, null)?.session_id).toBe("appr");
  });

  it("ohne Fokus, bei gleichem Rang: jüngste Aktivität gewinnt (deterministisch)", () => {
    const sessions = [
      session("alt", "running", "2026-06-25T10:00:00Z"),
      session("neu", "running", "2026-06-25T11:00:00Z"),
    ];
    expect(pickActiveSession(sessions, null)?.session_id).toBe("neu");
  });
});
