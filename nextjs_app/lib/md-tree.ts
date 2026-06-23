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
