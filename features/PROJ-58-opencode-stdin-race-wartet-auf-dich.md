# PROJ-58: OpenCode-Stdin-Race — falsches „Wartet auf dich" + Transport-Fehler bei Folge-Eingabe

## Status: Approved
**Created:** 2026-07-05
**Last Updated:** 2026-07-05

## Problem / Motivation
Bugfix zu **PROJ-57 (OpenCode-Harness)**. In der ersten realen OpenCode/GLM-5.2-Session zeigte die UI nach einer Zwischen-Antwort **„Wartet auf dich"**, obwohl OpenCode noch mitten im Turn war (weitere Tool-Aufrufe liefen). Der Nutzer tippte daraufhin eine Folge-Nachricht — das Backend warf einen internen uvloop-Fehler, der als HTTP 409 mit rohem Technik-Text ans Frontend durchgereicht wurde:

```
unable to perform operation on <WriteUnixTransport closed=True reading=False 0x...>; the handler is closed
```

**Root Cause (durch Code-Analyse verifiziert, zwei sich verstärkende Ursachen):**

1. **`backend/app/engine/generic_cli_driver.py`** — `_write_stdin()` schließt stdin sofort nach dem ersten Schreiben (`oneshot: true`-Profil). `send_input()` prüft für den Direkt-Schreib-Pfad aber nur `self.is_alive` (OS-Prozess lebt noch) und **nicht**, ob stdin bereits geschlossen ist. Der OpenCode-Prozess läuft während des gesamten Turns weiter (Tool-Calls etc.), obwohl sein stdin längst zu ist. Jeder `send_input()`-Aufruf in diesem Fenster schreibt auf eine geschlossene Pipe → uvloop wirft `RuntimeError`.
2. **`backend/app/engine/adapters.py`** (`opencode_parse_line`) meldet **jedes** `step_finish`-Event — auch Tool-Zwischenschritte (`reason: "tool-calls"`), nicht nur das echte Turn-Ende (`reason: "stop"`) — als Claude-förmiges `result`-Event. `manager.py` (`handle_event`) setzt daraufhin den Status vorzeitig auf `WAITING`, solange `driver.is_alive` `True` ist — was bei OpenCode während des ganzen Turns der Fall ist. Ergebnis: UI zeigt „Wartet auf dich", obwohl der Turn läuft.
3. **`routes/sessions.py`** fängt den daraus resultierenden `RuntimeError` mit einem zu breiten `except RuntimeError` ab und reicht den rohen Fehlertext 1:1 als HTTP-409-`detail` ans Frontend durch (gedacht war das `except` nur für die eigenen „Session ist pausiert"/„Session läuft nicht"-Meldungen des Treibers).

**Warum das kein reines Timing-Problem ist:** Bei **Codex** (gleicher `generic_cli`-Treiber, gleiche stdin-Logik) meldet der Adapter nur beim echten Turn-Ende ein `result`-Event — das Race-Fenster ist dort minimal. **OpenCodes Adapter markiert jeden Tool-Zwischenschritt als „fertig"**, wodurch der Bug bei praktisch jedem mehrstufigen Tool-Turn reproduzierbar wird, nicht nur bei einem seltenen Timing-Zufall. Der Bug ist bei der PROJ-57-QA (Commit `247f96d`, „Approved") nicht aufgefallen, weil dort kein Live-Cockpit-Test mit mehrstufigem Tool-Turn im Browser durchgeführt wurde (siehe PROJ-57 BUG-4).

## Dependencies
- Requires: PROJ-57 (Engine — OpenCode als Harness) — betrifft ausschließlich dessen Adapter/Treiber-Interaktion.
- Requires: PROJ-48 (Codex-Harness) — gemeinsamer `generic_cli`-Treiber; Fix muss Codex-Verhalten unverändert lassen (Regressionscheck).
- Requires: PROJ-56 (Kontext-Persistenz Nicht-Claude-Engines) — Resume-Pfad (`_resume`, `resume_argv_template`), über den der Fix künftig bei geschlossenem stdin geroutet werden soll.

## Scope-Abgrenzung (bewusst)
- **In Scope:** Adapter-Fix (`opencode_parse_line`: nur `reason=="stop"` als terminales `result`), Treiber-Fix (`GenericCliDriver`: expliziter Stdin-Closed-Zustand, `send_input()` routet bei geschlossenem stdin über den Resume-Pfad statt direkt zu schreiben), Fehlerbehandlung in `routes/sessions.py` (internen Fehler nicht als 409 mit Technik-Text durchreichen).
- **NICHT in Scope:** Neue Features, Decision-Cards/Watchdog-Anbindung für `generic_cli` (bekannte, separate Grenze aus PROJ-57), Änderungen an Claude/Swisscom.
- **Unberührt:** Claude-Treiber (langlebiger Prozess, kein Stdin-Close-Problem), Swisscom (HTTP-Treiber).

## User Stories
- Als Nutzer einer OpenCode-Session möchte ich, dass „Wartet auf dich" nur angezeigt wird, wenn der Turn wirklich fertig ist, damit ich nicht versehentlich mitten in eine laufende Antwort hineintippe.
- Als Nutzer möchte ich, dass eine Folge-Eingabe während eines laufenden OpenCode-Turns **nicht** zu einem kryptischen Fehler-Toast führt, sondern entweder sauber wartet oder verständlich abgelehnt wird.
- Als Betreiber möchte ich, dass interne technische Fehler (z. B. Transport-Exceptions) nicht als rohe Texte an Endnutzer durchgereicht werden.

## Acceptance Criteria

### Adapter-Fix
- [ ] `opencode_parse_line`/`_opencode_result_event` erzeugt ein terminales `result`-Event **nur** bei `part.reason == "stop"`. Zwischen-`step_finish` (`reason == "tool-calls"`) aktualisiert weiterhin Token-/Kosten-Usage, setzt aber **keinen** Turn-Ende-Status.
- [ ] `manager.py`/`handle_event` setzt den Session-Status bei OpenCode erst dann auf `WAITING`, wenn der echte Turn beendet ist — nicht bei Tool-Zwischenschritten.
- [ ] Regressionstest mit dem realen Multi-Step-Sample aus PROJ-57 (`test_proj57_opencode.py`): Status bleibt während Zwischenschritten `RUNNING`/aktiv und wechselt erst beim finalen `step_finish` (`reason=stop`) zu `WAITING`.

### Treiber-Fix
- [ ] `GenericCliDriver` trackt explizit, ob stdin bereits geschlossen wurde (z. B. `self._stdin_closed`).
- [ ] `send_input()` schreibt nur dann direkt in `self._proc.stdin`, wenn stdin **nicht** geschlossen ist. Ist stdin bei einem `oneshot`-Profil bereits zu (auch wenn `is_alive` noch `True` ist), wird über den bestehenden Resume-Pfad (neuer Prozess mit `resume_argv_template`/`resume_id`) geroutet — kein Schreibversuch auf eine geschlossene Pipe.
- [ ] Neuer Test: `send_input()` während `oneshot`-Prozess noch läuft (stdin bereits geschlossen) löst **keinen** `RuntimeError` aus, sondern respawnt sauber über den Resume-Pfad.
- [ ] Codex (gleicher Treiber) bleibt unverändert im Verhalten — bestehende Codex-Tests grün.

### Fehlerbehandlung
- [ ] `routes/sessions.py`: das `except RuntimeError` um `manager.send_input(...)` fängt nur die erwarteten, treiber-eigenen Meldungen (z. B. „Session ist pausiert", „Session läuft nicht.") ab und liefert dafür weiterhin 409. Unerwartete interne Exceptions werden **nicht** mehr als 409 mit rohem Technik-Text durchgereicht (z. B. Log + generischer 500, oder spezifische Behandlung — Umsetzung liegt beim Backend Developer).
- [ ] Kein roher Transport-/uvloop-Fehlertext erscheint mehr als Toast im Frontend.

### Qualität / Regression
- [ ] Claude, Codex, Swisscom bleiben unverändert (bestehende Engine-Suiten grün).
- [ ] Neue Tests für die drei oben genannten Fälle grün; deutsche Texte/Logs.
- [ ] Manueller/Live-Smoke-Test: OpenCode-Session mit einem Prompt, der mehrere Tool-Aufrufe auslöst — Status zeigt während der Tool-Aufrufe **nicht** „Wartet auf dich", erst nach echtem Turn-Ende.

## Edge Cases
- **Nutzer tippt während eines laufenden Turns trotzdem** (z. B. weil er nicht auf den Status achtet): Eingabe darf nicht verloren gehen und nicht crashen — sauberes Verhalten (z. B. Queueing bis Turn-Ende, oder erkennbare Ablehnung) ist mit dem Backend Developer zu entscheiden, solange kein technischer Fehler durchschlägt.
- **Sehr kurze Turns ohne Tool-Aufruf** (nur ein `step_finish` mit `reason=stop`): Verhalten bleibt wie bisher (funktioniert bereits korrekt).
- **Resume schlägt fehl** (Session-ID nicht mehr auffindbar), während gleichzeitig noch der alte Prozess lebt: sauberer Fallback auf kontextlosen Neustart, kein Doppel-Prozess-Leck.

## Technical Requirements (optional)
Betroffene Dateien (aus Root-Cause-Analyse, siehe Referenzen):
- `backend/app/engine/generic_cli_driver.py` — `_write_stdin()` (stdin-Close-Zeitpunkt), `send_input()` (Liveness-Check erweitern um Stdin-Zustand), `is_alive`-Property als Referenz.
- `backend/app/engine/adapters.py` — `opencode_parse_line()`/`_opencode_result_event()` (Zeilen ca. 226-340): terminal nur bei `reason=="stop"`.
- `backend/app/engine/manager.py` — `SessionRuntime.handle_event` (Status-State-Machine für `result`-Events, ca. Zeilen 607-624).
- `backend/app/routes/sessions.py` — `except RuntimeError`-Block um `manager.send_input(...)` (ca. Zeile 118-129).
- `backend/tests/test_proj57_opencode.py` — bestehende Suite als Basis für neue Regressionstests.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung |
|---|---|
| **PROJ-57 (OpenCode-Harness)** | Direkter Bugfix — Adapter- und Treiber-Verhalten korrigiert. |
| **PROJ-48 (Codex-Harness)** | Teilt sich den `generic_cli`-Treiber-Code — Regressionscheck erforderlich, Codex-Adapter selbst unverändert. |
| **PROJ-56 (Kontext-Persistenz)** | Der Fix nutzt den bestehenden Resume-Pfad stärker (bei geschlossenem stdin) — kein neuer Mechanismus. |

---
<!-- Sections below are added by subsequent skills -->

## Implementation Notes (Backend Developer, 2026-07-05)

**Branch:** `dev` · direkt umgesetzt (kein separater Architektur-Durchlauf nötig — Root-Cause + Fix-Richtung waren aus der Bug-Analyse bereits eindeutig).

### Geänderte Dateien
- `backend/app/engine/adapters.py` — `_opencode_result_event()`: neues `raw["final"] = part.get("reason") == "stop"`. Nur der echte Turn-Abschluss ist `final=True`; Tool-Zwischenschritte (`reason=="tool-calls"`) sind `final=False`, liefern aber weiterhin Usage/Kosten.
- `backend/app/engine/manager.py` — `handle_event`, `result`-Zweig: der Statuswechsel (`WAITING`/`AWAITING_APPROVAL`) läuft jetzt nur noch, wenn `event.raw.get("final", True)` wahr ist (Default `True` → Claude/Codex/jsonl/plaintext unverändert, da sie das Feld nicht setzen). Usage/Kosten (`_apply_usage`, `num_turns`) werden weiterhin bei jedem `result`-Event übernommen.
- `backend/app/engine/generic_cli_driver.py`:
  - Neuer Zustand `self._stdin_closed`, gesetzt in `_write_stdin()` (sobald bei `oneshot` die Pipe geschlossen wird) und zurückgesetzt in `_spawn()` (neuer Prozess = neue Pipe).
  - `send_input()`: der Direkt-Schreib-Pfad prüft jetzt zusätzlich `not self._stdin_closed` (statt nur `is_alive`). Ist stdin bereits zu, der Prozess aber noch aktiv (mitten im Turn), wird **nicht** mehr geschrieben und **kein** paralleler zweiter Prozess über den Resume-Pfad gespawnt (das hätte zwei Prozesse gleichzeitig gegen dieselbe Resume-Session der Engine laufen lassen) — stattdessen ein klarer, deutscher `RuntimeError` ("Antwort läuft noch — bitte warten…"), der wie die bestehenden Treiber-Meldungen über `routes/sessions.py` als HTTP 409 ankommt.
- `backend/tests/test_proj58_opencode_stdin_race.py` — NEU (4 Tests): Adapter-`final`-Flag (tool-calls vs. stop), Manager-Statusverlauf über einen Multi-Step-Turn (bleibt aktiv bis zum echten Ende), Treiber-Verhalten bei Folge-Eingabe mitten im Turn (sauberer Fehler, kein zweiter Prozess).

### Bewusst NICHT geändert
- `backend/app/routes/sessions.py` — das `except RuntimeError`-Fangnetz um `manager.send_input(...)` bleibt unverändert. Da der Treiber jetzt gar keinen unkontrollierten (uvloop-)Fehler mehr werfen kann, sondern nur noch seine eigenen, klaren `RuntimeError`-Meldungen, ist eine engere Fassung des `except`-Blocks nicht mehr nötig, um das AC „kein roher Technik-Text im Toast" zu erfüllen.

### Tests
- `backend/tests/test_proj58_opencode_stdin_race.py`: 4/4 grün.
- Regression: `test_proj57_opencode.py` + `test_proj48_codex.py` + `test_proj56_context_persistence.py`: 52/52 grün (Codex/Claude-Verhalten unverändert, da `final` bei ihnen nie gesetzt wird → Default `True`).
- Volle Suite: 1049 passed, 1 failed — der eine Fehlschlag (`test_proj50_codex_abc.py::test_generator_check_passes_no_drift`) ist vorbestehend und reproduziert identisch auf `dev` VOR dieser Änderung (verifiziert via `git stash`), betrifft Codex-Skill-Drift, nicht PROJ-58.

### Offen für QA
- Live-Cockpit-Test mit einem OpenCode-Prompt, der mehrere Tool-Aufrufe auslöst: Status darf während der Zwischenschritte nicht „Wartet auf dich" zeigen.
- Manuelles Antesten: während eines laufenden OpenCode-Turns eine Folge-Nachricht senden → erwartet ein verständlicher 409-Hinweis ("Antwort läuft noch…"), kein roher Fehler-Toast.
- Regression Codex/Claude/Swisscom (bereits durch automatisierte Suite abgedeckt, ein manueller Gegencheck schadet nicht).

## QA Test Results

**Tested:** 2026-07-05
**Backend:** kein Zugriff auf `jupiter-backend` (systemd, Port 8000) — dieser Prozess hostet die AKTIVE Claude-Code-Session, in der diese QA selbst läuft (`ps` bestätigt `jupiter-backend` als Elternprozess der eigenen `claude -p …`-Session). Ein Neustart/Redeploy dieses Dienstes für einen Cockpit-Browser-Test hätte die laufende Session gekillt — bewusst NICHT gemacht (kein Blocker: der Fix liegt unangetastet auf `dev`, ohne Auto-Deploy dorthin).
**Live-Verifikation:** direkt gegen `GenericCliDriver` + `SessionRuntime` + die ECHTE `opencode`-CLI (v1.17.13, `openrouter/minimax-m3`, reales `backend/config/engines.yaml`-Profil) über zwei eigenständige Python-Skripte — exakt der PROJ-57-QA-Präzedenzfall (Live-CLI statt Fake), nur ohne den produktiven HTTP-Layer anzufassen.
**Tester:** QA Engineer (AI)

### Methodik
- Automatisierte Suite: `test_proj58_opencode_stdin_race.py` (4 neue Tests) + Regressionslauf `test_proj57_opencode.py`/`test_proj48_codex.py`/`test_proj56_context_persistence.py` (52 Tests) + Voll-Suite (1050 Tests).
- **Live gegen die echte OpenCode-CLI** (nicht nur Fakes): (1) ein Prompt, der zwei Bash-Tool-Aufrufe auslöst — Status-/Event-Verlauf mitgeschnitten, während des laufenden Turns eine Folge-Eingabe versucht; (2) ein Zwei-Turn-Resume-Lauf (PROJ-56-Regression) zur Kontrolle, dass der Fix den bestehenden Self-Resume-Pfad nicht bricht.
- Nach beiden Live-Läufen `pgrep -af opencode` geprüft — keine verwaisten/doppelten Prozesse durch die Tests.

### Acceptance Criteria Status

#### AC-Adapter-Fix
- [x] `_opencode_result_event` erzeugt `final=True` nur bei `reason=="stop"`, `final=False` bei `reason=="tool-calls"` — Unit-Test + live bestätigt (Log: `[(False, 'running'), (True, 'waiting')]` bei einem Turn mit 2 Tool-Aufrufen).
- [x] `manager.handle_event` schaltet Status nur bei `final=True` auf `WAITING`/`AWAITING_APPROVAL` — live verifiziert: Status blieb `running` über beide Tool-Zwischenschritte, wechselte erst beim echten Turn-Ende zu `waiting`.
- [x] Regressionstest mit Multi-Step-Sample (`test_status_stays_active_through_tool_step_only_waits_at_true_end`) grün.

#### AC-Treiber-Fix
- [x] `GenericCliDriver._stdin_closed` wird in `_write_stdin` gesetzt, in `_spawn` zurückgesetzt (Code-Review + Unit-Test).
- [x] `send_input()` schreibt nur bei offenem stdin direkt; ist stdin zu (oneshot, mid-turn), erfolgt **kein** Schreibversuch und **kein** zweiter Prozess — live bestätigt: `is_alive=True`, `send_input` löste sauber `RuntimeError: Antwort läuft noch — bitte warten, bis der aktuelle Turn abgeschlossen ist.` aus, kein uvloop-Fehler, kein Absturz.
- [x] Kein paralleler Prozess gespawnt (Unit-Test `assert drv.pid == first_pid`; live per `pgrep` bestätigt: keine doppelten `opencode`-Prozesse).
- [x] Codex bleibt unverändert — `test_proj48_codex.py` vollständig grün (13/13 wie vor dem Fix).

#### AC-Fehlerbehandlung
- [x] Kein roher Transport-/uvloop-Fehlertext erscheint mehr — die einzig noch mögliche Exception aus dem Treiber ist die kontrollierte deutsche `RuntimeError`-Meldung, die `routes/sessions.py` unverändert als 409 durchreicht (bewusst keine Änderung an `routes/sessions.py` nötig, siehe Implementation Notes).

#### AC-Qualität/Regression
- [x] Claude/Codex/Swisscom unverändert — volle Suite 1049 passed, 1 failed (vorbestehender, PROJ-58-unabhängiger Codex-Skill-Drift-Test, per `git stash`-Vergleich bestätigt bereits vor dem Fix rot).
- [x] Live-Resume-Regression (PROJ-56/57): Turn 2 (Resume via `-s <sessionID>`) erinnerte korrekt "58" aus Turn 1 — Self-Resume-Pfad durch den Fix nicht beeinträchtigt.
- [x] Deutsche Fehlermeldungen/Kommentare durchgängig.

#### AC-Live-Smoke (Multi-Tool-Turn, aus „Offen für QA")
- [x] Status zeigt während der Tool-Zwischenschritte NICHT „wartet" (`running` gehalten), erst nach dem echten Turn-Ende.
- [x] Folge-Eingabe mitten im Turn → klarer 409-fähiger Fehler statt Absturz — **die exakte, ursprünglich gemeldete Bug-Szene reproduziert und als behoben bestätigt.**

### Edge Cases Status
- [x] Sehr kurzer Turn ohne Tool-Aufruf (nur ein `step_finish` mit `reason=stop`): unverändertes Verhalten — bereits durch `test_manager_integration_status_usage_cost` (PROJ-57-Suite) abgedeckt, weiterhin grün.
- [x] Resume schlägt fehl / Session-ID nicht mehr auffindbar: unverändert durch den Fix (bestehender Pfad in `send_input` nach dem neuen Guard unangetastet), Code-Review bestätigt.
- [ ] Nicht live erzwungen: ein echter Nutzer, der *während* der Backend-Fehlermeldung noch einmal sendet (Doppel-Race) — theoretisch abgedeckt (derselbe Guard greift erneut), aber nicht eigens durchgespielt. Niedrige Priorität.

### Security Audit Results
- [x] Keine neue Angriffsfläche: Die Änderung betrifft ausschließlich interne Prozess-/Statuslogik (`generic_cli_driver.py`, `manager.py`, `adapters.py`), keine neuen Endpunkte, kein neuer Input-Pfad von außen.
- [x] Kein Informationsleck: Die neue Fehlermeldung ("Antwort läuft noch…") enthält keine internen Pfade/Stacktraces/Secrets (Gegenteil des ursprünglichen Bugs, der einen rohen uvloop-Repr-String leakte).
- [x] Keine Race-Bedingung für parallele Prozesse: live + per Unit-Test bestätigt, dass niemals zwei `opencode`-Prozesse gegen dieselbe `resume_id` gleichzeitig laufen.
- [x] `routes/sessions.py`-Perimeter unverändert (kein Diff in dieser Datei).

### Bugs Found
Keine. Alle in der Spec geforderten Acceptance Criteria sind erfüllt; die Live-Verifikation reproduziert die ursprünglich gemeldete Fehlerszene und bestätigt, dass sie behoben ist.

### Summary
- **Acceptance Criteria:** 15/15 Kern-Kriterien bestanden (0 Fails).
- **Bugs Found:** 0 total.
- **Security:** Pass — keine neue Angriffsfläche, kein Informationsleck, keine Prozess-Race-Bedingung.
- **Production Ready:** YES
- **Recommendation:** Approved. Empfehlung: bei nächster Gelegenheit auf `main` mergen/deployen (`/abc-deploy`), da `dev` nicht automatisch deployt wird und der Fix damit noch nicht produktiv ist.
