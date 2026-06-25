// PROJ-18 QA: Render-Tests für die iFrame-Einbettung (Integrations-Tiefe 2) ohne
// jsdom — Initial-Render zu statischem HTML: das iFrame trägt src + sandbox aus dem
// Profil, und der Launch-Fallback („In neuem Tab öffnen") ist immer vorhanden.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { EmbedTab } from "./embed-tab";
import type { EngineRead } from "@/lib/types";

function iframeEngine(overrides: Partial<EngineRead> = {}): EngineRead {
  return {
    key: "excalidraw",
    label: "Excalidraw",
    kind: "iframe",
    driver: null,
    available: true,
    unavailable_reason: null,
    models: [],
    default_model: null,
    capabilities: [],
    url: "https://excalidraw.com",
    sandbox: "allow-scripts allow-same-origin",
    target: null,
    group: null,
    icon: null,
    ...overrides,
  };
}

describe("EmbedTab (PROJ-18 · Tiefe 2)", () => {
  it("rendert iFrame mit src + sandbox aus dem Profil", () => {
    const html = renderToStaticMarkup(<EmbedTab engine={iframeEngine()} />);
    expect(html).toContain("<iframe");
    expect(html).toContain('src="https://excalidraw.com"');
    expect(html).toContain('sandbox="allow-scripts allow-same-origin"');
  });

  it("bietet IMMER den Launch-Fallback (X-Frame-Options/CSP-Verweigerung)", () => {
    const html = renderToStaticMarkup(<EmbedTab engine={iframeEngine()} />);
    expect(html).toContain("In neuem Tab öffnen");
    expect(html).toContain('href="https://excalidraw.com"');
  });

  it("ohne url → nichts rendern (defensiv)", () => {
    const html = renderToStaticMarkup(<EmbedTab engine={iframeEngine({ url: null })} />);
    expect(html).toBe("");
  });

  // PROJ-39: Vollbild-Variante für die Orchestration-Route.
  it("fullHeight: iFrame füllt die Höhe (flex-1) statt fester 60vh", () => {
    const full = renderToStaticMarkup(
      <EmbedTab engine={iframeEngine({ key: "wayland", label: "Wayland" })} fullHeight />,
    );
    expect(full).toContain("flex-1");
    expect(full).not.toContain("h-[60vh]");
    // Fallback-Button bleibt auch in der Vollbild-Variante immer sichtbar.
    expect(full).toContain("In neuem Tab öffnen");
  });

  it("Default (ohne fullHeight) bleibt die kompakte 60vh-Karte", () => {
    const compact = renderToStaticMarkup(<EmbedTab engine={iframeEngine()} />);
    expect(compact).toContain("h-[60vh]");
  });
});
