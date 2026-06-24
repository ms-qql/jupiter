import { describe, expect, it } from "vitest";
import {
  aggregateUsage,
  filterByRange,
  formatCost,
  formatTokens,
  rangeStartMs,
} from "@/lib/usage";
import type { Session } from "@/lib/types";

// Minimaler Session-Stub — nur die fürs Dashboard relevanten Felder.
function makeSession(over: Partial<Session>): Session {
  return {
    session_id: "s",
    owner: "o",
    project_path: "/p/alpha",
    model: "sonnet",
    permission_mode: "default",
    engine: "claude",
    role: null,
    constitution_source: null,
    status: "running",
    created_at: "2026-06-24T12:00:00Z",
    last_activity: "2026-06-24T12:00:00Z",
    tokens_used: 0,
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
    project_name: null,
    abc_phase: null,
    abc_phase_reached: null,
    abc_feature: null,
    pending_decisions: [],
    liveness: "aktiv",
    liveness_auto_attempts: 0,
    liveness_last_result: null,
    ...over,
  };
}

const NOW = Date.parse("2026-06-24T15:00:00Z");

describe("rangeStartMs", () => {
  it("'all' hat keine Untergrenze", () => {
    expect(rangeStartMs("all", NOW)).toBe(Number.NEGATIVE_INFINITY);
  });
  it("'7d' liegt 7 Tage zurück", () => {
    expect(rangeStartMs("7d", NOW)).toBe(NOW - 7 * 86_400_000);
  });
});

describe("filterByRange", () => {
  const sessions = [
    makeSession({ session_id: "neu", created_at: "2026-06-24T10:00:00Z" }),
    makeSession({ session_id: "alt", created_at: "2026-06-01T10:00:00Z" }),
  ];
  it("7d behält nur junge Sessions", () => {
    const out = filterByRange(sessions, "7d", NOW);
    expect(out.map((s) => s.session_id)).toEqual(["neu"]);
  });
  it("all behält alles", () => {
    expect(filterByRange(sessions, "all", NOW)).toHaveLength(2);
  });
});

describe("aggregateUsage", () => {
  it("summiert Tokens + Kosten und gruppiert nach Modell", () => {
    const sessions = [
      makeSession({ model: "opus", tokens_used: 1000, total_cost_usd: 0.5 }),
      makeSession({ model: "opus", tokens_used: 500, total_cost_usd: 0.25 }),
      makeSession({ model: "haiku", tokens_used: 200, total_cost_usd: 0.01 }),
    ];
    const sum = aggregateUsage(sessions, "all", NOW);
    expect(sum.totalTokens).toBe(1700);
    expect(sum.totalCostUsd).toBeCloseTo(0.76);
    expect(sum.costStatus).toBe("complete");
    // nach Tokens absteigend → Opus (1500) vor Haiku (200)
    expect(sum.byModel.map((g) => g.label)).toEqual(["Opus", "Haiku"]);
    expect(sum.byModel[0].tokens).toBe(1500);
  });

  it("Subscription/Fremd-Engine ohne Kosten → costStatus none/partial", () => {
    const subscription = aggregateUsage(
      [makeSession({ engine: "openrouter", tokens_used: 100 })],
      "all",
      NOW,
    );
    expect(subscription.costStatus).toBe("none");

    const mixed = aggregateUsage(
      [
        makeSession({ engine: "claude", total_cost_usd: 0.1, tokens_used: 10 }),
        makeSession({ engine: "openai", tokens_used: 10 }),
      ],
      "all",
      NOW,
    );
    expect(mixed.costStatus).toBe("partial");
  });

  it("gruppiert nach Projekt über project_name/Basename", () => {
    const sum = aggregateUsage(
      [
        makeSession({ project_path: "/p/alpha", project_name: "Alpha", tokens_used: 5 }),
        makeSession({ project_path: "/p/beta", tokens_used: 7 }),
      ],
      "all",
      NOW,
    );
    expect(sum.byProject[0].label).toBe("beta"); // 7 > 5
    expect(sum.byProject[1].label).toBe("Alpha");
  });
});

describe("Formatierung", () => {
  it("formatTokens nutzt de-DE-Tausendertrennung", () => {
    expect(formatTokens(1234567)).toBe("1.234.567");
  });
  it("formatCost kennzeichnet Lage", () => {
    expect(formatCost(1.5, "complete")).toBe("$1.50");
    expect(formatCost(1.5, "partial")).toBe("~$1.50");
    expect(formatCost(0, "none")).toBe("n/v");
  });
});
