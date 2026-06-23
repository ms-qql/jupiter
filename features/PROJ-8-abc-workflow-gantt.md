# PROJ-8: ABC-Workflow-Gantt — Phasen-Fortschritt je Session/Projekt

## Status: Approved
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Backend:** ✅ implementiert (2026-06-23) · **Frontend:** ✅ implementiert (2026-06-23) · **QA:** ✅ bestanden (2026-06-23, 0 Bugs) → Approved

## Dependencies
- Requires: PROJ-3 (Cockpit) — der Gantt lebt **unter dem Kanban** in derselben Ansicht.
- Requires: PROJ-1 (Engine-Treiber) — muss pro Session die **aktive ABC-Phase** und das **aktuelle Feature** liefern (siehe „Benötigte Erweiterungen").
- Verwandt: PROJ-6 (Konstitution/Rollen) — die Rolle einer Session korreliert mit der Phase.

## Beschreibung
Unter dem Session-Kanban im Cockpit eine **horizontale Gantt-Ansicht**, die für **jede laufende Session** zeigt, wo das zugehörige Projekt im **ABC-Workflow** steht. Jede Session ist eine Zeile mit einer horizontalen Bar (links → rechts).

- **Links (Zeilen-Label):** Name des Projekts/Programms **plus** eine Indikation, an welchem Feature gemäß ABC-Workflow gerade gearbeitet wird (z. B. „Feature 6" / `PROJ-6`).
- **Rechts (Zeitachse):** Unterteilung nach den **Phasen des ABC-Workflows** in fester Reihenfolge:
  **Brainstorm → Requirements → Architecture → Frontend → Backend → QA → Deploy → Document.**
- Die Bar reicht von links bis zur **zuletzt abgeschlossenen Phase** und **hebt die aktuelle Phase** hervor — so sieht man auf einen Blick, wo jede Session (und damit jedes Projekt) gerade steht.

Der **Projektname** wird beim **Start einer neuen Session** im Setup abgefragt (neues Feld „Projekt", noch vor/zusätzlich zum Arbeitsverzeichnis). Das **aktuelle Feature** wird **dynamisch aus der Session** gelesen: läuft z. B. gerade `abc-requirements 6`, ist das Feature 6 — diese Zahl/Referenz erscheint im Bar-Label.

## User Stories
- Als Nutzer möchte ich unter dem Kanban eine Gantt-Ansicht sehen, die je Session den Fortschritt durch die ABC-Phasen zeigt, um den Reifegrad aller Projekte auf einen Blick zu erfassen.
- Als Nutzer möchte ich links pro Zeile den Projektnamen **und** das aktuell bearbeitete Feature sehen, um die Bar eindeutig zuzuordnen.
- Als Nutzer möchte ich die acht ABC-Phasen als feste Spalten sehen, mit Markierung der zuletzt abgeschlossenen und der aktuellen Phase.
- Als Nutzer möchte ich beim Erstellen einer Session zuerst das Projekt angeben, damit die Gantt-Zeile einen sprechenden Namen hat.
- Als Nutzer möchte ich, dass das aktuelle Feature automatisch aus der Session erkannt wird (z. B. aus `abc-requirements 6` → Feature 6), ohne es manuell pflegen zu müssen.

## Acceptance Criteria
- [ ] Im Cockpit erscheint **unter dem Kanban** ein Gantt-Bereich (gleiche Seite; eigener Abschnitt oder Unter-Tab).
- [ ] **Eine horizontale Bar pro Session**, von links nach rechts verlaufend.
- [ ] **Links** je Zeile: Projektname + Feature-Indikation (z. B. „`PROJ-6` · Feature 6").
- [ ] **Rechts** acht Phasen-Spalten in fester Reihenfolge: Brainstorm, Requirements, Architecture, Frontend, Backend, QA, Deploy, Document.
- [ ] Die Bar ist bis zur **zuletzt abgeschlossenen Phase** gefüllt; die **aktuelle Phase** ist deutlich hervorgehoben (Farbe/Marker).
- [ ] **Projektname stammt aus der Session-Erstellung**: Der „Neue Session"-Dialog (PROJ-3) fragt **zuerst das Projekt** ab.
- [ ] **Aktuelles Feature wird dynamisch aus der Session gelesen** (aktiver abc-Skill + dessen Argument → Feature-Nummer/Spec-Referenz).
- [ ] **Live-Aktualisierung** der Bars (gleiche Polling-/Update-Mechanik wie der Rest des Cockpits), ohne manuelles Reload.
- [ ] Phasen-Mapping ist konsistent mit der Ampel/Kanban-Logik (eine Session in QA steht in der QA-Phase).
- [ ] Responsive (Desktop-first; horizontal scrollbar, wenn die Phasen nicht in die Breite passen).
- [ ] **Versions-Anzeige in der Sidebar:** Neben dem „Jupiter"-Titel in der Sidebar wird die **aktuelle Version (Bump)** klein/dezent angezeigt (z. B. `🪐 Jupiter  v0.1.0`). Quelle: die App-Version (`package.json` / Release-Tag), nicht manuell gepflegt.

## Benötigte Erweiterungen an bestehenden Features
> Diese Spec ist **additiv**; sie setzt zwei kleine Erweiterungen voraus, die mit der Implementierung dieses Features kommen:
- **PROJ-3 (Cockpit / NewSessionDialog):** Neues Feld **„Projekt"** im Setup, vor dem Arbeitsverzeichnis. Wird mit der Session gespeichert und als Gantt-Zeilen-Label genutzt.
- **PROJ-1 (Engine-Treiber):** Pro Session zwei neue, dynamisch ermittelte Felder bereitstellen:
  - `abc_phase` — die aktuell aktive ABC-Phase (`brainstorm | requirements | architecture | frontend | backend | qa | deploy | document | none`), abgeleitet aus dem zuletzt aufgerufenen `abc-*`-Skill.
  - `abc_feature` — die aktuell bearbeitete Feature-/Spec-Referenz (z. B. `6` bzw. `PROJ-6`), abgeleitet aus dem Skill-Argument bzw. der gerade berührten `features/PROJ-X-*.md`.
  - Optional `abc_phase_history` / `last_completed_phase` für den gefüllten Teil der Bar.

## Edge Cases
- **Session ohne ABC-Phase** (Ad-hoc-Arbeit, kein abc-Skill aktiv) → neutrale Zeile/„keine Phase", keine irreführende Füllung.
- **Mehrere Sessions am selben Projekt** → mehrere Zeilen (je Session eine Bar); Projektname identisch, Feature ggf. unterschiedlich.
- **Feature nicht erkennbar** (Skill ohne Argument, kein eindeutiger Spec-Bezug) → Projektname ohne Feature-Indikation anzeigen, Bar zeigt nur die Phase.
- **Phasen nicht-linear** (z. B. Deploy vor Document, Frontend↔Backend-Wechsel) → Bar füllt bis zur „weitesten" erreichten Phase entlang der kanonischen Reihenfolge; aktuelle Phase separat markiert.
- **Projekt ohne ABC-Struktur** (kein `features/INDEX.md`) → Zeile mit Projektname, Phase „none".
- **0 Sessions** → Gantt-Bereich zeigt eigenen Empty-State.
- **Viele Sessions** → vertikal scrollbarer Gantt-Bereich, performant.
- **Session beendet/Fehler** → letzte bekannte Phase bleibt sichtbar (eingefroren), optisch als „beendet" markiert.

## Open Design Questions (mit Default-Vorschlag — in /abc-architecture zu klären)
1. **Phasen-Erkennung — Signalquelle?** _Default-Vorschlag:_ Der Engine-Treiber parst aus dem `stream-json`-Verlauf den **zuletzt aufgerufenen `abc-*`-Skill** (Skill-Invocation-Event) → Phase. Alternativen: aus der Session-`role` (PROJ-6) ableiten; oder explizit vom Skill via Marker gesetzt.
2. **Feature-Erkennung — woraus?** _Default-Vorschlag:_ aus dem **Argument des abc-Skills** (`/abc-requirements 6` → 6). Fallback: die zuletzt geschriebene/`features/PROJ-X-*.md`, die die Session berührt.
3. **„Abgeschlossene" Phase — Definition?** _Default-Vorschlag:_ eine Phase gilt als abgeschlossen, wenn ihr abc-Skill in dieser Session (oder laut `features/INDEX.md`-Status des Features) durchlaufen wurde. Quelle der Wahrheit ggf. der **INDEX-Status** des Features (Planned→Architected→…→Deployed) statt Session-lokaler Historie.
4. **Zeilen-Granularität — Session oder Projekt?** _Default-Vorschlag:_ **eine Zeile pro Session** (der User sprach von „jeder einzelnen Session"); Projekt = Label. Optional spätere Gruppierung nach Projekt.
5. **„Projekt" — neues Feld oder aus `project_path` abgeleitet?** _Default-Vorschlag:_ explizites Pflichtfeld im Dialog (freier Name oder Auswahl bekannter Projekte), unabhängig vom Pfad, damit das Label sprechend ist.
6. **Darstellung der Achse — echte Zeitachse oder Phasen-Raster?** _Default-Vorschlag:_ **Phasen-Raster** (8 gleich breite Spalten = Phasen), keine kalendarische Zeitachse — passt zu „Status, wo man steht" statt Dauer.

## Technical Requirements (optional)
- Next.js 16 (App Router) + Tailwind + shadcn/ui; Gantt als komponierte Ansicht (kein Hand-Roll vorhandener Primitives). Ggf. leichte eigene Bar-Komponente, da shadcn keinen Gantt liefert.
- Datenquelle: dieselbe gepollte Session-Liste wie Board/Rail (erweitert um `abc_phase`/`abc_feature`), kein Extra-Request.
- Alle Texte deutsch; Loading/Error/Empty-States explizit.
- Phasen-Reihenfolge zentral definiert (eine Konstante, geteilt mit etwaiger Phasen-Logik).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-23 · **Stack:** Next.js 16 (App Router) + Tailwind + shadcn/ui (Frontend) · FastAPI In-Memory-Engine (Backend, kein DB/RLS — Jupiter-Override) · **Branch:** dev

### Kurzfassung
Der Gantt ist eine **rein additive, gepollte Lese-Ansicht**. Er nutzt exakt dieselbe Session-Liste, die Board/Rail/Kanban schon alle 4 s laden ([sessions-provider.tsx:17](../nextjs_app/components/cockpit/sessions-provider.tsx#L17) → [listSessions, lib/api.ts:53](../nextjs_app/lib/api.ts#L53)) — **kein Extra-Request**. Es kommen drei neue Felder pro Session dazu (`project_name`, `abc_phase`, `abc_phase_reached`, `abc_feature`), die der Engine-Treiber aus den Skill-Aufrufen der Session ableitet. Damit ist die Live-Aktualisierung „gratis".

### A) Komponenten-Struktur (Frontend)
```
app/(cockpit)/page.tsx  (Kanban-Tab)
└── <section> „ABC-Fortschritt"        ← NEU, direkt UNTER <KanbanBoard/> (page.tsx:77-80)
    └── GanttChart (neu)
        ├── GanttHeader   → 8 feste Phasen-Spaltenköpfe (horizontal scrollbar)
        ├── GanttRow  (eine pro Session)
        │   ├── RowLabel  → „<Projektname> · Feature 8"  (links, sticky)
        │   └── PhaseTrack → 8 Zellen:
        │         · gefüllt bis  abc_phase_reached  (zuletzt erreichte Phase)
        │         · aktuelle Phase (abc_phase) farblich hervorgehoben/markiert
        │         · „beendet"-Session → Track eingefroren, dezent ausgegraut
        └── EmptyState → „Noch keine Sessions mit ABC-Phase."
```
- **shadcn-first:** Es gibt keinen shadcn-Gantt. `GanttChart` ist eine **komponierte** Ansicht aus `div`/Tailwind-Grid (8-Spalten-Raster) + bestehender `Badge`/`Card` für Labels — keine nachgebaute Primitive.
- **Sidebar-Version:** In [session-rail.tsx:48-54](../nextjs_app/components/cockpit/session-rail.tsx#L48) und der Mobile-Topbar ([cockpit-shell.tsx:52](../nextjs_app/components/cockpit/cockpit-shell.tsx#L52)) neben „🛰️ Jupiter" ein dezentes `v{version}` (muted, text-xs). Quelle: `version` aus [package.json](../nextjs_app/package.json#L3), zur Build-Zeit über `next.config.ts` als `NEXT_PUBLIC_APP_VERSION` injiziert (eine zentrale `lib/version.ts`-Konstante), **nicht** manuell gepflegt.

### B) Datenmodell (neue Felder je Session)
Erweiterung von `SessionState` ([manager.py:94](../backend/app/engine/manager.py#L94)) + `to_read()` ([manager.py:133](../backend/app/engine/manager.py#L133)) und spiegelbildlich `Session` in [types.ts:42](../nextjs_app/lib/types.ts#L42):

```
project_name      : string | null   – sprechendes Label aus dem „Neue Session"-Dialog
                                       (Fallback: Basename von project_path)
abc_phase         : Phase  | null    – AKTUELLE Phase (hervorgehoben). null = „keine Phase"
abc_phase_reached : Phase  | null    – WEITESTE bisher erreichte Phase (Bar-Füllung)
abc_feature       : string | null    – Feature-Referenz, z. B. „8" bzw. „PROJ-8"
```
`Phase` ∈ { brainstorm, requirements, architecture, frontend, backend, qa, deploy, document }.
State bleibt **in-memory** (kein Neon/RLS — konsistent mit PROJ-1). Keine Migration.

### C) Signalquelle & Ableitung (Backend, der Kern)
**Eine zentrale Phasen-Konstante** (geteilt): `app/engine/abc_phases.py` mit der kanonischen Reihenfolge + Mapping `abc-skill → Phase`; im Frontend gespiegelt als `ABC_PHASES` in [lib/status.ts](../nextjs_app/lib/status.ts) (analog zu `STATUS_META`/`COLUMNS`).

Skill-Aufrufe sind im MVP bereits sichtbar: jeder Tool-Aufruf läuft durch den Permission-Hook → `request_decision(tool_name, tool_input, …)` ([manager.py:324](../backend/app/engine/manager.py#L324), aufgerufen via [manager.py:566](../backend/app/engine/manager.py#L566)). Dort wird **vor** der bestehenden Card-Logik ein kleiner Detektor eingehängt:
- `tool_name == "Skill"` **und** `tool_input["skill"]` beginnt mit `abc-` → Phase via Mapping bestimmen.
- `abc_phase` = erkannte Phase; `abc_phase_reached` = max(bisher, neue Phase) entlang der kanonischen Reihenfolge (deckt nicht-lineare Sprünge ab, Edge-Case „Deploy vor Document").
- `abc_feature` = `tool_input["args"]` (z. B. „8"). Fallback: aus zuletzt von der Session berührtem `features/PROJ-X-*.md`-Pfad (Write/Edit-`file_path`).
- `abc-qa-e2e → qa`. Nicht-Phasen-Skills (`abc-refactor`, `abc-challenge`, `abc-clarification`, `/codegraph` …) ändern **nichts** (aktuelle Phase bleibt stehen).
- Tool ist read-only-ähnlich → die bestehende Auto-Allow-Logik bleibt unberührt; der Detektor läuft nur als Seiteneffekt, erzeugt keine Decision Card.

### D) API-Form
Keine neuen Endpoints. `GET /sessions` (Liste) und der WS-State-Broadcast ([manager.py:262](../backend/app/engine/manager.py#L262)) tragen die vier neuen Felder über das erweiterte `to_read()` automatisch mit. `POST /sessions` (`SessionCreate`, [schemas/sessions.py:15](../backend/app/schemas/sessions.py#L15)) bekommt ein optionales `project_name`.

### E) Entscheidungen zu den 6 offenen Design-Fragen
1. **Phasen-Signal:** Permission-Hook (`Skill`-Tool-Aufruf), nicht roher stream-json-Parser — nutzt einen vorhandenen Per-Tool-Seam, robust & billig.
2. **Feature-Erkennung:** primär `args` des abc-Skills; Fallback berührte `PROJ-X-*.md`.
3. **„Abgeschlossen":** **session-lokale** Phasen-Historie (`abc_phase_reached`), NICHT der INDEX-Status — weil Zeilen pro Session sind und mehrere Sessions sich ein Projekt teilen. INDEX-Cross-Check = späteres Optional.
4. **Granularität:** **eine Zeile pro Session**; Projektname = Label.
5. **„Projekt":** explizites Feld im Dialog (frei, vorbelegt aus Pfad-Basename), gespeichert als `project_name`.
6. **Achse:** **Phasen-Raster** (8 gleich breite Spalten), keine Kalender-Zeitachse.

### F) Abhängigkeiten (Pakete)
Keine neuen Pakete. Frontend: bestehendes Tailwind-Grid + shadcn `Badge`/`Card`. Backend: Standardbibliothek. (Versions-Injektion via vorhandenem `next.config.ts`.)

### G) Edge-Cases → Umsetzung
- **Keine Phase** (kein abc-Skill lief) → `abc_phase=null`, neutrale Zeile, leerer Track.
- **Feature unklar** (Skill ohne Arg) → Projektname ohne Feature-Suffix, Track zeigt nur die Phase.
- **Mehrere Sessions/Projekt** → mehrere Zeilen, gleiches Label.
- **Session beendet/Fehler** → letzter Stand eingefroren, optisch „beendet".
- **0 Sessions** → eigener Empty-State im Gantt-Abschnitt.
- **Viele Sessions** → vertikal scrollbarer Bereich; eine flache Zeile/Session, performant.

### H) Aufgaben-Zuschnitt für die Spezialisten
- **Backend (`/abc-backend`):** `abc_phases.py` (Konstante+Mapping), Detektor in `request_decision`, drei Felder in `SessionState`/`to_read()`, `project_name` in `SessionCreate`/Session-Anlage, Tests (Skill-Erkennung, max-Phase, Fallback).
- **Frontend (`/abc-frontend`):** `ABC_PHASES` in `status.ts`, `GanttChart`+Sub-Komponenten, Einhängen unter `KanbanBoard`, `project_name`-Feld im `NewSessionDialog`, Versions-Badge in Rail/Topbar, neue Felder in `types.ts`.

## Backend-Implementierung (2026-06-23)
Additiv, In-Memory (Jupiter-Override: kein DB/RLS/Migration). Umgesetzt gemäß Tech-Design Abschnitt B/C/D + Aufgaben-Zuschnitt H:

- **`backend/app/engine/abc_phases.py` (neu):** kanonische `ABC_PHASES` (8er-Tupel, einzige Quelle der Wahrheit), `SKILL_TO_PHASE`-Mapping (inkl. `abc-qa-e2e → qa`; Nicht-Workflow-Skills wie `abc-refactor`/`abc-fullstack` → `None`), `phase_for_skill`, `max_phase` (monotone „weiteste erreichte Phase", deckt nicht-lineare Sprünge ab), `feature_from_args`/`feature_from_path` und der seiteneffektfreie `detect_phase_signal`-Detektor.
- **`SessionState` (manager.py:94):** vier neue Felder `project_name`, `abc_phase`, `abc_phase_reached`, `abc_feature`; in `to_read()` ergänzt → fließen automatisch in REST-Liste **und** WS-State-Broadcast (Live-Update „gratis").
- **Detektor-Verdrahtung:** `SessionRuntime._detect_abc()` läuft als reiner Seiteneffekt **vor** der Card-Logik in `request_decision` — verändert nie, OB eine Decision Card entsteht; streamt bei Änderung einen State-Snapshot. `Skill`-Aufruf mit `abc-*` → Phase/erreichte-Phase/Feature; Write/Edit auf `features/PROJ-X-*.md` → Fallback-Feature.
- **`project_name`:** optional in `SessionCreate` (max 120) + `create()`-Parameter; Fallback = Basename von `project_path`. `reset()` vererbt das Label an die Kind-Session.
- **`SessionRead`:** vier neue Felder gespiegelt.
- **Tests (`backend/tests/test_proj8_gantt.py`, neu):** Phasen-Mapping, monotone max-Phase, Feature-Erkennung (Arg + Pfad), Detektor-Logik inkl. Rückwärtssprung & Nicht-Phasen-Skill, Hook-Verdrahtung (Skill öffnet weiterhin Card, Phase wird trotzdem gesetzt), `project_name`-Fallback, REST-Vertrag. **262 Tests grün** (volle Suite).

**Offen für `/abc-frontend`:** `ABC_PHASES` in `lib/status.ts` spiegeln, `GanttChart` unter dem `KanbanBoard`, vier Felder in `types.ts`, `project_name`-Feld im `NewSessionDialog`, Versions-Badge in Rail/Topbar.

## Frontend-Implementierung (2026-06-23)
Next.js (Jupiter-Override), additive, gepollte Lese-Ansicht — kein Extra-Request (nutzt den bestehenden 4s-Poll aus `sessions-provider.tsx`). Gemäß Tech-Design A + Aufgaben-Zuschnitt H:

- **`lib/status.ts`:** `ABC_PHASES` (8er-Liste mit Label + Kürzel, einzige Frontend-Quelle, spiegelt `abc_phases.py`) + `phaseIndex`-Helfer.
- **`lib/types.ts`:** `AbcPhase`-Typ; `Session` um `project_name`/`abc_phase`/`abc_phase_reached`/`abc_feature` erweitert; `SessionCreate` um optionales `project_name`.
- **`components/cockpit/gantt-chart.tsx` (neu):** komponierte Ansicht (Tailwind-Grid, kein nachgebautes Primitive). Phasen-Kopf (8 feste Spalten, sticky Label-Spalte, horizontal scrollbar), eine Zeile pro Session: Bar gefüllt bis `abc_phase_reached`, aktuelle Phase (`abc_phase`) per `ring`/Primärfarbe hervorgehoben. Beendete Sessions eingefroren + ausgegraut (`· beendet`), keine aktuelle Markierung. Neutrale Zeile ohne Phase. Vertikal scrollbar (max-h) für viele Sessions. Eigener Empty-State. `aria-label` je Zelle (offen/abgeschlossen/aktuelle Phase).
- **`app/(cockpit)/page.tsx`:** Gantt-Sektion „ABC-Fortschritt" direkt **unter** dem `KanbanBoard` im Kanban-Tab.
- **`new-session-dialog.tsx`:** neues Feld **„Projekt" als erstes** (vor dem Pfad); Placeholder = live Pfad-Basename; wird als `project_name` an `POST /sessions` durchgereicht (leer → Backend-Fallback).
- **Versions-Badge:** `lib/version.ts` (liest `NEXT_PUBLIC_APP_VERSION`), via `next.config.ts` aus `package.json` injiziert (nicht manuell gepflegt). Dezent `v{version}` neben „🛰️ Jupiter" in Rail + Mobile-Topbar.
- **Tests:** `lib/status.test.ts` (ABC_PHASES/phaseIndex) + `components/cockpit/gantt-chart.test.tsx` (neu: Füllung, Hervorhebung, nicht-linear, neutrale/beendete Zeile, Empty-State, Basename-Fallback) — via `renderToStaticMarkup`. **47 Vitest grün, ESLint sauber, `next build` erfolgreich** (TS clean, Version ins Client-Bundle injiziert).

## QA Test Results
**Getestet:** 2026-06-23 · **Branch:** dev · **Tester:** QA-Engineer (abc-qa)
**Automatisiert:** Backend `pytest` 263 grün (davon 50 PROJ-8) · Frontend `vitest` 47 grün (davon 32 status + Gantt) · `next build` erfolgreich (TS clean) · ESLint sauber.

### Akzeptanzkriterien (11/11 bestanden)
| # | Kriterium | Ergebnis | Nachweis |
|---|-----------|----------|----------|
| 1 | Gantt unter dem Kanban (eigener Abschnitt) | ✅ | `page.tsx` `<section> ABC-Fortschritt` direkt nach `<KanbanBoard/>` im Kanban-Tab |
| 2 | Eine horizontale Bar pro Session | ✅ | `GanttRow` je Session; Render-Test |
| 3 | Links Projektname + Feature-Indikation | ✅ | RowLabel `name` + „Feature N"; Test `Jupiter`/`Feature 8` |
| 4 | 8 Phasen-Spalten in fester Reihenfolge | ✅ | `ABC_PHASES`-Header; Test prüft exakte Reihenfolge |
| 5 | Bar bis zuletzt abgeschlossene Phase, aktuelle hervorgehoben | ✅ | Fill bis `abc_phase_reached`, `ring` auf `abc_phase`; Tests (linear + nicht-linear) |
| 6 | Projektname aus Session-Erstellung, Dialog fragt zuerst Projekt | ✅ | „Projekt"-Feld als **erstes** im `NewSessionDialog` → `project_name` an `POST /sessions` |
| 7 | Aktuelles Feature dynamisch aus der Session | ✅ | Detektor liest Skill-`args`/berührtes Spec-File; E2E-Test (Hook→`GET /sessions`) |
| 8 | Live-Aktualisierung (gleiche Polling-Mechanik) | ✅ | Felder über `to_read()` in REST-Liste **und** WS-Broadcast; kein Extra-Request |
| 9 | Phasen-Mapping konsistent mit Ampel/Kanban | ✅ | Phase aus `abc-*`-Skill abgeleitet (eigene Achse), `abc-qa`/`abc-qa-e2e → qa` |
| 10 | Responsive (Desktop-first, horizontal scrollbar) | ✅ | `overflow-x-auto` + `min-w`, `sm:`-Breakpoints, `max-h` vertikal scrollbar |
| 11 | Versions-Anzeige in der Sidebar neben „Jupiter" | ✅ | `v{version}` in Rail + Mobile-Topbar; ins Client-Bundle injiziert (verifiziert) |

### Edge Cases (alle abgedeckt)
- Session ohne ABC-Phase → neutrale Zeile, leerer Track (Test: 8 Zellen „offen", keine Hervorhebung).
- Mehrere Sessions/Projekt → mehrere Zeilen, gleiches Label (eine Zeile/Session by design).
- Feature unklar (Skill ohne Arg) → Projektname ohne Feature-Suffix, zuvor bekanntes Feature bleibt erhalten.
- Phasen nicht-linear (Deploy↔Document, FE↔BE) → Bar füllt bis weiteste Phase, aktuelle separat markiert (Test).
- Projekt ohne ABC-Struktur → Phase „none", neutrale Zeile.
- 0 Sessions → eigener Empty-State („Noch keine Sessions mit ABC-Phase.").
- Viele Sessions → vertikal scrollbarer Bereich (`max-h-[24rem]`).
- Session beendet/Fehler → letzter Stand eingefroren + ausgegraut, „· beendet", keine aktuelle Markierung (Test).

### Security-/Red-Team-Audit
> Kontext: Jupiter ist Single-User-MVP — **kein JWT/RLS/Mandanten-Isolation** (bewusster Override, siehe `routes/sessions.py`). Tenant-Red-Team daher N/A.
- **Neuer Code-Pfad (Detektor im Freigabe-Hook):** gegen feindliche/malformede `tool_input` geprobt (None, `skill` als int, `args` als dict/list, fehlende Keys) → **kein Crash**, fail-safe; ändert nie, OB eine Decision Card entsteht.
- **Kein neuer Endpoint, keine neue Trust-Boundary:** Detektor liest nur bereits durch den Hook fließende Felder. `/internal/permission` bleibt token-/localhost-geschützt (Regression-Test 403 grün).
- **XSS:** `project_name`/`abc_feature` werden als **Text** in JSX gerendert (React escaped; kein `dangerouslySetInnerHTML`) → sicher.
- **DoS:** `project_name` serverseitig auf 120 Zeichen begrenzt (Pydantic).

### Regression
Backend 263 grün (PROJ-1/2/4/5/6/7 inkl. Decision-Card-Flow unverändert), Frontend 47 grün (status/Kanban-Mapping unverändert). Detektor-Hook stört den bestehenden PROJ-4-Freigabe-Flow nicht.

### Hinzugefügte Tests (permanente Regression)
- `backend/tests/test_proj8_gantt.py` — Mapping, max-Phase, Feature-Erkennung, Detektor (inkl. Rückwärtssprung/Nicht-Phasen-Skill), Hook-Verdrahtung, **E2E REST+Hook → `GET /sessions`**, `project_name`-Fallback, REST-Vertrag (50 Tests).
- `nextjs_app/lib/status.test.ts` — `ABC_PHASES`/`phaseIndex`.
- `nextjs_app/components/cockpit/gantt-chart.test.tsx` — Füllung, Hervorhebung, nicht-linear, neutrale/beendete Zeile, Empty-State, Basename-Fallback.

### Bugs
Keine. **0 Critical / 0 High / 0 Medium / 0 Low.**

### Production-Ready: ✅ JA
Keine Critical/High-Bugs. Alle 11 AC + alle dokumentierten Edge Cases bestanden. Empfehlung: **Approved**.

> Hinweis (kein Bug): Eine vollständige visuelle Browser-Verifikation (Bars live wandern bei echtem `abc-*`-Skill-Lauf, 375/768/1440 px) wurde **nicht** in einem laufenden Full-Stack-Build durchgeführt — die Ansicht ist reines CSS-Grid (build-verifiziert) + Render-Tests. Empfohlen als kurzer Smoke beim `/abc-deploy`.

## Deployment
_To be added by /abc-deploy_
