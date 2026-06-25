# PROJ-37: File Explorer — kein leeres Vorschau-Fenster; aktives Fenster (Session) bleibt rechts

## Status: Architected
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-28 (Fileexplorer Drei-Spalten-Layout: Sidebar · Panel · Ansicht) — betrifft die rechte „Ansicht"-Spalte.
- Requires: PROJ-11 (Fileexplorer + Drag-and-Drop) — die Datei-Auswahl-/Preview-Logik.
- Requires: PROJ-3 (Cockpit / Session-Fenster) — das „aktive Fenster", das rechts bestehen bleibt, ist i. d. R. die laufende Session.

## Beschreibung
Im File Explorer (Drei-Spalten-Layout) zeigt die **rechte Ansicht-Spalte** beim ersten Öffnen / bei reiner **Ordnerübersicht** einen **leeren Platzhalter** („Wähle links eine Datei für die Vorschau."). Das ist verschenkter Raum und ein Bruch im Arbeitsfluss.

Gewünscht (Klärung 2026-06-25): Solange **keine Datei mit Vorschau gewählt** ist, soll rechts **das zuletzt aktive Fenster bestehen bleiben — typischerweise das Session-Fenster** — statt eines leeren Platzhalters. **Erst** wenn der Nutzer eine **Datei mit Vorschau anklickt**, wird das aktive Fenster **durch die Datei-Vorschau ersetzt**. Schließt/verlässt er die Datei-Vorschau (bzw. ist keine Datei mehr gewählt), kehrt die rechte Spalte wieder zum aktiven Fenster zurück.

## User Stories
- Als Nutzer möchte ich beim Öffnen des File Explorers **kein leeres Vorschau-Fenster** sehen, sondern weiter mein **aktives Fenster (die laufende Session)**, damit ich beim Stöbern den Kontext nicht verliere.
- Als Nutzer möchte ich, dass **erst ein Klick auf eine Datei mit Vorschau** die rechte Spalte auf die **Datei-Vorschau** umschaltet, damit ich gezielt entscheide, wann die Session weicht.
- Als Nutzer möchte ich, dass die rechte Spalte **zum aktiven Fenster zurückkehrt**, sobald keine Datei mehr ausgewählt ist (z. B. Vorschau geschlossen / Ordner gewechselt), damit ich nahtlos weiterarbeiten kann.
- Als Nutzer möchte ich, dass das Verhalten **nicht** auftritt, wenn es gar kein aktives Fenster gibt (dann ist ein neutraler Hinweis ok), damit nichts „kaputt" wirkt.

## Acceptance Criteria
- [ ] Beim Öffnen des File Explorers **ohne** ausgewählte Datei zeigt die rechte Ansicht-Spalte **das zuletzt aktive Fenster** (i. d. R. die aktuell aktive Session) statt des leeren Platzhalters.
- [ ] Klick auf eine **Datei mit Vorschau** (Bild/Markdown/Text) ersetzt die rechte Spalte durch die **Datei-Vorschau**.
- [ ] Wird die Datei-Auswahl aufgehoben (Datei nicht mehr vorhanden / Ordnerwechsel / Vorschau geschlossen), **kehrt** die rechte Spalte zum aktiven Fenster zurück (kein erneuter Leer-Platzhalter).
- [ ] Klick auf einen **Ordner** (Navigation) lässt die rechte Spalte am **aktiven Fenster**; nur Dateien mit Vorschau wechseln die Ansicht.
- [ ] Gibt es **kein** aktives Fenster (z. B. keine laufende Session), zeigt die rechte Spalte einen **neutralen Hinweis** statt eines Fehlers — der bisherige Platzhalter ist nur dieser Sonderfall.
- [ ] Das **Drei-Spalten-Layout** (PROJ-28) und das mobile Pane-Umschalten (Liste ↔ Ansicht) bleiben funktionsfähig.

## Edge Cases
- **Keine aktive Session vorhanden** → rechts neutraler Hinweis (z. B. „Keine aktive Session — wähle links eine Datei."), kein Leer-Bug, kein Crash.
- **Mehrere Sessions aktiv** → es bleibt **eine** definierte „aktive" Session rechts (zuletzt fokussierte/geöffnete); deterministisch, nicht zufällig wechselnd.
- **Ausgewählte Datei wird gelöscht/umbenannt** → Auswahl fällt auf „keine Datei" zurück → rechts erscheint wieder das aktive Fenster (nicht der Leer-Platzhalter).
- **Datei ohne Vorschau** (Binär) angeklickt → definiertes Verhalten: entweder „Vorschau nicht verfügbar" oder aktives Fenster bleibt — konsistent festgelegt (Vorschlag: Hinweis „Vorschau nicht verfügbar", da der Nutzer aktiv eine Datei wählte).
- **Mobile (schmaler Viewport):** Beim Wechsel in die „Ansicht"-Pane ohne gewählte Datei wird das aktive Fenster gezeigt, nicht der Leer-Platzhalter.
- **Performance:** Das Einblenden der Session rechts darf die laufende Session **nicht doppelt mounten/neu starten** (gemeinsamer Zustand, keine Zweit-Instanz).

## Technical Requirements (optional)
- **Frontend**; betrifft `nextjs_app/components/cockpit/file-explorer.tsx` (rechte `<main>`-Ansicht) und `file-preview.tsx` (Empty-State) sowie das Cockpit-Shell-Layout, das „aktives Fenster" kennt.
- Erfordert ggf. einen **geteilten Zustand** „welches Fenster ist aktiv" (Session vs. Datei-Vorschau) zwischen Explorer und Session-Ansicht — bewusst als technische Konsequenz der gewählten Variante (Klärung 2026-06-25).
- Die aktive Session **nicht neu mounten** (kein Reconnect/Neustart) — Wiederverwendung der bestehenden Session-Ansicht statt zweiter Instanz.
- **Keine** Backend-/API-Änderung erwartet.
- Texte/Hinweise deutsch.

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (App Router, TS) + React Context · **Branch:** dev

### Ausgangslage (aus CodeGraph)
- File Explorer und Session-Ansicht sind **getrennte Routen**: `/dateien` (`file-explorer.tsx`) bzw. `/sessions/[id]` (`app/(cockpit)/sessions/[id]/page.tsx`). Auf `/dateien` ist die Session-Ansicht **nicht gemountet**; der Live-Stream (`useSessionStream`, WebSocket) hängt am Route-Param und stirbt beim Verlassen.
- Rechte „Ansicht"-Spalte rendert heute `<FilePreview entry={selectedEntry} />`; bei `selectedEntry === null` kommt der Leer-Platzhalter („Wähle links eine Datei …", `file-preview.tsx`).
- Selection-State ist lokal: `selectedPath` → `selectedEntry` (auto-null, wenn Datei gelöscht/umbenannt). Ordner → `openDir()`, Datei → `selectFile()` (setzt zusätzlich `mobilePane="view"`).
- Globaler Zustand: **`SessionsProvider`** (Context) pollt `/sessions` ~4 s und liefert die Sessions-Liste für Rail + Board. **Kein** Zustand/Riverpod, **keine** „aktive Session"-Kennung.

### Gewählte Variante (Klärung 2026-06-25)
**2B Embedded-Compact** + **3i „zuletzt fokussiert"**. Begründung unten.

### A) Komponentenstruktur (rechte Spalte)
```
FileExplorer  (/dateien, Drei-Spalten-Layout PROJ-28)
└── <main> Ansicht-Spalte
    ├── selectedEntry vorhanden?  → FilePreview (Bild / MD / Text / „Vorschau nicht verfügbar")
    └── keine Datei gewählt:
        ├── aktive Session vorhanden? → ActiveSessionPanel (NEU, compact)
        │     ├── Header: Session-Titel + Status-/Phasen-Badge
        │     ├── letzte Log-/Aktivitätszeilen (aus SessionsProvider-Poll)
        │     ├── offene Decision-Card (falls vorhanden) als Hinweis
        │     └── Button „Session öffnen" → /sessions/[id]   (Voll-Live + Eingabe)
        └── keine aktive Session   → NeutralHint („Keine aktive Session — wähle links eine Datei.")
```
Die Umschaltlogik ist ein lokales Conditional in der `<main>`-Spalte; `FilePreview`-Empty-State wird nur noch im Sonderfall „keine aktive Session" (als `NeutralHint`) erreicht.

### B) „Aktives Fenster" — Datenquelle & Definition
- **Quelle:** ausschließlich der bereits global pollende `SessionsProvider` — **keine zweite WebSocket-Instanz, kein Reconnect, kein Doppel-Mount** der Live-Session (erfüllt AC „nicht doppelt mounten/neu starten").
- **„aktiv" = zuletzt fokussierte Session:** beim Betreten von `/sessions/[id]` wird die ID gemerkt (Context-Feld im `SessionsProvider` + Spiegelung in `localStorage` für Reload-Stabilität). Der Explorer liest diese ID und zieht die zugehörige Session aus der gepollten Liste. Deterministisch, nicht zufällig.
- **Fallback,** wenn keine gemerkte ID (oder die Session nicht mehr existiert/beendet): erste **laufende** Session nach fester Sortierung; gibt es gar keine → `NeutralHint`.

### C) Zustands-/Verhaltensregeln
- Klick **Datei mit Vorschau** → `selectFile()` → rechte Spalte = `FilePreview` (ersetzt Session-Panel).
- Klick **Ordner** → `openDir()`, Selection bleibt leer → Session-Panel bleibt stehen.
- Datei **gelöscht/umbenannt** → `selectedEntry` wird `null` → automatisch zurück zum Session-Panel (kein Leer-Platzhalter).
- **Datei ohne Vorschau** (Binär) → bewusst aktiv gewählt → `FilePreview` zeigt „Vorschau nicht verfügbar" (kein Rücksprung zur Session), konsistent mit Edge-Case-Festlegung.
- **Mobile:** beim Wechsel in die „Ansicht"-Pane ohne gewählte Datei wird das Session-Panel statt des Leer-Platzhalters gezeigt; `mobilePane`-Umschalten (PROJ-28) unverändert.

### D) Tech-Entscheidungen (WARUM)
- **Variante 2B statt 2A (Live-Embed):** Die laufende Session voll-live in zwei Routen zu halten würde den `useSessionStream`-WebSocket-State in einen Top-Level-Provider heben (großer Eingriff, Reconnect-/Doppel-Stream-Risiko). Das Acceptance Criterion „nicht doppelt mounten/neu starten" wird mit der **gepollten** Compact-Ansicht **sicherer** erfüllt — die Voll-Live-Session bleibt die dedizierte Route, einen Klick entfernt. Kein verlorener Kontext, kein Zweit-Mount.
- **„zuletzt fokussiert" (3i) statt fester Sortierung:** entspricht dem mentalen Modell „mein aktives Fenster bleibt"; localStorage macht es reload-fest.
- **Keine Backend-Änderung:** Status, Phase und letzte Aktivität liegen bereits im `/sessions`-Poll; nichts Neues nötig.

### E) Betroffene Dateien (Frontend-only)
- `nextjs_app/components/cockpit/file-explorer.tsx` — Conditional in der rechten `<main>`-Spalte (Datei vs. aktive Session vs. neutraler Hinweis).
- `nextjs_app/components/cockpit/active-session-panel.tsx` — **NEU**, compacte Session-Ansicht aus `SessionsProvider`-Daten.
- `nextjs_app/components/cockpit/sessions-provider.tsx` — „zuletzt fokussierte Session-ID" als Context-Feld + `localStorage`-Spiegel; Setter beim Betreten von `/sessions/[id]`.
- `nextjs_app/components/cockpit/file-preview.tsx` — Leer-Platzhalter wird zum reinen `NeutralHint`-Sonderfall (Text ggf. anpassen).

### F) Abhängigkeiten / neue Pakete
- **Keine** neuen Pakete. Reines React-Context + bestehende shadcn/ui-Bausteine (Card, Badge, Button).

### G) Out of Scope
- Keine zweite Live-WebSocket-Session im Explorer (bewusst 2B). Voll-Live-Interaktion bleibt `/sessions/[id]`.
