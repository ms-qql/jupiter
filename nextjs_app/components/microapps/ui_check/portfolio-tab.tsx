"use client";

// PROJ-21 (BUG-2 Fix): Portfolio-Tab zeigt den echten Registry-Katalog aus
// registry/registry.json statt statischer Stat-Karten. Liest über
// useUiCheckRegistry() (GET /ui-check/registry). Keine eigene
// Registry-/Scoring-Logik im Frontend — nur Filtern und Anzeigen.
//
// Hinweis: Der Backend-Vertrag liefert kein `preview_path`/Bild-Vorschau-Feld
// (siehe backend/app/schemas/ui_check.py UiCheckRegistryItem). Als nächstbeste
// technische Referenz wird deshalb der erste Datei-Pfad des Items gezeigt,
// klar als "Datei" statt "Vorschau" beschriftet.

import { useMemo, useState } from "react";
import { AlertTriangleIcon, BlocksIcon, FileCode2Icon, SearchIcon } from "lucide-react";
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
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { UiCheckRegistryItem } from "@/lib/types";
import { isGalleryItem, useUiCheckRegistry } from "./registry-data";
import { HalRegistryPanel } from "./hal-registry-panel";

const ALL = "__all__";

function distinct(values: (string | null | undefined)[]): string[] {
  return [...new Set(values.filter((v): v is string => Boolean(v)))].sort((a, b) =>
    a.localeCompare(b, "de"),
  );
}

function itemMatchesText(item: UiCheckRegistryItem, query: string): boolean {
  if (!query.trim()) return true;
  const haystack = `${item.name} ${item.title ?? ""} ${item.description ?? ""}`.toLowerCase();
  return haystack.includes(query.trim().toLowerCase());
}

export function PortfolioTab() {
  const { items, loading, error, reload } = useUiCheckRegistry();
  const [search, setSearch] = useState("");
  const [sectionFilter, setSectionFilter] = useState(ALL);
  const [industryFilter, setIndustryFilter] = useState(ALL);
  const [styleFilter, setStyleFilter] = useState(ALL);
  const [sourceFilter, setSourceFilter] = useState(ALL);
  const [slotsFilter, setSlotsFilter] = useState(ALL);
  const [interactiveFilter, setInteractiveFilter] = useState(ALL);
  const [selectedItem, setSelectedItem] = useState<UiCheckRegistryItem | null>(null);

  const galleryItems = useMemo(() => items.filter(isGalleryItem), [items]);

  const sectionOptions = useMemo(() => distinct(galleryItems.map((i) => i.section)), [galleryItems]);
  const industryOptions = useMemo(
    () => distinct(galleryItems.flatMap((i) => i.industry ?? [])),
    [galleryItems],
  );
  const sourceOptions = useMemo(() => distinct(galleryItems.map((i) => i.source)), [galleryItems]);

  const filtered = useMemo(() => {
    return galleryItems.filter((item) => {
      if (!itemMatchesText(item, search)) return false;
      if (sectionFilter !== ALL && item.section !== sectionFilter) return false;
      if (industryFilter !== ALL && !(item.industry ?? []).includes(industryFilter)) return false;
      if (styleFilter !== ALL && item.style !== styleFilter) return false;
      if (sourceFilter !== ALL && item.source !== sourceFilter) return false;
      const slotCount = item.image_slots?.length ?? 0;
      if (slotsFilter === "none" && slotCount > 0) return false;
      if (slotsFilter === "has" && slotCount === 0) return false;
      if (interactiveFilter === "yes" && item.interactive !== true) return false;
      if (interactiveFilter === "no" && item.interactive === true) return false;
      return true;
    });
  }, [
    galleryItems,
    search,
    sectionFilter,
    industryFilter,
    styleFilter,
    sourceFilter,
    slotsFilter,
    interactiveFilter,
  ]);

  const templates = filtered.filter((i) => i.type === "registry:template");
  const blocks = filtered.filter((i) => i.type !== "registry:template");

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangleIcon className="size-4 text-amber-500" />
            Registry-Katalog nicht lesbar
          </CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Dashboard und bestehende Run-Ergebnisse bleiben unabhängig davon nutzbar.
          </p>
          <Button type="button" variant="outline" size="sm" className="mt-3" onClick={reload}>
            Erneut versuchen
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Tabs defaultValue="catalog">
        <TabsList>
          <TabsTrigger value="catalog">Katalog</TabsTrigger>
          <TabsTrigger value="hal">Hal↔Registry</TabsTrigger>
        </TabsList>

        <TabsContent value="catalog" className="mt-4 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Registry-Filter</CardTitle>
          <CardDescription>
            Katalog aus registry/registry.json — Templates, Komponenten und Blocks.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="portfolio-search">Suche</Label>
            <div className="relative">
              <SearchIcon className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="portfolio-search"
                className="pl-8"
                placeholder="Name, Titel oder Beschreibung"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <div className="space-y-1.5">
              <Label>Section-Typ</Label>
              <Select value={sectionFilter} onValueChange={(v) => v && setSectionFilter(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>Alle</SelectItem>
                  {sectionOptions.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Industrie</Label>
              <Select value={industryFilter} onValueChange={(v) => v && setIndustryFilter(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>Alle</SelectItem>
                  {industryOptions.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Stil</Label>
              <Select value={styleFilter} onValueChange={(v) => v && setStyleFilter(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>Alle</SelectItem>
                  <SelectItem value="safe">Safe</SelectItem>
                  <SelectItem value="bold">Bold</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Quelle</Label>
              <Select value={sourceFilter} onValueChange={(v) => v && setSourceFilter(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>Alle</SelectItem>
                  {sourceOptions.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Bild-Slots</Label>
              <Select value={slotsFilter} onValueChange={(v) => v && setSlotsFilter(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>Alle</SelectItem>
                  <SelectItem value="none">Ohne Bilder</SelectItem>
                  <SelectItem value="has">Mit Bildern</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Interaktivität</Label>
              <Select
                value={interactiveFilter}
                onValueChange={(v) => v && setInteractiveFilter(v)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>Alle</SelectItem>
                  <SelectItem value="yes">Interaktiv</SelectItem>
                  <SelectItem value="no">Statisch</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-40 rounded-lg" />
          ))}
        </div>
      ) : galleryItems.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            Registry-Katalog ist leer (registry/registry.json enthält keine Templates/Blocks).
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            Keine Treffer für die aktuelle Filterkombination.
          </CardContent>
        </Card>
      ) : (
        <>
          {templates.length > 0 && (
            <div className="space-y-2">
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <FileCode2Icon className="size-4" /> Templates ({templates.length})
              </h2>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {templates.map((item) => (
                  <RegistryCard key={item.name} item={item} onDetails={() => setSelectedItem(item)} />
                ))}
              </div>
            </div>
          )}
          <div className="space-y-2">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <BlocksIcon className="size-4" /> Komponenten & Blocks ({blocks.length})
            </h2>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {blocks.map((item) => (
                <RegistryCard key={item.name} item={item} onDetails={() => setSelectedItem(item)} />
              ))}
            </div>
          </div>
        </>
      )}

      <Dialog open={selectedItem !== null} onOpenChange={(open) => !open && setSelectedItem(null)}>
        <DialogContent className="max-w-lg">
          {selectedItem && (
            <>
              <DialogHeader>
                <DialogTitle>{selectedItem.title ?? selectedItem.name}</DialogTitle>
                <DialogDescription>{selectedItem.name}</DialogDescription>
              </DialogHeader>
              <div className="space-y-3 text-sm">
                <p className="text-muted-foreground">
                  {selectedItem.description ?? "Keine Beschreibung hinterlegt."}
                </p>
                <div className="grid grid-cols-2 gap-2 rounded-lg border border-border p-3 text-xs">
                  <div>
                    <div className="text-muted-foreground">Section</div>
                    <div className="font-medium">{selectedItem.section ?? "n/v"}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Stil</div>
                    <div className="font-medium">{selectedItem.style ?? "n/v"}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Quelle</div>
                    <div className="font-medium">{selectedItem.source ?? "n/v"}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Bild-Slots</div>
                    <div className="font-medium">{selectedItem.image_slots.length}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Interaktiv</div>
                    <div className="font-medium">{selectedItem.interactive ? "Ja" : "Nein"}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Assembler-auswählbar</div>
                    <div className="font-medium">{selectedItem.assembler_selectable ? "Ja" : "Nein"}</div>
                  </div>
                </div>
                {selectedItem.industry.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {selectedItem.industry.map((tag) => (
                      <Badge key={tag} variant="outline">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}
                {selectedItem.files.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    Datei: {selectedItem.files[0].path}
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
        </TabsContent>

        <TabsContent value="hal" className="mt-4">
          <HalRegistryPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RegistryCard({
  item,
  onDetails,
}: {
  item: UiCheckRegistryItem;
  onDetails: () => void;
}) {
  const referenceFile = item.files[0]?.path ?? null;
  return (
    <Card size="sm" className="flex flex-col justify-between">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm">{item.title ?? item.name}</CardTitle>
          {item.assembler_selectable && (
            <Badge variant="outline" className="shrink-0 text-xs">
              Assembler
            </Badge>
          )}
        </div>
        <CardDescription className="font-mono text-xs">{item.name}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {item.description ?? "Keine Beschreibung hinterlegt."}
        </p>
        <div className="flex flex-wrap gap-1.5 text-xs">
          {item.section && <Badge variant="secondary">{item.section}</Badge>}
          {item.style && <Badge variant="outline">{item.style}</Badge>}
          {item.image_slots.length > 0 && (
            <Badge variant="outline">{item.image_slots.length} Bild-Slots</Badge>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 pt-1">
          <span className="truncate text-xs text-muted-foreground" title={referenceFile ?? undefined}>
            {referenceFile ?? "Keine Datei hinterlegt"}
          </span>
          <Button type="button" variant="outline" size="sm" onClick={onDetails}>
            Details
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
