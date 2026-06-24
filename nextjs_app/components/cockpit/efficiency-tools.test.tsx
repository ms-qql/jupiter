// PROJ-19 QA: SSR-Render-Smoke der Effizienz-Werkzeuge (RAG-Vorschau + Späher).
// Kein jsdom — statisches Markup wie session-tile.test.tsx; Netzwerk wird erst on-click
// angestoßen, der Initial-Render ist also requestfrei.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { RagPreviewPanel } from "./rag-preview-panel";
import { ScoutPanel } from "./scout-panel";

describe("RagPreviewPanel", () => {
  it("rendert Überschrift + Eingabe", () => {
    const html = renderToStaticMarkup(<RagPreviewPanel />);
    expect(html).toContain("RAG-Vorschau");
    expect(html).toContain("Wonach im Vault suchen");
  });
});

describe("ScoutPanel", () => {
  it("rendert Überschrift + Aufgaben-Eingabe", () => {
    const html = renderToStaticMarkup(<ScoutPanel />);
    expect(html).toContain("Späher-Agent");
    expect(html).toContain("was soll der Späher");
  });
});
