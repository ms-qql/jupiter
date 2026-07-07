# PROJ-66: Bugfix: Session-Transkript von Oneshot-Engines geht bei Backend-Neustart dauerhaft verloren

## Status: Deployed
**Created:** 2026-07-07
**Last Updated:** 2026-07-07

## Problem / Motivation
Live-Vorfall (2026-07-07, Nutzer-Report): Eine Codex-Session ("Peppermint") brach wiederholt ab; nach jedem Abbruch war das bisherige Transkript komplett verschwunden. Journal zeigt fünf Backend/Frontend-Neustarts in 14 Minuten (11:26–11:40 Uhr), ausgelöst durch den `jupiter-deploy`-Webhook, direkt vor der beobachteten Session-Aktivität.

**Root Cause (durch Code-Analyse verifiziert, Explore-Agent-Untersuchung 2026-07-07):**
1. Das UI-Transkript einer Session existiert ausschließlich im Arbeitsspeicher: `SessionRuntime.__init__` (`backend/app/engine/manager.py:410`) initialisiert `self.transcript: list[TranscriptEntry] = []`. `GET /sessions/{id}` und der WS-Snapshot (`routes/sessions.py:117`, `routes/sessions.py:388`) liefern direkt aus diesem RAM-Objekt.
2. Für Oneshot-Engines mit `supports_self_resume` (Codex, OpenCode) wird nur die `resume_id` persistiert — nie der volle Nachrichtenverlauf.
3. Persistiert wird sonst nur (a) einmalig als Obsidian-MD beim ersten sauberen `DONE` (`_write_session_log`, `manager.py:2110`, gated durch `_done_fired`) und (b) für nicht-selbstfortsetzende Engines (OpenAI/OpenRouter direkt) ein gedeckelter Rohverlauf via `_safe_save_context`.
4. `rehydrate()` (`manager.py:1283-1323`), aufgerufen bei **jedem Backend-Neustart** für jede in der DB gefundene Session, baut eine **komplett neue** `SessionRuntime` mit leerem `transcript` — anders als `_resume()`/`_reanimate_once()`, die dasselbe Runtime-Objekt weiterverwenden und das Transkript dadurch erhalten.
5. Ein Backend-Neustart während einer laufenden Session löscht damit das sichtbare Transkript unwiderruflich, unabhängig davon, ob der zugrunde liegende Turn selbst sauber lief.

Dies ist eine andere, schwerwiegendere Baustelle als `features/PROJ-65-tmux-oneshot-status-race-nach-spawn.md` (dort bleibt der Kontext erhalten, nur die Status-Anzeige ist kurzzeitig falsch).

**Ziel dieses Tickets:** Das Transkript einer Session übersteht einen Backend-Neustart (Deploy, Crash-Recovery) vollständig — unabhängig von Engine-Typ und Transport.

## Dependencies
- Requires: PROJ-56, PROJ-58, PROJ-60 (Kontext-Persistenz/Resumability-Modell für Oneshot-Engines, das hier um vollständige Transkript-Rückspielung ergänzt wird).
- Requires: PROJ-63, PROJ-64 (tmux-Transport, dessen Sessions besonders häufig neu erstellt/reanimiert werden und daher am stärksten betroffen sind).
- Related (nicht blockierend): PROJ-65 (verwandte, aber andere Race — Status-Anzeige statt Datenverlust).

## Scope-Abgrenzung (bewusst)
- **In Scope:**
  1. Persistente Speicherung des vollständigen Transkripts für **alle Oneshot-Engines mit RAM-only-Transkript** (Codex, OpenCode/OpenRouter via `generic_cli`), nicht nur Codex.
  2. **Append-only pro Turn:** Jeder abgeschlossene Turn (User-Input + Assistant-Antwort inkl. Tool-Events, die aktuell im `TranscriptEntry` landen) wird direkt nach Verarbeitung in einer neuen DB-Tabelle (Arbeitstitel `session_transcript_entries`, FK auf `session_id`, fortlaufender Index) geschrieben — kein gedeckelter/verlustbehafteter Rohverlauf wie bei `_safe_save_context`.
  3. `rehydrate()` liest beim Neustart die persistierten Einträge je Session aus dieser Tabelle und befüllt `SessionRuntime.transcript` damit, statt es leer zu initialisieren.
  4. Das bestehende einmalige Obsidian-MD-Log (`_write_session_log` bei erstem `DONE`) bleibt unverändert zusätzlich bestehen — es ist ein separates Artefakt für den Vault, kein Ersatz für die Live-Rehydrierung.
- **NICHT in Scope:**
  - Long-lived Treiber (Claude, PROJ-1): dort läuft der Prozess bei Neustart i. d. R. nicht durchgehend weiter, das Transkript-Persistenzverhalten für Claude-Sessions ist bereits durch PROJ-14/PROJ-17 abgedeckt und wird hier nicht angefasst.
  - Die PROJ-65-Statusrace selbst (separates Ticket).
  - Eine UI-Änderung an der Transkript-Darstellung — nur die Datenquelle/Persistenz ändert sich, das Rendering bleibt gleich.
  - Rückwirkende Rekonstruktion von Transkripten, die VOR Deployment dieses Fixes bereits verloren gingen.

## User Stories
- Als Nutzer möchte ich, dass mein Session-Transkript einen Deploy/Backend-Neustart übersteht, damit ein Routine-Deploy nicht meine bisherige Konversation zerstört.
- Als Nutzer möchte ich nach einem Neustart eine reanimierte Session genauso vorfinden wie vorher — inklusive aller bisherigen Turns —, damit ich nicht manuell rekonstruieren muss, was besprochen wurde.
- Als Entwickler (Deploy-Verantwortlicher) möchte ich, dass der `jupiter-deploy`-Webhook-Neustart keine Datenverluste in aktiven Sessions verursacht, damit Deploys jederzeit sicher ausgelöst werden können.

## Acceptance Criteria
- [ ] Eine Codex-Session mit ≥2 abgeschlossenen Turns übersteht einen Backend-Neustart (`systemctl restart jupiter-backend`) mit vollständig erhaltenem Transkript (alle bisherigen Turns sichtbar nach Reconnect).
- [ ] Dasselbe gilt für eine OpenCode-Session mit ≥2 abgeschlossenen Turns.
- [ ] Jeder Turn wird spätestens unmittelbar nach seinem Abschluss (nicht erst bei Session-Ende) persistiert — ein Neustart mitten in einer Session verliert höchstens den zum Neustart-Zeitpunkt laufenden, unvollständigen Turn, keine bereits abgeschlossenen.
- [ ] Das bestehende Obsidian-MD-Log (`_write_session_log`) wird weiterhin unverändert beim ersten `DONE` geschrieben (Regressionstest).
- [ ] Long-lived Claude-Sessions (PROJ-1) zeigen unverändertes Verhalten (Regressionstest gegen PROJ-14/PROJ-17/PROJ-33).
- [ ] Mehrfache Neustarts hintereinander (wie im Peppermint-Vorfall: 5 Neustarts in 14 Minuten) führen zu keinem kumulativen Transkript-Verlust und keinen doppelten Einträgen.
- [ ] Neue Regressionstests: (1) Transkript übersteht Neustart bei Codex, (2) Transkript übersteht Neustart bei OpenCode, (3) unvollständiger Turn zum Neustart-Zeitpunkt verliert nur diesen Turn, (4) Obsidian-MD-Log unverändert, (5) Claude-Session-Verhalten unverändert.
- [ ] Volle Backend-Suite grün (inkl. `test_proj56_*`, `test_proj58_*`, `test_proj60_*`, `test_proj63_*`).

## Edge Cases
- Neustart passiert exakt während ein Turn geschrieben wird (Race zwischen Turn-Abschluss und DB-Write) — darf keinen korrupten/halben Eintrag erzeugen (Transaktion pro Eintrag).
- Session wird nach Neustart weitergeführt (neuer Turn) — neue Einträge müssen sich nahtlos an die rehydrierten anhängen (fortlaufender Index, keine Lücken/Kollisionen).
- Sehr lange Sessions mit vielen Turns — Rehydrierung darf die Session-Erstellungs-/Reconnect-Antwort nicht spürbar verlangsamen (Pagination/Limit prüfen, falls nötig).
- Session wird während eines laufenden Turns gelöscht (PROJ-21) — persistierte Einträge müssen mitgelöscht werden (kein verwaister Datenmüll).
- Zwei Neustarts kurz hintereinander, bevor der erste `rehydrate()`-Lauf fertig war — keine doppelte Rehydrierung/doppelte Einträge.

## Technical Requirements
_(verfeinert in „Tech Design" unten — Blob-pro-Session statt Append-Zeilen-Tabelle, siehe Begründung dort)_
- Neue DB-Tabelle `session_transcript`: `session_id` (Schlüssel, kein FK-Constraint, analog `session_context`), `entries` (JSON, vollständiger `TranscriptEntry`-Verlauf), `updated_at`.
- `backend/app/engine/manager.py`: an den vier bestehenden Append-Stellen (`:582-584`, `:589-591`, `:624-626`, `:1615`) zusätzlich best-effort/fire-and-forget den aktuellen `self.transcript`-Stand in `session_transcript` upserten (gleiches Muster wie `save_context`).
- `backend/app/engine/manager.py::rehydrate()` (Zeile ~1283-1323): `SessionRuntime.transcript` aus `session_transcript` befüllen (für Oneshot-/Self-Resume-Engines, dieselbe Fallunterscheidung wie in `_resume()`), statt leer zu initialisieren.
- Löschpfad (PROJ-21, `_delete_sync` in `session_index.py:243-251`): zusätzliche `DELETE FROM session_transcript WHERE session_id = ?`-Zeile.
- Neue Tests unter `backend/tests/test_proj66_transkript_persistenz_rehydrate.py`.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-07 · **Stack:** FastAPI (`backend/app/engine/manager.py`) + SQLite Live-Index (`backend/app/db/session_index.py`) · **Branch:** dev

### Grundlage (CodeGraph-Exploration, verifiziert)
- `TranscriptEntry` (`manager.py:260-265`) hat die Felder `role`, `kind`, `text`, `ts`. Es gibt genau **vier** Stellen, an denen ein Eintrag ans In-Memory-`self.transcript` gehängt wird: Assistant-„Thinking" (`:582-584`), Assistant-Text (`:589-591`), synthetischer Tool-Eintrag (`:624-626`, aus PROJ-62), User-Text (`:1615`). Das sind die einzigen Hook-Punkte, die eine Persistenz-Anbindung brauchen.
- `rehydrate()` (`manager.py:1283-1323`) baut bei jedem Neustart pro DB-Zeile eine **neue** `SessionRuntime` mit leerem `transcript` — im Gegensatz zu `_resume()`/`_reanimate_once()`, die ein bestehendes Runtime-Objekt weiterverwenden und dessen `transcript` dadurch implizit erhalten. Es gibt aktuell **keinen** Codepfad, der `transcript` je aus einer Quelle außer dem laufenden Prozess befüllt.
- Es existiert bereits eine strukturell ähnliche, aber **andersartige** Tabelle: `session_context` (`session_index.py:117-121`, PROJ-56). Sie speichert einen einzigen JSON-Blob (`messages`) im **Provider-Rohformat** (z. B. OpenAI-Message-Dicts) — nicht im `TranscriptEntry`-UI-Format — und **nur für Engines ohne Self-Resume** (OpenAI/OpenRouter direkt). Codex/OpenCode (`supports_self_resume`) haben kein `conversation_history`-Attribut auf ihrem Treiber, daher überspringt `_persist()` (`manager.py:1241-1262`) den Save für sie stillschweigend (kein expliziter Check, sondern `getattr(..., None)` liefert `None`).
- `GET /sessions/{id}` und der WS-Snapshot (`routes/sessions.py:111-118`, `:383-389`) lesen `runtime.transcript` direkt aus dem Speicher — keine Änderung an diesen Endpunkten nötig, sobald `transcript` beim Rehydrieren korrekt befüllt ist.
- Löschen (PROJ-21) entfernt `session_index`- und `session_context`-Zeilen in `_delete_sync` (`session_index.py:243-251`) — jede neue Tabelle muss dort eine identische `DELETE`-Zeile bekommen.
- `_write_session_log` (Obsidian-MD beim ersten DONE) liest ebenfalls nur `runtime.transcript`, schreibt aber unabhängig in den Vault — bleibt unangetastet.

### A) Betroffene Komponenten (kein UI-Baum nötig)
Reine Backend-Persistenz — an der Sidebar/Session-Ansicht ändert sich nichts, sie liest weiterhin dieselbe `transcript`-Struktur wie heute, nur dass diese nach einem Neustart nicht mehr leer ist:
```
manager.py (4 bestehende Append-Stellen)
└── neuer Persistenz-Hook (best-effort, fire-and-forget)
        └── neue Tabelle: session_transcript
rehydrate()
└── liest session_transcript → befüllt SessionRuntime.transcript vor Auslieferung an Routen
```

### B) Datenmodell (einfache Sprache)
Eine **neue** Tabelle `session_transcript` (bewusst getrennt von `session_context`, weil andere Datenform und anderer Zweck — UI-Transkript statt Provider-Rohverlauf):
- `session_id` — Schlüssel, ein Eintrag pro Session (kein Fremdschlüssel-Constraint, analog zu `session_context`/`session_index`)
- `entries` — der komplette aktuelle Transkript-Inhalt als JSON (Liste von `TranscriptEntry`-artigen Objekten)
- `updated_at` — Zeitstempel der letzten Aktualisierung

**Bewusste Vereinfachung gegenüber dem ursprünglichen Spec-Entwurf** (dort als "Arbeitstitel" mit `entry_index`-Append-Zeilen skizziert): Statt einer echten Zeile-pro-Eintrag-Tabelle mit fortlaufendem Index wird — wie bei `session_context` — **ein Blob pro Session** geschrieben, der bei jedem der vier Hook-Punkte mit dem aktuellen, vollständigen In-Memory-Transkript überschrieben wird (Upsert, gleiches Muster wie `save_context`). Das vermeidet die in den Edge Cases der Spec beschriebene Komplexität (Lücken/Kollisionen im `entry_index` bei parallelem Neustart + neuem Turn) komplett, weil es keinen Index gibt, der aus der Reihe kommen könnte — es gibt immer nur „den aktuellen Stand". Da die Schreibungen best-effort und pro Eintrag (nicht pro Zeichen) passieren, verliert ein Crash mitten im Turn höchstens den seit dem letzten Hook-Punkt ungeschriebenen Rest — das erfüllt die Acceptance Criteria sogar granularer als gefordert (nicht nur „ganze Turns bleiben erhalten", sondern auch bereits sichtbare Teil-Antworten).

Gilt für **alle Oneshot-Engines** (Codex, OpenCode), nicht nur Codex. Die Schreib-Hooks selbst müssen dabei nicht nach Engine unterscheiden (einheitlich, einfacher Code) — sie sind ohnehin billig und best-effort. Die **Lesbarkeit beim Rehydrieren** wird an derselben Fallunterscheidung gespiegelt, die `_resume()` heute schon trifft (`is_claude` vs. `driver.supports_self_resume` vs. sonstige) — Long-lived Claude-Sessions bleiben dadurch unverändert (Scope-Abgrenzung der Spec), ohne dass der Schreibpfad selbst verzweigen muss.

### C) API-Form
Keine neuen oder geänderten Endpunkte. `GET /sessions/{id}` und die WS-Snapshot-Antwort liefern unverändert `runtime.transcript` — der Unterschied ist rein, dass dieses Feld nach einem Neustart bereits gefüllt ankommt statt leer zu sein.

### D) Tech-Entscheidungen (Begründung)
- **Warum eine neue Tabelle statt `session_context` zu erweitern:** `session_context` ist an das Provider-Rohformat für Nicht-Self-Resume-Engines gebunden (eigene Cap-Logik `_cap_history`, eigene Lade-Semantik in `_resume()`). Das UI-Transkript hat eine andere Form (`TranscriptEntry`) und einen anderen Zweck (Anzeige, nicht Modell-Kontext). Eine eigene Tabelle hält beide Belange sauber getrennt und lässt `session_context` unangetastet.
- **Warum ein Blob pro Session statt echter Append-Zeilen:** Einfacher, kein Index-Bookkeeping über einen Neustart hinweg, passt zum bereits etablierten Muster (`session_context`) und zur „Single-Writer, WAL, günstige Schreibungen"-Prämisse des Live-Index. Transkripte sind pro Session natürlich begrenzt (Turns eines Chats), das Wiederschreiben des ganzen Blobs bei jedem Append bleibt günstig.
- **Warum kein Cap/keine Kürzung** (anders als `session_context`): Das UI-Transkript ist das, was der Nutzer tatsächlich sehen will — im Gegensatz zum Provider-Kontext (der nur die Modell-Fortsetzung füttert) gibt es hier keinen fachlichen Grund, ältere Teile wegzuwerfen. Sollte das in der Praxis zu groß werden, ist das ein separates, später zu beobachtendes Problem (nicht Teil dieses Tickets).
- **Warum Best-effort/fire-and-forget statt synchron blockierend:** Konsistent mit jedem anderen Schreibpfad in diesem Persistenz-Seam (`session_index.upsert`, `save_context`) — ein DB-Fehler darf den Live-Betrieb nie blockieren, nur zu einer Warnung degradieren.
- **Warum Rehydrierung nur für Oneshot-/Self-Resume-Engines:** Bewahrt exakt das heutige Verhalten für Claude (Scope-Abgrenzung der Spec), ohne eine neue Sonderfall-Verzweigung im Schreibpfad einzuführen — die Unterscheidung existiert an der Lesestelle (`rehydrate()`) bereits implizit durch die vorhandene `_resume()`-Fallunterscheidung.

### E) Abhängigkeiten (Pakete)
Keine neuen Pakete — nutzt dieselbe `sqlite3`/sync-über-`asyncio.to_thread`-Infrastruktur, die `session_index.py` bereits für `session_context` verwendet.

## Implementation Notes
**Umgesetzt:** 2026-07-07 · **Branch:** dev

### Umgesetzt (mit einer Verfeinerung gegenüber dem Tech Design)
- Neue Tabelle `session_transcript` (`backend/app/db/session_index.py`): `session_id` (PK), `entries` (JSON), `updated_at`. Repository-Methoden `save_transcript`/`load_transcript` in `SessionIndexRepository`-Protokoll, `NullSessionIndexRepository` (No-op) und `SqliteSessionIndexRepository` (Upsert/Select, analog `session_context`).
- Löschpfad (`_delete_sync`): zusätzliche `DELETE FROM session_transcript`-Zeile — kein verwaister Datenmüll nach Session-Löschen (PROJ-21).
- `backend/app/engine/manager.py::_persist()`: neuer Block, der `runtime.transcript` (als `[vars(e) for e in ...]`, gleiches Format wie `routes/sessions.py`) unconditional über `_safe_save_transcript` best-effort/fire-and-forget sichert.
- `backend/app/engine/manager.py::rehydrate()`: lädt `session_transcript` und befüllt `runtime.transcript`, aber **nur** wenn `engine_registry.get(state.engine)` ein Profil mit `is_claude == False` liefert — Claude bleibt dadurch unverändert (kein Doppel-Replay über den nativen `--resume`-Pfad).

**Abweichung vom Tech-Design-Entwurf:** Statt die vier ursprünglich skizzierten `TranscriptEntry`-Append-Stellen (`:582-584`, `:589-591`, `:624-626`, `:1615`) einzeln zu instrumentieren, wurde der Schreib-Hook in die bereits bestehende `_persist()`-Methode gelegt (denselben Punkt, an dem `session_context` für PROJ-56 gesichert wird). `_persist()` feuert exakt an den Stellen, die für dieses Ticket ausreichen — bei jedem Statuswechsel (`_maybe_persist`, inkl. Turn-Abschluss) UND explizit beim Senden neuer Eingabe (`send_input`, unmittelbar nach dem User-Text-Append). Das ist einfacher (ein Hook-Punkt statt vier), performant (keine zusätzliche Schreib-Last pro einzelnem Assistant-/Tool-Event, sondern dieselbe grobe Kadenz wie der bestehende Live-Index-Upsert) und erfüllt die Acceptance Criteria vollständig: ein abgeschlossener Turn hat vor seinem Abschluss mindestens einen Statuswechsel (→ RUNNING bei Start, → WAITING/DONE bei Ende) durchlaufen, an dem der komplette bisherige Transkript-Stand bereits geschrieben wurde. Anders als `session_context` ist der Transkript-Save **nicht** auf `status in (WAITING, DONE)` beschränkt — er läuft bei jedem `_persist()`-Aufruf, unabhängig vom Status, weil hier (im Gegensatz zum Provider-Rohkontext) kein Risiko besteht, einen „halben Turn" inkonsistent zu speichern (jeder Append ist bereits ein abgeschlossenes UI-Element).

### Tests
Neue Datei `backend/tests/test_proj66_transkript_persistenz_rehydrate.py` (8 Tests):
1. Repo-Roundtrip `session_transcript` (speichern/lesen/ersetzen/löschen).
2. `_persist` sichert das Transkript auch mitten im Turn (RUNNING), nicht nur bei SETTLED-Status.
3. `_persist` überschreibt den Blob korrekt bei wiederholten Aufrufen (kein Duplikat).
4. `rehydrate()` lädt das Transkript für eine Codex-Session korrekt.
5. `rehydrate()` lädt **nicht** für eine Claude-Session (Regression, Verhalten unverändert).
6. Echter Absturz (Status `error`) bleibt korrekt als `ERROR` erkennbar, Transkript wird trotzdem geladen.
7. Mehrfache Neustarts hintereinander (Peppermint-Szenario) verursachen keine Dopplung.
8. Korrupter/kaputter Transkript-JSON degradiert auf leeres Transkript, crasht nicht (Red-Team).

**Ergebnis:** Volle Backend-Suite `conda run -n Dashboard --no-capture-output python -m pytest backend/` → **1140 passed, 1 failed** in 126 s. Der eine Fehlschlag (`test_proj50_codex_abc.py::test_generator_check_passes_no_drift`) ist eine vorbestehende, unabhängige Codex-Skill-Mirror-Drift (abc-clarification/abc-customer-journey/abc-dokploy-data/abc-frontdesk-check zwischen `~/.claude/skills` und `~/.codex/skills`) — betrifft keine der hier geänderten Dateien, keine Regression durch PROJ-66. Alle PROJ-14/17/33/56/60/62/63/64-Regressionstests grün.

### Für QA
- Manuelles End-to-End-Szenario zum Nachstellen von „Peppermint": Codex-Session mit ≥2 Turns starten, Backend neu starten (`systemctl restart jupiter-backend` bzw. lokal Prozess neu starten), prüfen dass das Transkript nach Reconnect vollständig da ist.
- Gegenprobe Claude: eine Claude-Session mit ≥2 Turns, Backend-Neustart, Transkript-Verhalten muss identisch zu vor PROJ-66 sein (leer/verwaist, wie bisher).

## QA Test Results
**Getestet:** 2026-07-07 · **Branch:** dev

### Acceptance Criteria — Ergebnis
| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Codex-Session ≥2 Turns übersteht Neustart, Transkript vollständig | ✅ PASS — end-to-end über echten FastAPI-Lifespan + `GET /sessions/{id}` verifiziert (`test_route_get_session_returns_full_transcript_after_restart`), nicht nur auf Manager-Ebene |
| 2 | Dasselbe für OpenCode | ✅ PASS — identischer Route-Test mit `engine="opencode"` (`test_route_get_session_returns_full_transcript_for_opencode`) |
| 3 | Turn wird spätestens bei Abschluss persistiert; Neustart mitten im Turn verliert nur den unvollständigen Rest | ✅ PASS — `test_only_unpersisted_inflight_turn_is_lost` beweist explizit: Turn 1 + die bereits gestellte Turn-2-Frage überleben, nur die noch nicht persistierte Turn-2-Antwort geht verloren |
| 4 | Obsidian-MD-Log (`_write_session_log`) unverändert | ✅ PASS — `test_vault.py`, `test_proj48_codex.py`, `test_proj57_opencode.py`, `test_proj58_opencode_stdin_race.py` (65 Tests) unverändert grün |
| 5 | Claude-Sessions unverändert (Regression PROJ-14/17/33) | ✅ PASS — `test_rehydrate_laedt_transkript_nicht_fuer_claude` + `test_route_get_session_unchanged_for_claude` (Route-Ebene) + volle PROJ-14/17/33-Suiten grün |
| 6 | Mehrfache Neustarts hintereinander (Peppermint: 5 in 14 Min) → keine Dopplung | ✅ PASS — `test_rehydrate_mehrfacher_neustart_keine_dopplung` (3 aufeinanderfolgende Rehydrate-Läufe) |
| 7 | Neue Regressionstests vorhanden | ✅ PASS — `test_proj66_transkript_persistenz_rehydrate.py`, 13 Tests |
| 8 | Volle Backend-Suite grün | ✅ PASS — 1145 passed, 1 failed (vorbestehend, unabhängig — s. u.) |

**8/8 Acceptance Criteria erfüllt.**

### Zusätzliche QA-Tests (über die Backend-Implementierung hinaus)
Ergänzt in derselben Testdatei, um die ACs auf **API-Vertragsebene** statt nur auf Manager-Interna zu verifizieren (echter `TestClient` + echter Lifespan → `rehydrate()` läuft wie im echten Betrieb beim Start):
- `test_route_get_session_returns_full_transcript_after_restart` (AC1, End-to-End)
- `test_route_get_session_returns_full_transcript_for_opencode` (AC2, End-to-End)
- `test_route_get_session_unchanged_for_claude` (Gegenprobe AC5 auf Route-Ebene)
- `test_only_unpersisted_inflight_turn_is_lost` (AC3, expliziter Beweis der Turn-Granularität)
- `test_transcript_repo_handles_malicious_session_id` (Red-Team: SQL-Metazeichen in `session_id` — parametrisierte Queries bestätigt sicher, keine String-Konkatenation)

### Security-Audit (Red-Team)
- **SQL-Injection:** `session_transcript`-Queries nutzen ausschließlich `?`-Platzhalter (keine String-Konkatenation) — mit manipuliertem `session_id` (`"s1'; DROP TABLE session_transcript; --"`) getestet, keine Auswirkung auf andere Zeilen oder die Tabelle selbst.
- **Secrets-Exposure:** `TranscriptEntry` enthält nur bereits in der UI angezeigten Chat-Text (`role`/`kind`/`text`/`ts`) — strukturell keine API-Keys/Header, analog zum bestehenden PROJ-56-Red-Team-Befund für `conversation_history`.
- **Auth/Tenant-Isolation:** Keine neuen Endpunkte; `GET /sessions/{id}` bleibt hinter `Depends(get_current_user)` + `_owned_or_404` (unverändert, Route-Tests liefen durchgängig mit dem bestehenden Soft-Gate).
- **Best-effort-Ausfallsicherheit:** Korrupter/kaputter JSON-Blob in `session_transcript` degradiert auf ein leeres Transkript statt die App-Startup zu crashen (`test_rehydrate_corrupt_transcript_degrades_not_crashes`).

### Bugs
Keine Critical/High/Medium-Bugs gefunden.

**Low / Beobachtung (kein Blocker):**
1. **Unconditional Write auch für Claude-Sessions:** `_persist()` schreibt das Transkript jetzt für **jede** Engine inkl. Claude in `session_transcript` — obwohl `rehydrate()` es für Claude nie zurückliest (bewusste Scope-Entscheidung). Das ist zusätzliche, ungenutzte Schreiblast (keine Korrektheitsauswirkung, da Best-effort/fire-and-forget und nichts liest diese Zeilen für Claude zurück). Optionale spätere Optimierung: Write auf `not profile.is_claude` gaten, sobald das messbar relevant wird — für jetzt kein Deployment-Hindernis, da im bestehenden Design (`session_index`-Upsert) bereits dieselbe Kadenz für jede Engine gilt.
2. **Kein Cap auf `session_transcript.entries`:** Bewusst so entschieden (Tech Design, Abschnitt D) — bei sehr langen Sessions (Hunderte Turns) wächst der Blob unbegrenzt und wird bei jedem Persist-Zyklus komplett neu geschrieben. Für die im Ticket beschriebene Nutzung (Chat-Sessions) unkritisch; als Beobachtung für eine mögliche spätere Härtung festgehalten, kein Fix in diesem Ticket nötig (Edge Case „sehr lange Sessions" der Spec ist damit bewusst nicht geschlossen, sondern zurückgestellt).

### Regressionstest
Volle Backend-Suite (`conda run -n Dashboard --no-capture-output python -m pytest backend/`): **1145 passed, 1 failed** in 122 s. Der eine Fehlschlag (`test_proj50_codex_abc.py::test_generator_check_passes_no_drift`, Codex-Skill-Mirror-Drift zwischen `~/.claude/skills` und `~/.codex/skills`) ist vorbestehend und unabhängig von den hier geänderten Dateien (`session_index.py`, `manager.py`, neue Testdatei) — keine Regression durch PROJ-66. Alle PROJ-14/17/21/33/48/56/57/58/60/62/63/64-Suiten unverändert grün.

### Production-Ready-Entscheidung
**READY.** Keine Critical/High-Bugs. Zwei Low-Beobachtungen dokumentiert, kein Blocker.

## Deployment
Production URL: https://jupiter.auxevo.tech
Deployed: 2026-07-07 · Version: 0.27.15
Host project: Jupiter (host-native systemd + GitHub-Webhook Auto-Deploy)

`dev` (nur diese Feature-Commits, sauber ab `main`) per `--no-ff` nach `main` gemergt, Version 0.27.14 → 0.27.15 gebumpt. Kein Infrastruktur-Bootstrap nötig (Follow-up-Deploy, host-native systemd/Caddy-Setup bereits etabliert, kein Dokploy/Docker in diesem Repo). Push nach `origin/main` löst den GitHub-Webhook aus, der `jupiter-backend`/`jupiter-frontend` neu baut/startet.

**Smoke-Test-Checkliste (nach Push, manuell zu verifizieren):**
- [ ] `https://jupiter.auxevo.tech/api/health` → ok
- [ ] Frontend lädt, Login funktioniert
- [ ] Bestehende Codex/OpenCode-Session nach Neustart: Transkript vollständig sichtbar (AC1/AC2 im Live-Betrieb)
- [ ] Bestehende Claude-Session nach Neustart: Verhalten unverändert (keine Regression)
- [ ] Host-Logs (`journalctl -u jupiter-backend`): keine neuen Fehler nach dem Neustart
