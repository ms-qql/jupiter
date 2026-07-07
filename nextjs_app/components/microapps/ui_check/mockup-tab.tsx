"use client";

// PROJ-21: Ersetzt den bisherigen Haupttab "Vorher/Nachher". Der Fokus liegt auf
// dem Mockup-Ergebnis: mockup.html, Safe/Bold-Gates, Bildfüllstatus,
// Registry-Auswahl und Score-Delta. Vorher/Nachher bleibt als sekundärer
// Abschnitt erhalten, wenn Original-Screenshots vorhanden sind.

import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  ImageIcon,
  RotateCcwIcon,
  WandSparklesIcon,
  XCircleIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  UiCheckImageFillStatus,
  UiCheckRunDetail,
  UiCheckSectionSelection,
} from "@/lib/types";
import { ArtifactButton, fmtScore } from "./shared";
import { hasImagesFilled, hasMockupExisting, hasRedesignArtifacts } from "./pipeline-modes";

function GateRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok ? (
        <CheckCircle2Icon className="size-4 shrink-0 text-emerald-500" />
      ) : (
        <XCircleIcon className="size-4 shrink-0 text-muted-foreground" />
      )}
      <span className={ok ? "" : "text-muted-foreground"}>{label}</span>
    </div>
  );
}

function ImageFillCard({ images }: { images: UiCheckImageFillStatus | undefined }) {
  if (!images || images.total_slots === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        Noch keine Bild-Slot-Daten (images-fill.json fehlt).
      </div>
    );
  }
  return (
    <div className="space-y-2">
      <GateRow label="Alle Bild-Slots befüllt" ok={images.placeholder_slots === 0} />
      <div className="text-xs text-muted-foreground">
        {images.filled_slots} von {images.total_slots} Slots befüllt
        {images.placeholder_slots > 0 && ` · ${images.placeholder_slots} Platzhalter offen`}
      </div>
    </div>
  );
}

function RegistrySelectionList({
  title,
  items,
}: {
  title: string;
  items: UiCheckSectionSelection[];
}) {
  return (
    <div>
      <div className="text-xs font-medium text-muted-foreground">{title}</div>
      {items.length === 0 ? (
        <div className="mt-1 text-xs text-muted-foreground">Keine Registry-Auswahl vorhanden.</div>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          {items.map((item, i) => (
            <Badge
              key={`${title}-${item.id ?? item.type ?? i}`}
              variant={item.decision === "registry" ? "outline" : "secondary"}
              title={item.reason ?? undefined}
            >
              {item.id ?? item.type ?? "Sektion"}:{" "}
              {item.decision === "registry" ? item.block ?? "Registry" : "Generiert"}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

export function MockupTab({
  detail,
  busy,
  onRedesign,
  onImages,
  onExport,
  onForceExport,
  conflictOpen,
  onDismissConflict,
}: {
  detail: UiCheckRunDetail | null;
  busy: boolean;
  onRedesign: () => void;
  onImages: () => void;
  onExport: () => void;
  onForceExport: () => void;
  conflictOpen: boolean;
  onDismissConflict: () => void;
}) {
  const redesignExists = hasRedesignArtifacts(detail);
  const imagesFilled = hasImagesFilled(detail);
  const mockupExists = hasMockupExisting(detail);
  const hasScreens = Boolean(detail?.artifacts?.screenshots?.length);
  const scoreDelta =
    detail?.mockup_status?.score_delta ??
    (typeof detail?.score_total === "number" && typeof detail?.redesign_score === "number"
      ? detail.redesign_score - detail.score_total
      : null);
  const safeReady = detail?.mockup_status?.safe_ready ?? false;
  const boldReady = detail?.mockup_status?.bold_ready ?? false;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Mockup-Ergebnis</CardTitle>
            <CardDescription>
              Self-contained mockup.html aus dem Redesign-Prozess (Safe/Bold, Bilder base64
              eingebettet).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid min-h-56 place-items-center rounded-lg border border-dashed border-border bg-muted/40 p-6 text-center">
              {!detail?.run_id ? (
                <div>
                  <ImageIcon className="mx-auto size-10 text-muted-foreground" />
                  <div className="mt-3 text-sm font-medium">Kein Lauf ausgewählt</div>
                  <p className="mt-1 max-w-md text-sm text-muted-foreground">
                    Im Dashboard einen Lauf aus der Historie wählen, um dessen Mockup-Status zu
                    sehen.
                  </p>
                </div>
              ) : mockupExists ? (
                <div>
                  <WandSparklesIcon className="mx-auto size-10 text-emerald-500" />
                  <div className="mt-3 text-sm font-medium">mockup.html ist verfügbar</div>
                  <p className="mt-1 max-w-md text-sm text-muted-foreground">
                    Authentifiziert öffnen — der Link umgeht die Jupiter-Auth nicht.
                  </p>
                  <div className="mt-4 flex justify-center gap-2">
                    <ArtifactButton runId={detail.run_id} kind="mockup" label="Mockup öffnen" />
                    <Button type="button" variant="outline" size="sm" onClick={onForceExport} disabled={busy}>
                      <RotateCcwIcon className="size-3.5" />
                      Neu-Export erzwingen
                    </Button>
                  </div>
                </div>
              ) : !redesignExists ? (
                <div>
                  <ImageIcon className="mx-auto size-10 text-muted-foreground" />
                  <div className="mt-3 text-sm font-medium">Noch kein Mockup vorhanden</div>
                  <p className="mt-1 max-w-md text-sm text-muted-foreground">
                    Für diesen Lauf existiert noch kein Redesign-Ordner mit Safe/Bold-Varianten.
                  </p>
                  <div className="mt-4 flex justify-center">
                    <Button type="button" size="sm" onClick={onRedesign} disabled={busy}>
                      <RotateCcwIcon className="size-3.5" />
                      Redesign nachziehen
                    </Button>
                  </div>
                </div>
              ) : !imagesFilled ? (
                <div>
                  <ImageIcon className="mx-auto size-10 text-amber-500" />
                  <div className="mt-3 text-sm font-medium">Redesign vorhanden, Bilder fehlen</div>
                  <p className="mt-1 max-w-md text-sm text-muted-foreground">
                    Die Bild-Slots sind noch Platzhalter. Vor dem Export empfiehlt sich die
                    Bildbefüllung.
                  </p>
                  <div className="mt-4 flex justify-center gap-2">
                    <Button type="button" size="sm" onClick={onImages} disabled={busy}>
                      <ImageIcon className="size-3.5" />
                      Bilder füllen
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={onExport} disabled={busy}>
                      Trotzdem exportieren
                    </Button>
                  </div>
                </div>
              ) : (
                <div>
                  <WandSparklesIcon className="mx-auto size-10 text-muted-foreground" />
                  <div className="mt-3 text-sm font-medium">Bereit für den Mockup-Export</div>
                  <p className="mt-1 max-w-md text-sm text-muted-foreground">
                    Redesign und Bilder sind vorhanden — mockup.html wurde noch nicht exportiert.
                  </p>
                  <div className="mt-4 flex justify-center">
                    <Button type="button" size="sm" onClick={onExport} disabled={busy}>
                      Mockup exportieren
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {hasScreens && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Vorher/Nachher (Details)</CardTitle>
              <CardDescription>
                Sekundäre Ansicht — der Hauptvergleich lebt im exportierten mockup.html.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between gap-3 rounded-lg border border-border p-3 text-sm">
                <div className="flex gap-4">
                  <span>
                    Original <strong>{fmtScore(detail?.score_total ?? null)}</strong>
                  </span>
                  <span>
                    Nachher <strong>{fmtScore(detail?.redesign_score ?? null)}</strong>
                  </span>
                </div>
                {detail?.run_id && (
                  <ArtifactButton runId={detail.run_id} kind="screenshots" label="Screenshots" />
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Safe / Bold</CardTitle>
            <CardDescription>Vorhandene Redesign-Varianten dieses Laufs.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="rounded-lg border border-border p-3">
              <GateRow label="Safe vorhanden" ok={safeReady} />
            </div>
            <div className="rounded-lg border border-border p-3">
              <GateRow label="Bold vorhanden" ok={boldReady} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Bildfüllstatus</CardTitle>
            <CardDescription>Slots aus redesign/images-fill.json (PROJ-20).</CardDescription>
          </CardHeader>
          <CardContent>
            <ImageFillCard images={detail?.mockup_status?.images} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Score-Delta</CardTitle>
          </CardHeader>
          <CardContent>
            {scoreDelta === null ? (
              <div className="text-sm text-muted-foreground">
                Noch kein Score-Delta verfügbar.
              </div>
            ) : (
              <div className={`text-2xl font-semibold ${scoreDelta >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                {scoreDelta >= 0 ? "+" : ""}
                {Math.round(scoreDelta)}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Registry-Auswahl</CardTitle>
            <CardDescription>Entscheidung je Sektion: Registry-Block oder Generierung.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail?.registry_selection &&
            (detail.registry_selection.safe.length > 0 || detail.registry_selection.bold.length > 0) ? (
              <>
                <RegistrySelectionList title="Safe" items={detail.registry_selection.safe} />
                <RegistrySelectionList title="Bold" items={detail.registry_selection.bold} />
              </>
            ) : (
              <div className="text-sm text-muted-foreground">
                Noch keine Registry-Auswahl für diesen Lauf vorhanden.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={conflictOpen} onOpenChange={(open) => !open && onDismissConflict()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangleIcon className="size-4 text-amber-500" />
              mockup.html existiert bereits
            </DialogTitle>
            <DialogDescription>
              Für diesen Lauf liegt bereits ein exportiertes Mockup vor. Ein Neu-Export
              überschreibt die bestehende Datei nicht automatisch — erst nach Bestätigung.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onDismissConflict}>
              Abbrechen
            </Button>
            <Button
              type="button"
              onClick={() => {
                onDismissConflict();
                onForceExport();
              }}
            >
              <RotateCcwIcon className="size-3.5" />
              Neu-Export erzwingen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
