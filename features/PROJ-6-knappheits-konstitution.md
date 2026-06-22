# PROJ-6: Knappheits-Konstitution

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — Konstitution wird beim Session-Start injiziert

## Beschreibung
Output-Kultur zentral durchgesetzt (#24): ein global gepflegter System-Prompt („Konstitution"), der bei jedem Session-Start injiziert wird und Disziplin erzwingt — keine Vorreden, keine Wiederholungen, keine „Soll ich…?"-Schleifen. Pro Rolle/Skill überschreibbar. Klein, aber prägt das Verhalten **aller** Sessions (deshalb früh in der Bau-Reihenfolge).

## User Stories
- Als Nutzer möchte ich, dass alle Sessions standardmäßig knapp und ohne Geschnatter antworten, um Tokens zu sparen.
- Als Nutzer möchte ich die Konstitution pro Rolle überschreiben können, wenn eine Rolle bewusst mehr Ausführlichkeit braucht.
- Als Nutzer möchte ich die effektive Konstitution einer Session einsehen können (Transparenz).

## Acceptance Criteria
- [ ] Ein zentral gepflegter globaler System-Prompt (Konstitution) wird beim Start jeder Session injiziert.
- [ ] Inhalt erzwingt: keine Vorreden, keine Wiederholungen, keine „Soll ich…?"-Schleifen, knappe Antworten.
- [ ] Pro Rolle/Skill kann die Konstitution ergänzt oder überschrieben werden.
- [ ] Die **effektive** Konstitution einer Session (global + Rollen-Override) ist einsehbar.

## Edge Cases
- Rolle ohne Override → globale Konstitution gilt.
- Konflikt zwischen globaler Regel und Rollen-Regel → Rollen-Override gewinnt, nachvollziehbar dokumentiert.
- Leere/fehlende Konstitution → Session startet trotzdem (kein Hard-Fail).

## Technical Requirements (optional)
- Konstitution als **versioniertes Artefakt** (Vault/Config), nicht hartcodiert — so bleibt sie ohne Deploy editierbar.
- Zusammenspiel mit PROJ-1: Injektion beim `claude -p`-Start (System-Prompt-Mechanismus).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
