# PROJ-3: Cockpit — Mission Control + Session-Kanban + Ampel-Kacheln

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — für Session-Status/Events
- Requires: PROJ-2 (Vault-Anbindung) — für Session-Liste/Persistenz

## Beschreibung
Das Gesicht von Jupiter: der erste Screen als kompaktes Lagebild der gesamten Flotte. Mission Control (#1) + Ampel-Kacheln (#2) + Session-Kanban nach Zustand (#3). Enthält die manuelle Modell-Wahl pro Session (UI-Seite von #22). Cockpit-first, nicht Chat-first.

## User Stories
- Als Nutzer möchte ich beim Öffnen von Jupiter ein kompaktes Lagebild aller Agenten und Sessions sehen.
- Als Nutzer möchte ich Sessions als Kacheln mit Ampel sehen (arbeitet / wartet auf dich / fertig / Fehler), um Handlungsbedarf sofort zu erkennen.
- Als Nutzer möchte ich Sessions in einem Kanban nach Zustand sehen (Arbeitet → Wartet auf dich → Review/Approval → Fertig).
- Als Nutzer möchte ich pro Session das Modell wählen (Haiku/Sonnet/Opus).
- Als Nutzer möchte ich auf eine Kachel klicken und in die Session-Detailansicht springen.

## Acceptance Criteria
- [ ] Startbildschirm zeigt einen kleinen globalen Status (Anzahl aktiv / wartend / Fehler) + Liste aller Sessions.
- [ ] Jede Session-Kachel zeigt ohne Klick: Ampel-Status, aktive Rolle/Skill, Projekt, Laufzeit.
- [ ] Kanban-Board mit Spalten **Arbeitet / Wartet auf dich / Review/Approval / Fertig**; Karten wandern bei Statuswechsel automatisch.
- [ ] „Wartet auf dich" ist visuell das stärkste Signal.
- [ ] Modell-Auswahl (Haiku/Sonnet/Opus) pro Session in der UI; Auswahl wird an den Treiber (#22, PROJ-1) durchgereicht.
- [ ] Live-Aktualisierung der Kachel-Zustände (WebSocket oder Polling) ohne manuelles Reload.
- [ ] Responsive (Desktop-first; nutzbar ab Tablet).

## Edge Cases
- 0 Sessions → klarer Empty-State mit „Neue Session"-CTA.
- Viele Sessions (> 20) → Board bleibt performant und scrollbar.
- Backend nicht erreichbar → Fehler-State statt leerem/irreführendem Board.
- Session im Fehlerstatus → rote Ampel + Kurzgrund direkt auf der Kachel.

## Technical Requirements (optional)
- Next.js 16 (App Router) + React + Tailwind + shadcn/ui; Komponenten zuerst aus shadcn/ui (kein Hand-Roll von Card/Tabs/Dialog).
- Live-Updates via WebSocket oder Polling gegen PROJ-1.
- Alle Texte deutsch; Loading/Error/Empty/Success-States explizit.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
