# PROJ-4: Decision Cards — Freigabe-Flow

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — Session signalisiert genehmigungspflichtige Aktion
- Requires: PROJ-3 (Cockpit) — Cards werden im Cockpit/Kanban angezeigt

## Beschreibung
Der Entscheidungsmoment, optimiert: Wenn eine Session deine Freigabe braucht, entsteht eine **Decision Card** mit allem für eine 5-Sekunden-Entscheidung (#4). Im MVP **fixer konservativer Trigger** (Schreib-/Shell-Operationen → Card, reine Lesezugriffe → auto); die konfigurierbare Trust-Policy (#5) ist P1.

## User Stories
- Als Nutzer möchte ich benachrichtigt werden, wenn ein Agent meine Freigabe braucht.
- Als Nutzer möchte ich in einer Karte sofort sehen, was der Agent will, warum, und den relevanten Ausschnitt (Diff/Befehl), um in Sekunden zu entscheiden.
- Als Nutzer möchte ich Freigeben / Ablehnen / Mit Kommentar zurück / In Session springen.

## Acceptance Criteria
- [ ] Erreicht eine Session eine genehmigungspflichtige Aktion (fixer konservativer Trigger: Schreib-/Shell-Operationen → Card; reine Lesezugriffe → auto), entsteht eine Decision Card.
- [ ] Karte zeigt: **Was** (Aktion), **relevanter Ausschnitt** (Diff/Befehl — NICHT das ganze Log), **Warum**, **Kontext** (Projekt / abc-Phase).
- [ ] Aktionen: **Freigeben**, **Ablehnen**, **Mit Kommentar zurück**, **In Session springen**.
- [ ] Freigabe/Ablehnung wird an die wartende Session zurückgespielt; Session läuft entsprechend weiter oder bricht ab.
- [ ] Eine wartende Session erscheint im Kanban (PROJ-3) in der Spalte „Wartet auf dich".
- [ ] Der Trigger ist im MVP fix/konservativ und an **einer** zentralen Stelle im Code definiert (vorbereitet auf konfigurierbare Policy #5).

## Edge Cases
- Mehrere offene Cards gleichzeitig → klar gelistet, einzeln entscheidbar.
- Session stirbt, während eine Card offen ist → Card wird als „obsolet" markiert.
- Nutzer ignoriert Card lange → Session bleibt sauber pausiert (kein Timeout-Autoproceed).
- „Mit Kommentar zurück" → Kommentartext wird als nächste Eingabe an die Session gesendet.

## Technical Requirements (optional)
- Trigger-Logik an einer zentralen Stelle kapseln, damit #5 (konfigurierbare Trust-Policy, P1) sie ersetzen kann.
- Ausschnitt-Erzeugung (Diff/Befehl statt Volltext) zahlt auf Token-Disziplin ein.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
