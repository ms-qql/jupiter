"use client";

// PROJ-21: Sichtbarer Ausführungsplan + Voraussetzungs-Gate fürs Dashboard.
// Übersetzt PIPELINE_MODES (pipeline-modes.ts) in Auswahl, Command-Vorschau
// und ein Voraussetzungs-Checklist-Gate — ohne eigene Pipeline-Logik.

import { CheckCircle2Icon, CircleIcon, TerminalIcon } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { PipelineModeDef, PipelineModeId, PrerequisiteItem } from "./pipeline-modes";

export function PipelineModeSelector({
  modes,
  value,
  onChange,
}: {
  modes: PipelineModeDef[];
  value: PipelineModeId;
  onChange: (id: PipelineModeId) => void;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {modes.map((m) => (
        <button
          key={m.id}
          type="button"
          onClick={() => onChange(m.id)}
          className={`rounded-lg border p-3 text-left transition-colors ${
            value === m.id
              ? "border-primary bg-primary/10"
              : "border-border bg-background hover:bg-muted"
          }`}
        >
          <div className="text-sm font-semibold">{m.label}</div>
          <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {m.description}
          </div>
        </button>
      ))}
    </div>
  );
}

export function CommandPlanPreview({ mode }: { mode: PipelineModeDef }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <TerminalIcon className="size-4" />
          Ausführungsplan
        </CardTitle>
        <CardDescription>
          Fachlicher Skill-Command aus docs/pipeline.md — nur zur Information, nicht
          editierbar.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <pre className="overflow-x-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
          {mode.commandLines.join("\n")}
        </pre>
      </CardContent>
    </Card>
  );
}

export function PrerequisiteChecklist({ items }: { items: PrerequisiteItem[] }) {
  if (items.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Voraussetzungen</CardTitle>
        <CardDescription>
          Fehlende Voraussetzungen sperren den Start-Button für diesen Modus.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-sm">
            {item.satisfied ? (
              <CheckCircle2Icon className="size-4 shrink-0 text-emerald-500" />
            ) : (
              <CircleIcon className="size-4 shrink-0 text-muted-foreground" />
            )}
            <span className={item.satisfied ? "" : "text-muted-foreground"}>
              {item.label}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
