# PROJ-29: Eingabefeld-Höhe symmetrisch zu den drei Buttons (Terminalfenster)

## Status: Deployed
**Created:** 2026-06-24
**Last Updated:** 2026-06-24

## Implementation Notes (Frontend)
- **Geändert:** `nextjs_app/app/(cockpit)/sessions/[id]/page.tsx` — Eingabeleiste-`<form>` von `flex items-end` auf `flex items-stretch`. Eine Zeile (+ Kommentar). Kein weiterer Code, keine neuen Pakete, kein Backend.
- **Mechanismus:** Cross-Axis-Stretch lässt die `flex-1`-Textarea die natürliche Höhe der Button-Spalte übernehmen; die Buttons bleiben `h-8` (oben ausgerichtet). `field-sizing-content` + `min-h-16` bleiben → Auto-Grow erhalten, Höhe ohne Magic-Number aus den Buttons abgeleitet (selbst-justierend bei 2 vs. 3 Buttons).
- **Verifiziert (Playwright, exaktes Markup, 1440px):** Initial Textarea **112px** == Button-Spalte **112px** (bündig); nach 6-Zeilen-Eingabe wächst die Textarea auf 138px, Spalte folgt → Auto-Grow intakt. Buttons bündig oben+unten.
- **Offen für QA:** Verifikation am echten Build inkl. beendeter Session (2 Buttons = ~80px) und responsive 375/768.

## Dependencies
- Requires: PROJ-3 (Cockpit / Session-Fenster) — betrifft die Eingabeleiste (`SessionInputBar`) im Session-Detail.
- Requires: PROJ-11 (Fileexplorer / Surface B) — durch den dort ergänzten **„Anhängen"-Button** ist die Button-Gruppe höher geworden als das Eingabefeld.

## Beschreibung
Seit im Terminalfenster der **„Anhängen"-Button** (PROJ-11, Surface B) zur Button-Gruppe hinzugekommen ist, sind die **drei Knöpfe rechts höher** als das **Eingabefeld** — die Leiste wirkt unsymmetrisch. Gewünscht: Die **initiale (Anfangs-)Höhe des Eingabefelds** soll der **Gesamthöhe der drei Knöpfe** entsprechen, sodass Eingabefeld und Button-Gruppe **bündig/symmetrisch** abschließen.

Dies ist ein reiner visueller Layout-Fix; das Verhalten (Auto-Grow der Textarea beim Tippen, Senden, Anhängen) bleibt unverändert.

## User Stories
- Als Nutzer möchte ich, dass das Eingabefeld in seiner Anfangshöhe **genauso hoch** ist wie die drei Knöpfe daneben, damit die Eingabeleiste symmetrisch aussieht.
- Als Nutzer möchte ich, dass die Textarea beim Tippen weiterhin normal wächst, ohne dass die Symmetrie im Ausgangszustand verloren geht.

## Acceptance Criteria
- [ ] Im **Ausgangszustand** (leeres/einzeiliges Eingabefeld) entspricht die **Höhe der Textarea** der **Gesamthöhe der drei Buttons** rechts — sie schließen bündig ab (kein Höhenversatz).
- [ ] Eingabefeld und Button-Gruppe sind **vertikal mittig/bündig** ausgerichtet; die drei Knöpfe stehen nicht mehr höher als das Feld.
- [ ] Das **Auto-Grow-Verhalten** der Textarea beim Tippen bleibt erhalten (verhaltenswahrend).
- [ ] Die Korrektur ist **responsive** stabil (Desktop/Tablet/Mobil) — keine neue Verschiebung auf schmalen Breiten.
- [ ] Keine Funktionsänderung an Senden/Anhängen/Tastatur-Shortcuts.

## Edge Cases
- **Sehr langer mehrzeiliger Text** → Textarea wächst wie bisher; die Symmetrie gilt für den Ausgangszustand, nicht für den gewachsenen.
- **Schmaler Viewport**, in dem die Buttons umbrechen → definiertes Verhalten (Buttons unter das Feld o. ä.), kein abgeschnittenes/überlappendes Layout.
- **Button-Gruppe ändert sich** (z. B. ein Button mehr/weniger) → Höhe leitet sich aus der tatsächlichen Button-Höhe ab, kein hartkodierter Pixelwert, der erneut bricht.

## Technical Requirements (optional)
- Reiner **Frontend-/CSS-Fix** in der Session-Eingabeleiste; keine Backend-/API-Änderung.
- Höhe möglichst aus Theme-/Komponenten-Maßen ableiten (shadcn-Button-Höhe) statt Magic-Number, damit künftige Button-Änderungen die Symmetrie nicht erneut brechen.
- Alle Texte/Tooltips deutsch (unverändert).

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** Next.js 16 (App Router, Tailwind + shadcn/ui) · **Branch:** dev

### Betroffene Komponente (eine Datei, ein Mini-Diff)
```
SessionDetail (sessions/[id]/page.tsx)
└── <form>  «flex items-end gap-2»        ← Ausrichtung wird angepasst
    ├── <Textarea>  flex-1 · min-h-16 (64px) · field-sizing-content (Auto-Grow)
    └── <div>  «flex flex-col gap-2»  (Button-Spalte)
        ├── Button «Senden/Fortsetzen»   h-8 (32px)
        ├── SessionClipboardButton «Anhängen»  h-8 (32px)
        └── Button «Stop» (entfällt wenn Session beendet)  h-8 (32px)
```
Datei: `nextjs_app/app/(cockpit)/sessions/[id]/page.tsx` (~Zeile 323–374). Sonst nichts.

### Diagnose (Ist-Zustand)
- Button-Spalte = 3 × 32px + 2 × 8px Gap = **112px**.
- Textarea-Starthöhe = `min-h-16` = **64px**.
- `items-end` macht beide nur **unten** bündig → der ~48px-Versatz oben ist die wahrgenommene Unsymmetrie.

### Entscheidung: Höhe aus der Button-Spalte ableiten — kein Pixel-Magic-Number
Statt die Textarea auf einen festen Wert (z. B. `min-h-28`) zu pinnen, lässt die Eingabeleiste die **Textarea auf die natürliche Höhe der Button-Spalte mitwachsen** (Cross-Axis-Stretch der Flex-Zeile). Vorteile:
- **Selbst-justierend:** Fällt der „Stop"-Button weg (beendete Session) oder kommt künftig ein Button hinzu, folgt die Starthöhe automatisch — die Symmetrie bricht nicht erneut (erfüllt Edge-Case „Button-Gruppe ändert sich").
- **Auto-Grow bleibt:** `field-sizing-content` wächst beim Tippen weiter über die Starthöhe hinaus; die Button-Spalte streckt sich mit, die Buttons selbst bleiben `h-8` (oben angeordnet) — keine Funktionsänderung.
- **`min-h-16` bleibt als Untergrenze** erhalten (Fallback, falls die Button-Spalte je niedriger wäre als ein Textfeld-Minimum).

> Umsetzungs-Spielraum fürs Frontend (kein Code hier): Cross-Axis-Stretch der Form-Zeile so wählen, dass die **Textarea** die Spaltenhöhe übernimmt, ohne die **Buttons** zu strecken (Buttons behalten `h-8`, oben ausgerichtet). Ein hartkodierter Pixelwert ist ausdrücklich Plan B, nur falls Stretch im Zusammenspiel mit `field-sizing-content` instabil ist.

### Kein Backend / keine Daten
- Keine API-, DB-, MinIO- oder Schema-Änderung. Kein neuer State, kein Riverpod/Provider.
- Keine neuen Pakete.

### Verantwortlich
- **Frontend Developer** (`/abc-frontend`) — einziger Schritt. Danach **QA** (`/abc-qa`) gegen die Akzeptanzkriterien (insb. responsive 375/768/1440 + beendete vs. aktive Session = 2 vs. 3 Buttons).

## QA Test Results
**Getestet:** 2026-06-24 · **Branch:** dev · **Methode:** deterministische Layout-Messung (Playwright/Chromium, exaktes Klassen-Markup der echten `Textarea`+`Button`-Komponenten — `min-h-16` · `field-sizing-content` · Default-Button `h-8`) über 3 Viewports × {aktiv 3 Buttons, beendet 2 Buttons}. Gemessen via `getBoundingClientRect()`.

### Akzeptanzkriterien
| # | Kriterium | Ergebnis |
|---|-----------|----------|
| 1 | Ausgangszustand: Textarea-Höhe == Gesamthöhe der 3 Buttons (bündig) | ✅ Pass — 112px == 112px auf 375/768/1440; oben **und** unten bündig (`topFlush`+`botFlush`) |
| 2 | Eingabefeld + Button-Gruppe vertikal bündig, Buttons nicht höher | ✅ Pass — kein Höhenversatz mehr; Buttons bleiben `h-8`, oben ausgerichtet |
| 3 | Auto-Grow beim Tippen erhalten | ✅ Pass — bei 6 Zeilen wächst die Textarea (1440: 138px, 375: 162px), Spalte folgt |
| 4 | Responsive stabil (Desktop/Tablet/Mobil), keine neue Verschiebung | ✅ Pass — identisch bündig auf 1440/768/375, kein Umbruch/Überlappung (`wrapped:false`) |
| 5 | Keine Funktionsänderung Senden/Anhängen/Shortcuts | ✅ Pass — Diff ist genau **eine** Klasse (`items-end`→`items-stretch`); Handler/Logik unverändert (Code-Inspektion) |

**5/5 bestanden.**

### Edge Cases
- **Sehr langer mehrzeiliger Text** → Textarea wächst wie bisher (Symmetrie gilt für Ausgangszustand). ✅
- **Schmaler Viewport (375)** → kein Umbruch/abgeschnittenes Layout, weiterhin bündig. ✅
- **Button-Gruppe ändert sich** (beendete Session: Stop entfällt → 2 Buttons) → Textarea folgt automatisch: **72px == 72px** bündig. Höhe aus Buttons abgeleitet, **kein Magic-Number**. ✅

### Security / Regression
- **Security:** N/A — reiner Frontend-CSS-Fix, keine Auth-/Daten-/Tenant-/API-Oberfläche berührt.
- **Regression:** nur eine `className` in `sessions/[id]/page.tsx` geändert; keine geteilten Widgets, kein Backend, kein State. Kein Regressionsrisiko für andere Features.

### Automatisierte Tests
Kein Unit-/E2E-Test ergänzt: rein präsentationale Ein-Klassen-Änderung ohne Logik; abgedeckt durch die obige deterministische Layout-Messung. Ein DOM-Snapshot-Test hätte keinen über die Messung hinausgehenden Wert.

### Production-Ready: **JA** — keine Critical/High/Medium/Low-Bugs.

## Deployment
- **Live:** https://jupiter.auxevo.tech · **Datum:** 2026-06-24 · **Version:** 0.9.0 (Batch mit PROJ-28)
- Ausgeliefert: Eingabeleiste `items-end`→`items-stretch` in `sessions/[id]/page.tsx` — Textarea-Höhe symmetrisch zur Button-Spalte.
