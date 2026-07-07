# PROJ-62: Bugfix: OpenCode-Session endet lautlos ohne Transkript und ohne Fehler, wenn der Turn nur aus Tool-Calls besteht

## Status: Deployed
**Created:** 2026-07-05
**Last Updated:** 2026-07-07

## Problem / Motivation
Nutzer meldete: eine OpenCode-Session (`openrouter/z-ai/glm-5.2`, Skill `/abc-qa`, Titel „UI 21 QA GLM") zeigte 1 Turn, $0.0332 Kosten und 15% Kontext-Füllstand, aber **kein einziger Transkript-Eintrag** war sichtbar — im Log war nur ein `bash`-Tool-Call (`git log --all --oneline | head -30`) erkennbar. Die Session endete danach als „Session beendet/nicht steuerbar" (Reaktivieren-Button), ohne dass ein Fehler angezeigt wurde.

**Root Cause (durch Code-Analyse verifiziert, Explore-Agent-Untersuchung 2026-07-05):**

1. `SessionManager.handle_event` (`backend/app/engine/manager.py:592-610`) verarbeitet `tool_use`-Events (z. B. `bash`) nur über `_emit_activity(...)` (Zeile 516-532) — das ist laut eigenem Docstring explizit NICHT für `self.transcript`/Vault/`_write_session_log` gedacht, sondern ein flüchtiger Activity-Ticker (PROJ-46/61). Nur `assistant`-Events (Zeile 563-580) hängen einen `TranscriptEntry` an. Besteht ein Turn ausschließlich aus Tool-Calls ohne begleitenden/folgenden Assistant-Text, bleibt `self.transcript` leer — und damit auch das, was der Nutzer im Cockpit als „Transkript-Historie" sieht.
2. `adapters.py:256-310` (`_opencode_result_event`) liefert für **jeden** `step_finish` — auch `reason=="tool-calls"`, nicht nur den echten Turn-Abschluss `reason=="stop"` — ein `result`-Event mit echtem `usage`/`total_cost_usd`. `manager.py:612-632` verbucht Turns/Kosten/Kontext aus jedem `result`-Event unabhängig von `final`. Dadurch zeigt die UI plausible Zahlen (1 Turn, $0.0332), obwohl der Turn nie einen sichtbaren Inhalt produziert hat.
3. Bricht der Prozess danach ab, ohne je einen finalen `step_finish{reason:"stop"}` gesehen zu haben, greift der PROJ-60-Fix in `generic_cli_driver.py:277-289`: Es wird korrekt ein `system/closed`-Event gefeuert (verhindert das lautlose Für-immer-Hängen aus PROJ-60) — aber **ohne jede Fehlermeldung**. `manager.py:558-560` setzt daraufhin nur `status = DONE`, `state.error` bleibt `None`.
4. `derive_liveness` (`manager.py:456`) mappt `DONE` + toter Prozess auf `LIVENESS_DEAD` → Cockpit zeigt „Session beendet/nicht steuerbar" mit „Reaktivieren".

Der exakte Ablauf (`step_start` → `tool_use` bash → `step_finish` `reason="tool-calls"` → Prozessende `rc=0`, kein finaler Step) ist bereits 1:1 in `backend/tests/test_proj60_opencode_silent_hang.py::FAKE_CRASH_MID_TURN` nachgebaut — der bestehende Test prüft dort aber nur „Session hängt nicht mehr ewig", nicht „Transkript ist leer" und nicht „Fehler wird sichtbar gemacht". PROJ-60 hat also „hängt für immer lautlos" korrekt durch „endet lautlos ohne Transkript/Fehler" ersetzt — das schließt die Lücke nicht vollständig.

## Dependencies
- Requires: PROJ-57 (OpenCode-Harness), PROJ-58 (führte das `final`-Flag ein), PROJ-60 (führte den `closed`-Fallback bei fehlendem finalen Result ein, den dieser Fix ergänzt), PROJ-46/PROJ-61 (Activity-Ticker, von dem sich der persistente Transkript-Pfad bewusst abgrenzt).

## Scope-Abgrenzung (bewusst)
- **In Scope:** (a) Tool-Only-Turns hinterlassen einen für den Nutzer sichtbaren Transkript-Eintrag (z. B. „Tool-Aufruf: bash — `git log …`" als eigener Eintragstyp, nicht nur den flüchtigen Activity-Ticker). (b) Der stille `system/closed`-Pfad in `generic_cli_driver.py` (PROJ-60-Fall: Prozessende ohne finalen `step_finish`) setzt einen diagnostischen Hinweis in `state.error` statt ihn leer zu lassen, damit „beendet/nicht steuerbar" nicht ohne jede Erklärung auftaucht.
- **NICHT in Scope:** die eigentliche Ursache, warum der OpenRouter/GLM-Prozess nach dem Tool-Call ohne finalen Step endet (Provider-/Netzwerkverhalten, außerhalb unserer Kontrolle — wie schon bei PROJ-60 abgegrenzt). Ziel ist Sichtbarkeit (Transkript + Fehlerursache), nicht die Verhinderung des Abbruchs selbst.
- **Unberührt:** Claude-Treiber, Codex (liefert je Turn nur ein finales `result` — nicht von diesem Tool-Only-Turn-Fall betroffen).

## User Stories
- Als Nutzer möchte ich, dass jeder Tool-Aufruf (z. B. `bash`) im Session-Transkript sichtbar bleibt, auch wenn danach kein Assistant-Text mehr folgt, damit ich nachvollziehen kann, was die Session getan hat, bevor sie endete.
- Als Nutzer möchte ich, wenn eine Session lautlos als „beendet/nicht steuerbar" terminiert, einen kurzen technischen Hinweis sehen (z. B. „Prozess endete ohne Abschluss-Signal"), statt vor einem leeren Transkript ohne jede Erklärung zu stehen.

## Acceptance Criteria
- [ ] `tool_use`-Events erzeugen zusätzlich zum bestehenden Activity-Ticker einen persistenten `TranscriptEntry` (in `self.transcript`, damit er in Vault/`_write_session_log` und der Cockpit-Transkript-Ansicht erscheint).
- [ ] Ein Turn, der ausschließlich aus Tool-Calls besteht (kein Assistant-Text), zeigt nach Sessionende mindestens einen Transkript-Eintrag — nicht „Noch keine Transkript-Historie".
- [ ] Der `system/closed`-Fallback-Pfad aus PROJ-60 (Prozessende ohne finalen `step_finish`) setzt `state.error` auf einen kurzen, für den Nutzer verständlichen Hinweis, statt `None` zu belassen.
- [ ] Ein echtes, sauberes Turn-Ende (`reason=="stop"`) bleibt unverändert ohne diesen Fehlerhinweis — Session bleibt self-resumable (PROJ-56/58/60 unverändert).
- [ ] Turns/Kosten/Kontext-Buchung aus Zwischenschritt-`result`-Events (PROJ-58-Verhalten) bleibt unverändert — dieser Fix ändert nur Transkript-Sichtbarkeit und Fehlerdiagnose, nicht die Abrechnung.
- [ ] Codex/Claude unverändert (eigene Regressionssuiten grün).
- [ ] Neue Regressionstests: (1) Tool-Only-Turn ohne Assistant-Text → Transkript enthält den Tool-Call; (2) stiller `closed`-Fallback → `state.error` ist gesetzt und nicht leer; (3) sauberes Turn-Ende → weiterhin kein Fehlerhinweis.
- [ ] Volle Backend-Suite grün (inkl. bestehender `test_proj60_opencode_silent_hang.py`, `test_proj58_opencode_stdin_race.py`, `test_proj59_opencode_stop_hang.py`, `test_proj57_opencode.py`).

## Edge Cases
- Turn mit mehreren aufeinanderfolgenden Tool-Calls ohne jeden Assistant-Text dazwischen: alle Tool-Calls müssen einzeln im Transkript auftauchen, nicht nur der letzte.
- Turn mit Tool-Call gefolgt von Assistant-Text (Normalfall): unverändertes Verhalten, kein Duplikat-Eintrag für denselben Tool-Call.
- Prozess crasht bereits VOR jedem Event (sofortiger Absturz, kein Tool-Call sichtbar): weiterhin `closed` ohne Transkript-Eintrag (nichts zu zeigen), aber `state.error` sollte trotzdem einen Hinweis tragen statt leer zu bleiben.
- Exit-Code ≠ 0 (bestehender `error`-Zweig mit Stderr-Text): unverändert — dort ist bereits ein Fehlertext vorhanden, dieser Fix betrifft nur den bisher leeren `rc==0`-ohne-finales-Result-Fall.

## Technical Requirements
- `backend/app/engine/manager.py` — `handle_event` (`tool_use`-Branch, Zeile ~592-610): zusätzlich zu `_emit_activity` einen `TranscriptEntry` anhängen; `system/closed`-Handling (Zeile ~558-560): `state.error` bei fehlendem vorherigem Fehler mit Diagnosetext füllen.
- `backend/app/engine/generic_cli_driver.py` — `_read_stdout()` (Zeile ~277-289): beim stillen `closed`-Fallback (kein `_saw_final_result`) einen kurzen Grund-String im `StreamEvent`-Payload mitgeben, den `manager.py` in `state.error` übernehmen kann.
- Neue/erweiterte Tests in `backend/tests/test_proj60_opencode_silent_hang.py` oder neue Datei `backend/tests/test_proj62_opencode_leeres_transkript.py`.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-05 · **Stack:** FastAPI-Backend (`SessionManager`/`GenericCliDriver`) + Next.js-16-Cockpit (Session-Detailseite) · **Branch:** `specs/PROJ-62-opencode-leeres-transkript`

### Codebasis-Befund (Explore-Agent, gegen den echten Code verifiziert)
- `TranscriptEntry` (`manager.py:261-265`) ist bereits ein generisches `{role, kind, text, ts}` — kein neues Feld, kein Schema-Update nötig. Assistant-Text nutzt es schon (`manager.py:568-578`); der `tool_use`-Branch (`manager.py:592-610`) hängt aktuell NICHTS an `self.transcript` an, nur an den flüchtigen Activity-Ticker (`_emit_activity`, `manager.py:516-532`).
- `SessionState.error: str | None` existiert bereits (`manager.py:295`), ist bereits Teil von `to_read()` (`manager.py:370`) und bereits im API-Response-Schema `SessionRead.error` (`schemas/sessions.py:129`) sowie im Next.js-Typ `Session.error` (`lib/types.ts:167`) verdrahtet — **Ende-zu-Ende bereits vorhanden**, nur der `system`/`closed`-Handler (`manager.py:549-561`) befüllt es im stillen PROJ-60-Fallback-Pfad nicht.
- `StreamEvent` (`events.py:25-34`) hat ein freies `raw: dict` — ein Grund-String lässt sich verlustfrei durchreichen, ohne die Event-Struktur zu ändern.
- Der Transcript-Renderer im Next.js-Cockpit (`app/(cockpit)/sessions/[id]/page.tsx:318-329`) ist bereits generisch (rendert `role`/`text` ohne Switch auf `kind`) — ein neuer `role:"tool"`-Eintrag erscheint automatisch, ohne neue UI-Verzweigung.
- Die „beendet/nicht steuerbar"-Banner-Anzeige (`page.tsx:276-278`) zeigt `error` aktuell NUR, wenn `status === "error"` (`page.tsx:296-299`) — der PROJ-60-Fallback belässt den Status aber bei `DONE`. Das ist die einzige Stelle, die eine echte neue UI-Verzweigung braucht.

### A) Komponentenstruktur (was sich sichtbar ändert)
```
Session-Detailseite (Next.js Cockpit)
├── Transcript-Panel (bereits generisch — zeigt neue Tool-Einträge automatisch)
│   └── neuer Eintrag: role="tool", kind="tool_use", text="Tool-Aufruf: bash — `git log …`"
└── „Session beendet/nicht steuerbar"-Banner
    └── NEU: zeigt state.error auch wenn status=DONE (nicht nur bei status=error)
```
Kein neuer Screen, kein neuer Endpoint — reine Erweiterung bestehender Komponenten.

### B) Datenmodell (Klartext)
- Jeder Tool-Aufruf (z. B. `bash`) hinterlässt ab jetzt zusätzlich zum Activity-Ticker einen persistenten Transkript-Eintrag: Rolle „tool", Text = Tool-Name + Kurzfassung der Eingabe (z. B. Befehlszeile), Zeitstempel.
- Bricht der zugrunde liegende Prozess ab, ohne einen echten Turn-Abschluss geliefert zu haben (PROJ-60-Fall), wird ein kurzer, für Menschen lesbarer deutscher Grund-Text in das bereits existierende `error`-Feld der Session geschrieben (z. B. „Der Prozess wurde beendet, ohne den Turn regulär abzuschließen.") — nur wenn dort noch nichts steht, damit ein echter Absturz-Fehler (Exit-Code ≠ 0) nicht überschrieben wird.
- Keine neue Datenbank-/Speicherstruktur, keine neue Tabelle — alles nutzt bestehende In-Memory-Session-Felder.

### C) API-Shape (keine Änderung nötig)
- `GET /sessions/{id}` liefert `transcript` und `error` bereits im Response-Schema (`SessionDetail`/`SessionRead`) — beide Felder sind schon Ende-zu-Ende bis in den Next.js-Typ `Session`/`TranscriptEntry` verdrahtet. Dieser Fix füllt nur bereits existierende Felder mit echtem Inhalt, ändert kein Schema und keinen Endpoint.

### D) Tech-Entscheidungen (Warum)
- **Kein neues Schema, kein neues Feld:** `error` und der generische `TranscriptEntry`-Typ existieren bereits Ende-zu-Ende — die kleinstmögliche Änderung ist, sie korrekt zu befüllen, statt Parallelstrukturen einzuführen.
- **Tool-Aufrufe als eigener Transkript-Eintrag statt „stiller" Sonderfall:** Der Activity-Ticker (PROJ-46/61) bleibt bewusst unangetastet — er ist für Live-„was passiert gerade"-Anzeige gedacht, nicht für die persistente Historie. Diese Trennung bleibt erhalten; wir fügen nur den fehlenden persistenten Pfad hinzu.
- **Kurzer, stabiler Grund-Text statt Rohdaten/Stacktrace im `error`-Feld:** Für den Nutzer verständlich, kein Leak interner Fehlerdetails — konsistent mit dem bestehenden `error`-Zweig bei Exit-Code ≠ 0 (dort steht bereits Stderr-Text, keine Stacktraces).
- **`error` wird nur gesetzt, wenn noch leer:** verhindert, dass der stille PROJ-60-Fallback einen bereits vorhandenen, aussagekräftigeren Fehler (z. B. aus dem `error`-Event-Zweig) überschreibt.
- **Frontend-Banner-Bedingung erweitern statt neue Komponente:** Die Dead-Banner-Anzeige ist die einzige Stelle, die eine echte neue UI-Verzweigung braucht (aktuell nur `status==="error"` statt „liveness tot UND error gesetzt", unabhängig vom genauen Status). Kleinstmöglicher Frontend-Touch.

### E) Dependencies (Pakete)
- Keine neuen Pakete — reine Nutzung bestehender Datenstrukturen (Backend: Python-Standardbibliothek; Frontend: kein neues npm-Paket).

---
<!-- Sections below are added by subsequent skills -->

## Implementation Notes (Backend Developer, 2026-07-05)

### Geänderte Dateien
- `backend/app/engine/manager.py`:
  - `TranscriptEntry.role`/`.kind`-Kommentar erweitert (`"tool"` / `"tool_use"`, PROJ-62).
  - `tool_use`-Branch in `handle_event` (~Zeile 592-620): hängt zusätzlich zum bestehenden `_emit_activity`-Aufruf einen persistenten `TranscriptEntry("tool", "tool_use", "<tool_name>: <sanitize_target(...)>", ts)` an `self.transcript` an. Nutzt die bereits vorhandene `sanitize_target`-Funktion (PROJ-46) — keine neue Sanitisierung nötig.
  - `system/closed`-Branch (~Zeile 558-566): setzt `state.error` auf einen festen deutschen Hinweistext, wenn `event.raw.get("reason") == "no_final_result"` UND `state.error` noch leer ist. Überschreibt nie einen bereits vorhandenen (aussagekräftigeren) Fehler.
- `backend/app/engine/generic_cli_driver.py`:
  - `_read_stdout()` (~Zeile 277-289): der stille PROJ-60-Fallback-Pfad (Prozessende `rc in (0, None)` ohne je ein finales `result`-Event) emittiert jetzt `StreamEvent("system", "closed", {"reason": "no_final_result"})` statt eines leeren Payloads. Der deliberate-stop-Pfad (`self._stopping`) bleibt unverändert ohne Grund — kein Fehlertext bei gewolltem Stopp.
- `backend/tests/test_proj62_opencode_leeres_transkript.py` — NEU (7 Tests): Tool-Use-Event landet im Transkript; Tool-Only-Turn bleibt nach stillem Fallback sichtbar; Activity-Ticker bleibt unverändert; stiller Fallback setzt `error`; Fallback ohne Grund setzt keinen Fehler; bestehender Fehler wird nicht überschrieben; Treiber-Ebene liefert den `reason`-String im `closed`-Event.

### Bewusst NICHT in diesem Backend-Schritt umgesetzt
- Der in der Architektur benannte Frontend-Touch (Dead-Banner in `app/(cockpit)/sessions/[id]/page.tsx` zeigt `error` bisher nur bei `status==="error"`, nicht bei `status==="done"` mit gesetztem `error`) ist Next.js-Scope — folgt in `/abc-frontend`. Backend liefert den Wert bereits korrekt (End-zu-Ende bestehendes `SessionRead.error`-Feld), nur die UI-Bedingung fehlt noch.

### Tests
- `test_proj62_opencode_leeres_transkript.py`: 7/7 grün.
- Regression: `test_proj46_activity_ticker.py`, `test_proj57_opencode.py`, `test_proj58_opencode_stdin_race.py`, `test_proj59_opencode_stop_hang.py`, `test_proj60_opencode_silent_hang.py`, `test_proj48_codex.py`, `test_proj50_codex_abc.py`: alle grün (kein neuer Fail).
- Volle Suite: 1066 passed, 1 failed — der Fail (`test_generator_check_passes_no_drift`) ist der vorbestehende, unabhängige Codex-Skill-Drift-Test (bereits in PROJ-60s QA-Notizen als vorbestehend/unabhängig dokumentiert, betrifft `.codex/skills`-Sync, nichts mit dieser Änderung).

### Offen für QA
- Backend-Teil (Transkript-Persistenz + `state.error`) vollständig testbar und getestet.
- Der Frontend-Banner-Touch ist noch offen (separater `/abc-frontend`-Schritt) — bis dahin liefert die API zwar korrekt `error`, das Cockpit zeigt ihn im DONE-Fallback-Fall aber noch nicht an.

## Implementation Notes (Frontend Developer, 2026-07-05)

### Geänderte Dateien
- `nextjs_app/app/(cockpit)/sessions/[id]/page.tsx`: die rote Fehlertext-Anzeige (bisher nur `head?.status === "error" && head.error`) zeigt jetzt zusätzlich `head.error`, wenn `head?.liveness === "tot"` — genau der Fall, den der stille PROJ-60-Fallback erzeugt (Status bleibt `done`, aber `error` trägt jetzt den PROJ-62-Hinweistext aus dem Backend). Kein neuer Typ, keine neue Komponente — der generische Transkript-Renderer (`role`/`text`) brauchte keine Änderung, da `TranscriptEntry.role` bereits als offener `string`-Typ typisiert ist (neuer Wert `"tool"` läuft automatisch mit).

### Tests
- `npm run lint`: sauber.
- `npm run test`: 18/20 Testdateien grün, 172/174 Tests grün. Die 2 Fails (`file-preview.test.tsx`, `sidebar-prefs-provider.test.ts`) sind vorbestehend und unabhängig — per `git stash`-Vergleich verifiziert: identischer Fail-Stand auch ohne diese Änderung (gehören zu einer anderen, parallel laufenden Session/Feature im selben Working Tree, nicht zu PROJ-62).
- Kein dediziertes Unit-Test-Setup für die Session-Detailseite (`page.tsx`) im Repo vorhanden — Abdeckung erfolgt visuell/über QA bzw. e2e.

### Offen für QA
- Visuelle Verifikation im Cockpit: eine Session, die über den PROJ-60-Fallback endet, sollte jetzt sowohl mindestens einen Tool-Transkript-Eintrag als auch den roten Fehlertext im "beendet/nicht steuerbar"-Zustand zeigen.

## QA Test Results

**Tested:** 2026-07-05
**Backend:** kein Zugriff auf den produktiven `jupiter-backend`-Dienst (Restart würde die aktive Session beenden — PROJ-58/59/60-Präzedenzfall). Live-Verifikation direkt gegen `GenericCliDriver` + `SessionRuntime` + `SessionState` (reale Produktionsklassen, End-zu-Ende über den echten Event-Pfad, NICHT nur die Implementierungstests des Backend-Devs).
**Tester:** QA Engineer (AI)

### Methodik
- Automatisierte Suite: `test_proj62_opencode_leeres_transkript.py` (7 Tests) + volle Backend-Suite (1067 Tests) + Frontend-Suite (`npm run lint`, `npm run test`).
- **Unabhängige Live-Reproduktion** des exakt gemeldeten Falls: eine Fake-CLI, die haargenau den Original-Screenshot nachstellt (`bash: git log --all --oneline | head -30`, Kosten `$0.0332`, dann Prozessende ohne finalen `step_finish`), an eine ECHTE `SessionRuntime` + `GenericCliDriver` gehängt (kein Mock der zu testenden Logik selbst). Geprüft: `state.status`, `state.error`, `runtime.transcript`, `runtime.derive_liveness()`.
- Zusätzliche unabhängige Live-Reproduktionen für: sauberes Turn-Ende (Regression), sofortiger Absturz ohne jedes Event (Edge Case), mehrere Tool-Calls ohne Assistant-Text dazwischen (Edge Case).
- Statische Prüfung aller bestehenden `state.error =`-Zuweisungsstellen in `manager.py`, um sicherzustellen, dass die neue Banner-Bedingung (`status==="error" || liveness==="tot"`) keine bestehende Fehleranzeige verdoppelt oder eine neue Stelle fälschlich triggert (alle bestehenden `error`-Zuweisungen koexistieren bereits mit `status=ERROR`, decken sich also mit der alten Bedingung).

### Acceptance Criteria Status
- [x] `tool_use`-Events erzeugen einen persistenten `TranscriptEntry` — Live-Repro: `role='tool', kind='tool_use', text='bash: git log --all --oneline | head -30'` erscheint in `runtime.transcript`.
- [x] Tool-Only-Turn zeigt nach Sessionende mindestens einen Transkript-Eintrag — Live-Repro exakter gemeldeter Fall: 1 Eintrag statt „Noch keine Transkript-Historie".
- [x] Stiller `closed`-Fallback setzt `state.error` — Live-Repro: `error == "Der Prozess wurde beendet, ohne den Turn regulär abzuschließen."`, `status == DONE`, `derive_liveness() == "tot"` (bestätigt die volle Kette bis zur Frontend-Bedingung).
- [x] Sauberes Turn-Ende bleibt ohne Fehlerhinweis — Live-Repro: `status == "waiting"`, `error is None`, `derive_liveness() == "aktiv"` (self-resumable, unverändert).
- [x] Turns/Kosten/Kontext-Buchung unverändert — Live-Repro: `num_turns == 1`, `total_cost_usd == 0.0332` (identisch zum Original-Screenshot) trotz leerem Assistant-Text.
- [x] Codex/Claude unverändert — volle Regressionssuite (`test_proj48_codex.py`, `test_proj50_codex_abc.py`, Claude-Treiber-Tests) grün, kein neuer Fail.
- [x] Neue Regressionstests (3 Fälle) vorhanden und grün — `test_proj62_opencode_leeres_transkript.py`, 7/7.
- [x] Volle Backend-Suite grün bis auf den vorbestehenden, unabhängigen Codex-Skill-Drift-Test — per `git stash` + Checkout auf `main` verifiziert: identischer Fail auch ohne diese Änderung.

### Edge Cases Status
- [x] Mehrere Tool-Calls ohne Assistant-Text dazwischen: unabhängig verifiziert — alle 3 Tool-Calls erscheinen einzeln im Transkript (`bash: ls`, `Read: a.py`, `Edit: b.py`).
- [x] Tool-Call gefolgt von Assistant-Text (Normalfall): durch bestehende Suite abgedeckt (`test_proj57_opencode.py`, `test_proj48_codex.py` unverändert grün) — kein Duplikat-Eintrag.
- [x] Sofortiger Absturz VOR jedem Event: unabhängig verifiziert — `transcript` bleibt leer (nichts zu zeigen), aber `state.error` ist gesetzt (`"Der Prozess wurde beendet, ohne den Turn regulär abzuschließen."`) statt leer zu bleiben.
- [x] Exit-Code ≠ 0: unverändert — Code-Review bestätigt, dieser Zweig (`generic_cli_driver.py`, `error`-Branch) wurde nicht angefasst.

### Security Audit Results
- [x] Keine neue Angriffsfläche: reine interne In-Memory-Zustands-/Transkriptlogik, kein neuer Endpoint, kein neues Auth-/Tenant-Feld (Jupiter-MVP: single-user, kein JWT/RLS-Scope betroffen — siehe Stack-Override-Konvention).
- [x] XSS-Check: der neue `role="tool"`-Transkript-Eintrag wird identisch zu bestehenden Einträgen als reiner JSX-Textkindknoten gerendert (`<p>{t.text}</p>`, React escaped automatisch) — kein `dangerouslySetInnerHTML`, kein Injection-Risiko auch bei potenziell beliebigen Tool-Kommandozeilen.
- [x] Kein Info-Leak: `sanitize_target` (PROJ-46, unverändert wiederverwendet) kappt bei 80 Zeichen und kollabiert Whitespace — dieselbe serverseitige Sanitisierung wie beim bestehenden Activity-Ticker. `state.error` trägt im neuen Pfad ausschließlich einen festen, statischen deutschen Text (keine Stacktraces/Rohdaten).
- [x] Bestehende Fehlerpfade (Exit-Code ≠ 0, API-Fehler) unverändert — kein neuer Pfad, der Rohdaten/Exceptions in `error` durchreicht.

### Bugs Found
Keine. Der ursprünglich gemeldete Fehlerfall (leeres Transkript + unerklärtes Sessionende) ist durch die unabhängige Live-Reproduktion bestätigt behoben — inklusive exakter Nachstellung der Original-Screenshot-Werte (Kosten, Tool-Aufruf).

### Summary
- **Acceptance Criteria:** 8/8 bestanden (0 Fails).
- **Edge Cases:** 4/4 bestanden.
- **Bugs Found:** 0 total.
- **Security:** Pass.
- **Production Ready:** YES
- **Empfehlung:** Approved. Bei nächster Gelegenheit deployen (`/abc-deploy`) — der offene Frontend-Punkt aus den Implementation Notes (Banner-Bedingung) ist bereits umgesetzt und Teil dieses QA-Durchlaufs.

## Deployment

**Bookkeeping-Nachtrag (2026-07-07):** Bereits am 2026-07-05 als Teil von Commit `9d8d565` („chore(deploy): Bump 0.27.10 (PROJ-62 OpenCode-Tool-Only-Turn-Fix)") nach `main` deployt — der Status hier war seither nicht auf „Deployed" nachgezogen worden.

**Datum:** 2026-07-05 · **Version:** 0.27.10 · **Branch:** main · **Production URL:** https://jupiter.auxevo.tech

### Ausgeliefert
- `tool_use`-Events hinterlassen einen persistenten Transkript-Eintrag (nicht nur den flüchtigen Activity-Ticker).
- Stiller PROJ-60-Fallback (Prozessende ohne finalen `step_finish`) setzt `state.error` mit einem verständlichen Hinweistext, sichtbar auch bei `status=done` im Cockpit-Banner.
