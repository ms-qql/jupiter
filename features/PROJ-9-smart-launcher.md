# PROJ-9: Smart Launcher — mitdenkender Session-Start

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #12

## Dependencies
- Requires: PROJ-3 (Cockpit / `NewSessionDialog`) — der Launcher ersetzt/erweitert den heutigen „Neue Session"-Dialog.
- Requires: PROJ-1 (Engine-Treiber) — startet die Session mit gewähltem Skill/Modell.
- Verwandt: PROJ-6 (Konstitution/Rollen) — Rollen-Vorschlag korreliert mit der abc-Phase. PROJ-8 (Gantt) — nutzt dieselbe Phasen-/Feature-Logik.

## Beschreibung
Der „Neue Session"-Start ist kein leeres Formular mehr, sondern ein **Vorschlag aus dem eigenen Workflow**: Jupiter liest die `features/INDEX.md` des gewählten Projekts, erkennt das nächste sinnvolle Feature + die nächste ABC-Phase und schlägt **Skill, Rolle und Modell** vor. Default-Engine bleibt Claude Max. Der Nutzer bestätigt oder überschreibt.

## User Stories
- Als Nutzer möchte ich beim Session-Start einen konkreten Vorschlag (Feature + nächste abc-Phase + Skill) sehen, damit ich nicht selbst in der INDEX.md nachschlagen muss.
- Als Nutzer möchte ich den vorgeschlagenen Skill/Rolle/Modell mit einem Klick übernehmen oder einzeln überschreiben.
- Als Nutzer möchte ich, dass das passende Modell (Haiku/Sonnet/Opus) zur Phase vorgeschlagen wird (z. B. Opus für Architektur, Haiku für mechanische Phasen).
- Als Nutzer möchte ich für Ad-hoc-Arbeit den Vorschlag ignorieren und frei einen Prompt eingeben können.
- Als Nutzer möchte ich, dass Projekte ohne `features/INDEX.md` trotzdem startbar sind (Freitext-Modus).

## Acceptance Criteria
- [ ] Beim Öffnen des Dialogs nach Projektwahl wird die `features/INDEX.md` des Projekts gelesen und das **nächste empfohlene Feature** (erste Zeile, deren Status nicht „Deployed" ist) ermittelt.
- [ ] Aus dem Feature-Status wird die **nächste abc-Phase** abgeleitet (z. B. Status „Architected" → nächste Phase „Frontend/Backend") und der zugehörige `abc-*`-Skill vorgeschlagen.
- [ ] Es wird ein **Modell-Vorschlag** je Phase angezeigt (mappingbasiert, überschreibbar).
- [ ] Der Vorschlag ist mit **einem Klick übernehmbar** („Vorschlag starten") und füllt Skill, Rolle, Modell, Initial-Prompt vor.
- [ ] Jedes Feld bleibt **manuell überschreibbar** (Phase, Skill, Modell, Prompt).
- [ ] Projekt ohne `features/INDEX.md` → Hinweis „Kein abc-Workflow erkannt" + Fallback auf den heutigen Freitext-Dialog, ohne Fehler.
- [ ] Der gewählte Skill + sein Argument werden so an die Session übergeben, dass PROJ-8 daraus `abc_phase`/`abc_feature` lesen kann.
- [ ] Alle Texte deutsch; Lade-/Fehler-/Leer-Zustände explizit.

## Edge Cases
- **INDEX.md leer / nur Deployed-Features** → Vorschlag „Alle Features deployed — neues Feature mit `/abc-requirements`?".
- **Mehrere Features in Arbeit** → das mit dem geringsten Reifegrad bzw. höchster Prio vorschlagen; Auswahlliste anbieten.
- **Status nicht parsebar** (manuell editierte INDEX) → robust degradieren auf Freitext, kein Crash.
- **Projektpfad außerhalb erlaubter Roots** → gleiche Scope-Prüfung wie heute (`validate_project_path`), klare Fehlermeldung.
- **Skill ohne klaren Phasenbezug** (z. B. refactor) → kein Phasen-Vorschlag, nur Modell/Prompt.

## Technical Requirements (optional)
- Datenquelle: Datei-Read der `features/INDEX.md` im Projekt (kein neuer DB-State).
- Phasen-/Modell-Mapping aus derselben zentralen Konstante wie PROJ-8 (`abc_phases`).
- Antwortzeit des Vorschlags < 300 ms (reiner File-Parse).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
