# PROJ-35: Session-Titel = eingegebener Projektname (Sidebar + Header) statt „jupiter"

## Status: Planned
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

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
