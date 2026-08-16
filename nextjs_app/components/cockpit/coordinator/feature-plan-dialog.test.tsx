// PROJ-79 QA-BUG-6-Fix: Minimaler Render-Smoke-Test (analog zu den bestehenden
// coordinator-Komponenten) — schließt aus, dass der Dialog im geschlossenen Zustand
// (kein Poll, keine Netzwerkanfrage) beim Mount wirft.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { FeaturePlanDialog } from "./feature-plan-dialog";

describe("FeaturePlanDialog — PROJ-79", () => {
  it("geschlossen: rendert ohne zu werfen, keine Dialog-Inhalte im Markup", () => {
    const html = renderToStaticMarkup(
      <FeaturePlanDialog
        open={false}
        onOpenChange={() => {}}
        projectPath="/home/dev/projects/jupiter"
        featureId="PROJ-101"
        onDispatched={() => {}}
      />,
    );
    expect(html).not.toContain("Feature-Verteilungsplan");
  });
});
