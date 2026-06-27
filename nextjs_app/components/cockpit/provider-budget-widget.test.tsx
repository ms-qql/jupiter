// PROJ-52: Render-Smoke für das Sidebar-Budget-Widget.
// SSR rendert den requestfreien Initialzustand; Fetch läuft erst im Browser-useEffect.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import {
  formatReset,
  ProviderBudgetWidget,
  resolveWindowQuality,
} from "./provider-budget-widget";

describe("ProviderBudgetWidget", () => {
  it("rendert kompakten Sidebar-Block mit Refresh-Aktion", () => {
    const html = renderToStaticMarkup(<ProviderBudgetWidget />);
    expect(html).toContain("Budget");
    expect(html).toContain("Budget aktualisieren");
    expect(html).toContain("bg-muted");
  });

  it("markiert abgelaufene Reset-Fenster clientseitig als veraltet", () => {
    const nowMs = Date.parse("2026-06-27T12:00:00.000Z");
    expect(
      resolveWindowQuality(
        { quality: "estimated", reset_at: "2026-06-27T11:59:00.000Z" },
        nowMs,
      ),
    ).toBe("stale");
    expect(formatReset("2026-06-27T11:59:00.000Z", nowMs)).toBe("fällig");
  });
});
