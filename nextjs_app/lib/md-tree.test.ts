import { describe, expect, it } from "vitest";
import {
  buildTree,
  buildWikilinkIndex,
  resolveWikilink,
  searchNotes,
  splitFrontmatter,
} from "./md-tree";
import { remarkWikilink } from "./remark-wikilink";
import type { MdIndexEntry } from "./types";

function entry(rel: string): MdIndexEntry {
  return { rel, name: rel.split("/").pop()!, path: `/root/${rel}` };
}

describe("buildTree", () => {
  it("nests folders and sorts folders before files", () => {
    const tree = buildTree([
      entry("README.md"),
      entry("features/PROJ-7-md-reader.md"),
      entry("features/PROJ-1.md"),
      entry("docs/architektur.md"),
    ]);
    // Ordner (docs, features) zuerst, dann Datei (README.md).
    expect(tree.map((n) => n.name)).toEqual(["docs", "features", "README.md"]);
    const features = tree.find((n) => n.name === "features");
    expect(features?.type).toBe("folder");
    if (features?.type === "folder") {
      expect(features.children.map((c) => c.name)).toEqual([
        "PROJ-1.md",
        "PROJ-7-md-reader.md",
      ]);
    }
  });
});

describe("wikilink resolution", () => {
  const idx = buildWikilinkIndex([
    entry("features/PROJ-7-md-reader.md"),
    entry("00 Context/Note.md"),
  ]);

  it("resolves by basename, case-insensitive", () => {
    expect(resolveWikilink("PROJ-7-md-reader", idx)?.rel).toBe(
      "features/PROJ-7-md-reader.md",
    );
    expect(resolveWikilink("note", idx)?.rel).toBe("00 Context/Note.md");
  });

  it("resolves by full rel path and ignores #anchors", () => {
    expect(resolveWikilink("features/PROJ-7-md-reader#ziel", idx)?.rel).toBe(
      "features/PROJ-7-md-reader.md",
    );
  });

  it("returns null for missing targets", () => {
    expect(resolveWikilink("does-not-exist", idx)).toBeNull();
  });
});

describe("splitFrontmatter (PROJ-12)", () => {
  it("strips a leading YAML block and keeps the body", () => {
    const { body } = splitFrontmatter("---\ntitle: X\ntags: [a]\n---\n# H\nText");
    expect(body).toBe("# H\nText");
  });

  it("returns content unchanged when there is no frontmatter", () => {
    expect(splitFrontmatter("# H\nText").body).toBe("# H\nText");
  });

  it("does not strip a non-leading --- separator", () => {
    const md = "# H\n\n---\n\nmehr";
    expect(splitFrontmatter(md).body).toBe(md);
  });
});

describe("searchNotes (PROJ-12 [[-autocomplete)", () => {
  const notes = [
    entry("features/PROJ-7-md-reader.md"),
    entry("features/PROJ-12-md-editor.md"),
    entry("docs/architektur.md"),
  ];

  it("ranks name-prefix matches above substring/path matches", () => {
    const res = searchNotes(notes, "proj-12");
    expect(res[0].name).toBe("PROJ-12-md-editor.md");
  });

  it("matches against the rel path too", () => {
    const res = searchNotes(notes, "docs/");
    expect(res.map((e) => e.name)).toContain("architektur.md");
  });

  it("returns all entries (capped) for an empty query", () => {
    expect(searchNotes(notes, "", 2)).toHaveLength(2);
  });

  it("returns nothing for a non-match", () => {
    expect(searchNotes(notes, "zzz")).toHaveLength(0);
  });
});

describe("remarkWikilink plugin", () => {
  // Minimaler mdast-Baum mit einem Absatz, der einen Wikilink + Embed enthält.
  function paragraph(text: string) {
    return {
      type: "root",
      children: [{ type: "paragraph", children: [{ type: "text", value: text }] }],
    };
  }

  it("converts [[Ziel|Alias]] into a wikilink: link node", () => {
    const tree = paragraph("siehe [[PROJ-7|den Reader]] hier");
    remarkWikilink()(tree);
    const kids = (tree.children[0] as { children: { type: string; url?: string; value?: string }[] }).children;
    const link = kids.find((k) => k.type === "link");
    expect(link?.url).toBe("wikilink:PROJ-7");
    expect((link as { children: { value: string }[] }).children[0].value).toBe("den Reader");
  });

  it("marks ![[bild.png]] as a wikiembed: link", () => {
    const tree = paragraph("![[bild.png]]");
    remarkWikilink()(tree);
    const kids = (tree.children[0] as { children: { type: string; url?: string }[] }).children;
    expect(kids[0].url).toBe("wikiembed:bild.png");
  });

  it("leaves plain text untouched", () => {
    const tree = paragraph("kein link hier");
    remarkWikilink()(tree);
    const kids = (tree.children[0] as { children: { type: string; value?: string }[] }).children;
    expect(kids).toHaveLength(1);
    expect(kids[0].value).toBe("kein link hier");
  });
});
