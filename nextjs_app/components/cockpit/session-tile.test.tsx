// PROJ-18 QA: Render-Tests für die engine-agnostische Kachel-Sicht ohne jsdom —
// SSR zu statischem HTML. Fremd-Engines zeigen einen Engine-Badge und „n/v" statt
// eines Kosten-Betrags; Claude bleibt unverändert ($-Betrag, kein Engine-Badge).

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SessionTile } from "./session-tile";
import type { Session } from "@/lib/types";

function session(overrides: Partial<Session> = {}): Session {
  return {
    session_id: "id",
    owner: "dev",
    project_path: "/home/dev/projects/jupiter",
    model: "sonnet",
    permission_mode: "default",
    engine: "claude",
    role: null,
    constitution_source: null,
    status: "running",
    created_at: "2026-06-24T10:00:00Z",
    last_activity: "2026-06-24T10:00:00Z",
    tokens_used: 1000,
    cache_read_tokens: 0,
    cache_creation_tokens: 0,
    context_fill_pct: 12,
    context_known: true,
    context_fill_threshold_pct: 80,
    threshold_warning: false,
    total_cost_usd: 0.123,
    num_turns: 1,
    error: null,
    rate_limit: null,
    parent_session_id: null,
    child_session_id: null,
    parent_coordinator_id: null,
    ticket_id: null,
    child_session_ids: [],
    contract_pointer: null,
    project_name: "jupiter",
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

describe("SessionTile — engine-agnostische Degradation (PROJ-18 · AC-5)", () => {
  it("Claude: $-Kosten, kein Engine-Badge", () => {
    const html = renderToStaticMarkup(<SessionTile session={session()} now={Date.parse("2026-06-24T10:05:00Z")} />);
    expect(html).toContain("$0.123");
    expect(html).not.toContain("n/v");
    // kein eigener Engine-Badge für die Default-Engine
    expect(html).not.toContain(">claude<");
  });

  it("Fremd-Engine (openai): „n/v“ statt Kosten + Engine-Badge", () => {
    const html = renderToStaticMarkup(
      <SessionTile session={session({ engine: "openai", total_cost_usd: 0 })} now={Date.parse("2026-06-24T10:05:00Z")} />,
    );
    expect(html).toContain("n/v");
    expect(html).not.toContain("$0.000");
    expect(html).toContain("openai"); // Engine-Badge sichtbar
  });

  it("Engine ohne Token-Daten (context_known=false) → Kontext „unbekannt“", () => {
    const html = renderToStaticMarkup(
      <SessionTile session={session({ engine: "ollama", context_known: false })} now={Date.parse("2026-06-24T10:05:00Z")} />,
    );
    expect(html).toContain("unbekannt");
  });
});
