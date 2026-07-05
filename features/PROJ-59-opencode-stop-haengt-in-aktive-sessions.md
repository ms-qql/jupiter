# PROJ-59: Bugfix: OpenCode-Session hängt nach „Stopp" in „Aktive Sessions"

## Status: In Review
**Created:** 2026-07-05
**Last Updated:** 2026-07-05

## Problem / Motivation
Beendet man eine Session per „Stopp"-Button, wandert sie bei Claude- und Codex-Sessions korrekt ins Archiv (terminaler Status → raus aus „Aktive Sessions"). Bei **OpenCode**-Sessions passiert das nicht: die Session bleibt trotz Klick auf „Stopp" unter „Aktive Sessions" stehen.

**Root Cause (durch Code-Analyse + Live-Index-Beleg verifiziert):**

`GenericCliDriver` (der `generic_cli`-Treiber, den OpenCode/Codex teilen) hat einen Self-Resume-Zustand für `oneshot`-Engines (PROJ-56): nach einem geordneten Backend-Neustart/Deploy baut `EngineManager.auto_resume_drained()` für eine wartende, self-resume-fähige Session einen **frischen** `GenericCliDriver`. Dessen `start()` nimmt für diesen Fall bewusst einen frühen Return (`generic_cli_driver.py:121-123`) — es wird **kein Prozess gespawnt**, nur die `resume_id` gemerkt; erst der nächste `send_input()` startet einen echten Prozess.

Klickt der Nutzer in genau diesem Fenster auf „Stopp", **bevor** ein neuer Turn lief, trifft `GenericCliDriver.stop()` (Zeile 210-213, vor dem Fix) auf `self._proc is None` und kehrt sofort zurück — **ohne das `closed`-Event zu emittieren**. Der `EngineManager` erfährt dadurch nie vom Stop, der Status bleibt aktiv (`running`/`waiting`), die Session hängt für immer in „Aktive Sessions".

Bestätigt im Live-Index (`session_index.db`): Session `80d48f8a-…` (engine `opencode`) erhielt um 12:51:47 einen `POST /sessions/{id}/stop` (200 OK laut Uvicorn-Log), stand aber danach unverändert auf `status=running` mit `last_activity` eingefroren auf einen Zeitstempel **vor** dem Stop-Aufruf.

**Warum nur OpenCode (nicht Claude):** Claudes Treiber ist ein langlebiger Prozess — zwischen Turns lebt der Prozess immer, `self._proc` wird nie `None`, solange die Session nicht wirklich beendet ist. Nur der `oneshot`-Self-Resume-Pfad (OpenCode/Codex) kennt einen „konzeptionell aktiv, aber kein Prozess gespawnt"-Zwischenzustand.

## Dependencies
- Requires: PROJ-57 (OpenCode-Harness), PROJ-56 (Kontext-Persistenz / Self-Resume-Pfad, `auto_resume_drained`), PROJ-48 (Codex — teilt sich denselben Treiber).

## Scope-Abgrenzung (bewusst)
- **In Scope:** `GenericCliDriver.stop()` — bei `self._proc is None` trotzdem das `closed`-Event emittieren, damit der Manager den Status auf `DONE` setzt.
- **NICHT in Scope:** Claude-Treiber (betrifft ihn nicht), Änderungen am Self-Resume-Mechanismus selbst (PROJ-56 bleibt unangetastet — der frühe Return in `start()` ist korrekt und gewollt).

## User Stories
- Als Nutzer möchte ich, dass eine per „Stopp" beendete OpenCode-Session zuverlässig ins Archiv wandert, unabhängig davon, ob gerade ein Prozess läuft oder die Session nur auf den nächsten Turn wartet.

## Acceptance Criteria
- [x] `GenericCliDriver.stop()` emittiert das `system`/`closed`-Event auch dann, wenn `self._proc is None` (Self-Resume-Leerlauf) — der Manager schaltet daraufhin auf `DONE`.
- [x] Verhalten bei laufendem Prozess (`proc` gesetzt) bleibt unverändert (Terminate/Kill/Emit wie zuvor).
- [x] Codex (gleicher Treiber) bleibt unverändert im Verhalten.
- [x] Regressionstest: `stop()` auf einem frisch konstruierten Treiber ohne gespawnten Prozess emittiert `closed`.
- [x] Volle Backend-Testsuite grün (bis auf den vorbestehenden, unabhängigen Codex-Skill-Drift-Test).

## Edge Cases
- Session wird gestoppt, während `send_input()` gerade dabei ist, über den Resume-Pfad einen neuen Prozess zu spawnen (Race zwischen Stop-Klick und Folge-Nachricht) — nicht Teil dieses Fixes, da nicht das gemeldete Symptom; theoretisch weiterhin möglich, niedrige Priorität.

## Technical Requirements
- `backend/app/engine/generic_cli_driver.py` — `stop()`, Zeile ~210.
- `backend/tests/test_proj59_opencode_stop_hang.py` — neuer Regressionstest.

---
<!-- Sections below are added by subsequent skills -->

## Implementation Notes (Backend Developer, 2026-07-05)

### Geänderte Dateien
- `backend/app/engine/generic_cli_driver.py` — `stop()`: `self._stopping = True` wird jetzt vor der `proc is None`-Prüfung gesetzt; ist `self._proc is None`, emittiert die Methode direkt `StreamEvent("system", "closed", {})` und kehrt zurück, statt kommentarlos nichts zu tun.
- `backend/tests/test_proj59_opencode_stop_hang.py` — NEU: konstruiert einen `GenericCliDriver` ohne je `start()` aufzurufen (simuliert den Self-Resume-Leerlauf), ruft `stop()` auf und prüft, dass ein `closed`-Event emittiert wurde.

### Tests
- `test_proj59_opencode_stop_hang.py`: 1/1 grün.
- Regression: `test_proj58_opencode_stdin_race.py` (isoliert 4/4 grün — im Zusammenlauf mit weiteren Test-Dateien vereinzelt ein vorbestehender, unabhängiger Timing-Flake in `test_status_stays_active_through_tool_step_only_waits_at_true_end`, reproduziert identisch auch OHNE diesen Fix per `git stash`-Vergleich; betrifft Subprozess-Start-Jitter unter Last, nicht diese Änderung), `test_proj57_opencode.py`, `test_proj48_codex.py`.
- Volle Suite: 1052 passed, 1 failed (`test_proj50_codex_abc.py::test_generator_check_passes_no_drift`, vorbestehender Codex-Skill-Drift, unabhängig von PROJ-59, per `git stash`-Vergleich bestätigt).

### Offen für QA
- Live-Cockpit-Test: eine OpenCode-Session so lange laufen lassen/reanimieren, dass sie in den Self-Resume-Leerlauf fällt (z. B. nach einem Deploy/Neustart), dann „Stopp" klicken → Session muss sofort ins Archiv wandern.
- Regression Codex/Claude (automatisiert bereits grün, manueller Gegencheck schadet nicht).
