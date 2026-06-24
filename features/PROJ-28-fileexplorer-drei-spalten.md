# PROJ-28: Fileexplorer Drei-Spalten-Layout (Sidebar · Datei-Panel · Ansicht)

## Status: Approved
**Created:** 2026-06-24
**Last Updated:** 2026-06-24

## Implementation Notes (Frontend, 2026-06-24)
- **`app/(cockpit)/dateien/page.tsx`** → Thin-Wrapper, rendert nur noch `<FileExplorer />` (volles Layout liegt wie bei Doku in der Komponente).
- **`components/cockpit/file-explorer.tsx`** → auf 3-Spalten umgebaut: `flex h-dvh flex-col` (Header) + `flex min-h-0 flex-1` (Body) mit `aside w-80` (Datei-Panel, `ScrollArea`) und `main flex-1 min-w-0 overflow-y-auto` (Vorschau). Cockpit-Sidebar kommt unverändert aus `CockpitShell`. Alle PROJ-11-Operationen erhalten (Upload Drag/Paste/Dialog, Pfad kopieren, Umbenennen, Löschen, Download, Clipboard-Pin, RootSelector). RootSelector + Drop-Zone sitzen jetzt im Datei-Panel; Toolbar im Header.
- **`components/cockpit/file-preview.tsx`** (NEU) → Typ-Dispatch via Endung: `.md`→`MarkdownView` (leerer Wikilink-Index), Text/Code inkl. `.txt`/`.yaml`/`.yml`/`.json`/… → monospace `<pre>`, Bilder → `<img src=downloadUrl>`, Binär/zu-groß → Hinweis + Download. Inhalt aus bestehendem `/files/download` (`fetch().text()`), **keine Backend-Änderung**.
- **Edge Cases:** ausgewählte Datei wird aus dem aktuellen Listing abgeleitet → Löschen/Umbenennen/Wegnavigieren ⇒ automatisch Empty-State (kein toter Verweis). Größen-Limit 2 MB (Text/MD) gegen Browser-Hänger; `<pre>` zusätzlich auf 200 KB gekürzt mit Hinweis. `FilePreview` wird per `key={path}` remountet (frischer Lade-Stand, konform zur „setState nur in Callbacks"-Konvention).
- **Responsive:** `md+` zeigt Panel + Ansicht nebeneinander; `<md` schaltet Panel ⇄ Ansicht um (Datei-Klick → Ansicht, „← Liste"-Button zurück), kein Horizontal-Overflow.
- **Verifikation:** ESLint clean; tsc fehlerfrei für die geänderten Dateien (einziger tsc-Fehler ist vorbestehend in `lib/md-tree.test.ts`, unabhängig).

## QA Test Results (2026-06-24)
**Tester:** QA Engineer · **Branch:** dev · **Methode:** Code-Review gegen Acceptance Criteria + statische Verifikation (vitest, ESLint, `next build` inkl. TypeScript). Reines Frontend-Feature ohne Backend-/Auth-Oberfläche.

### Automatisierte Verifikation
- `npx vitest run` → **94/94 grün** (88 Bestand + 6 neue für `FilePreview`); kein Regress.
- Neue Tests: `components/cockpit/file-preview.test.tsx` (Empty / Bild / Binär / zu-groß / Lade-Zustand Text+MD / Datei-Kopf).
- `next build` → erfolgreich, TypeScript fehlerfrei, `/dateien` prerendered.
- ESLint über alle geänderten/neuen Dateien → clean (inkl. `react-hooks/set-state-in-effect`).

### Acceptance Criteria
| # | Kriterium | Ergebnis |
|---|-----------|----------|
| 1 | Dreispaltig (Sidebar · Panel · Ansicht) | ✅ Pass — Cockpit-Sidebar via `CockpitShell`, `aside w-80`, `main flex-1`. |
| 2 | Aufbau wie Doku-Ansicht (PROJ-7) | ✅ Pass — identisches `flex h-dvh`/`min-h-0 flex-1`-Muster + `ScrollArea`. |
| 3 | Datei-Klick → Preview, Ordner-Klick → navigiert | ✅ Pass — `selectFile()` vs. `openDir()`. |
| 4 | Alle PROJ-11-Operationen erreichbar | ✅ Pass — Upload (Drag aufs Panel / globaler Paste / Dialog), Pfad kopieren (Header + je Eintrag), Umbenennen, Löschen, Download (je Eintrag + Vorschau-Kopf), Clipboard-Pin, RootSelector. |
| 5 | Binär/nicht-darstellbar → Hinweis + Download, kein Preview-Fehler | ✅ Pass — `PreviewHint` + Download-Button. |
| 6 | Responsive: Panel kollabiert, umschaltbar, kein H-Overflow | ✅ Pass — `mobilePane`-Toggle (`hidden md:flex`/`block`), Header `flex-wrap`, Pfad auf Mobil ausgeblendet. |
| 7 | Lade-/Fehler-/Leer-Zustände explizit, deutsch | ✅ Pass — „Lädt…", Fehlerbox, Empty-States; durchgehend deutsch. |

### Edge Cases
- Lange Listen → Panel-`ScrollArea` scrollt unabhängig von der Ansicht. ✅
- Keine Auswahl → neutraler Empty-State. ✅
- Sehr große Datei → 2 MB-Gate (Text/MD) + `<pre>`-Kürzung auf 200 KB mit Hinweis; `MarkdownView` kürzt zusätzlich bei 400 KB. ✅
- Schmaler Viewport → Panel/Ansicht nie gleichzeitig gequetscht. ✅
- Ausgewählte Datei gelöscht/umbenannt → `selectedEntry` aus dem Listing abgeleitet ⇒ Empty-State, kein toter Verweis (zusätzlich `setSelectedPath(null)`). ✅

### Security
Lokales Single-User-Tool (kein JWT/RLS im MVP). Kein neuer Endpunkt; Vorschau nutzt das bestehende `/files/download` (Root-Whitelist serverseitig aus PROJ-11). Kein neuer Angriffsvektor:
- Text → `<pre>` (React escaped) · MD → gehärtete `MarkdownView` (ohne `rehype-raw`, separat getestet) · kein `dangerouslySetInnerHTML`.
- CORS: app-weite `CORSMiddleware` deckt `/files/download` mit ab → `fetch()`-Vorschau funktioniert überall, wo der restliche API-Client läuft.
- `Content-Disposition: attachment` (FileResponse) stört weder `fetch().text()` noch `<img>`.

### Bugs
Keine Critical/High/Medium. Beobachtungen (Low, nicht blockierend):
- **L1:** Bild mit korrektem Suffix, das nicht ladbar ist, zeigt ein gebrochenes `<img>` (kein `onError`-Fallback auf Download). Reiner Edge-UX.
- **L2:** `formatBytes` ist in `file-explorer.tsx` und `file-preview.tsx` dupliziert — Refactor-Kandidat (`/abc-refactor`).
- **L3:** `h-dvh` unter `CockpitShell` (mit Mobile-Topbar) kann auf Mobil minimal überstehen — **identisch zur bereits deployten Doku-Ansicht**, daher konsistent.

### Fazit
**Production-Ready: JA.** 7/7 Acceptance Criteria bestanden, alle Edge Cases abgedeckt, keine Critical/High/Medium-Bugs, keine Regression.

## Dependencies
- Requires: PROJ-11 (Fileexplorer) — verändert dessen Surface A (`/dateien`-Ansicht) von Vollbild auf ein dreigeteiltes Layout.
- Requires: PROJ-7 (MD-Reader / Doku) — dient als **Layout-Vorbild** (Sidebar + schmales Listen-/Baum-Panel + große Inhaltsansicht).

## Beschreibung
Der Fileexplorer (PROJ-11, Surface A) nutzt heute den **kompletten Bildschirm**. Gewünscht ist stattdessen ein **dreigeteiltes Layout** analog zur Doku-Ansicht:

1. **Sidebar** (wie überall im Cockpit),
2. ein **zweites, schmales Fenster/Panel** mit der **Datei-/Verzeichnis-Darstellung** (Baum/Liste),
3. ein **großes Fenster** mit der **Ansicht der aktuell ausgewählten Datei** (Vorschau/Inhalt).

So bleibt — wie bei Doku — die Navigation kompakt links, während die eigentliche Datei-Ansicht den großen Bereich einnimmt; das übrige Cockpit (u. a. das Terminalfenster) bleibt mental/visuell im selben Schema erreichbar, statt vom Vollbild-Explorer verdeckt zu werden.

## User Stories
- Als Nutzer möchte ich im Fileexplorer **links die Sidebar, daneben ein schmales Datei-Panel und rechts eine große Datei-Ansicht** sehen, damit der Explorer nicht den ganzen Bildschirm einnimmt.
- Als Nutzer möchte ich dieselbe Aufteilung wie in der Doku-Ansicht wiedererkennen, damit die Bedienung konsistent ist.
- Als Nutzer möchte ich eine Datei im schmalen Panel auswählen und ihren Inhalt sofort im großen Bereich sehen, ohne die Navigation zu verlieren.
- Als Nutzer möchte ich, dass die Datei-Operationen (Upload, Pfad kopieren, Umbenennen, Löschen, Download) aus PROJ-11 im neuen Layout weiter erreichbar bleiben.

## Acceptance Criteria
- [ ] Die `/dateien`-Ansicht ist **dreispaltig**: (1) Cockpit-Sidebar, (2) schmales Datei-/Verzeichnis-Panel (Baum/Liste + Breadcrumb), (3) großer Inhalts-/Vorschau-Bereich der aktuell gewählten Datei.
- [ ] Das Layout entspricht im Aufbau der **Doku-Ansicht** (PROJ-7) — konsistente Spaltenlogik/-proportionen.
- [ ] Auswahl einer Datei im Panel rendert ihren Inhalt/Preview im großen Bereich; Ordner-Klick navigiert im Panel.
- [ ] **Alle bestehenden PROJ-11-Operationen** (Upload via Drag-and-Drop/Paste/Dialog, „Pfad kopieren", Umbenennen, Löschen, Download, Clipboard-Pin, RootSelector) bleiben im neuen Layout funktional erreichbar.
- [ ] Der große Bereich rendert **Markdown** (`.md`), **Text/Code inkl. `.txt`, `.yaml`/`.yml`** (sowie `.json`, `.log`, `.csv`, `.xml` u. ä. als Roh-`<pre>`) und **Bilder** inline.
- [ ] Für **nicht-darstellbare/Binär-Dateien** zeigt der große Bereich einen klaren Hinweis + Download (kein Preview-Fehler), konsistent mit PROJ-11.
- [ ] **Responsive:** Auf schmalen Breiten kollabiert das Datei-Panel sinnvoll (z. B. Panel ↔ Ansicht umschaltbar), kein horizontaler Overflow; Desktop-first.
- [ ] Lade-/Fehler-/Leer-Zustände explizit; alle Texte deutsch.

## Edge Cases
- **Sehr lange Datei-/Ordnerlisten** → Datei-Panel scrollt unabhängig vom Inhalts-Bereich.
- **Keine Datei ausgewählt** → großer Bereich zeigt neutralen Empty-State („Datei links wählen").
- **Sehr große oder sehr lange Datei** in der Ansicht → performant rendern/streamen oder abschneiden mit Hinweis (kein Browser-Hänger).
- **Schmaler Viewport (Tablet/Mobil)** → Panel und Ansicht nicht gleichzeitig quetschen; umschaltbare Darstellung.
- **Ausgewählte Datei wird gelöscht/umbenannt** → Ansicht reagiert sauber (Empty-State bzw. aktualisierte Auswahl), kein toter Verweis.

## Technical Requirements (optional)
- Reines **Frontend-Layout-Refactor** der bestehenden `file-explorer.tsx`/`/dateien`-Route; keine Backend-/API-Änderung (das `/files`-API aus PROJ-11 bleibt unverändert).
- Layout/Spalten über das vorhandene Doku-Layout-Muster (PROJ-7) wiederverwenden statt neu erfinden (shadcn-first, kein Hand-Roll vorhandener Primitives).
- Inhalts-Ansicht nutzt die bestehende Datei-Vorschau-Logik; verhaltenswahrend gegenüber PROJ-11.

## Open Design Questions (in /abc-architecture zu klären)
1. **Spaltenbreiten fix oder resizable?** _Default-Vorschlag:_ feste, an die Doku-Ansicht angelehnte Proportionen im MVP; Resizable als optionaler Ausbau.
2. **Preview-Umfang im großen Bereich** — nur MD/Text/Bild oder mehr? _Default:_ wie PROJ-11 (Text/MD/Bild; Binär → Download-Hinweis), kein neuer Renderer.

---

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** Next.js 16 (App Router, TS) + Tailwind + shadcn/ui — Frontend-only · **Branch:** dev

### Wichtige Vorab-Korrektur (Befund aus CodeGraph)
Die Spec nimmt an, PROJ-11 habe bereits eine „bestehende Datei-Vorschau-Logik", die nur ins neue Layout zu schieben sei. **Das stimmt nicht:** der heutige Explorer (`components/cockpit/file-explorer.tsx`) ist eine reine **Datei-Verwaltung ohne jede Vorschau** — Dateien sind download-only, eine flache Liste, kein Inhalts-Bereich. Die **Inhalts-Ansicht (Spalte 3) ist damit Neubau**, nicht nur ein Umzug. Der wiederverwendbare Renderer (`MarkdownView`) stammt aus PROJ-7 (Doku) und liest dort aus dem Vault — nicht aus den freien Explorer-Roots. → Mehraufwand gegenüber dem „reinen Layout-Refactor" der Spec, aber weiterhin **ohne Backend-Änderung** machbar (siehe Tech-Entscheidung 3).

### A) Komponenten-Struktur (Ziel-Layout)
Vorbild ist exakt der Doku-Reader (`app/(cockpit)/doku/page.tsx`). Die Cockpit-Sidebar (`SessionRail`) liefert bereits Spalte 1 über `CockpitShell` — **am Shell wird nichts geändert**. Die `/dateien`-Seite baut darin die Spalten 2+3:

```
/dateien  (in CockpitShell → liefert Spalte 1: SessionRail)
└── FileExplorerLayout  (flex h-full flex-col)
    ├── Header  (Breadcrumb + RootSelector + Toolbar: Up · Refresh · Neuer Ordner · Upload · Pfad kopieren)
    └── Body  (flex min-h-0 flex-1)
        ├── Spalte 2 — Datei-Panel  (aside, w-72 shrink-0, border-r, hidden md:flex)
        │   ├── RootSelector (Roots + Clipboard-Pin)
        │   └── ScrollArea (flex-1)
        │       └── Verzeichnis-Liste (Ordner-Klick navigiert · Datei-Klick wählt)
        │           └── pro Datei: Aktionen (Pfad kopieren · Download · Umbenennen · Löschen)
        └── Spalte 3 — Inhalts-Ansicht  (main, min-w-0 flex-1 overflow-y-auto)
            └── FilePreview (NEU)
                ├── Empty-State („Datei links wählen")
                ├── Lade-/Fehler-Zustand
                ├── .md         → MarkdownView (aus PROJ-7 wiederverwendet)
                ├── Text-Typen  → <pre>/Code-Ansicht
                ├── Bild-Typen  → <img src={downloadUrl}>
                └── Binär/zu groß → Hinweis + Download-Button (kein Preview-Fehler)
```

**Responsive:** identisch zu Doku — Spalte 2 `hidden md:flex`. Auf schmalen Breiten wird zwischen **Panel** und **Ansicht** umgeschaltet (eine sichtbar, kein gleichzeitiges Quetschen, kein Horizontal-Overflow). Spalte 1 (SessionRail) kollabiert bereits über `CockpitShell` in den Drawer.

### B) Datenmodell
**Keine Änderung.** Es entstehen keine neuen Tabellen/Felder. Verwendet werden ausschließlich die bestehenden PROJ-11-Strukturen (`RootEntry`, `DirListing`, `FileEntry`). Ein leichter Frontend-State kommt hinzu: `selectedPath` (aktuell gewählte Datei) + abgeleiteter Vorschau-Zustand (laden/inhalt/fehler).

### C) API-Form
**Keine neuen Endpunkte, keine Backend-Änderung.** Genutzt werden die vorhandenen PROJ-11-Endpunkte:
```
GET  /files/roots              → Roots (unverändert)
GET  /files/list?path=…        → Verzeichnis-Inhalt (unverändert)
GET  /files/download?path=…    → liefert die Datei (unverändert) — Doppelrolle: Download UND Vorschau-Quelle
POST /files/upload · mkdir · rename · move · delete   (unverändert)
```
Die Vorschau bezieht den Inhalt aus `/files/download`: für Text/MD via `fetch(downloadUrl).text()`, für Bilder direkt als `<img src={downloadUrl}>`. So bleibt das Feature strikt frontend-only.

### D) Tech-Entscheidungen (Begründung)
1. **Layout 1:1 vom Doku-Reader übernehmen** (genestete Flexbox: `flex h-dvh flex-col` → `flex min-h-0 flex-1` → `aside w-72 shrink-0` + `main flex-1 min-w-0 overflow-y-auto`). Garantiert die geforderte Konsistenz zur Doku-Ansicht und vermeidet Neuerfindung.
2. **Feste Spaltenbreiten (Open Question 1 → fix).** Panel `w-72` wie überall im Cockpit; großer Bereich nimmt den Rest. Kein neues Paket (`react-resizable-panels` ist nicht im Repo). Resizable bleibt optionaler Ausbau.
3. **Vorschau aus dem Download-Endpoint statt neuem `/files/content`-API.** Hält das Versprechen „keine Backend-Änderung" und vermeidet doppelte Datei-Lese-Logik. Trade-off: Text wird einmal vollständig geladen → deshalb **Größen-Limit** (z. B. ab Schwelle X abschneiden + Hinweis), um Browser-Hänger bei sehr großen Dateien zu verhindern (Edge Case der Spec).
4. **Preview-Umfang (Open Question 2 → Default + ausdrücklich Text/YAML/TXT):**
   - `.md` → `MarkdownView` (gerendert, aus PROJ-7).
   - **Text-/Code-Typen → monospace `<pre>`-Ansicht (Roh-Inhalt), ausdrücklich inkl. `.txt`, `.yaml`, `.yml`** sowie `.json`, `.log`, `.csv`, `.xml`, `.toml`, `.ini`, `.env`, `.sh` u. ä. Optional zusätzlich der Markdown-Quelltext, wenn der Nutzer eine `.md` als Rohtext sehen will (nice-to-have, kein MVP-Muss).
   - Bilder → `<img src={downloadUrl}>`.
   - alles andere/Binär/zu-groß → klarer Hinweis + Download.
   - Kein neuer Markdown-Renderer; Syntax-Highlighting ist optionaler Ausbau (MVP: schlichtes `<pre>`).
5. **Verzeichnis-Darstellung bleibt die bestehende flache Liste pro Ebene** (Ordner-Klick navigiert), kein neuer Baum — die `FileTree`-Komponente aus PROJ-7 hängt am Vault-Index und passt nicht ohne Umbau auf die freien Explorer-Roots. Geringeres Risiko, näher an PROJ-11.
6. **Auswahl-Robustheit:** wird die ausgewählte Datei gelöscht/umbenannt, fällt die Ansicht sauber auf Empty-State bzw. neue Auswahl zurück (Spec-Edge-Case).

### E) Abhängigkeiten
**Keine neuen Pakete.** Wiederverwendet: `ScrollArea` (`components/ui/scroll-area.tsx`), `MarkdownView` (`components/cockpit/markdown-view.tsx`), Layout-Muster aus `app/(cockpit)/doku/page.tsx`, sowie alle PROJ-11-Operationen aus `components/cockpit/file-explorer.tsx`.

### Betroffene Dateien (Orientierung für /abc-frontend)
- `nextjs_app/app/(cockpit)/dateien/page.tsx` — von zentrierter Einspalten- auf 3-Spalten-Shell umbauen.
- `nextjs_app/components/cockpit/file-explorer.tsx` — in Header + schmales Datei-Panel (Spalte 2) zerlegen; Operationen erhalten.
- `nextjs_app/components/cockpit/file-preview.tsx` — **NEU** (Spalte 3, Typ-Dispatch MD/Text/Bild/Binär).
- Backend: **unverändert**.
