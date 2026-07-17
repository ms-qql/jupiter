# PROJ-74: Bugfix: Backend-Neustart orphaniert lebende tmux-Sessions unnötig (rehydrate() ignoriert echte Prozess-Liveness)

## Status: Architected
**Created:** 2026-07-17
**Last Updated:** 2026-07-17

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
- [ ] Reproduktion vor Fix: Eine Session mit tmux-Transport wird gestartet, das Backend wird **hart** beendet (kein `drain()`), das Backend startet neu → Session landet aktuell in `ERROR`/orphaned, obwohl der tmux-Pane-Prozess nachweislich noch läuft. Dieser Fall muss als fehlschlagender Test reproduzierbar sein, bevor der Fix beginnt.
- [ ] Nach dem Fix: Im identischen Szenario (harter Backend-Stopp, laufender tmux-Pane, kein `drained_at`) erkennt `rehydrate()` die echte Prozess-Liveness und versetzt die Session **nicht** in `ERROR` — sie bleibt reconnect-/reanimierbar.
- [ ] Gegenprobe: Ist der tmux-Pane beim Neustart tatsächlich tot (Prozess existiert nicht mehr), markiert `rehydrate()` die Session weiterhin korrekt als `ERROR`/orphaned — keine falschen Positiven in die andere Richtung.
- [ ] Geordnetes `drain()` (`drained_at` gesetzt) verhält sich unverändert wie bisher (kein Regressions-Bruch am bestehenden Happy-Path aus PROJ-33/PROJ-66).
- [ ] Engines ohne tmux-Transport (`direct`) zeigen unverändertes Verhalten — dieses Ticket ändert deren Orphan-Logik nicht.
- [ ] Bestehende Resume-/Rehydrate-/Liveness-Testsuiten (proj27, proj33, proj63, proj64, proj66) bleiben grün.

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

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
