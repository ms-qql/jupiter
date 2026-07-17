# PROJ-75: Bugfix-Verifikation: PROJ-72-Transkript-Replay nach wiederholtem Resume in Produktion nicht restlos ausgeschlossen

## Status: Planned
**Created:** 2026-07-17
**Last Updated:** 2026-07-17

## Problem / Motivation
Report `docs/reports/2026-07-17-session-management-vergleich.md` hat beim Vergleich mit Waylands DB-Replay-Fallback folgenden offenen Punkt aus PROJ-72 aufgegriffen:

PROJ-72 (Status: Deployed, Version 0.27.31) hat den Offset-0-Replay von `out.log` beim Claude-tmux-Resume eliminiert (`seek_to_end`, `transport.py`, `claude_driver.py`) und dokumentiert selbst im eigenen "Rest-Risiko"-Abschnitt: *"Produktiv-Smoke nach Deploy bleibt erforderlich, weil der ursprüngliche Gegenbeleg erst im Live-Resume-Betrieb sichtbar wurde."* Der erste Deploy-Versuch (0.27.30) hatte in Produktion tatsächlich einen Fall gezeigt, in dem trotz Fix weiterhin ein vollständiger Faktor-2-Replay nach einem Resume auftrat (Session `90a13f65`, 44 Dubletten; Session `d162bff5`, 202 Wiederholungen) — der Nachfolge-Deploy (0.27.31) hat die Ursache (Kopplung des Seeks an `spec.resume` statt an jeden tmux-Start) korrigiert, aber die Bestätigung im Live-Betrieb über **mehrere aufeinanderfolgende** reale Resumes (nicht nur die Test-Suite) steht laut eigenem Ticket noch aus.

Für Nutzer sind doppelte/vervielfachte Transkript-Einträge nicht von echtem Kontextverlust zu unterscheiden — beides sieht wie "Session bricht ab / muss neu geladen werden" aus. Bevor an Punkt 1 (PROJ-74) oder weiterer Session-Stabilität gearbeitet wird, muss geklärt sein, ob diese konkrete, bereits einmal in Produktion widerlegte Annahme jetzt wirklich hält.

## Dependencies
- Requires: PROJ-72 (der zu verifizierende Fix), PROJ-63 (Tmux-Transport), PROJ-66 (DB-Transkript-Persistenz), PROJ-70 (Fragekarten-Guard als zweite Verteidigungslinie)

## Scope-Abgrenzung (bewusst)
- **In Scope:** Gezielte Reproduktion/Verifikation an einer real laufenden Claude-tmux-Session über **mehrere** aufeinanderfolgende Resume-Auslöser (manuelle Reanimierung, Auto-Resume nach Liveness-Timeout, Backend-Neustart) — Prüfung, ob Transkript-Einträge sich vervielfachen. Fällt der Repro rot aus: Root-Cause-Fix am tatsächlich noch lückenhaften Pfad (kleinster korrekter Eingriff, gleiche Systematik wie der bereits erfolgte PROJ-72-Reopening-Fix).
- **Out of Scope:** Bereits vorhandene, historisch korrumpierte Transkript-Dubletten automatisiert bereinigen — laut PROJ-72 bewusst nicht Teil des Fixes (legitime Wiederholungen nicht sicher von Replay-Dubletten unterscheidbar); bleibt auch hier ausgeschlossen, außer der Nutzer entscheidet im Gespräch anders.
- **Out of Scope:** Der separat in PROJ-72 vermerkte Nebenbefund "kein atomarer Turn-/Resume-Lock pro Konversation bei `send_input`" — das ist laut PROJ-72 explizit ein eigenes Requirement, nicht Teil dieser Verifikation.

## User Stories
- Als Nutzer möchte ich, dass eine lange laufende Claude-Session auch nach mehreren Neustarts/Reanimierungen des Backends **kein** vervielfachtes Transkript zeigt — damit ich der Session-Historie vertrauen kann.
- Als Entwickler möchte ich einen belastbaren, wiederholbaren Produktions-nahen Nachweis (nicht nur Unit-Tests) haben, dass PROJ-72 unter realen, mehrfachen Resume-Zyklen hält — weil der erste Fix genau daran bereits einmal gescheitert ist.

## Acceptance Criteria
- [ ] Eine reale (oder Produktions-nah simulierte) Claude-tmux-Session durchläuft **mindestens drei** aufeinanderfolgende Resume-Zyklen (z. B. zwei manuelle Reanimierungen + ein Backend-Neustart) mit Turns dazwischen.
- [ ] Nach jedem Zyklus wird das persistierte Transkript (DB, `session_transcript`) auf Dubletten-Faktor geprüft — jeder Assistant-Eintrag darf nur genau 1× vorkommen, unabhängig von der Anzahl der Resumes.
- [ ] Fragekarten wiederholen sich nach keinem der Zyklen (PROJ-70-Guard bleibt wirksam über mehrere Zyklen hinweg, nicht nur nach einem einzigen Resume).
- [ ] Tritt dabei erneut eine Vervielfachung auf: Root-Cause im tatsächlich betroffenen Pfad wird benannt (Datei:Zeile), kleinster korrekter Fix umgesetzt, Reproduktion wird danach grün nachgewiesen.
- [ ] Ergebnis (hält der Fix / hielt er nicht und wurde nachgebessert) wird im PROJ-72-Spec unter Implementation Notes nachgetragen, nicht nur in diesem Ticket — damit die Deploy-Historie von PROJ-72 vollständig bleibt.
- [ ] Bestehende Resume-/Transport-/Persistenz-Testsuiten (proj27, proj63, proj64, proj66, proj70, proj72) bleiben grün.

## Edge Cases
- Resume-Zyklen in schneller Folge (kurz hintereinander, bevor der letzte Ausgabe-Rest persistiert wurde) — prüfen, ob das laut PROJ-72 "akzeptierte Rest-Risiko" (Datenverlust bei ungeordnetem Abbruch mitten im Turn, nicht Duplizierung) sauber von einer echten Regression zu unterscheiden ist.
- Zwei Browser-Clients verbunden während eines Resume-Zyklus — laut PROJ-72 darf ein read-only Client keine zusätzlichen Resumes/Transkript-Mutationen auslösen; das muss auch über mehrere Zyklen stabil bleiben.
- Resume nach einem Zyklus, in dem eine Fragekarte noch unbeantwortet war — prüfen, ob sie nach dem nächsten Zyklus weiterhin genau einmal (nicht erneut dupliziert) erscheint.

## Technical Requirements (optional)
- Betroffene Bereiche: `backend/app/engine/transport.py` (`seek_to_end`), `backend/app/engine/claude_driver.py` (`_spawn_tmux`), `backend/app/engine/manager.py` (`rehydrate()`, Resume-Pfade), Testdateien `test_proj63_claude_tmux.py`, `test_proj63_tmux_transport.py`, `test_proj66_transkript_persistenz_rehydrate.py`, `test_proj72_*` (falls vorhanden, sonst neu anzulegen für den Mehrfach-Resume-Fall).
- Verifikation nach `/abc-backoffice`-Kontrakt: Reproduktion-vor-Fix (mehrfacher Resume-Zyklus, nicht nur Einzel-Resume wie in den bestehenden PROJ-72-Tests) → falls rot: Fix → grün.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
