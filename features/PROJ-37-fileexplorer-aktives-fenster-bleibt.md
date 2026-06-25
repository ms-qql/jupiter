# PROJ-37: File Explorer — kein leeres Vorschau-Fenster; aktives Fenster (Session) bleibt rechts

## Status: Deployed
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Implementation Notes (Frontend)
**Umgesetzt:** 2026-06-25 · Branch `dev` · Variante 2B (Embedded-Compact) + 3i (zuletzt fokussiert).

- **`components/cockpit/sessions-provider.tsx`** — `focusedSessionId` zur Context-Value ergänzt: ID wird beim Betreten von `/sessions/<id>` abgeleitet (Muster „State beim Pathname-Wechsel anpassen", kein `setState` im Effect → erfüllt die strikten `react-hooks`-Lintregeln) und in `localStorage` (`jupiter.focusedSessionId`) gespiegelt (Reload-stabil, SSR-sicher via `readStoredFocus`).
- **`lib/status.ts`** — `pickActiveSession(sessions, focusedId)`: bevorzugt die fokussierte **laufende** Session, sonst die dringlichste (`railRank`, dann jüngste Aktivität); keine laufende Session → `null`.
- **`components/cockpit/active-session-panel.tsx`** (NEU) — kompakte Session-Ansicht aus dem bereits pollenden `SessionsProvider` (Ampel, Name, Rolle/Status, Phase, Kontext, Laufzeit/letzte Aktivität, Freigabe-Hinweis, „Session öffnen" → `/sessions/<id>`). **Keine** zweite WebSocket-Instanz, kein Reconnect, kein Doppel-Mount. Ohne laufende Session → neutraler Hinweis (kein Leer-Bug).
- **`components/cockpit/file-explorer.tsx`** — rechte `<main>`-Spalte: `selectedEntry ? <FilePreview> : <ActiveSessionPanel>`. Ordner-Navigation lässt die Auswahl leer → Session-Panel bleibt; Datei-Klick ersetzt es; gelöschte/umbenannte Datei fällt automatisch zurück. Mobile Pane-Umschalten (PROJ-28) unverändert.
- `FilePreview`-Empty-State bleibt als harmlose Sicherheits-Fallback bestehen (im Explorer nicht mehr erreicht; der neutrale Hinweis lebt jetzt im `ActiveSessionPanel`).
- **Keine** Backend-/API-Änderung. ESLint + tsc (für die berührten Dateien) sauber.

## QA Test Results
**Getestet:** 2026-06-25 · Branch `dev` · QA Engineer · Next.js (Vitest + SSR-Static-Render)

### Zusammenfassung
- **Acceptance Criteria:** 6/6 bestanden (Code-Verifikation + Unit-Tests).
- **Edge Cases:** 6/6 abgedeckt.
- **Automatisierte Tests:** 132/132 grün (11 neu für PROJ-37; 0 Regressionen, vorher 121).
- **Bugs:** keine (Critical 0 · High 0 · Medium 0 · Low 0).
- **Security:** ohne Befund (rein Frontend, keine Backend-/Auth-Änderung).
- **Produktionsreife:** **READY**.

### Acceptance Criteria (pass/fail)
| # | Kriterium | Status | Nachweis |
|---|-----------|--------|----------|
| 1 | Öffnen ohne Datei → aktives Fenster statt Leer-Platzhalter | ✅ | `file-explorer.tsx` Conditional; `pickActiveSession` (Unit-Test) |
| 2 | Datei mit Vorschau → FilePreview ersetzt das Fenster | ✅ | `selectFile` → `selectedEntry` → `FilePreview` |
| 3 | Auswahl aufgehoben (gelöscht/Ordnerwechsel/Vorschau zu) → zurück zum Fenster, kein Leer | ✅ | `selectedEntry`-Ableitung + Null-Setzen in delete/rename/openDir |
| 4 | Ordner-Klick lässt rechte Spalte am aktiven Fenster | ✅ | `openDir` setzt `selectedPath=null` → `ActiveSessionPanel` |
| 5 | Kein aktives Fenster → neutraler Hinweis statt Fehler | ✅ | `pickActiveSession`=null → Hinweis (Panel-Test) |
| 6 | 3-Spalten-Layout (PROJ-28) + Mobile-Pane bleiben funktionsfähig | ✅ | Markup/`mobilePane`-Logik unverändert |

### Edge Cases
- Keine aktive Session → neutraler Hinweis (Test „done"-only → null). ✅
- Mehrere Sessions → deterministisch (fokussiert, sonst railRank+jüngste Aktivität; Tests). ✅
- Ausgewählte Datei gelöscht/umbenannt → Auswahl `null` → aktives Fenster. ✅
- Binär-Datei aktiv gewählt → `FilePreview`-Hinweis „keine Vorschau" (konsistent mit Spec-Festlegung). ✅
- Mobile schmaler Viewport → Ansicht-Pane zeigt aktives Fenster, nicht Leer. ✅
- Performance: kein Doppel-Mount/Neustart — Panel nutzt ausschließlich den bestehenden `SessionsProvider`-Poll, keine zweite WebSocket-Instanz. ✅

### Neue Tests
- `lib/active-session.test.ts` — 7 Fälle für `pickActiveSession` (Fokus-Vorrang, Terminal-Ignoranz, Fallback-Reihenfolge, Leerfälle).
- `components/cockpit/active-session-panel.test.tsx` — 4 Render-Fälle (aktive Session · neutraler Hinweis · Erstladen · Freigabe-Hinweis) via Modul-Mock.

### Security-Audit
- Rein Frontend; keine Backend-/API-/Auth-Änderung (MVP ohne JWT/RLS). 
- `session_id` in `localStorage` (`jupiter.focusedSessionId`) — nicht sensibler als die ohnehin sichtbare URL; in `href`/Text via React escaped → kein XSS/Injection.
- Keine Geheimnis-Exposition, keine neuen Netzwerk-Endpunkte.

### Offen / Empfehlung
- Live-Visual-Smoke (Browser 375/768/1440 px) in dieser Umgebung **nicht** ausgeführt — Markup der 3 Spalten/Mobile-Pane ist unverändert, Risiko gering. Empfehlung: kurzer Sicht-Check im Rahmen von `/abc-deploy`.

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

## Deployment
- **Production URL:** https://jupiter.auxevo.tech
- **Deployed:** 2026-06-25 · **Version:** 0.13.0 · Host-nativ (systemd + Caddy, Webhook auf `main`)
- **Geliefert:** Aktives Session-Fenster bleibt im File-Explorer rechts statt leerer Vorschau (Variante 2B + zuletzt-fokussiert).
- Gemeinsamer Deploy mit PROJ-38 (Sidebar-Sektionen).
