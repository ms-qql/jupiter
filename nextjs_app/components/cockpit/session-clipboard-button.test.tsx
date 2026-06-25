// PROJ-36 QA: Der Anhängen-Button ist Icon-only (kein Text), behält aber ein
// deutsches aria-label/title für Barrierefreiheit. Render zu statischem Markup
// (kein jsdom), das genügt für Markup-/Attribut-Assertions.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SessionClipboardButton } from "./session-clipboard-button";

describe("SessionClipboardButton (PROJ-36 Icon-only)", () => {
  it("zeigt keine Textbeschriftung mehr", () => {
    const html = renderToStaticMarkup(
      <SessionClipboardButton onPick={() => {}} />,
    );
    expect(html).not.toContain("Anhängen<");
    expect(html).not.toContain(">Anhängen");
  });

  it("traegt ein deutsches aria-label + title (Barrierefreiheit trotz Icon-only)", () => {
    const html = renderToStaticMarkup(
      <SessionClipboardButton onPick={() => {}} />,
    );
    expect(html).toContain('aria-label="Datei anhängen"');
    expect(html).toContain("Datei anhängen");
  });

  it("uploading -> Lade-aria-label statt Standard, Button disabled", () => {
    const html = renderToStaticMarkup(
      <SessionClipboardButton onPick={() => {}} uploading />,
    );
    expect(html).toContain('aria-label="Datei wird angehängt…"');
    expect(html).toContain("disabled");
  });

  it("disabled-Prop deaktiviert den Button", () => {
    const html = renderToStaticMarkup(
      <SessionClipboardButton onPick={() => {}} disabled />,
    );
    expect(html).toContain("disabled");
  });

  it("durchgereichte className landet am Button (flex-1 fuer die Icon-Reihe)", () => {
    const html = renderToStaticMarkup(
      <SessionClipboardButton onPick={() => {}} className="flex-1" />,
    );
    expect(html).toContain("flex-1");
  });
});
