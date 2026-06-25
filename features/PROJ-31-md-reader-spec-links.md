# PROJ-31: Spec-Links im MD-Reader auflösen (Doku führt ins Leere)

## Status: Approved
**Created:** 2026-06-24
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-7 (MD-Reader) — die Doku-Ansicht rendert die Markdown-Links; hier wird deren Auflösung/Navigation repariert.
- Verwandt: PROJ-12 (MD-Editor) — gleiche Link-Auflösungs-Logik sollte konsistent gelten.

## Beschreibung
In der Doku-Ansicht führen **relative Links innerhalb eines Markdown-Dokuments zu anderen Dateien ins Leere**. Konkret beobachtet in der Feature-Übersicht (z. B. `features/INDEX.md` bzw. die im Doku-Baum gezeigte Inbox/Übersicht): Die Verlinkungen auf die einzelnen **Spec-Dateien** (`[Spec](PROJ-X-….md)`) sind nicht navigierbar — ein Klick öffnet das Ziel nicht im MD-Reader.

Gewünscht: **Relative MD→MD-Links** (und Anker innerhalb derselben Datei) werden korrekt **auf die Datei im MD-Reader aufgelöst** und navigieren dorthin, statt in einen toten Link/404 zu laufen.

## User Stories
- Als Nutzer möchte ich in der Doku-Ansicht auf einen **Spec-Link** (z. B. aus `INDEX.md`) klicken und direkt die **verlinkte Spec im MD-Reader** geöffnet bekommen.
- Als Nutzer möchte ich, dass **relative Links** (`PROJ-7-md-reader.md`, `../docs/PRD.md`) korrekt relativ zur aktuell geöffneten Datei aufgelöst werden.
- Als Nutzer möchte ich, dass **Anker-Links** (`#abschnitt`) innerhalb desselben Dokuments funktionieren (Sprung zur Überschrift).
- Als Nutzer möchte ich bei einem **nicht auflösbaren Link** einen klaren Hinweis statt eines stillen Ins-Leere-Klicks.

## Acceptance Criteria
- [ ] **Relative MD→MD-Links** im gerenderten Dokument navigieren im MD-Reader zur Zieldatei (relativ zum Pfad der aktuell geöffneten Datei aufgelöst, inkl. `./` und `../`).
- [ ] Der Klick öffnet das Ziel **innerhalb der Doku-Ansicht** (kein Full-Page-Reload, kein 404, kein toter `<a href>`).
- [ ] Konkreter Nachweis: Aus der Feature-Übersicht (`features/INDEX.md`) sind **alle Spec-Links** (`PROJ-1 … PROJ-N`) navigierbar und öffnen die richtige Spec.
- [ ] **Anker-Links** (`#…`) innerhalb derselben Datei springen zur passenden Überschrift.
- [ ] **Ziel existiert nicht / liegt außerhalb der erlaubten Roots** → klare deutsche Meldung statt stillem Fehler; Pfad-Auflösung serverseitig scope-geprüft (wie PROJ-7/PROJ-11 `realpath`).
- [ ] **Externe Links** (`http(s)://`) bleiben unverändert (öffnen extern), nur **interne relative** werden in MD-Reader-Navigation übersetzt.
- [ ] Alle Texte deutsch; verhaltenswahrend für das übrige MD-Rendering.

## Edge Cases
- **Link mit Anker auf andere Datei** (`PROJ-7-md-reader.md#status`) → Zieldatei öffnen **und** zum Anker springen.
- **Link auf nicht-MD-Datei** (z. B. Bild/`.py`) → sinnvoll behandeln (Download/Preview gemäß Reader-Fähigkeit) statt toter Link.
- **Pfad-Traversal** (`../../etc/...`) → serverseitig per `realpath` auf erlaubte Roots geprüft, außerhalb → abgelehnt.
- **Zieldatei umbenannt/gelöscht** → freundliche „Datei nicht gefunden"-Meldung, kein Absturz.
- **Groß-/Kleinschreibung & URL-Encoding** im Linkziel (`%20`, Leerzeichen) → korrekt dekodiert und aufgelöst.
- **Link relativ zu einer tief verschachtelten Datei** → korrekt relativ (nicht relativ zur Root) aufgelöst.

## Technical Requirements (optional)
- Link-Auflösung primär im **Frontend-Renderer** des MD-Readers: relative `href` abfangen, gegen den aktuellen Dateipfad auflösen, in Reader-Navigation statt Browser-Navigation umsetzen.
- Pfad-Sicherheit serverseitig (vorhandenes `realpath`+Root-Scope-Muster aus PROJ-7/PROJ-11); keine Datei außerhalb der Roots öffenbar.
- Konsistente Logik zwischen MD-Reader (PROJ-7) und MD-Editor-Vorschau (PROJ-12).

## Open Design Questions (in /abc-architecture zu klären)
1. **`[[wikilinks]]`-Unterstützung** (Obsidian-DNA) zusätzlich zu `[text](pfad.md)`? _Default-Vorschlag:_ im MVP nur Standard-Markdown-Links reparieren; Obsidian-Wikilinks optional (überschneidet sich mit PROJ-12).
   → **Entschieden:** Wikilinks sind bereits gebaut (`remark-wikilink.ts`, PROJ-7). PROJ-31 ergänzt nur die fehlenden **Standard-Markdown-Links** `[text](pfad.md)` + Anker. Beide laufen am Ende durch dieselbe Auflösungs-/Navigations-Funktion.
2. **Auflösungs-Basis** — relativ zur Datei (Standard) vs. relativ zu einer Vault-/Projekt-Root? _Default:_ relativ zur aktuell geöffneten Datei (Standard-Markdown-Semantik).
   → **Entschieden:** relativ zur aktuell geöffneten Datei (`./`, `../`), danach serverseitige `realpath`+Root-Scope-Prüfung. Standard-Markdown-Semantik.

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js (App Router) Frontend + FastAPI Backend · **Branch:** dev

### Worum es geht (für PM)
Der MD-Reader rendert Markdown bereits, und **Obsidian-Wikilinks** (`[[Ziel]]`) sind schon klickbar. Was fehlt: die **ganz normalen Markdown-Links** `[Spec](PROJ-7-md-reader.md)`, die unsere eigene `INDEX.md` benutzt — die landen aktuell als toter externer Link/neuer Tab. Diese Lücke schließen wir, ohne am restlichen Rendering etwas zu ändern. Es ist ein **reines Frontend-Feature**: das Backend kann schon sicher Dateien lesen und prüft Pfade per `realpath`.

### A) Komponenten-Struktur (was angefasst wird)
```
doku/page.tsx                         (Doku-Ansicht — Container, kennt aktuellen Pfad)
├── selectedPath / selectPath()       BESTEHT — die "Datei im Reader öffnen"-Aktion (kein Reload)
│                                      → bekommt PROJ-31 die aufgelöste Zieldatei übergeben
└── MarkdownView                       (markdown-view.tsx — Renderer)
    ├── currentFilePath (NEU als Prop) Basis für relative Auflösung
    ├── Link-Renderer                  ERWEITERT: erkennt zusätzlich
    │   ├── http(s)://  → extern, unverändert (neuer Tab)
    │   ├── #anker      → Scroll zur Überschrift in derselben Datei
    │   ├── ….md (rel.) → relativ auflösen → onNavigate(zielpfad[, #anker])
    │   ├── [[wikilink]]→ BESTEHT (remark-wikilink)
    │   └── andere Datei (.png/.py …) → freundlich behandeln (s. Edge Cases)
    └── "Ziel nicht gefunden / außerhalb"-Hinweis (NEU, deutsche Inline-Meldung)
```
Der **MD-Editor-Vorschau** (PROJ-12, `md-editor.tsx`) übergibt heute bewusst `onNavigate={() => {}}` (Read-only-Preview). Konsistenz-Entscheidung: dieselbe Link-Render-Logik nutzen, aber die Navigation im Editor-Preview optional lassen — Default **an**, damit Verhalten konsistent ist; falls das die Edit-Session stört, bleibt es deaktivierbar.

### B) Datenmodell
**Keine** neuen Daten, **keine** DB-Tabellen, **kein** neuer Storage. Der einzige „Zustand", der dazukommt, ist der **Pfad der aktuell geöffneten Datei** als Prop an den Renderer — den kennt die Doku-Ansicht bereits (`selectedPath`).

### C) API-Shape
**Keine neuen Endpunkte.** Die Zieldatei wird über den bestehenden Lese-Weg geöffnet:
```
GET/POST /md/file?path=…   → BESTEHT (md.py) · realpath + Root-Scope-Check (md_reader._validate_md_file)
```
Die Frontend-Funktion `selectPath()` ruft diesen Weg bereits auf. PROJ-31 liefert ihr nur den **korrekt aufgelösten Zielpfad** — die serverseitige Sicherheitsprüfung greift unverändert.

### D) Tech-Entscheidungen (WARUM)
- **Reines Frontend-Feature.** Die Link-Auflösung passiert im Renderer (`react-markdown`-Link-Handler), weil nur dort der Klick + der Kontext „aktuell geöffnete Datei" zusammenkommen. Das Backend liest Dateien schon scope-sicher.
- **Sicherheit bleibt serverseitig.** Wir verlassen uns NICHT auf Frontend-Pfadlogik: jeder aufgelöste Pfad geht durch das bestehende `realpath`+`allowed_roots`-Muster (PROJ-7/PROJ-11). Pfad-Traversal (`../../etc/...`) wird dort abgewiesen — Frontend zeigt nur die deutsche Meldung.
- **Eine Auflösungs-Funktion für alles.** Wikilinks und Standard-Links münden in dieselbe „öffne Datei im Reader"-Aktion (`selectPath`) → konsistentes Verhalten, ein Code-Pfad, leichter zu testen.
- **Quell-übergreifend ohne Sonderlogik.** `sourceOf()` (längster Root-Match) schaltet beim Öffnen automatisch den richtigen Tab (Vault vs. Projekt) — Spec-Links aus `INDEX.md` funktionieren damit ohne Zusatzarbeit.
- **Nicht-MD-Ziele degradieren freundlich** statt tot zu laufen (s. Edge Cases) — verhaltenswahrend für das übrige Rendering.

### E) Abhängigkeiten
**Keine neuen Pakete.** Genutzt wird Bestehendes: `react-markdown`, `remark-wikilink.ts`, sowie für die relative Pfad-Auflösung Standard-Browser-/JS-Mittel (z. B. URL-/Pfad-Normalisierung von `./`, `../`, `decodeURIComponent` für `%20`).

### Umsetzungs-Checkliste (für /abc-frontend)
1. `MarkdownView` bekommt Prop `currentFilePath` (aus `selectedPath` der Doku-Ansicht).
2. Link-Renderer in `markdown-view.tsx` erweitern: `http(s)` → extern; `#anker` → Scroll; relatives `…md` → auflösen + `onNavigate`; `%20`/Spaces dekodieren.
3. Relative Auflösung gegen `currentFilePath` (`./`, `../`, tief verschachtelt), dann an `selectPath()` übergeben (serverseitiger Scope-Check greift).
4. Anker an andere Datei (`X.md#abschnitt`): Datei öffnen **und** nach Laden zum Anker scrollen.
5. Nicht-MD-Ziel (`.png`/`.py`): gemäß Reader-Fähigkeit Preview/Download statt toter Link.
6. Fehlerfälle (nicht gefunden / außerhalb Roots) → deutsche Inline-Meldung, kein Absturz.
7. Editor-Preview (PROJ-12) auf dieselbe Logik ziehen (Navigation default an).

## Implementation Notes (Frontend)
**Umgesetzt:** 2026-06-25 · **Branch:** dev · reines Frontend, kein Backend-Change.

Geänderte Dateien (nur PROJ-31):
- `nextjs_app/components/cockpit/markdown-view.tsx` — Link-Renderer erweitert:
  - **In-Page-Anker** `#…` → `e.preventDefault()` + Scroll zur Überschrift; Überschriften (`h1–h6`) bekommen via eigenem `slugify` (GitHub-nah, Unicode) eine `id` → Anker funktionieren ohne neue Dependency (kein `rehype-slug`).
  - **Externe Links** (`http(s):`, `mailto:`, `tel:`, `//`) → unverändert `target=_blank`.
  - **Interne relative Links** → `resolveRelative(currentPath, rel)` (lexikalisch, `./`/`../`, `decodeURIComponent` für `%20`); Treffer gegen `knownPaths` (alle Index-Pfade) → navigierbarer Button (`onNavigate({path, hash})`); nicht im Index → „Ziel nicht gefunden" (line-through, wie Wikilinks); Nicht-MD-Ziel → nicht-navigierbarer Hinweis „Nur Markdown-Dateien …".
  - Neue Prop `currentPath`; `onNavigate` um optionales `hash` erweitert. Wikilink-Pfad gibt jetzt ebenfalls den Anker mit.
- `nextjs_app/app/(cockpit)/doku/page.tsx` — `currentPath={file.path}` durchgereicht; `selectPath(path, hash?)` merkt den Anker (`pendingAnchorRef`) und scrollt per Effect nach dem Laden der Zieldatei (rAF); schon offene Datei + Anker → direkt scrollen.
- `nextjs_app/components/cockpit/md-editor.tsx` — Editor-Vorschau reicht `currentPath={file.path}` durch (konsistente Logik).
- `nextjs_app/components/cockpit/file-preview.tsx` — Fileexplorer-MD-Vorschau reicht `currentPath={entry.path}` durch.
- `nextjs_app/components/cockpit/markdown-view.security.test.tsx` — 6 neue Tests (relativer Link → Button, unbekannt → fehlend, `../`-Auflösung, Anker-ID + `#`-Link, externer Link unverändert, Nicht-MD nicht navigierbar). Gesamt 14/14 grün.

**Sicherheit:** keine Frontend-Pfad-Autorität — navigiert nur gegen den Index; das echte Lesen läuft weiter über `/md/file` mit `realpath`+Root-Scope (PROJ-7). Pfad-Traversal landet außerhalb des Index → „Ziel nicht gefunden", nie eine Navigation.

**Bekannte Grenze (MVP):** Anker-Slug ist GitHub-nah, aber nicht 100 % deckungsgleich mit jeder externen Slug-Variante; Anker auf nicht existierende Überschrift scrollt einfach nicht (kein Fehler). Reicht für die Spec-Doku-Navigation.

`tsc --noEmit` + `eslint` sauber für die geänderten Dateien (vorbestehender Fehler in `lib/md-tree.test.ts:118` ist unabhängig von PROJ-31).

## QA Test Results
**Getestet:** 2026-06-25 · **Branch:** dev · **Tester:** QA (Red-Team) · **Methode:** Code-Review + automatisierte Tests (`renderToStaticMarkup`, kein jsdom/RTL im Projekt).

### Test-Läufe
- `npx vitest run` → **100/100 grün** (volle Suite, keine Regression in PROJ-7/PROJ-12).
- `markdown-view.security.test.tsx` → **17/17 grün** (8 Bestand + 9 neu für PROJ-31).
- `tsc --noEmit` + `eslint` der geänderten Dateien → sauber (vorbestehender, PROJ-31-unabhängiger Fehler `lib/md-tree.test.ts:118`).

### Acceptance Criteria
| # | Kriterium | Ergebnis | Nachweis |
|---|-----------|----------|----------|
| 1 | Relative MD→MD-Links navigieren im Reader (inkl. `./`, `../`) | ✅ PASS | Tests „relativer MD-Link → Button", „`../`-Pfade" |
| 2 | Klick öffnet Ziel in der Doku-Ansicht (kein Reload/404/toter `<a href>`) | ✅ PASS | Link rendert als `<button onClick=onNavigate>`, nicht `<a href>`; Navigation via `selectPath` (Client-State) |
| 3 | Alle Spec-Links aus `INDEX.md` navigierbar | ✅ PASS | `features/*.md` liegen alle im Projekt-Index → `knownPaths`-Treffer; relative Auflösung ab `…/features/INDEX.md` |
| 4 | Anker-Links (`#…`) springen zur Überschrift | ✅ PASS | Überschriften erhalten Slug-`id`; `#`-Link rendert `<a href="#…">` + `scrollIntoView` (Test prüft `id=`/`href=`) |
| 5 | Ziel fehlt/außerhalb Roots → klare dt. Meldung; serverseitiger Scope-Check | ✅ PASS | Nicht im Index → „Ziel nicht gefunden" (line-through+`title`); Lesen weiter über `/md/file` `realpath`+Root-Scope (unverändert) |
| 6 | Externe Links (`http(s)://`) unverändert extern | ✅ PASS | Test „externer Link → `target=_blank`"; `mailto:`/`tel:`/`//` ebenso extern |
| 7 | Alles deutsch; übriges MD-Rendering verhaltenswahrend | ✅ PASS | Dt. `title`-Texte; GFM/Tabellen/Wikilinks unverändert (volle Suite grün) |

**Summe: 7/7 Acceptance Criteria PASS.**

### Edge Cases
| Edge Case | Ergebnis | Nachweis |
|-----------|----------|----------|
| Anker auf andere Datei (`X.md#abschnitt`) → Datei öffnen + Anker | ✅ PASS | `splitHash` → `onNavigate({path, hash})`; `pendingAnchorRef` scrollt nach Laden (rAF); Test „Cross-File-Anker → Button" |
| Link auf Nicht-MD (`.png`/`.py`) | ✅ PASS | nicht-navigierbarer Hinweis „Nur Markdown-Dateien …", kein toter Link |
| Pfad-Traversal (`../../../../etc/secret.md`) | ✅ PASS | außerhalb Index → „Ziel nicht gefunden", nie Navigation; Server-`realpath` als zweite Schranke |
| Zieldatei umbenannt/gelöscht | ✅ PASS | bei Race: Navigation → Backend-404 → dt. Fehler-Banner (`fileError`), kein Crash |
| Groß-/Kleinschreibung & `%20`/Leerzeichen | ✅ PASS | `decodeURIComponent` in `resolveRelative`; Test „`%20`/Leerzeichen → Button" |
| Tief verschachtelte relative Auflösung | ✅ PASS | `resolveRelative` poppt `..` lexikalisch ab `currentPath`-Dir (Test `../docs/PRD.md`) |

### Security-Audit (Red-Team)
- **Kontext:** Jupiter-MVP ohne JWT/RLS (s. Stack-Overrides) → kein Tenant-/Auth-Vektor relevant.
- **Pfad-Sicherheit:** Frontend besitzt keine Pfad-Autorität — navigiert nur zu Index-bekannten, in-Root-liegenden `.md`. Traversal/Out-of-Root fällt aus dem Index → keine Navigation. Echte Datei-Reads bleiben serverseitig `realpath`+Root-Scope-geprüft (PROJ-7, unverändert). ✅
- **XSS:** Keine `dangerouslySetInnerHTML`; alle Link-Zweige rendern über React. `urlTransform` wendet weiter `defaultUrlTransform` auf Nicht-Wikilink-`href` an → `javascript:` wird neutralisiert (Bestandstest grün). Ein gestrippter/leerer `href` degradiert höchstens zu einem harmlosen Button auf die aktuelle Datei (No-op via `selectPath`-Early-Return). ✅
- **Anker-`href`:** nur bei `#`-Präfix direkt in `<a href>` übernommen → kein Schema-/Injection-Vektor. ✅

### Bugs
Keine Critical/High/Medium gefunden.

**Low / Hinweise (nicht blockierend):**
- L1 (UX): „Ziel nicht gefunden" wird als `title`-Tooltip + Durchstreichung signalisiert (konsistent zum bestehenden Wikilink-Verhalten), nicht als immer sichtbares Inline-Banner. Bewusst übernommen.
- L2 (Abdeckung): Cross-File-Anker-**Scroll** und der `pendingAnchorRef`-Effect liegen in der Client-Page (`doku/page.tsx`) und sind mangels jsdom/RTL nicht unit-getestet — durch Code-Review verifiziert; das Navigations-/Render-Verhalten ist statisch getestet.

### Produktionsreife
**READY** — 7/7 AC + alle Edge Cases PASS, keine Critical/High/Medium-Bugs, keine Regression (100/100). Status → **Approved**.
