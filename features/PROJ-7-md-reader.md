# PROJ-7: MD-Reader

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung) — liefert die MD-Dateien + Suche/Index

## Beschreibung
Doku ohne Tool-Wechsel: Vault-MD im Browser lesen, mit Obsidian-DNA (#16, **read-first**). `[[Wikilinks]]` werden klickbar gerendert; Handovers/Doku zu einer Session sind direkt aufrufbar. Der volle Editor (#16 voll) ist P1.

## User Stories
- Als Nutzer möchte ich Vault-MD-Dateien im Browser lesen, ohne das Tool zu wechseln.
- Als Nutzer möchte ich `[[Wikilinks]]` anklicken, um zwischen Doku-Dateien zu navigieren.
- Als Nutzer möchte ich Handovers/Doku zu einer Session direkt aufrufen.

## Acceptance Criteria
- [ ] MD-Dateien aus dem Vault (über PROJ-2) werden gerendert dargestellt (Headings, Listen, Code, Tabellen).
- [ ] `[[Wikilinks]]` werden als klickbare Links gerendert und navigieren zur Zieldatei (falls vorhanden).
- [ ] Datei-Navigation/Baum, um Vault-MD zu durchstöbern.
- [ ] YAML-Frontmatter wird sauber dargestellt (nicht als roher Text).
- [ ] **Read-only** (Editor = P1).

## Edge Cases
- Wikilink auf nicht-existente Datei → als „fehlend" markiert, kein Crash.
- Sehr große MD-Datei → lädt performant (Lazy/Virtualisierung).
- Nicht-MD-Datei angeklickt → Hinweis statt Fehlversuch.
- Bild-Embeds (`![[bild.png]]`) → Platzhalter (Anzeige = nice-to-have).

## Technical Requirements (optional)
- Markdown-Rendering React-seitig; Wikilink-Auflösung gegen den Vault-Index aus PROJ-2.
- Keine Schreibpfade im MVP (read-only); Architektur hält Editor (#16 voll, P1) offen.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
