# PROJ-74: Bugfix: Backend-Neustart orphaniert lebende tmux-Sessions unnötig (rehydrate() ignoriert echte Prozess-Liveness)

## Status: Deployed
**Created:** 2026-07-17
**Last Updated:** 2026-07-18
**Deployed:** 2026-07-18 · Version 0.27.34 · https://jupiter.auxevo.tech

## Problem / Motivation
Report `docs/reports/2026-07-17-session-management-vergleich.md` (Vergleich mit Wayland/Agentic-OS-Session-Management) hat folgende Lücke identifiziert:

`rehydrate()` (`backend/app/engine/manager.py:1391-1447`) markiert bei Backend-Neustart **jede** vorher `ACTIVE` Session pauschal als `ERROR`/verwaist — außer `drained_at` wurde durch ein *geordnetes* `drain()` gesetzt (`manager.py:1449-1471`). Bei einem **harten** Backend-Absturz (Crash, OOM, Deploy ohne graceful shutdown) existiert kein `drained_at`, obwohl der zugrunde liegende **tmux-Pane-Prozess (PROJ-63) technisch weiterlebt** — der Agent arbeitet unbeobachtet weiter, während die UI/DB die Session bereits als tot/verwaist führt. Der bestehende Code-Kommentar an dieser Stelle (`manager.py:1394-1398`) markiert die Logik selbst als vermutlich veraltet seit PROJ-63 (Einführung des langlebigen tmux-Transports).

Referenzarchitekturen lösen das strukturell:
- **Wayland**: Suspend statt Kill bei Disconnect, Resume lazy bei nächster Nachricht — Prozesslebensdauer ist von der Server-Verbindung entkoppelt.
- **Agentic OS**: Kindprozesse laufen `detached`/`unref()`'t, überleben den Supervisor-Neustart; beim nächsten Read wird über PID-Check + Log-Reconciliation rekonstruiert, ob ein als "verwaist" geführter Prozess tatsächlich noch lebt.

Das ist der im Report als wahrscheinlichster Auslöser identifizierte Fall für "Session bricht ab / muss neu geladen werden, obwohl der Agent eigentlich noch lief".

## Dependencies
- Requires: PROJ-63 (Tmux-Session-Transport), PROJ-27 (Liveness-Indikator + Reanimieren), PROJ-33 (Session-Lifecycle-Härtung: Restart-Resilienz), PROJ-66 (Transkript-Persistenz nach Neustart)

## Scope-Abgrenzung (bewusst)
- **In Scope:** `rehydrate()` erweitern, sodass für tmux-gestützte Sessions vor dem Orphanieren die tatsächliche Prozess-/Pane-Liveness geprüft wird (analog dem bereits vorhandenen `pid_alive()`-Mechanismus aus der Liveness-Loop, `liveness.py`), statt sich ausschließlich auf `drained_at` zu verlassen.
- **Out of Scope:** Engines ohne tmux-Transport (Codex/OpenCode/OpenAI, `direct`-Transport) — deren Prozesslebensdauer ist bereits an die Backend-Lebenszeit gekoppelt (bekannt, dokumentiert), das ändert dieses Ticket nicht.
- **Out of Scope:** `direct` als Default-Transport umkehren oder ein Config-Lint für fehlende `engine_overrides`-Einträge (separates Ticket, falls gewünscht).
- **Out of Scope:** Eine formale Zustandsmaschine für `SessionRuntime` (Report-Punkt 5) — das ist ein `/abc-refactor`-Thema (verhaltenswahrender Umbau ohne akuten Einzel-Bug), kein Bugfix-Feature.

## User Stories
- Als Nutzer möchte ich, dass eine Claude-Session, die beim Absturz/Neustart des Backends gerade in einem lebenden tmux-Pane weiterläuft, nach dem Neustart **weiterhin als aktiv/wiederverbindbar** erkannt wird, statt fälschlich als Fehler/verwaist markiert zu werden — damit ich nicht unnötig Kontext oder eine laufende Session verliere.
- Als Nutzer möchte ich, dass eine Session, deren tmux-Pane beim Neustart **tatsächlich** tot ist, weiterhin korrekt als Fehler/verwaist markiert wird — damit ich keine tote Session für aktiv halte.
- Als Entwickler möchte ich, dass die Orphan-Entscheidung bei `rehydrate()` nachvollziehbar geloggt wird (welches Kriterium griff: `drained_at` gesetzt / Pane lebt / Pane tot), um zukünftige Fälle schnell diagnostizieren zu können.

## Acceptance Criteria
- [x] Reproduktion vor Fix: Eine Session mit tmux-Transport wird gestartet, das Backend wird **hart** beendet (kein `drain()`), das Backend startet neu → Session landet aktuell in `ERROR`/orphaned, obwohl der tmux-Pane-Prozess nachweislich noch läuft. Dieser Fall muss als fehlschlagender Test reproduzierbar sein, bevor der Fix beginnt. — `test_rehydrate_tmux_pane_still_alive_is_not_orphaned` lief vor dem Fix rot (`AttributeError: 'TmuxTransport' object has no attribute 'pane_alive_after_restart'`, danach mit dem alten Verzweigungscode ERROR).
- [x] Nach dem Fix: Im identischen Szenario (harter Backend-Stopp, laufender tmux-Pane, kein `drained_at`) erkennt `rehydrate()` die echte Prozess-Liveness und versetzt die Session **nicht** in `ERROR` — sie bleibt reconnect-/reanimierbar.
- [x] Gegenprobe: Ist der tmux-Pane beim Neustart tatsächlich tot (Prozess existiert nicht mehr), markiert `rehydrate()` die Session weiterhin korrekt als `ERROR`/orphaned — keine falschen Positiven in die andere Richtung. (`test_rehydrate_tmux_pane_dead_is_still_orphaned`)
- [x] Geordnetes `drain()` (`drained_at` gesetzt) verhält sich unverändert wie bisher (kein Regressions-Bruch am bestehenden Happy-Path aus PROJ-33/PROJ-66). (`test_rehydrate_drained_is_resume_candidate` weiterhin grün)
- [x] Engines ohne tmux-Transport (`direct`) zeigen unverändertes Verhalten — dieses Ticket ändert deren Orphan-Logik nicht. (`test_rehydrate_crash_orphan_is_not_resume_candidate` weiterhin grün, transport bleibt Default `"direct"`)
- [x] Bestehende Resume-/Rehydrate-/Liveness-Testsuiten (proj27, proj33, proj63, proj64, proj66) bleiben grün. 168/168 gezielt + volle Suite 1185 passed (2 vorbestehende, themenfremde Fails in `test_proj50_codex_abc.py`, s. Verifikation).

## Edge Cases
- Tmux-Server selbst ist nach dem Neustart nicht erreichbar (z. B. `tmux`-Daemon down) — die Liveness-Prüfung muss das als "Pane tot" behandeln, nicht als Timeout/Hänger (Bezug zu PROJ-64: bekannte `tmux`-CLI-Hang-Absicherung mit `_cmd_timeout_seconds`).
- Pane existiert, gehört aber inzwischen zu einer anderen, neu gestarteten Session-ID (PID-Wiederverwendung durch das OS) — Fehlklassifikation als "lebt noch" muss ausgeschlossen werden (Pane-Identität, nicht nur nackte PID, prüfen).
- Mehrere Sessions werden beim selben Neustart rehydriert — die Liveness-Prüfung pro Session darf den Rehydrate-Vorgang insgesamt nicht spürbar verlangsamen (viele `tmux`-CLI-Aufrufe hintereinander).
- Session war zum Zeitpunkt des Absturzes mitten in einem Tool-Aufruf (`tool_in_flight`, PROJ-45-Hysterese) — die als "lebt noch" erkannte Session muss nach Reconnect denselben Zustand respektieren, nicht fälschlich als neu/leer erscheinen.

## Technical Requirements (optional)
- Betroffene Datei/Funktion: `backend/app/engine/manager.py:1391-1447` (`rehydrate()`), ggf. `manager.py:1449-1471` (`drain()`-Gegenstück), Liveness-Primitive aus `backend/app/engine/liveness.py` (`pid_alive()`-Äquivalent) wiederverwenden statt neu erfinden.
- Kein neuer Endpoint, keine Schema-Änderung erwartet — reine Backend-Logikänderung im Rehydrate-Pfad.
- Verifikation nach `/abc-backoffice`-Kontrakt: Reproduktion-vor-Fix (roter Test) → Fix → grün, plus Regressionslauf der genannten Suiten.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-17 · **Stack:** Backend-only (FastAPI, kein Frontend-Anteil) · **Branch:** dev

### A) Betroffene Komponente (kein UI)
Reiner Backend-Fix im Engine-Layer, kein Screen/Widget betroffen:
```
SessionManager.rehydrate()  (backend/app/engine/manager.py:1391-1447)
└── liest pro Zeile: state.transport ("tmux" | "direct"), state.drained_at, row.pid
    └── NEU: bei transport == "tmux" und fehlendem drained_at
        → TmuxTransport(session_id).refresh_liveness() / session_exists() befragen
        → Pane lebt  → Status bleibt reconnect-/reanimierbar (kein ERROR)
        → Pane tot   → wie bisher: ERROR mit Orphan-Notiz
```

### B) Datenmodell (keine Schema-Änderung)
Keine neue Spalte nötig — alle Bausteine existieren bereits, sind nur nicht verdrahtet:
- `session_index`-Zeile trägt bereits `transport` (`"tmux"`/`"direct"`, Default `"direct"`) und `drained_at`.
- Die tmux-Pane-Zieladresse ist **kein gespeicherter Wert**, sondern deterministisch aus der `session_id` ableitbar (`sanitize_tmux_session_name(session_id)` → `"jupiter-<id>"`, `transport.py:66-73`) — genau dasselbe Muster, das `ClaudeCodeDriver`/`GenericCliDriver` beim normalen Spawn schon verwenden. Kein Risiko durch OS-PID-Wiederverwendung, weil nicht die nackte PID, sondern der tmux-Session-Name die Quelle der Wahrheit ist.
- Die vorbereiteten, aber ungenutzten Spalten `tmux_session`/`tmux_pane`/`tmux_capture_cursor`/`transport_status` in `session_index.py` bleiben außerhalb des Scopes dieses Fixes unangetastet (totes Schema, kein Teil dieser Lösung).

### C) Ablauf (kein API-Shape — kein neuer Endpoint)
Kein neuer/geänderter HTTP- oder WebSocket-Endpoint. Der Fix wirkt ausschließlich im internen Startup-Pfad:
```
Backend-Start
→ rehydrate() liest alle Zeilen mit status ∈ ACTIVE_STATES
→ pro Zeile mit transport == "tmux" und ohne drained_at:
    await TmuxTransport(session_id).session_exists() / refresh_liveness()
    (wiederverwendet bestehende Primitive, transport.py:646-691 — kein neuer Code für die Prüfung selbst)
→ Ergebnis entscheidet die bisher schon vorhandene Verzweigung (ERROR vs. reanimierbar)
```

### D) Tech-Entscheidungen (Warum)
- **Bestehende Primitive wiederverwenden, nichts Neues bauen:** `TmuxTransport._probe_alive()`/`refresh_liveness()` (`transport.py:646-668`) und `session_exists()` (`:687-691`) existieren bereits und werden aktuell nirgends beim Rehydrate befragt — der kleinste korrekte Eingriff ist, sie an der einen fehlenden Stelle aufzurufen, nicht eine neue Liveness-Prüfung zu erfinden.
- **Fail-safe Richtung bleibt konservativ erhalten:** Ist der tmux-Daemon selbst nicht erreichbar oder der `tmux`-CLI-Call schlägt fehl (Timeout, `rc != 0`), gilt die Session weiterhin als "nicht lebendig" → ERROR wie bisher. Der Fix erweitert nur den Fall "Pane nachweislich lebendig", nie umgekehrt — dadurch kann kein totes/unklares Pane fälschlich als aktiv durchgehen.
- **Transport-Typ ist bereits pro Zeile bekannt** (`state.transport`), daher betrifft die Änderung ausschließlich tmux-transportierte Sessions; `direct`-Sessions (Codex/OpenCode/OpenAI im Default) verhalten sich exakt wie heute — kein Risiko einer Verhaltensänderung außerhalb des beschriebenen Faclls.
- **Async passt ohne Umbau:** `rehydrate()` ist bereits eine `async`-Funktion; die zusätzlichen `await`-Aufrufe der tmux-CLI-Prüfung fügen sich ohne Sync/Async-Bruch ein (bestätigt durch Codegraph-Exploration).
- **Kosten vertretbar:** ein zusätzlicher `tmux`-Subprozess-Aufruf pro potenziell verwaister tmux-Zeile beim Start — vernachlässigbar außer bei sehr vielen gleichzeitigen Orphans; Timeout/Retry-Verhalten ist bereits über `settings.tmux_cmd_timeout_seconds`/`tmux_cmd_retries` (`config.py:305,312`) abgesichert (PROJ-64-Härtung), kein neuer Zeitbudget-Mechanismus nötig.

### E) Abhängigkeiten (Pakete)
- Keine neuen Pakete — reine Logikänderung, nutzt ausschließlich bereits vorhandene interne Module (`transport.py`, `manager.py`, `liveness.py`).

### Umsetzungshinweis für /abc-backoffice
Root Cause bereits lokalisiert (`manager.py:1391-1447`, Verzweigung ignoriert `_pid_alive`/tmux-Liveness für die Status-Entscheidung, nutzt sie nur für den Fehlertext). Reproduktion-vor-Fix: bestehende Tests `test_rehydrate_markiert_aktive_als_verwaist` (test_proj14) und `test_rehydrate_crash_orphan_is_not_resume_candidate` (test_proj33) als Ausgangspunkt für einen neuen, tmux-spezifischen Gegenfall erweitern (Pane lebt → keine ERROR-Markierung). Tmux-Fixtures dafür bereits in `test_proj63_tmux_transport.py`/`test_proj63_manager_transport.py` vorhanden.

## Implementation Notes

**Root Cause (verifiziert):** `manager.py:1396` (vor dem Fix) setzte `state.status = ERROR`
unconditional für JEDE vorher aktive Session ohne `drained_at` — der bereits vorhandene
`_pid_alive(row.get("pid"))`-Check (Zeile 1402 alt) floss nur in den Fehlertext ein, nie in
die Status-Entscheidung. Zusätzlich hätte ein reiner bare-PID-Check für tmux-Sessions ein
PID-Reuse-Risiko gehabt (`os.kill(pid, 0)` kennt keine Prozess-Identität).

**Fix (kleinster korrekter Eingriff, zwei Dateien):**
1. `backend/app/engine/transport.py` — `TmuxTransport._probe_alive()` unverändert in
   Verhalten, aber in eine geteilte `_pane_has_live_process()` (die eigentliche
   `list-panes -F "#{pane_dead}"`-Abfrage) und das `_spawned`-Gate zerlegt. Neue öffentliche
   `pane_alive_after_restart()`: dieselbe Abfrage OHNE das `_spawned`-Gate (das Gate schützt
   nur davor, eine Instanz VOR ihrem eigenen `spawn()` zu befragen — sagt nichts über die
   tmux-Pane selbst aus; bei einer frisch konstruierten Rehydrate-Instanz ist `_spawned`
   naturgemäß immer `False`, obwohl die Pane einer FRÜHEREN Instanz durchaus noch lebt).
   Fail-safe: jeder `TransportError`/`TmuxTimeoutError` → `False`.
2. `backend/app/engine/manager.py` — `rehydrate()`: dritter Zweig zwischen `drained_at` und
   dem alten Crash-Orphan-Fallback: `state.transport == "tmux" and await
   TmuxTransport(sid).pane_alive_after_restart()` → `state.status` bleibt UNVERÄNDERT (keine
   Herabstufung auf ERROR), nur eine akkurate, nicht-alarmierende `state.error`-Notiz. Der
   Persist-Trigger am Ende der Schleife wurde von „nur bei Statuswechsel" auf „jede Zeile, die
   den ACTIVE_STATES-Zweig durchläuft" umgestellt, sonst wäre die neue Fehlertext-Aktualisierung
   in diesem Zweig nur im RAM gelandet (kein Statuswechsel → alter Guard hätte nicht persistiert).

**Bewusst NICHT verändert (Scope-Wächter):**
- `DeadDriver.is_alive` bleibt `False` — würde man das für den verifiziert-lebendigen Fall auf
  `True` setzen, griffe `derive_liveness()`s Hänger-Erkennung mit einer beim Neustart
  zurückgesetzten Fortschritts-Uhr sofort und triggerte via `evaluate_liveness_once()` eine
  AUTOMATISCHE Reanimierung unmittelbar nach jedem Neustart — und da `_ensure_no_stale_session()`
  bei JEDEM Resume ohnehin unconditional killt+neu spawnt, wäre das ein waschechtes
  Resume-Storm-Risiko bei einem Backend-Crash-Loop (genau das, was PROJ-33 mit dem
  `drained_at`-Gate bewusst verhindert). Diese verifiziert-lebendigen Sessions bleiben daher
  bewusst NICHT Teil von `auto_resume_drained()` — reines Bookkeeping/Messaging-Fix, keine
  Änderung an Auto-Resume-Policy.
- `session_exists()` (has-session) wurde NICHT als Liveness-Signal verwendet — wegen
  `remain-on-exit on` (PROJ-63) bleibt eine tmux-Session auch nach Prozessende technisch
  "vorhanden"; nur `list-panes -F "#{pane_dead}"` unterscheidet echte Liveness.

## QA Test Results

**Tested:** 2026-07-18
**Backend:** rein Backend/pytest — kein laufender Server nötig (kein neuer Endpoint)
**Frontend:** entfällt (kein UI-Anteil, s. Tech Design A)
**Tester:** QA Engineer (AI)

### Acceptance Criteria Status

#### AC-1: Reproduktion vor Fix
- [x] `test_rehydrate_tmux_pane_still_alive_is_not_orphaned` unabhängig nachvollzogen (Fix per `git stash` temporär entfernt → Test rot, `git stash pop` → grün). Entwickler-Angabe verifiziert, nicht nur übernommen.

#### AC-2: Pane lebt → kein ERROR
- [x] Bestätigt: `state.status` bleibt unverändert (z. B. `RUNNING`), Fehlertext nennt „reanimieren" statt „Verwaist".

#### AC-3: Gegenprobe — Pane tot → weiterhin ERROR
- [x] `test_rehydrate_tmux_pane_dead_is_still_orphaned` grün. **Aber:** deckt nur den Fall „tmux-Session existiert gar nicht" (`rc != 0`) ab. Der zweite Dead-Fall — Session existiert noch (`remain-on-exit on`), aber Pane ist tot (`pane_dead=1`, z. B. nach einem bereits abgeschlossenen Oneshot-Turn) — ist NICHT durch einen eigenen Test abgedeckt. Logik ist bei Code-Lesung korrekt (`any(line.strip()=="0" ...)` liefert für `pane_dead=1` ebenfalls `False`), aber unbewiesen. → EC-5 (neu, unten).

#### AC-4: Drained-Pfad unverändert
- [x] `test_rehydrate_drained_is_resume_candidate` weiterhin grün, unverändertes Verhalten bestätigt.

#### AC-5: `direct`-Transport unverändert
- [x] `test_rehydrate_crash_orphan_is_not_resume_candidate` weiterhin grün.

#### AC-6: Bestehende Suiten grün
- [x] Unabhängig nachgefahren (nicht nur Entwickler-Angabe übernommen): gezielter Lauf (proj14/27/33/63/64/66 + `test_proj4_decision_cards.py`) 168 passed. Volle Suite: **1185 passed, 2 failed** — beide vorbestehend/themenfremd (`test_proj50_codex_abc.py::test_generator_check_passes_no_drift`, `::test_generator_short_description_nonempty_all_skills`, Codex-Skillgenerator-Drift durch neu hinzugekommene Skills `abc-backoffice`/`abc-customer-journey`, unabhängig verifiziert mit Einzellauf + Fehlerausgabe — kein Bezug zu Engine/Manager/Transport-Code).

### Edge Cases Status

#### EC-1: tmux-Daemon nach Neustart nicht erreichbar
- [ ] **BUG-1 (siehe unten).** Nur der explizit erwartete Fehlerfall (`TransportError`/`TmuxTimeoutError`, z. B. Timeout) wird abgefangen und konservativ als „tot" behandelt. Ein *anderer* Fehler bei der tmux-Subprozess-Erstellung (z. B. `FileNotFoundError`, wenn `tmux_bin` nicht auffindbar ist) wird NICHT abgefangen und reißt den gesamten `rehydrate()`-Durchlauf ab.

#### EC-2: PID-Wiederverwendung
- [x] Durch Design ausgeschlossen: Die Liveness-Prüfung nutzt den tmux-Session-Namen (`sanitize_tmux_session_name`), nicht die rohe PID — verifiziert per Code-Lesung, kein dedizierter Test nötig (strukturelle Garantie, keine laufzeitabhängige Heuristik).

#### EC-3: Viele Sessions beim selben Neustart
- [x] Kein Bug, aber quantifiziert (vorher nur qualitativ als „vernachlässigbar" im Tech Design eingeschätzt): `rehydrate()` iteriert sequenziell, jede tmux-Liveness-Prüfung ist mit `tmux_cmd_timeout_seconds=10.0` × (`tmux_cmd_retries=1` + 1 Versuch) auf bis zu ~20 s Worst-Case begrenzt — bei einem komplett hängenden tmux-Daemon und N orphanierten tmux-Zeilen addiert sich das zu N×20s Backend-Startup-Verzögerung. Bei Jupiters Single-User-MVP-Größenordnung (wenige parallele Sessions) real begrenzt, aber schlimmer als im Tech Design suggeriert — als Hinweis für spätere Skalierung festgehalten, kein blockierender Bug.

#### EC-4: `tool_in_flight`-Zustand nach Reconnect
- [x] Nicht von diesem Fix berührt — `rehydrate()` fasst `watchdog`/`tool_in_flight` nicht an; das Zurücksetzen passiert unverändert erst in `_resume()` (`runtime.watchdog.clear_tool_in_flight()`). Kein Regressionsrisiko durch PROJ-74.

#### EC-5: Pane existiert noch, ist aber tot (`remain-on-exit`) — NEU identifiziert
- [ ] Nicht durch Test abgedeckt (s. AC-3). Kein bestätigter Bug, aber ungeprüft.

### Security Audit Results
- Kein Auth-/Tenant-/RLS-Bezug (Jupiter-MVP: bewusst kein Auth auf diesem Layer, s. `docs/PRD.md` Non-Goals). Kein neuer Endpoint, keine Nutzereingabe, kein SQL — reine interne Rehydrate-Logik.
- `sid` stammt aus der DB-Zeile (`session_id`), fließt in `TmuxTransport(sid)` → `sanitize_tmux_session_name()` (bestehender, ungeänderter Sanitizer) — keine neue Injektionsfläche.
- [x] Kein Secrets-/Auth-Bezug — Abschnitt entfällt inhaltlich für dieses Ticket.

### Bugs Found

#### BUG-1: Unerwartete Exception in der neuen tmux-Liveness-Prüfung reißt den GESAMTEN `rehydrate()`-Durchlauf ab (nicht nur die betroffene Session)
- **Severity:** High
- **Steps to Reproduce (unabhängig reproduziert, siehe Kommando unten):**
  1. Zwei Live-Index-Zeilen seeden: A (`transport=tmux`, `status=running`, kein `drained_at`), B (`transport=direct`, `status=running`, kein `drained_at`) — B nach A.
  2. `settings.tmux_bin` auf einen nicht existierenden Binary-Namen setzen (simuliert z. B. eine defekte `tmux`-Installation/PATH-Drift zwischen Original-Spawn und Neustart).
  3. `await mgr.rehydrate()` aufrufen.
  4. **Erwartet** (laut Tech Design, Abschnitt D „Fail-safe Richtung bleibt konservativ erhalten"): Zeile A fällt konservativ auf ERROR zurück, Zeile B wird trotzdem normal rehydriert.
  5. **Tatsächlich:** `rehydrate()` wirft `FileNotFoundError` unbehandelt (nur `TransportError`/`TmuxTimeoutError` werden in `pane_alive_after_restart()` gefangen — ein `FileNotFoundError` aus `asyncio.create_subprocess_exec`, wenn das Binary fehlt, ist keins von beiden). Die Schleife bricht komplett ab: **weder A noch B landen in `mgr._sessions`**, unabhängig verifiziert:
    ```
    rehydrate() RAISED: <class 'FileNotFoundError'> [Errno 2] No such file or directory: 'definitely-not-a-real-tmux-binary-xyz'
    sessions in memory after rehydrate: []
    ```
  6. Da `backend/app/main.py:243-253` `rehydrate()` **und** `auto_resume_drained()` in einem gemeinsamen `try/except Exception: pass` kapselt, startet die App zwar weiter (kein Crash), aber: (a) **alle** vorher aktiven Sessions verschwinden kommentarlos aus der Übersicht — auch `direct`-transportierte, thematisch unbeteiligte Sessions, die alphabetisch/zeitlich nach der betroffenen tmux-Zeile stehen; (b) `auto_resume_drained()` läuft gar nicht mehr → selbst sauber gedrainte Sessions (der eigentliche „gute" PROJ-33-Pfad) werden nicht automatisch fortgesetzt. Das ist ein stärkerer Kontextverlust als der Bug, den PROJ-74 eigentlich beheben sollte.
- **Warum das die eigene Design-Absicht verfehlt:** Tech Design (Abschnitt D) verspricht explizit „Ist der tmux-Daemon selbst nicht erreichbar oder der tmux-CLI-Call schlägt fehl ... gilt die Session weiterhin als 'nicht lebendig'" — das gilt nur für den engen `TransportError`-Fall, nicht für die tatsächliche Fehlerbreite eines Subprozess-Starts. Nur zwei Zeilen weiter oben (`raw = await self._repo.load_transcript(sid)`) existiert bereits das richtige Muster (`except Exception: logger.warning(...)`, best-effort, Schleife läuft weiter) — der neue Zweig hält sich nicht an dieses direkt benachbarte, etablierte Muster.
- **Priority:** Fix vor Deployment (High — auch wenn der Auslöser selten ist, ist der Blast Radius unverhältnismäßig groß: EINE fehlerhafte tmux-Zeile reißt JEDE Session mit, nicht nur sich selbst).

#### BUG-2 (Low, Test-/Spec-Lücke, kein Funktionsfehler): Zwei nicht-blockierende Lücken
- **a)** Der Dead-Pane-Fall „Session existiert noch, Pane aber tot" (`pane_dead=1`, unterscheidet sich vom getesteten „Session existiert gar nicht", `rc != 0`) hat keinen dedizierten Test — Logik korrekt laut Code-Lesung, aber unbewiesen.
- **b)** User Story 3 der Spec („Orphan-Entscheidung nachvollziehbar geloggt — welches Kriterium griff") wurde nicht umgesetzt; es gibt weiterhin nur den bestehenden Batch-Log am Ende (`Live-Index rehydriert: %d Session(s).`), keinen Log-Eintrag pro Zweig/Session. Keine AC-Checkbox verlangt das explizit, aber es ist unerledigtes Spec-Intent.
- **Priority:** Nice to have — kann zusammen mit BUG-1 behoben werden (z. B. der Log-Eintrag ergibt sich fast automatisch aus einem korrekten `except Exception`-Block für BUG-1).

### Summary
- **Acceptance Criteria:** 6/6 formal erfüllt (AC-3 mit dokumentierter Test-Lücke, s. o.)
- **Bugs Found:** 2 total (1 High, 1 Low)
- **Security:** Kein Auth-/Tenant-Bezug — nicht einschlägig für dieses Ticket, keine Befunde
- **Production Ready:** **NO**
- **Recommendation:** BUG-1 vor Deployment fixen — der neue tmux-Liveness-Zweig braucht dieselbe best-effort-`except Exception`-Absicherung wie der direkt benachbarte Transkript-Load-Block (Zeile darüber), damit ein einzelner Fehler nicht die gesamte Rehydrierung aller Sessions abreißt. Fix ist klein (ein `try/except` mehr, kein Architektur-Umbau) — passt in denselben `/abc-backoffice`-Zyklus zurück.

### Re-Test nach Fix (2026-07-18)

**BUG-1 gefixt** — `TmuxTransport.pane_alive_after_restart()` (`transport.py`) fängt jetzt
`except (TransportError, OSError)` statt nur `except TransportError` — deckt `FileNotFoundError`
(fehlendes Binary) und verwandte Subprozess-Fehler (`PermissionError` etc.) ab, konsistent mit dem
Docstring-Versprechen „jeder tmux-Fehler gilt als nicht lebendig". Reproduktion-vor-Fix: `except`
temporär auf `TransportError` zurückgesetzt → neuer Regressionstest
`test_rehydrate_tmux_binary_missing_does_not_abort_whole_batch` rot (`FileNotFoundError`
unbehandelt, `sessions in memory after rehydrate: []`); Fix zurückgeholt → grün, unbeteiligte
Zeile B wird jetzt korrekt mitrehydriert.

**BUG-2 gefixt:**
- **a)** neuer Test `test_pane_alive_after_restart_false_for_dead_pane_in_existing_session`
  (echte tmux-Session, oneshot-Prozess läuft ab, `remain-on-exit` hält die Session, Pane ist tot)
  belegt jetzt den zweiten Dead-Fall — war schon vor dem Fix grün (Logik war korrekt, nur unbewiesen).
- **b)** Logging pro Rehydrate-Entscheidung ergänzt (`manager.py`): je ein `logger.info(...)` für
  gedraint / tmux-Pane-lebendig / verwaist, mit Session-ID und Kriterium — User Story 3 jetzt erfüllt.

**Verifikation:** `test_proj74_tmux_liveness_rehydrate.py` 6/6 grün (2 neue Tests). Regressionslauf
proj14/27/33/63/64/66 + `test_proj4_decision_cards.py`: 170 passed (168 + 2 neue). Volle Suite:
**1187 passed, 2 failed** — dieselben vorbestehenden, themenfremden `test_proj50_codex_abc.py`-Fails
(unverändert gegenüber dem Erst-Lauf, kein neuer Fehler).

### Summary (Re-Test)
- **Acceptance Criteria:** 6/6 erfüllt, AC-3-Testlücke geschlossen
- **Bugs Found:** 0 offen (BUG-1 High, BUG-2 Low — beide gefixt und verifiziert)
- **Security:** nicht einschlägig, keine Befunde
- **Production Ready:** **YES**
- **Recommendation:** Deploy

## Deployment
**Production URL:** https://jupiter.auxevo.tech
**Deployed:** 2026-07-18 · Version: 0.27.34
**Host:** host-nativ (systemd `jupiter-backend`/`jupiter-frontend`) auf demselben Dev-VPS, GitHub-Webhook (`jupiter-webhook.service`) löst bei Push auf `main` `deploy.sh` aus (`git reset --hard origin/main`, `npm ci && npm run build`, `systemctl restart jupiter-backend jupiter-frontend`) — kein Dokploy/Docker in diesem Projekt.

**Branch-Hinweis:** `dev` war seit dem letzten PROJ-72-Redeploy/PROJ-73/PROJ-53 nicht mehr mit `main` synchronisiert (main lief bereits auf v0.27.33, `dev` noch auf v0.27.30). Statt `dev` blind zu mergen, wurden nur die beiden PROJ-74-Commits per Cherry-Pick auf `main` aufgesetzt (Konflikte in `docs/PRD.md`/`features/INDEX.md` manuell aufgelöst, main-Inhalt bleibt führend). `dev` selbst bleibt vorerst divergent — Empfehlung: bei Gelegenheit `dev` mit `main` synchronisieren (`git checkout dev && git merge --no-ff origin/main`), bevor das nächste Feature dort startet.
