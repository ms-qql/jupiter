"use client";

// PROJ-7: ausklappbarer Datei-Baum (read-only) aus dem flachen MD-Index.
// Ordner mit Default-Prefix (z. B. "features" / "Agentic OS/Jupiter") sind
// initial aufgeklappt, weil die dort liegenden Specs/Handovers am häufigsten
// gelesen werden.

import { useState } from "react";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FileTextIcon,
  FolderIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { TreeFolder, TreeNode } from "@/lib/md-tree";

export function FileTree({
  nodes,
  activePath,
  defaultExpandedPrefixes = [],
  onSelect,
}: {
  nodes: TreeNode[];
  activePath: string | null;
  defaultExpandedPrefixes?: string[];
  onSelect: (path: string) => void;
}) {
  if (nodes.length === 0) {
    return (
      <p className="px-2 py-6 text-center text-xs text-muted-foreground">
        Keine Markdown-Dateien.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-0.5">
      {nodes.map((node) => (
        <TreeNodeRow
          key={node.type === "folder" ? `d:${node.rel}` : `f:${node.path}`}
          node={node}
          depth={0}
          activePath={activePath}
          defaultExpandedPrefixes={defaultExpandedPrefixes}
          onSelect={onSelect}
        />
      ))}
    </ul>
  );
}

function shouldExpand(folder: TreeFolder, prefixes: string[]): boolean {
  return prefixes.some(
    (p) =>
      folder.rel === p || // exakter Treffer
      folder.rel.startsWith(p + "/") || // Ordner liegt im Prefix
      p.startsWith(folder.rel + "/"), // Ordner ist Vorfahr des Prefix
  );
}

interface RowProps {
  depth: number;
  activePath: string | null;
  defaultExpandedPrefixes: string[];
  onSelect: (path: string) => void;
}

// Dispatcher — hält die Hook-Reihenfolge stabil (Datei: kein Hook, Ordner: useState).
function TreeNodeRow({ node, ...props }: RowProps & { node: TreeNode }) {
  return node.type === "file" ? (
    <TreeFileRow node={node} {...props} />
  ) : (
    <TreeFolderRow node={node} {...props} />
  );
}

function TreeFileRow({
  node,
  depth,
  activePath,
  onSelect,
}: RowProps & { node: Extract<TreeNode, { type: "file" }> }) {
  const active = activePath === node.path;
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(node.path)}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        className={cn(
          "flex w-full items-center gap-1.5 rounded-md py-1.5 pr-2 text-left text-sm transition-colors",
          active
            ? "bg-accent font-medium text-accent-foreground"
            : "text-foreground/90 hover:bg-accent/50",
        )}
      >
        <FileTextIcon className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate">{node.name.replace(/\.md$/i, "")}</span>
      </button>
    </li>
  );
}

function TreeFolderRow({
  node,
  depth,
  activePath,
  defaultExpandedPrefixes,
  onSelect,
}: RowProps & { node: Extract<TreeNode, { type: "folder" }> }) {
  const [open, setOpen] = useState(() =>
    shouldExpand(node, defaultExpandedPrefixes),
  );
  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        className="flex w-full items-center gap-1 rounded-md py-1.5 pr-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"
      >
        {open ? (
          <ChevronDownIcon className="size-3.5 shrink-0" />
        ) : (
          <ChevronRightIcon className="size-3.5 shrink-0" />
        )}
        <FolderIcon className="size-3.5 shrink-0" />
        <span className="truncate">{node.name}</span>
      </button>
      {open && (
        <ul className="flex flex-col gap-0.5">
          {node.children.map((child) => (
            <TreeNodeRow
              key={child.type === "folder" ? `d:${child.rel}` : `f:${child.path}`}
              node={child}
              depth={depth + 1}
              activePath={activePath}
              defaultExpandedPrefixes={defaultExpandedPrefixes}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
