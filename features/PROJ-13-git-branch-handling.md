# PROJ-13: Git-Branch-Handling (in-App, abc-konform)

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #31

## Dependencies
- Requires: PROJ-3 (Cockpit) — Branch-Status erscheint im Kontext von Projekt/Session.
- Verwandt: PROJ-8 (Gantt/abc-Phasen) und die Branch-Strategie des `abc-architecture`-Skills (`main ↔ dev`, `specs/PROJ-X-…`).

## Beschreibung
Eine **Ein-Klick-UI** für die Git-Branch-Logik des abc-Workflows — ohne Terminal: aktuellen Branch je Projekt/Session sehen, einfach wechseln (`main ↔ dev`), Feature-Branches `specs/PROJ-X-<slug>` anlegen und am Ende `dev → main` promoten. Die Versionskontroll-Logik des abc-Workflows wird sichtbar und bedienbar.

## User Stories
- Als Nutzer möchte ich pro Projekt den aktuellen Branch und den Sauberkeits-Status (clean/dirty) sehen.
- Als Nutzer möchte ich mit einem Klick zwischen `main` und `dev` wechseln.
- Als Nutzer möchte ich einen Feature-Branch `specs/PROJ-X-<slug>` aus der Feature-Auswahl anlegen.
- Als Nutzer möchte ich am Feature-Ende `dev → main` (bzw. Feature-Branch → `dev`) **promoten**, geführt und mit Vorab-Check.
- Als Nutzer möchte ich vor einem Wechsel/Merge gewarnt werden, wenn uncommittete Änderungen vorliegen.

## Acceptance Criteria
- [ ] Anzeige je Projekt: **aktueller Branch**, ahead/behind, **clean/dirty**, Liste vorhandener Branches.
- [ ] **Branch-Wechsel** per Klick; bei dirty Working Tree wird gewarnt und blockiert/optionen angeboten (stash/abbrechen), nie stiller Datenverlust.
- [ ] **Feature-Branch anlegen** mit korrektem Schema `specs/PROJ-X-<kebab-slug>` (Slug aus Spec-Titel), von `main` bzw. `dev` abgezweigt.
- [ ] **Promote-Flow** `dev → main` (und Feature → `dev`): Vorab-Check (clean, Branch ⊇ Ziel), Bestätigung, dann Merge `--no-ff`.
- [ ] Merge-/Wechsel-**Konflikte** werden klar gemeldet; die App führt keinen erzwungenen Merge aus.
- [ ] Alle Git-Operationen laufen **innerhalb der erlaubten Roots** und nur auf echten Git-Repos.
- [ ] Aktion ist nachvollziehbar protokolliert (welcher Branch, welche Operation, Ergebnis).
- [ ] Alle Texte deutsch; gefährliche Operationen (force) sind **nicht** Ein-Klick.

## Edge Cases
- **Dirty Working Tree** beim Wechsel → Optionen statt Zwang (stash / commit-Hinweis / abbrechen).
- **Merge-Konflikt** beim Promote → abbrechen + verständlicher Hinweis, Auflösung bleibt manuell/Terminal.
- **Kein Git-Repo** im Projekt → Aktionen ausgegraut, Angebot „git init?".
- **Branch existiert bereits** (z. B. Feedback-Runde 2) → auschecken statt neu anlegen.
- **Remote nicht erreichbar** → lokale Operationen funktionieren, Push/Pull klar getrennt und mit Fehlertoleranz.
- **Detached HEAD** → erkennen und sicher zurück auf einen Branch führen.

## Technical Requirements (optional)
- Backend kapselt Git über parametrisierten Subprozess (keine interaktiven Flags `-i`).
- Force-Operationen erfordern explizite, gesonderte Bestätigung (kein Default).
- Status-Abfrage performant (< 500 ms), pollbar im Cockpit.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
