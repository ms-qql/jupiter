# PROJ-8: ABC-Workflow-Gantt — Phasen-Fortschritt je Session/Projekt

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23

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
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
