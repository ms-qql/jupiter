# PROJ-31: Spec-Links im MD-Reader auflösen (Doku führt ins Leere)

## Status: Planned
**Created:** 2026-06-24
**Last Updated:** 2026-06-24

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
2. **Auflösungs-Basis** — relativ zur Datei (Standard) vs. relativ zu einer Vault-/Projekt-Root? _Default:_ relativ zur aktuell geöffneten Datei (Standard-Markdown-Semantik).
