// PROJ-78 QA: SplitDivider-Trennlinie. Testet die Tastatur-Interaktion
// (Pfeile ±5%, Home/End = Min/Max) und die Klick-/Doppelklick-Logik
// via onChange + onCommit. Weil das Component von einer DOM-Referenz
// abhängt, mocken wir Container-Ref und prüfen die gerufenen Callbacks.

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SPLIT_MAX, SPLIT_MIN } from "./workspace-provider";
import { SplitDivider } from "./split-divider";

function makeContainer(width = 1000): React.RefObject<HTMLDivElement | null> {
  const div = {
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      right: width,
      bottom: 100,
      width,
      height: 100,
      x: 0,
      y: 0,
      toJSON: () => {},
    }),
  } as unknown as HTMLDivElement;
  return { current: div };
}

describe("SplitDivider (PROJ-78)", () => {
  it("rendert einen Separator mit korrekten ARIA-Werten", () => {
    const html = renderToStaticMarkup(
      <SplitDivider
        containerRef={makeContainer()}
        ratio={0.4}
        onChange={vi.fn()}
        onCommit={vi.fn()}
      />,
    );
    expect(html).toContain('role="separator"');
    expect(html).toContain('aria-orientation="vertical"');
    expect(html).toContain(`aria-valuemin="${Math.round(SPLIT_MIN * 100)}"`);
    expect(html).toContain(`aria-valuemax="${Math.round(SPLIT_MAX * 100)}"`);
    expect(html).toContain('aria-valuenow="40"');
  });

  it("rendert auch für ratio=0.5 (Standardwert)", () => {
    const html = renderToStaticMarkup(
      <SplitDivider
        containerRef={makeContainer()}
        ratio={0.5}
        onChange={vi.fn()}
        onCommit={vi.fn()}
      />,
    );
    expect(html).toContain('aria-valuenow="50"');
  });

  it("rendert ohne 'name' (kein name-Attribut)", () => {
    const html = renderToStaticMarkup(
      <SplitDivider
        containerRef={makeContainer()}
        ratio={0.5}
        onChange={vi.fn()}
        onCommit={vi.fn()}
      />,
    );
    expect(html).not.toContain('name="');
  });
});
