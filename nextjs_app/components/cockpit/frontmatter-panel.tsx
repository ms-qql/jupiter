"use client";

// PROJ-7: zeigt YAML-Frontmatter als saubere Key/Value-Tabelle (NICHT als Rohtext).
// Das Backend liefert es bereits geparst getrennt vom Body.

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.map(renderValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function FrontmatterPanel({
  frontmatter,
}: {
  frontmatter: Record<string, unknown>;
}) {
  const entries = Object.entries(frontmatter ?? {});
  if (entries.length === 0) return null;

  return (
    <dl className="mb-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg border border-border bg-card/40 px-4 py-3 text-sm">
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="font-medium text-muted-foreground">{key}</dt>
          <dd className="min-w-0 break-words">{renderValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
