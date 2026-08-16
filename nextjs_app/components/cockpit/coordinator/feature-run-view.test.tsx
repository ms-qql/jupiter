// PROJ-79 QA-BUG-6-Fix: Minimaler Render-Smoke-Test (analog zu den bestehenden
// coordinator-Komponenten) — der Live-Poll (useEffect) läuft bei
// renderToStaticMarkup nicht, daher ist der initiale "Lade …"-Zustand deterministisch
// prüfbar, ohne Netzwerk/Fetch zu mocken.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { FeatureRunView } from "./feature-run-view";
import type { Session } from "@/lib/types";

describe("FeatureRunView — PROJ-79", () => {
  it("initial (kein Poll-Ergebnis): zeigt Lade-Zustand, wirft nicht", () => {
    const coordinator = {
      session_id: "coord-1",
      project_name: "jupiter · PROJ-101",
    } as unknown as Session;
    const html = renderToStaticMarkup(
      <FeatureRunView featureId="101" coordinator={coordinator} />,
    );
    expect(html).toContain("Feature 101");
    expect(html).toContain("Lade Feature-Ausführung");
  });
});
