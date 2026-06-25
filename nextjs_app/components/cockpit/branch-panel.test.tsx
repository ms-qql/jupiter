// PROJ-13 QA: reine Badge-Darstellung (describeBranch) ohne Netz/jsdom.
// Deckt alle Status-Varianten ab: lädt, kein Repo, detached, clean, dirty,
// ahead/behind. Die Mutations-Calls liegen im Backend-Vertrag (pytest).

import { describe, expect, it } from "vitest";
import { describeBranch } from "./branch-panel";
import type { BranchStatus } from "@/lib/types";

function status(overrides: Partial<BranchStatus> = {}): BranchStatus {
  return {
    path: "/home/dev/projects/jupiter",
    is_repo: true,
    branch: "dev",
    detached: false,
    dirty: false,
    ahead: null,
    behind: null,
    branches: ["main", "dev"],
    ...overrides,
  };
}

describe("describeBranch", () => {
  it("zeigt einen Lade-Platzhalter ohne Status", () => {
    expect(describeBranch(null).label).toBe("Git…");
  });

  it("markiert ein Nicht-Repo", () => {
    const d = describeBranch(status({ is_repo: false, branch: null, branches: [] }));
    expect(d.label).toBe("Kein Git-Repo");
    expect(d.variant).toBe("outline");
  });

  it("clean → Default-Variante, nur Branchname", () => {
    const d = describeBranch(status());
    expect(d.label).toBe("dev");
    expect(d.variant).toBe("default");
  });

  it("dirty → Secondary + Punkt-Marker", () => {
    const d = describeBranch(status({ dirty: true }));
    expect(d.label).toBe("dev •");
    expect(d.variant).toBe("secondary");
  });

  it("ahead/behind werden angehängt", () => {
    const d = describeBranch(status({ ahead: 2, behind: 1 }));
    expect(d.label).toBe("dev ↑2 ↓1");
  });

  it("detached HEAD wird deutlich (destructive)", () => {
    const d = describeBranch(status({ detached: true, branch: "a1b2c3d" }));
    expect(d.label).toBe("detached @a1b2c3d");
    expect(d.variant).toBe("destructive");
  });
});
