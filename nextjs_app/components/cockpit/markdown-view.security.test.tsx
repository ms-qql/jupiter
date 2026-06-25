// PROJ-7 QA: Security-/Render-Tests für MarkdownView ohne jsdom — react-markdown
// serverseitig zu statischem HTML rendern und das Markup prüfen.

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MarkdownView } from "./markdown-view";
import { buildWikilinkIndex } from "@/lib/md-tree";
import type { MdIndexEntry } from "@/lib/types";

function render(
  body: string,
  entries: MdIndexEntry[] = [],
  currentPath = "/root/features/INDEX.md",
) {
  const index = buildWikilinkIndex(entries);
  return renderToStaticMarkup(
    <MarkdownView
      body={body}
      index={index}
      currentPath={currentPath}
      onNavigate={vi.fn()}
    />,
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

// QA-7.2 (behoben): MarkdownView setzt einen urlTransform, der wikilink:/wikiembed:
// durchlässt (sonst defaultUrlTransform → XSS-Schutz bleibt).
describe("MarkdownView — Wikilinks & GFM", () => {
  it("rendert ein existierendes [[Ziel]] als klickbaren Button", () => {
    const html = render("siehe [[PROJ-7]]", [FILE]);
    expect(html).toContain("<button");
    expect(html).toContain("PROJ-7");
  });

  it("markiert ein fehlendes [[Ziel]] (line-through, kein Button/Link)", () => {
    const html = render("siehe [[Gibtsnicht]]", [FILE]);
    expect(html).toContain("line-through");
    expect(html).not.toContain("<button");
  });

  it("rendert ![[bild.png]] als Platzhalter-Badge (border-dashed, kein <img>)", () => {
    const html = render("![[bild.png]]", [FILE]);
    expect(html).not.toContain("<img");
    expect(html).toContain("border-dashed"); // Platzhalter-Badge, nicht nur Text
  });

  it("rendert GFM-Tabellen als <table>", () => {
    const html = render("| A | B |\n|---|---|\n| 1 | 2 |\n");
    expect(html).toContain("<table");
    expect(html).toContain("<td");
  });

  it("kürzt sehr große Dateien mit Hinweis (QA-7.4)", () => {
    const big = "x".repeat(450_000);
    const html = render(big);
    expect(html).toContain("gekürzt");
  });
});

// PROJ-31: Standard-Markdown-Links (relativ + Anker) im Reader auflösen.
describe("MarkdownView — Spec-Links (PROJ-31)", () => {
  it("rendert relativen MD-Link auf eine bekannte Datei als Button (kein <a href>)", () => {
    const html = render("siehe [Spec](PROJ-7.md)", [FILE]);
    expect(html).toContain("<button");
    expect(html).not.toMatch(/<a [^>]*href="PROJ-7\.md"/);
  });

  it("markiert relativen MD-Link auf eine unbekannte Datei als fehlend (line-through)", () => {
    const html = render("siehe [Spec](PROJ-99.md)", [FILE]);
    expect(html).toContain("line-through");
    expect(html).not.toContain("<button");
  });

  it("löst ../-Pfade relativ zur aktuellen Datei auf", () => {
    const prd: MdIndexEntry = { rel: "docs/PRD.md", name: "PRD.md", path: "/root/docs/PRD.md" };
    const html = render("siehe [PRD](../docs/PRD.md)", [prd]);
    expect(html).toContain("<button");
  });

  it("vergibt Überschriften-IDs und rendert In-Page-Anker als <a href=\"#…\">", () => {
    const html = render("[zu Status](#status)\n\n## Status\n");
    expect(html).toContain('id="status"');
    expect(html).toContain('href="#status"');
    expect(html).not.toContain("<button");
  });

  it("lässt externe http(s)-Links unverändert (target=_blank)", () => {
    const html = render("[extern](https://example.com)");
    expect(html).toMatch(/<a [^>]*href="https:\/\/example\.com"/);
    expect(html).toContain('target="_blank"');
  });

  it("behandelt interne Nicht-MD-Links als nicht-navigierbar (kein toter Link/Button)", () => {
    const html = render("siehe [Bild](bild.png)", [FILE]);
    expect(html).not.toContain("<button");
    expect(html).not.toMatch(/<a [^>]*href="bild\.png"/);
    expect(html).toContain("Nur Markdown-Dateien");
  });

  it("dekodiert %20/Leerzeichen im Linkziel und löst korrekt auf", () => {
    const spaced: MdIndexEntry = {
      rel: "features/My Spec.md",
      name: "My Spec.md",
      path: "/root/features/My Spec.md",
    };
    const html = render("siehe [Spec](My%20Spec.md)", [spaced]);
    expect(html).toContain("<button");
  });

  it("weist Pfad-Traversal ab (außerhalb des Index → fehlend, keine Navigation)", () => {
    const html = render("siehe [boom](../../../../etc/secret.md)", [FILE]);
    expect(html).toContain("line-through");
    expect(html).not.toContain("<button");
  });

  it("rendert Cross-File-Anker (X.md#abschnitt) als navigierbaren Button", () => {
    const html = render("siehe [Status](PROJ-7.md#status)", [FILE]);
    expect(html).toContain("<button");
  });
});
