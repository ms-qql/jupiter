# PROJ-65: Bugfix: Frisch erstellte tmux-Session zeigt sofort „beendet" statt aktiv (Status-Race bei schnellen Oneshot-Turns)

## Status: Planned
**Created:** 2026-07-07
**Last Updated:** 2026-07-07

## Problem / Motivation
Live-Vorfall (2026-07-07, Nutzer-Report, nach PROJ-64-Deploy): Eine neu erstellte Codex-Session mit `transport=tmux` brauchte spürbar länger als sonst, bis sie erschien — dann aber bereits mit abgeschlossenem Turn (1 Turn, echter Assistant-Text, Header-Badge „Fertig"), gleichzeitig zeigte der Status-Banner „Session beendet/nicht steuerbar" und die Session fehlte komplett in „Aktive Sessions" in der Sidebar. Manuelles „Reaktivieren" stellte sie wieder her.

**Root Cause (durch Code-Analyse verifiziert, Explore-Agent-Untersuchung 2026-07-07):**
1. `manager.py::create()` setzt `state.status = RUNNING` **synchron, bevor** `spawn()` aufgerufen wird.
2. Der Reader-Task, der den Turn-Abschluss verarbeitet, wird in `generic_cli_driver.py::_spawn_tmux()` **erst nach** `TmuxTransport.spawn()` gestartet — und `spawn()` kann durch PROJ-64s neue Retry-/Existenz-Check-Schleife jetzt bis zu ~20-30s dauern.
3. Ein schneller Codex-Oneshot-Turn ist oft schon fertig (Pane-Prozess bereits beendet, `EXIT_MARKER:0` im `err.log`), **bevor** der Reader-Task je zu laufen beginnt.
4. Die erste Liveness-/Status-Berechnung für die `POST /sessions`-Antwort sieht: Prozess tot, Reader hat noch nichts verarbeitet → `derive_liveness()` liefert **DEAD** (`manager.py:463-464`).
5. Verarbeitet der Reader später das gepufferte `result`-Event, prüft `manager.py:652` erneut `driver.is_alive` — der Prozess ist weiterhin tot → Status wird **DONE** (Endzustand) statt **WAITING** (resumable), obwohl der Turn sauber durchlief.

Dies ist **kein neuer Bug**, sondern eine in `features/PROJ-63-tmux-session-transport.md` (Zeile 476) bereits als Restrisiko dokumentierte, bewusst zurückgestellte Race ("Race in `manager.py:652` ... sollte als eigener Punkt nachverfolgt werden"). PROJ-64s zusätzliche `spawn()`-Latenz macht sie jetzt deutlich wahrscheinlicher, statt eines seltenen Randfalls.

**Ziel dieses Tickets:** eine neu erstellte Session, deren zugrunde liegender Turn bereits sauber abgeschlossen hat, landet direkt im korrekten, resumable Zustand — unabhängig davon, wie lange `spawn()` gebraucht hat.

## Dependencies
- Requires: PROJ-63 (führte `TmuxTransport`, `derive_liveness()`-tmux-Bewusstsein und die hier behobene Restrisiko-Race in `manager.py:652` ein).
- Requires: PROJ-64 (die dort eingeführte Retry-/Attach-Latenz in `spawn()` macht diese Race erst praktisch relevant).
- Requires: PROJ-56, PROJ-58, PROJ-60 (Kontext-Persistenz/Resumability-Modell für Oneshot-Engines — WAITING-vs-DONE-Semantik, die hier korrigiert wird).

## Scope-Abgrenzung (bewusst)
- **In Scope:**
  1. Die Status-Entscheidung in `manager.py:652` (`WAITING if self.driver.is_alive else DONE`) nicht mehr blind an `driver.is_alive` binden, sondern daran, ob ein **sauberes finales Result-Event** vorliegt (das an dieser Stelle im Code ja bereits verarbeitet wurde) — ein bereits beendeter Prozess nach einem sauberen Turn-Abschluss ist der ERWARTETE Normalfall bei Oneshot-Engines (Codex/OpenCode), kein Fehler.
  2. Die initiale Liveness-/Status-Berechnung für die `POST /sessions`-Direktantwort (bzw. den ersten Sidebar-Render danach) so absichern, dass sie nicht fälschlich DEAD meldet, nur weil der Reader-Task noch nicht gelaufen ist.
- **NICHT in Scope:** weitere Reduktion der PROJ-64-`spawn()`-Latenz selbst (das ist eine separate, dort bereits behandelte Fragestellung); Claude/long-lived-Treiber (dort läuft der Prozess i. d. R. noch, wenn der Reader startet — nicht betroffen); `DirectTransport`.
- **Bewusst erhalten:** echte Abstürze (Exit-Code ≠ 0, PROJ-60-Fallback ohne finalen Result) bleiben unverändert korrekt als DEAD/DONE mit Fehlermeldung erkennbar.

## User Stories
- Als Nutzer möchte ich, dass eine neu erstellte Session sofort korrekt als aktiv/wartend angezeigt wird, wenn der zugrunde liegende Turn sauber abgeschlossen hat — unabhängig davon, wie lange die Session-Erstellung selbst gedauert hat, damit ich nicht bei jeder schnell abgeschlossenen Codex-Session manuell reaktivieren muss.

## Acceptance Criteria
- [ ] Eine neu erstellte tmux-Session, deren Oneshot-Turn bereits vor dem Start des Reader-Tasks sauber beendet ist (Prozess bereits tot, `EXIT_MARKER:0` im `err.log`), landet nach Verarbeitung des gepufferten Outputs korrekt im Status **WAITING** (resumable), nicht DONE.
- [ ] `POST /sessions` bzw. der unmittelbar folgende Sidebar-Zustand meldet für eine solche Session **keine** fälschliche DEAD-Liveness.
- [ ] Die Session erscheint direkt nach dem Erstellen in „Aktive Sessions" in der Sidebar, ohne dass manuelles „Reaktivieren" nötig ist.
- [ ] Ein Turn, der tatsächlich abstürzt (Exit-Code ≠ 0 oder PROJ-60-Fallback ohne finalen Result), bleibt unverändert korrekt als DEAD/DONE mit Fehlermeldung erkennbar — kein Rückschritt bei echten Fehlern.
- [ ] Long-lived Treiber (Claude, PROJ-1) bleiben unverändert (Regressionstest gegen PROJ-27/33/56).
- [ ] Neue Regressionstests: (1) schneller Oneshot-Turn, bereits beendet vor Reader-Start → landet auf WAITING; (2) echter Absturz bleibt DEAD/DONE mit Fehlermeldung; (3) Direktantwort/erster Zustand nach Erstellung zeigt für Fall (1) keine DEAD-Liveness.
- [ ] Volle Backend-Suite grün (inkl. `test_proj63_*`, `test_proj64_*`, `test_proj60_opencode_silent_hang.py`).

## Edge Cases
- Prozess stirbt, während der Reader gerade das `result`-Event verarbeitet (Race innerhalb des Racefensters) — muss weiterhin korrekt WAITING liefern, wenn ein sauberer finaler Result vorliegt.
- Prozess stirbt VOR jedem Event (sofortiger Absturz, kein Result) — bleibt korrekt DEAD/DONE mit Fehlerhinweis (PROJ-62-Verhalten unverändert, kein Rückschritt).
- Long-lived-Session (Claude): Prozess läuft zum Zeitpunkt des ersten Liveness-Checks normalerweise noch — unverändertes Verhalten sicherstellen.
- Sehr langsamer Oneshot-Turn (Prozess läuft beim ersten Check noch) — unverändert weiterhin `RUNNING`/normaler Verlauf.

## Technical Requirements
- `backend/app/engine/manager.py`: Zeile ~652 (`status = WAITING if self.driver.is_alive else DONE`) — Entscheidung an das Vorliegen eines sauberen finalen Result-Events statt (nur) an `driver.is_alive` koppeln.
- `backend/app/engine/manager.py::create()` / `backend/app/routes/sessions.py`: initiale Liveness-/Status-Berechnung für die Erstellungs-Antwort auf Race-Sicherheit gegenüber dem noch nicht gelaufenen Reader-Task prüfen.
- Neue Tests in `backend/tests/test_proj65_tmux_oneshot_status_race.py` oder Erweiterung von `backend/tests/test_proj63_manager_transport.py` / `test_proj60_opencode_silent_hang.py`.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## Implementation Notes
_To be added by /abc-backend_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
