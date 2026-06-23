// PROJ-7: kleines remark-Plugin, das Obsidian-Wikilinks in mdast-Link-Knoten
// umwandelt. Bewusst ohne Zusatz-Dependency (manuelle Rekursion über children):
//
//   [[Ziel]]            → Link  url="wikilink:Ziel"        Text "Ziel"
//   [[Ziel|Alias]]      → Link  url="wikilink:Ziel"        Text "Alias"
//   [[Ziel#Abschnitt]]  → Link  url="wikilink:Ziel#Abschnitt"
//   ![[bild.png]]       → Link  url="wikiembed:bild.png"   Text "bild.png"
//
// Die eigentliche Auflösung (Treffer/„fehlend") macht die Viewer-Komponente über
// die Link-Renderer-Funktion. Code-/Inline-Code-Knoten sind kein `text`-Typ und
// werden daher nie angefasst.

interface MdastNode {
  type: string;
  value?: string;
  url?: string;
  title?: string | null;
  children?: MdastNode[];
}

const WIKILINK = /(!?)\[\[([^\]\n]+?)\]\]/g;

function splitTextNode(value: string): MdastNode[] | null {
  WIKILINK.lastIndex = 0;
  if (!WIKILINK.test(value)) return null;
  WIKILINK.lastIndex = 0;

  const out: MdastNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = WIKILINK.exec(value)) !== null) {
    if (m.index > last) out.push({ type: "text", value: value.slice(last, m.index) });
    const isEmbed = m[1] === "!";
    const inner = m[2];
    const [targetRaw, alias] = inner.split("|");
    const target = targetRaw.trim();
    const label = (alias ?? target).trim();
    out.push({
      type: "link",
      url: `${isEmbed ? "wikiembed" : "wikilink"}:${target}`,
      title: null,
      children: [{ type: "text", value: label }],
    });
    last = m.index + m[0].length;
  }
  if (last < value.length) out.push({ type: "text", value: value.slice(last) });
  return out;
}

function transform(node: MdastNode): void {
  if (!node.children) return;
  // Nicht in bestehende Links hineinschreiben (keine verschachtelten Links).
  if (node.type === "link" || node.type === "linkReference") {
    node.children.forEach(transform);
    return;
  }
  const next: MdastNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && child.value) {
      const replaced = splitTextNode(child.value);
      if (replaced) {
        next.push(...replaced);
        continue;
      }
    }
    transform(child);
    next.push(child);
  }
  node.children = next;
}

export function remarkWikilink() {
  return (tree: MdastNode) => transform(tree);
}
