# PROJ-60: Bugfix: OpenCode-Session hängt lautlos in „Arbeitet", wenn der Prozess nach einem Tool-Zwischenschritt abbricht

## Status: Deployed
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

## QA Test Results

**Tested:** 2026-07-05
**Backend:** kein Zugriff auf den produktiven `jupiter-backend`-Dienst (hostet die aktive Session, in der diese QA läuft — siehe PROJ-58/59-Präzedenzfall). Live-Verifikation direkt gegen `GenericCliDriver` + `SessionRuntime` + `SessionManager`-Konstanten (reale Klassen, End-to-End über den echten Event-Pfad).
**Tester:** QA Engineer (AI)

### Methodik
- Automatisierte Suite: `test_proj60_opencode_silent_hang.py` (2 Tests) + volle Backend-Suite (1060 Tests).
- **Unabhängige Live-Reproduktion** (nicht nur der Implementierungs-Test): ein Fake-CLI, das einen Tool-Zwischenschritt liefert und danach ohne finalen `step_finish` abbricht, an eine ECHTE `SessionRuntime` gehängt (nicht nur den nackten Treiber) — Ende-zu-Ende über `driver.start()` → `_read_stdout` → `handle_event`. Geprüft: `state.status` verlässt `ACTIVE_STATES` (statt für immer `running` zu bleiben).

### Acceptance Criteria Status
- [x] `_saw_final_result` statt `_saw_result` — Code-Review + Test bestätigt.
- [x] Absturz nach Tool-Zwischenschritt → `closed`-Event → Session terminiert — Live-Reproduktion: `state.status` == `done`, nicht mehr in `ACTIVE_STATES`.
- [x] Sauberes Turn-Ende (`reason=stop`) bleibt ohne `closed`, Session self-resumable — Regressionstest `test_clean_turn_end_still_suppresses_closed_for_self_resume` grün.
- [x] Codex/Claude unverändert — eigene Suiten (`test_proj48_codex.py`, Claude-Treiber-Tests) unangetastet, volle Suite grün.
- [x] Neue Regressionstests für beide Fälle — 2/2 grün.
- [x] Volle Backend-Suite grün bis auf den vorbestehenden, unabhängigen Codex-Skill-Drift-Test (1059 passed, 1 deselected in der gezielten Zählung / 1060 passed, 1 failed in der vollen Zählung — identisch vor dieser Änderung reproduzierbar).

### Edge Cases Status
- [x] Absturz VOR jedem `result`-Event: unverändert abgedeckt (`_saw_final_result` bleibt `False` von Anfang an) — Code-Review bestätigt, kein neuer Test nötig (Verhalten identisch zum Vorzustand).
- [x] Exit-Code ≠ 0: unverändert, landet weiterhin im `error`-Zweig — Code-Review bestätigt (dieser Zweig wurde nicht verändert).

### Security Audit Results
- [x] Keine neue Angriffsfläche: reine interne Prozess-/Statuslogik, kein neuer Endpunkt, kein neuer Input-Pfad.
- [x] Kein Informationsleck: das `closed`-Event trägt kein Payload.

### Bugs Found
Keine. Die ursprünglich gemeldete Fehlerszene (Session hängt lautlos bei „Arbeitet") ist durch die Live-Reproduktion bestätigt behoben.

### Summary
- **Acceptance Criteria:** 6/6 bestanden (0 Fails).
- **Bugs Found:** 0 total.
- **Security:** Pass.
- **Production Ready:** YES
- **Empfehlung:** Approved. Bei nächster Gelegenheit deployen (`/abc-deploy`) — Auto-Deploy greift bei Jupiter nur bei Push nach `main` (bereits der aktuelle Branch).

## Deployment

**Production URL:** https://jupiter.auxevo.tech
**Deployed:** 2026-07-05 · **Version:** 0.27.9
**Host:** Dev-VPS (host-native, systemd `jupiter-backend`/`jupiter-frontend`), Auto-Deploy via GitHub-Webhook auf Push nach `main`
**Was ausgeliefert wurde:** `GenericCliDriver` unterdrückt das `closed`-Event nur noch bei einem ECHTEN Turn-Ende (`final=True`), nicht mehr bei irgendeinem Zwischenergebnis — ein Absturz nach einem Tool-Zwischenschritt lässt die Session jetzt sichtbar terminieren statt lautlos zu hängen. Gemeinsam mit PROJ-59 und PROJ-61 in einem Deploy ausgeliefert.
**Hinweis:** Deploy löst einen Neustart von `jupiter-backend` aus (beendet die aktuell aktive Claude-Code-Session, erwartet). Vor dem Push wurden uncommittete Änderungen einer parallel laufenden OpenCode-Session (`3a3111f2`, nicht Teil dieses Features) per Patch gesichert (`/home/dev/jupiter-deploy/backups/`), da derselbe Working Tree geteilt wird — Restrisiko für Schreibvorgänge nach dem Snapshot bewusst in Kauf genommen (User-Entscheidung).
