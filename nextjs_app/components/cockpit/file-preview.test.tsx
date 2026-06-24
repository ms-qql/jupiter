// PROJ-28 QA: Render-Tests für FilePreview ohne jsdom (renderToStaticMarkup).
// Geprüft werden die synchronen Zweige (Empty / Bild / Binär / zu groß / Header)
// sowie der initiale Lade-Zustand für Text/MD (der fetch-Effect läuft im SSR-
// Render nicht — die Initial-State-Logik wird damit deterministisch testbar).

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { FilePreview } from "./file-preview";
import type { FileEntry } from "@/lib/types";

function entry(name: string, size = 100): FileEntry {
  return { name, kind: "file", size, mtime: "2026-06-24T00:00:00Z", path: `/root/${name}` };
}

function render(e: FileEntry | null) {
  return renderToStaticMarkup(<FilePreview entry={e} />);
}

describe("FilePreview", () => {
  it("zeigt Empty-State ohne Auswahl", () => {
    const html = render(null);
    expect(html).toContain("Wähle links eine Datei");
    expect(html).not.toContain("Herunterladen");
  });

  it("rendert Bilder als <img> mit Download-Link auf /files/download", () => {
    const html = render(entry("foto.png"));
    expect(html).toMatch(/<img[^>]+src="[^"]*\/files\/download/);
    expect(html).toContain("Herunterladen");
  });

  it("zeigt Hinweis + Download für Binär-/unbekannte Typen (kein Preview-Fehler)", () => {
    const html = render(entry("archiv.zip"));
    expect(html).toContain("keine Vorschau");
    expect(html).toContain("Herunterladen");
  });

  it("blockt zu große Text-/MD-Dateien mit Hinweis statt Render", () => {
    const html = render(entry("riesig.txt", 5_000_000));
    expect(html).toContain("zu groß");
    expect(html).toContain("Herunterladen");
  });

  it("startet bei Text/MD im Lade-Zustand (fetch via Effect)", () => {
    expect(render(entry("notiz.md"))).toContain("Lädt…");
    expect(render(entry("config.yaml"))).toContain("Lädt…");
    expect(render(entry("daten.json"))).toContain("Lädt…");
  });

  it("zeigt Dateiname + Größe im Kopf", () => {
    const html = render(entry("readme.txt", 2048));
    expect(html).toContain("readme.txt");
    expect(html).toContain("2.0 KB");
  });
});
