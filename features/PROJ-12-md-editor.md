# PROJ-12: MD-Editor (voll) — Obsidian-DNA

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #16 (voller Ausbau; Reader = PROJ-7)

## Dependencies
- Requires: PROJ-7 (MD-Reader) — erweitert die read-only-Ansicht um Editieren; nutzt denselben Index, Wikilink-Parser, Frontmatter-Split.
- Verwandt: PROJ-2 (Vault) — Schreiben zurück in den Hal-Vault.

## Beschreibung
Der MD-Reader (PROJ-7) wird zum **leichten Editor mit Obsidian-DNA**: Markdown nicht nur lesen, sondern direkt **bearbeiten und speichern**, mit `[[Wikilinks]]` (inkl. Autovervollständigung) und **Backlinks**. Ziel: Doku lebendig bearbeitbar, kein Tool-Wechsel zu Obsidian.

## User Stories
- Als Nutzer möchte ich eine `.md`-Datei direkt im Jupiter-UI bearbeiten und speichern, ohne nach Obsidian zu wechseln.
- Als Nutzer möchte ich beim Tippen von `[[` eine Autovervollständigung existierender Notizen bekommen.
- Als Nutzer möchte ich die **Backlinks** einer Notiz sehen (welche Dateien verlinken hierher).
- Als Nutzer möchte ich zwischen **Edit- und Vorschau-Modus** wechseln (oder Split-View).
- Als Nutzer möchte ich, dass das Frontmatter (YAML) erhalten und valide bleibt.

## Acceptance Criteria
- [ ] Editor lädt Inhalt (Frontmatter + Body) und speichert zurück an denselben Pfad (`PUT`/Save), atomar (kein Teil-Schreiben).
- [ ] `[[`-Eingabe öffnet eine **Autovervollständigung** aus dem MD-Index (PROJ-7); Auswahl fügt einen gültigen Wikilink ein.
- [ ] Wikilinks im Vorschaumodus sind klickbar und navigieren zur Zieldatei (Auflösung wie PROJ-7).
- [ ] **Backlinks-Panel** zeigt alle Dateien, die auf die aktuelle Notiz verlinken.
- [ ] Umschalten **Edit ↔ Vorschau** (mind. eines von beidem; Split-View optional); Body-Markdown rendert mit Tabellen/Code/Headings.
- [ ] **Ungespeicherte Änderungen** werden erkannt; Warnung beim Verlassen/Navigieren.
- [ ] Schreibziel ist auf erlaubte Roots/Vault beschränkt; Pfad serverseitig geprüft.
- [ ] Alle Texte deutsch; Lade-/Fehler-/Speicher-Zustände explizit.

## Edge Cases
- **Externe Änderung** der Datei seit dem Laden → Konflikt erkennen (z. B. mtime/Hash), nachfragen statt blind überschreiben.
- **Ungültiges Frontmatter** beim Speichern → Validierung, klare Fehlermeldung, kein Datenverlust.
- **Wikilink auf nicht existierende Notiz** → als „unaufgelöst" markieren (nicht klickbar), kein Crash.
- **Sehr große Datei** → performant laden/scrollen; ggf. Edit-Limit mit Hinweis.
- **Gleichzeitiges Editieren in zwei Tabs** → letzter Speichervorgang gewinnt, aber mit Konflikt-Warnung.

## Technical Requirements (optional)
- Baut auf den vorhandenen PROJ-7-Komponenten (`md-tree`, `remark-wikilink`, `markdown-view`) und dem `/md`-Backend auf.
- Speichern atomar (temp + rename); Schreibpfad serverseitig auf Vault/Roots beschränkt.
- Optimistic UI mit Rollback bei Speicherfehler.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
