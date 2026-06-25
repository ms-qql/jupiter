// PROJ-37 QA: Render-Verhalten des aktiven Session-Fensters (rechte Spalte des
// Fileexplorers ohne gewählte Datei). useSessions/useNow werden gemockt, damit
// die drei Zustände — aktive Session · neutraler Hinweis · Erstladen — ohne
// echten Poll/Context deterministisch (SSR-Static) geprüft werden können.

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { Session, SessionStatus } from "@/lib/types";

const state: {
  sessions: Session[];
  initialLoading: boolean;
  focusedSessionId: string | null;
} = { sessions: [], initialLoading: false, focusedSessionId: null };

vi.mock("./sessions-provider", () => ({
  useSessions: () => ({ ...state, error: null, refresh: () => {} }),
  useNow: () => Date.parse("2026-06-25T12:00:00Z"),
}));

// Import erst nach vi.mock (hoisted), damit der Mock greift.
const { ActiveSessionPanel } = await import("./active-session-panel");

function session(overrides: Partial<Session> = {}): Session {
  return {
    session_id: "sess-1",
    owner: "dev",
    project_path: "/home/dev/projects/jupiter",
    model: "sonnet",
    permission_mode: "default",
    engine: "claude",
    role: "Frontend Developer",
    constitution_source: null,
    status: "running" as SessionStatus,
    created_at: "2026-06-25T11:00:00Z",
    last_activity: "2026-06-25T11:58:00Z",
    tokens_used: 0,
    cache_read_tokens: 0,
    cache_creation_tokens: 0,
    context_fill_pct: 42,
    context_known: true,
    context_fill_threshold_pct: 80,
    threshold_warning: false,
    total_cost_usd: 0,
    num_turns: 0,
    error: null,
    rate_limit: null,
    parent_session_id: null,
    child_session_id: null,
    project_name: "PROJ-37",
    abc_phase: "qa",
    abc_phase_reached: "qa",
    abc_feature: "37",
    pending_decisions: [],
    liveness: "aktiv",
    liveness_auto_attempts: 0,
    liveness_last_result: null,
    ...overrides,
  };
}

describe("ActiveSessionPanel (PROJ-37)", () => {
  it("zeigt die aktive Session mit Name, Status, Phase, Kontext und Öffnen-Link", () => {
    state.sessions = [session()];
    state.initialLoading = false;
    state.focusedSessionId = "sess-1";

    const html = renderToStaticMarkup(<ActiveSessionPanel />);
    expect(html).toContain("PROJ-37");
    expect(html).toContain("Arbeitet"); // statusMeta(running).label
    expect(html).toContain("QA"); // phaseLabel(qa)
    expect(html).toContain("42%"); // contextLabel
    expect(html).toContain("Session öffnen");
    expect(html).toContain('href="/sessions/sess-1"');
    expect(html).not.toContain("Keine aktive Session");
  });

  it("zeigt den neutralen Hinweis, wenn keine laufende Session existiert", () => {
    state.sessions = [session({ status: "done" })];
    state.initialLoading = false;
    state.focusedSessionId = null;

    const html = renderToStaticMarkup(<ActiveSessionPanel />);
    expect(html).toContain("Keine aktive Session");
    expect(html).not.toContain("Session öffnen");
  });

  it("zeigt Lade-Hinweis beim Erstladen statt voreilig „keine Session“", () => {
    state.sessions = [];
    state.initialLoading = true;
    state.focusedSessionId = null;

    const html = renderToStaticMarkup(<ActiveSessionPanel />);
    expect(html).toContain("Lädt…");
    expect(html).not.toContain("Keine aktive Session");
  });

  it("weist auf offene Freigaben hin", () => {
    state.sessions = [
      session({
        status: "awaiting_approval",
        pending_decisions: [{ id: "d1" } as never],
      }),
    ];
    state.initialLoading = false;
    state.focusedSessionId = "sess-1";

    const html = renderToStaticMarkup(<ActiveSessionPanel />);
    expect(html).toContain("Freigabe wartet auf dich");
  });
});
