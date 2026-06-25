# PROJ-35: Session-Titel = eingegebener Projektname (Sidebar + Header) statt „jupiter"

## Status: In Progress
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Implementation Notes (Frontend)
- **Branch:** dev. Reiner Next.js-Anzeige-Fix, keine Backend-/DB-Änderung (wie im Tech-Design).
- Neuer geteilter Helper `displayName(session)` in `nextjs_app/lib/status.ts` (neben `projectName`): `project_name?.trim() || projectName(project_path)`. Strukturell typisiert ({project_name, project_path}) → nutzbar für `Session` **und** `SessionDetail`.
- Drei Render-Stellen von `projectName(session.project_path)` auf `displayName(session)` umgestellt, jeweils mit `title`-Attribut für Volltext-Tooltip bei langen Titeln (`truncate` war schon vorhanden):
  - `nextjs_app/components/cockpit/session-rail.tsx` (Sidebar/Rail-Item)
  - `nextjs_app/components/cockpit/session-tile.tsx` (Cockpit-Kachel)
  - `nextjs_app/app/(cockpit)/sessions/[id]/page.tsx` (Session-Header `<h1>`)
- Konsistenz: `DeleteSessionButton`-`projectName`-Prop in Rail + Tile ebenfalls auf `displayName(session)` umgestellt → Lösch-Dialog nennt denselben Namen wie die Anzeige.
- Verifikation: `npx tsc --noEmit` ohne neue Fehler in den geänderten Dateien (einziger Fehler vorbestehend in `lib/md-tree.test.ts`), `eslint` der vier Dateien sauber.

## Dependencies
- Requires: PROJ-3 (Cockpit / Session-Rail + Session-Header) — die Anzeigeorte.
- Requires: PROJ-9 (Smart Launcher / Neue-Session-Dialog) — liefert das Feld `project_name` aus dem Dialogfeld „Projekt".

## Beschreibung
In der linken Sidebar („AKTIVE SESSIONS") und im **Header über dem Session-Fenster** wird aktuell **immer der Ordnername** angezeigt — bei allen Sessions im selben Projektordner also stur **„jupiter"**. Dadurch sind parallele Sessions **nicht unterscheidbar**.

Befund aus dem Code: Das beim Erstellen eingegebene Feld **`project_name`** (Dialogfeld „Projekt") wird **bereits gespeichert und mit der Session zurückgeliefert**, aber Sidebar und Header rendern stur `projectName(session.project_path)` (= Pfad-Basename) und **ignorieren `project_name`**.

Gewünscht: Sidebar **und** Header (und konsistent die Session-Kachel im Cockpit, falls dort derselbe Name steht) zeigen den **eingegebenen Projekttitel**. Der Nutzer trägt dort typischerweise die **Feature-Nummer** ein → Sessions werden auseinanderhaltbar. Fehlt ein Titel, bleibt der **Pfad-Basename als Fallback**.

## User Stories
- Als Nutzer möchte ich, dass jede Session in der **Sidebar** den von mir eingegebenen **Projekttitel** trägt (oft die Feature-Nummer), damit ich mehrere Sessions im selben Ordner unterscheiden kann.
- Als Nutzer möchte ich, dass der **Header über dem Session-Fenster** denselben eingegebenen Titel zeigt, damit ich beim Öffnen sofort weiß, in welcher Session ich bin.
- Als Nutzer möchte ich, dass bei **leer gelassenem** Projekttitel weiterhin der **Ordnername** angezeigt wird, damit alte/schnelle Sessions nicht namenlos sind.
- Als Nutzer möchte ich, dass der Titel **überall konsistent** ist (Sidebar, Header, Kachel), damit dieselbe Session nicht zwei verschiedene Namen trägt.

## Acceptance Criteria
- [ ] In der **Sidebar** („AKTIVE SESSIONS") zeigt jede Session `project_name`, sofern gesetzt; sonst Fallback auf `projectName(project_path)` (Basename).
- [ ] Im **Header über dem Session-Fenster** (Session-Detail) gilt dieselbe Logik (`project_name` || Basename).
- [ ] Wenn dieselbe Session an weiteren Stellen benannt wird (z. B. Cockpit-Kachel `SessionTile`), wird **dieselbe** Logik verwendet — keine widersprüchlichen Namen.
- [ ] Zwei Sessions im **gleichen** Projektordner mit **unterschiedlichem** Titel werden in der Sidebar **unterschiedlich** angezeigt.
- [ ] Eine Session **ohne** Titel zeigt unverändert den Pfad-Basename (Regression-frei zu heute).
- [ ] Lange Titel werden **abgeschnitten/ellipsiert** (kein Layoutbruch der Sidebar), Tooltip/`title`-Attribut zeigt optional den vollen Wert.

## Edge Cases
- **Bestandssessions ohne `project_name`** (vor diesem Fix erstellt) → fallen sauber auf den Basename zurück, kein Crash/leerer Name.
- **Sehr langer Titel / Sonderzeichen** → Ellipsis + kein Umbruch; keine HTML-Injektion (Text wird escaped gerendert).
- **Titel == Ordnername** → unproblematisch, zeigt schlicht denselben Text.
- **Leerer/Whitespace-Titel** → wird wie „nicht gesetzt" behandelt (trim), Fallback auf Basename.
- **Titel-Änderung nach Erstellung** (falls später editierbar — out of scope hier) → diese Spec deckt nur Anzeige beim Erstellungswert ab.

## Technical Requirements (optional)
- Reiner **Frontend-Anzeige-Fix**; das Feld `project_name` existiert bereits in `Session` und kommt vom Backend — **keine** DB-/Schema-/API-Änderung nötig.
- Betroffen: `nextjs_app/components/cockpit/session-rail.tsx` (RailItem) und `nextjs_app/app/(cockpit)/sessions/[id]/page.tsx` (Header `<h1>`); ggf. `SessionTile` für Konsistenz.
- Gemeinsame Hilfslogik „Anzeigename" (z. B. `displayName(session) = session.project_name?.trim() || projectName(session.project_path)`) statt an drei Stellen duplizierter Inline-Logik.
- Texte deutsch; sicheres Text-Rendering (kein `dangerouslySetInnerHTML`).

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (App Router, nur Frontend) · keine Backend-/DB-Änderung · **Branch:** dev

### Befund (am Code verifiziert)
- `Session.project_name: string | null` existiert bereits im Typ (`nextjs_app/lib/types.ts:108`, aus PROJ-8/Gantt) und kommt vom Backend zurück — **keine** API-/Schema-/DB-Arbeit nötig.
- Drei Render-Stellen zeigen stur den Pfad-Basename via `projectName(session.project_path)`:
  - Sidebar/Rail-Item: `nextjs_app/components/cockpit/session-rail.tsx:191`
  - Cockpit-Kachel: `nextjs_app/components/cockpit/session-tile.tsx:51`
  - Session-Header `<h1>`: `nextjs_app/app/(cockpit)/sessions/[id]/page.tsx:153`
- Helper `projectName(path)` liegt in `nextjs_app/lib/status.ts:206` (Basename aus Pfad). Bleibt als Fallback erhalten.
- Alle drei Stellen tragen bereits `truncate` → Ellipsis ist vorhanden; es fehlt nur ein `title`-Attribut für den Volltext.

### Was gebaut wird
**Ein** neuer geteilter Helper neben `projectName` in `lib/status.ts`:
`displayName(session)` → getrimmter `project_name`, sonst Basename. Eine Quelle der Wahrheit, kein dreifaches Inline-Duplikat. (WHY: verhindert, dass dieselbe Session in Sidebar/Header/Kachel auseinanderlaufende Namen zeigt — genau das Akzeptanzkriterium „überall konsistent".)

Die drei Render-Stellen tauschen `projectName(session.project_path)` gegen `displayName(session)` und bekommen ein `title={displayName(session)}` für den Volltext-Tooltip bei langen Titeln.

### Komponenten-/Datenfluss (keine neuen Komponenten)
```
lib/status.ts
└── displayName(session) = session.project_name?.trim() || projectName(session.project_path)
        ▲                         ▲                              ▲
        │                         │                              │
session-rail.tsx (RailItem)  session-tile.tsx (SessionTile)  sessions/[id]/page.tsx (Header <h1>)
   truncate + title              truncate + title                 title
```

### Daten / API / DB
- Datenmodell: unverändert. `project_name` ist bereits Teil von `Session`.
- API: keine. DB/RLS/MinIO: keine.

### Hinweis zur DeleteSessionButton-Prop
`session-rail.tsx:200` und `session-tile.tsx:68` geben `projectName(...)` als `projectName`-Prop an `DeleteSessionButton` (Bestätigungstext „Session ‚X' löschen?"). Konsistenz-Empfehlung: auch dort `displayName(session)` verwenden, damit der Lösch-Dialog denselben Namen nennt wie die Anzeige. (Anzeige-Kriterien fordern es nicht zwingend, aber es vermeidet einen zweiten Namen für dieselbe Session.)

### Tech-Entscheidungen (WHY)
- **Helper statt Inline-Logik:** Akzeptanzkriterium „keine widersprüchlichen Namen" ist nur garantierbar, wenn alle Stellen dieselbe Funktion aufrufen.
- **Fallback auf Basename:** Bestandssessions ohne `project_name` (vor PROJ-8) und leer gelassene Titel bleiben benannt — Regression-frei.
- **`trim()` im Helper:** Whitespace-only-Titel = „nicht gesetzt" → Fallback, ohne dass jede Render-Stelle das wissen muss.
- **`title`-Attribut statt eigenes Tooltip-Widget:** Ellipsis ist schon da (`truncate`); natives `title` reicht für den Volltext, kein Layout-/Komponenten-Aufwand. Text wird als JSX-Child/Attribut gerendert → automatisch escaped, keine Injektion.

### Dependencies
Keine neuen Pakete (Frontend wie Backend).

### Aufwand / Risiko
Sehr klein (1 Helper + 3 Edits, optional 2 Prop-Edits). Risiko gering; einzige Regressionsfläche ist der Basename-Fallback (durch Edge Cases abgedeckt).
