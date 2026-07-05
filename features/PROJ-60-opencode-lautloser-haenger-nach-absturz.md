# PROJ-60: Bugfix: OpenCode-Session hängt lautlos in „Arbeitet", wenn der Prozess nach einem Tool-Zwischenschritt abbricht

## Status: In Review
**Created:** 2026-07-05
**Last Updated:** 2026-07-05

## Problem / Motivation
Nutzer meldete: eine OpenCode-Session (`openrouter/z-ai/glm-5.2`) zeigte 2 Minuten lang nur „Arbeitet" ohne jeglichen sichtbaren Output — Kosten liefen weiter hoch ($0.0692, 1 Turn), aber weder Tool-Aktivität noch Text erschienen. Unklar, ob die Session hängt oder nur langsam ist.

**Root Cause (durch Code-Analyse + Repro-Skript verifiziert):**

`GenericCliDriver._read_stdout` (`backend/app/engine/generic_cli_driver.py`) unterdrückt das terminale `closed`-Event am Prozessende, sobald irgendein `result`-Event im Turn vorkam (`self._saw_result`, jetzt `self._saw_final_result`). OpenCodes Adapter liefert aber für **jeden** Tool-Zwischenschritt ein `result`-Event mit `final: False` (PROJ-58) — nicht nur beim echten Turn-Ende. Bricht der Prozess NACH einem solchen Zwischenschritt ab (z. B. Provider-Timeout/Fehler bei GLM-5.2 über OpenRouter, Exit-Code 0, aber ohne den finalen `step_finish{reason:"stop"}`), wertete der Treiber das fälschlich als „Turn normal beendet, Session wartet auf die nächste Eingabe" — kein `closed`-Event, kein Fehler, die Session bleibt für immer im letzten Status hängen (typischerweise `running`/„Arbeitet"), obwohl der Prozess längst tot ist.

Verifiziert mit einem Fake-CLI, das genau dieses Verhalten nachstellt: Tool-Zwischenschritt → Absturz (kein finaler `step_finish`) → **vor dem Fix**: kein `closed`-Event, Session bleibt hängen; **nach dem Fix**: `closed` wird emittiert, Session terminiert sichtbar.

## Dependencies
- Requires: PROJ-57 (OpenCode-Harness), PROJ-58 (führte das `final`-Flag ein, das dieser Fix konsumiert), PROJ-48 (Codex — teilt sich denselben Treiber, aber liefert je Turn nur EIN result-Event → nicht betroffen).

## Scope-Abgrenzung (bewusst)
- **In Scope:** `GenericCliDriver._read_stdout` — nur ein `result`-Event mit `raw["final"]` wahr markiert den Turn als „sauber beendet, self-resumable". Jeder andere Prozess-Exit emittiert `closed`.
- **NICHT in Scope:** die eigentliche Ursache des Provider-Abbruchs selbst (OpenRouter/GLM-Verhalten) — liegt außerhalb unserer Kontrolle. Ziel ist, dass die Session in diesem Fall sichtbar terminiert statt lautlos zu hängen, nicht den Abbruch zu verhindern.
- **Unberührt:** Claude-Treiber, Codex (liefert nur ein finales result je Turn — `final` fehlt im raw-Dict, Default `True` greift unverändert).

## User Stories
- Als Nutzer möchte ich, dass eine OpenCode-Session, die wegen eines Provider-Fehlers mitten im Turn abbricht, sichtbar terminiert (Fehler oder zumindest „fertig"), statt für immer bei „Arbeitet" hängen zu bleiben, damit ich nicht rätseln muss, ob ich nur ungeduldig bin.

## Acceptance Criteria
- [x] `GenericCliDriver` trackt, ob der zuletzt gesehene `result` ein ECHTES Turn-Ende war (`raw.get("final", True)`), nicht nur „irgendein result kam vor".
- [x] Bricht der Prozess NACH einem Tool-Zwischenschritt ab (kein finales result), emittiert `stop()`/`_read_stdout` ein `closed`-Event → die Session terminiert (Manager setzt `DONE`, sofern nicht bereits `ERROR`).
- [x] Ein echtes, sauberes Turn-Ende (`reason=="stop"`) bleibt weiterhin ohne `closed` — Session bleibt self-resumable (PROJ-56/58 unverändert).
- [x] Codex/Claude unverändert (eigene Regressionssuiten grün).
- [x] Neue Regressionstests für beide Fälle (Absturz nach Zwischenschritt → `closed`; sauberes Ende → kein `closed`).
- [x] Volle Backend-Suite grün bis auf den vorbestehenden, unabhängigen Codex-Skill-Drift-Test.

## Edge Cases
- Der Prozess crasht bereits VOR jedem `result`-Event (z. B. sofortiger Absturz): unverändert abgedeckt — `_saw_final_result` bleibt `False`, `closed` wird emittiert (identisch zum Vorzustand für diesen Fall).
- Prozess beendet sich mit Exit-Code ≠ 0: unverändert — landet weiterhin im `error`-Zweig (Stderr-Text), unabhängig von diesem Fix.

## Technical Requirements
- `backend/app/engine/generic_cli_driver.py` — `_read_stdout()`, `stop()` (Umbenennung `_saw_result` → `_saw_final_result` + Bedingung erweitert um `raw.get("final", True)`).
- `backend/tests/test_proj60_opencode_silent_hang.py` — neue Regressionstests.

---
<!-- Sections below are added by subsequent skills -->

## Implementation Notes (Backend Developer, 2026-07-05)

### Geänderte Dateien
- `backend/app/engine/generic_cli_driver.py`:
  - `self._saw_result` → `self._saw_final_result`, zurückgesetzt in `_spawn()` (neuer Prozess = neuer Turn).
  - `_read_stdout()`: `if event.type == "result" and event.raw.get("final", True): self._saw_final_result = True` (vorher: jedes `result`-Event setzte das Flag).
  - Post-Loop-Entscheidung nutzt jetzt `self._saw_final_result` statt `self._saw_result` — nur ein ECHTES Turn-Ende unterdrückt `closed`.
- `backend/tests/test_proj60_opencode_silent_hang.py` — NEU (2 Tests): Absturz nach Tool-Zwischenschritt → `closed` wird emittiert; sauberes Turn-Ende (`reason=stop`) → weiterhin KEIN `closed` (Self-Resume-Pfad unverändert).

### Tests
- `test_proj60_opencode_silent_hang.py`: 2/2 grün.
- Regression: `test_proj58_opencode_stdin_race.py`, `test_proj57_opencode.py`, `test_proj48_codex.py`, `test_proj59_opencode_stop_hang.py`: 42/42 grün.
- Volle Suite: 1059 passed, 1 deselected (der vorbestehende, unabhängige Codex-Skill-Drift-Test wurde in dieser Zählung bewusst ausgeschlossen — separat per `git stash`-Vergleich als vorbestehend bestätigt).

### Offen für QA
- Live-Smoke wäre ideal (echten Provider-Timeout reproduzieren), ist aber nicht deterministisch erzwingbar — die Fake-CLI-Regressionstests decken den Mechanismus exakt ab.
- Regression Codex/Claude (automatisiert bereits grün).
