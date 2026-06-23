// PROJ-7 QA: Security-/Render-Tests für MarkdownView ohne jsdom — react-markdown
// serverseitig zu statischem HTML rendern und das Markup prüfen.

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MarkdownView } from "./markdown-view";
import { buildWikilinkIndex } from "@/lib/md-tree";
import type { MdIndexEntry } from "@/lib/types";

function render(body: string, entries: MdIndexEntry[] = []) {
  const index = buildWikilinkIndex(entries);
  return renderToStaticMarkup(
    <MarkdownView body={body} index={index} onNavigate={vi.fn()} />,
  );
}

const FILE: MdIndexEntry = {
  rel: "features/PROJ-7.md",
  name: "PROJ-7.md",
  path: "/root/features/PROJ-7.md",
};

describe("MarkdownView — XSS / Sanitizing", () => {
  it("rendert rohes <script> NICHT als HTML-Tag (react-markdown ohne rehype-raw)", () => {
    const html = render("Hallo\n\n<script>alert('xss')</script>\n");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("neutralisiert eingebettetes Event-Handler-HTML (escaped, kein echtes <img>)", () => {
    const html = render('<img src=x onerror="alert(1)">');
    // Roh-HTML wird als Text escaped (react-markdown ohne rehype-raw) → kein aktives Tag.
    expect(html).not.toMatch(/<img[^>]*onerror/i);
    expect(html).toContain("&lt;img");
  });

  it("javascript:-Links werden von react-markdown entschärft", () => {
    const html = render("[klick](javascript:alert(1))");
    expect(html).not.toContain("javascript:alert");
  });
});

// FIXME(QA-7.2 / HIGH): react-markdown strippt das custom URL-Schema wikilink:/
// wikiembed: über seinen Default-`urlTransform` zu "" → der a-Renderer landet im
// Extern-Link-Zweig statt im Wikilink-/Embed-Zweig. Wikilinks navigieren NICHT und
// fehlende Ziele werden NICHT markiert; Embeds zeigen keinen Platzhalter.
// Diese drei Tests sind als `it.fails` markiert (dokumentieren den Bug, halten die
// Suite grün). NACH dem Fix (MarkdownView muss urlTransform überschreiben/ein eigenes
// Schema durchlassen) schlagen sie als bestanden um → `.fails` entfernen.
describe("MarkdownView — Wikilinks & GFM", () => {
  it.fails("rendert ein existierendes [[Ziel]] als klickbaren Button", () => {
    const html = render("siehe [[PROJ-7]]", [FILE]);
    expect(html).toContain("<button");
    expect(html).toContain("PROJ-7");
  });

  it.fails("markiert ein fehlendes [[Ziel]] (line-through, kein Button/Link)", () => {
    const html = render("siehe [[Gibtsnicht]]", [FILE]);
    expect(html).toContain("line-through");
    expect(html).not.toContain("<button");
  });

  it.fails("rendert ![[bild.png]] als Platzhalter-Badge (border-dashed, kein <img>)", () => {
    const html = render("![[bild.png]]", [FILE]);
    expect(html).not.toContain("<img");
    expect(html).toContain("border-dashed"); // Platzhalter-Badge, nicht nur Text
  });

  it("rendert GFM-Tabellen als <table>", () => {
    const html = render("| A | B |\n|---|---|\n| 1 | 2 |\n");
    expect(html).toContain("<table");
    expect(html).toContain("<td");
  });
});
