# PROJ-14: PROJ-1-Härtung — Limit paralleler Sessions + Persistenz

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** — (Härtung aus QA-3 von PROJ-1)

## Dependencies
- Requires: PROJ-1 (Engine-Treiber / In-Memory-Registry) — härtet dessen offene Punkte (Session-Limit + Persistenz).
- Verwandt: PROJ-17 (Recovery) — Persistenz ist die Voraussetzung für Wiederherstellung; PROJ-3 (Cockpit) zeigt Limit-Status.

## Beschreibung
PROJ-1 hält den Session-Zustand heute rein **in-memory** und kennt **kein Limit** paralleler Sessions. Dieses Feature schließt beide Lücken aus dem QA-Befund: ein konfigurierbares **Limit gleichzeitiger Sessions** (Schutz vor Ressourcen-Überlast) und ein **Persistenz-Seam** (Postgres-Live-Index), damit der Live-Zustand einen Backend-Neustart übersteht.

## User Stories
- Als Nutzer möchte ich ein konfigurierbares Maximum gleichzeitiger aktiver Sessions, damit der VPS nicht überlastet.
- Als Nutzer möchte ich beim Erreichen des Limits eine klare Rückmeldung statt eines stillen Fehlers.
- Als Nutzer möchte ich, dass der Live-Index der Sessions einen Backend-Restart übersteht (kein Totalverlust der Übersicht).
- Als Nutzer möchte ich, dass beendete/fehlerhafte Sessions die Limit-Zählung nicht dauerhaft blockieren.

## Acceptance Criteria
- [ ] Ein konfigurierbares **`max_parallel_sessions`** (Default sinnvoll, z. B. anhand CPU); Quelle: zentrale Settings.
- [ ] Beim Überschreiten wird die Erstellung **abgelehnt** mit klarer deutscher Meldung (HTTP 429/409) — kein Crash, kein stiller Abbruch.
- [ ] Nur **aktive** Zustände (starting/running/waiting/awaiting_approval) zählen gegen das Limit; done/error nicht.
- [ ] **Persistenz-Seam**: der Session-Live-Index wird in Postgres gespiegelt (anlegen/Status-Update/beenden), ohne den In-Memory-Pfad zu verlangsamen.
- [ ] Nach **Backend-Neustart** ist die Session-Liste (Metadaten/letzter Status) wieder sichtbar; laufende Claude-Prozesse, die den Restart überlebt haben, werden — soweit möglich — re-attacht oder als „verwaist" markiert.
- [ ] Das Repository-Seam ist so geschnitten, dass PROJ-17 (Recovery über Vault) darauf aufsetzen kann.
- [ ] Bestehende PROJ-1-Tests bleiben grün (verhaltenswahrend für den Normalfall).

## Edge Cases
- **Limit-Race** (zwei gleichzeitige Creates am Limit) → atomare Prüfung, höchstens das Limit wird zugelassen.
- **Prozess überlebt Restart nicht** → Session als „verwaist/beendet" markieren, sauber aus der Zählung nehmen.
- **DB nicht erreichbar** → In-Memory bleibt führend (MVP-Prinzip), Persistenz best-effort, sichtbare Warnung statt Hard-Fail.
- **Inkonsistenz Speicher↔DB nach Crash** → beim Start abgleichen; In-Memory/Prozess-Realität gewinnt.
- **Limit = 0 / Fehlkonfiguration** → auf sinnvolles Minimum klemmen.

## Technical Requirements (optional)
- Persistenz als **Live-Index** (schneller Spiegel), nicht als Wahrheit — Wahrheit bleibt Vault (PRD-Constraint).
- Limit-Prüfung atomar im SessionManager; Konfiguration via `pydantic-settings`.
- Kein Performance-Regress im Hot-Path der Event-Verarbeitung.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
