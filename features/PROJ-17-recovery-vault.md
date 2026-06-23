# PROJ-17: Recovery über den Vault

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #20 (kritischstes Failure-Szenario)

## Dependencies
- Requires: PROJ-2 (Vault) — der Vault ist die persistente Wahrheit/Recovery-Quelle.
- Requires: PROJ-5 (Handover) — der letzte Handover ist der Wiederanknüpfpunkt.
- Requires: PROJ-1 / PROJ-14 (Engine + Persistenz-Seam) — rekonstruierte Sessions werden wieder als Live-Sessions geführt.

## Beschreibung
Nach einem VPS-Reboot oder Backend-Crash **rekonstruiert Jupiter Sessions aus dem Vault** bis zum letzten Handover und bietet pro Strang einen „Hier ging's weiter"-Vorschlag an. Der Vault wirkt als **Crash-Recovery-Journal** — ein Konzept, das zusammen mit Gedächtnis (#9) und Doku (#8) dreifach zahlt.

## User Stories
- Als Nutzer möchte ich nach einem Reboot eine Liste wiederherstellbarer Sessions sehen, statt bei null anzufangen.
- Als Nutzer möchte ich pro Session den letzten bekannten Stand (Handover) und einen „Hier weitermachen"-Vorschlag sehen.
- Als Nutzer möchte ich entscheiden, welche Sessions ich wiederherstelle und welche ich verwerfe.
- Als Nutzer möchte ich, dass eine wiederhergestellte Session den verdichteten Handover als Kontext-Seed mitbekommt.

## Acceptance Criteria
- [ ] Beim Start erkennt Jupiter aus dem Vault **wiederherstellbare Stränge** (letzter Handover je Session/Projekt).
- [ ] Es gibt eine **Recovery-Ansicht**: Liste der Kandidaten mit Projekt, letzter Phase, Zeitpunkt des letzten Handovers.
- [ ] Pro Kandidat ein **„Hier ging's weiter"-Vorschlag** (Zusammenfassung offener Punkte aus dem Handover).
- [ ] **Wiederherstellen** startet eine neue Session mit dem Handover als System-Kontext (Seed), verknüpft als Nachfolger (`parent_session_id`, analog PROJ-5).
- [ ] **Verwerfen** entfernt den Kandidaten aus der Ansicht, ohne den Vault-Eintrag zu löschen (Audit bleibt).
- [ ] Recovery funktioniert auch, wenn der In-Memory-Zustand vollständig weg ist (reiner Vault-Wiederaufbau).
- [ ] Bereits laufende/erfolgreich re-attachte Sessions (PROJ-14) erscheinen **nicht** doppelt als Recovery-Kandidat.
- [ ] Alle Texte deutsch; Lade-/Fehler-/Leer-Zustände explizit.

## Edge Cases
- **Kein Handover vorhanden** (Session ohne sauberen Übergabepunkt) → letzter roher Stand als schwächerer Vorschlag, klar als „unvollständig" markiert.
- **Beschädigter/halber Handover** → robust parsen, fehlende Felder tolerieren, Warnung anzeigen.
- **Mehrere Handovers je Strang** → den jüngsten als Anknüpfpunkt wählen.
- **Projektpfad existiert nicht mehr** → Kandidat anzeigen, aber Wiederherstellen blockieren mit Hinweis.
- **Doppelte Wiederherstellung** desselben Strangs → idempotent, nur eine Nachfolge-Session pro Strang (1 Strang = 1 Nachfolger, wie PROJ-5).

## Technical Requirements (optional)
- Liest die Vault-Handover-Artefakte (PROJ-5/#8) und die Schicht-Struktur (PROJ-15).
- Wiederherstellung nutzt denselben Reset-Kind-Mechanismus wie PROJ-5 (Seed + Staffelstab-Verknüpfung).
- Setzt den Persistenz-Seam aus PROJ-14 voraus, um Doppelungen mit re-attachten Sessions zu vermeiden.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
