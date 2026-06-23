// PROJ-7: reine Helfer für den MD-Reader — Baum + Wikilink-Auflösung aus dem
// flachen Index (eine /md/index-Antwort speist beide). Keine React-Abhängigkeit
// → mit vitest testbar.

import type { MdIndexEntry } from "./types";

export interface TreeFile {
  type: "file";
  name: string; // Basisname inkl. .md
  rel: string;
  path: string; // absolut
}

export interface TreeFolder {
  type: "folder";
  name: string;
  rel: string; // Pfad des Ordners relativ zur Wurzel
  children: TreeNode[];
}

export type TreeNode = TreeFolder | TreeFile;

/** Baut aus den flachen Index-Einträgen einen verschachtelten Ordnerbaum. */
export function buildTree(entries: MdIndexEntry[]): TreeNode[] {
  const root: TreeFolder = { type: "folder", name: "", rel: "", children: [] };

  for (const entry of entries) {
    const parts = entry.rel.split("/");
    let cursor = root;
    // Alle Segmente außer dem letzten sind Ordner.
    for (let i = 0; i < parts.length - 1; i++) {
      const folderRel = parts.slice(0, i + 1).join("/");
      let next = cursor.children.find(
        (c): c is TreeFolder => c.type === "folder" && c.rel === folderRel,
      );
      if (!next) {
        next = { type: "folder", name: parts[i], rel: folderRel, children: [] };
        cursor.children.push(next);
      }
      cursor = next;
    }
    cursor.children.push({
      type: "file",
      name: parts[parts.length - 1],
      rel: entry.rel,
      path: entry.path,
    });
  }

  sortNodes(root.children);
  return root.children;
}

/** Ordner zuerst, dann Dateien; jeweils alphabetisch (locale-aware). */
function sortNodes(nodes: TreeNode[]): void {
  nodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    return a.name.localeCompare(b.name, "de", { sensitivity: "base" });
  });
  for (const n of nodes) {
    if (n.type === "folder") sortNodes(n.children);
  }
}

function normalizeKey(s: string): string {
  return s.replace(/\.md$/i, "").toLowerCase();
}

/** Index für die Wikilink-Auflösung: Basisname UND voller rel-Pfad → Eintrag. */
export function buildWikilinkIndex(
  entries: MdIndexEntry[],
): Map<string, MdIndexEntry> {
  const map = new Map<string, MdIndexEntry>();
  for (const entry of entries) {
    const relKey = normalizeKey(entry.rel);
    // Voller Pfad gewinnt immer (eindeutig).
    map.set(relKey, entry);
    // Basisname nur setzen, wenn noch frei (erste Datei gewinnt bei Kollision).
    const baseKey = normalizeKey(entry.name);
    if (!map.has(baseKey)) map.set(baseKey, entry);
  }
  return map;
}

/**
 * PROJ-12: Trennt einen führenden YAML-Frontmatter-Block (``---\n…\n---``) vom
 * Body — fürs Live-Rendern des Editor-Entwurfs. Spiegelt die Backend-Logik
 * (``_parse_frontmatter``), ohne YAML zu parsen: gibt nur den Body zurück.
 */
export function splitFrontmatter(content: string): { body: string } {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(content);
  return { body: match ? content.slice(match[0].length) : content };
}

/**
 * PROJ-12: Notiz-Suche fürs ``[[``-Autocomplete. Filtert die Index-Einträge
 * gegen `query` (Teilstring in Name oder rel-Pfad, case-insensitive). Exakte
 * Namens-Präfixe ranken vor reinen Teiltreffern; gekappt auf `limit`.
 */
export function searchNotes(
  entries: MdIndexEntry[],
  query: string,
  limit = 8,
): MdIndexEntry[] {
  const q = query.trim().toLowerCase();
  const scored: { entry: MdIndexEntry; score: number }[] = [];
  for (const e of entries) {
    const name = normalizeKey(e.name);
    const rel = e.rel.toLowerCase();
    if (!q) {
      scored.push({ entry: e, score: 0 });
    } else if (name.startsWith(q)) {
      scored.push({ entry: e, score: 3 });
    } else if (name.includes(q)) {
      scored.push({ entry: e, score: 2 });
    } else if (rel.includes(q)) {
      scored.push({ entry: e, score: 1 });
    }
  }
  scored.sort(
    (a, b) =>
      b.score - a.score ||
      a.entry.name.localeCompare(b.entry.name, "de", { sensitivity: "base" }),
  );
  return scored.slice(0, limit).map((s) => s.entry);
}

/**
 * Löst ein Wikilink-Ziel gegen den Index auf. Unterstützt ``[[Name]]``,
 * ``[[Ordner/Name]]`` und ``[[Name#Überschrift]]`` (Anker wird ignoriert).
 * Gibt den Eintrag zurück oder ``null`` (→ „fehlend").
 */
export function resolveWikilink(
  target: string,
  index: Map<string, MdIndexEntry>,
): MdIndexEntry | null {
  const clean = target.split("#")[0].trim();
  if (!clean) return null;
  const key = normalizeKey(clean);
  return index.get(key) ?? index.get(key.split("/").pop() ?? key) ?? null;
}
