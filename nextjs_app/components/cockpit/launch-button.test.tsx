// PROJ-18 QA: Render-Tests für den Startknopf (Integrations-Tiefe 3) ohne jsdom —
// die Komponente serverseitig zu statischem HTML rendern und das Verhalten je
// Ziel-Art (Web-URL vs. lokaler Befehl) prüfen.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { LaunchButton } from "./launch-button";

describe("LaunchButton (PROJ-18 · Tiefe 3)", () => {
  it("Web-URL → Anchor in neuem Tab mit noopener", () => {
    const html = renderToStaticMarkup(
      <LaunchButton label="ChatGPT" target="https://chat.openai.com" />,
    );
    expect(html).toContain("<a");
    expect(html).toContain('href="https://chat.openai.com"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain("noopener");
    expect(html).toContain("ChatGPT");
  });

  it("lokaler Befehl (keine URL) → Button zum Kopieren, kein Auto-Öffnen", () => {
    const html = renderToStaticMarkup(
      <LaunchButton label="Ollama starten" target="ollama serve" />,
    );
    expect(html).toContain("<button");
    expect(html).not.toContain("<a ");
    expect(html).toContain("Befehl kopieren");
  });

  it("javascript:-Ziel wird NICHT als Web-Link geöffnet (kein XSS-Absprung)", () => {
    const html = renderToStaticMarkup(
      <LaunchButton label="böse" target="javascript:alert(1)" />,
    );
    expect(html).not.toContain("href=");
    expect(html).toContain("<button");
  });
});
