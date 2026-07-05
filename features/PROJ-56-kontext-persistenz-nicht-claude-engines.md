# PROJ-56: Kontext-Persistenz & Resume für Nicht-Claude-Engines (Codex, GLM/OpenRouter)

## Status: Approved
**Created:** 2026-07-04
**Last Updated:** 2026-07-05

## Problem / Motivation
Claude-Sessions behalten ihren Kontext zuverlässig, weil der `claude`-Prozess langlebig ist und `claude --resume` echten serverseitigen Konversationskontext lädt. **Codex** (generic-CLI, oneshot) und **GLM 5.2** (Modell `z-ai/glm-5.2` der Engine `openrouter`, HTTP-`OpenAIDriver`) verlieren dagegen ihren Kontext: Die Sessions „brechen ab" und der Agent vergisst, was vorher besprochen wurde.

**Root-Cause-Analyse (Code-verifiziert):**
- **GLM 5.2** hält die komplette History nur im RAM (`openai_driver.py:56` `self._messages`). Es gibt keinerlei Resume-/Persistenz-Mechanismus (`openai_driver.py:10-13`). Sobald das Treiber-Objekt neu gebaut wird, ist der Chat leer.
- **Codex** kann sich per `thread_id` selbst fortsetzen — aber nur **innerhalb eines Backend-Prozesses**. Die `resume_id` liegt nur im RAM (`generic_cli_driver.py:80`), wird nirgends persistiert, und der Manager-`_resume`-Pfad nutzt fälschlich das **Nicht-Resume-argv** (`manager.py:1573`, `resume=is_claude=False`) → startet einen brandneuen, leeren Codex-Thread.
- **Gemeinsamer Kern:** Für Nicht-Claude-Engines wird beim Treiber-Neubau **kein Kontext wiederhergestellt** — weder Codex' `thread_id` noch GLMs Nachrichten werden persistiert oder replayed.

**Auslöser des Kontextverlusts (alle drei müssen abgedeckt werden):**
1. **Backend-Restart** (`rehydrate` → `DeadDriver` → `_resume`, `manager.py:1239/1302`) — z.B. jeder Push auf `main` → `deploy.sh` → `systemctl restart`.
2. **Auto-/Manuelle Reanimierung** eines als „hängend" markierten RUNNING-Turns (`_reanimate_once` → `stop()` + `_resume`, `manager.py:1634-1642`).
3. **Jeder `_resume`-Pfad** bei totem Treiber ohne self-resume (`send_input`, `manager.py:1536`) — trifft GLM sofort.

## Dependencies
- Requires: PROJ-48 (Engine — OpenAI Codex CLI) — der generic-CLI-Treiber + Codex-Adapter.
- Requires: PROJ-18 (Weitere Engines + iFrame/Launch) — OpenRouter/OpenAI-HTTP-Treiber, unter dem GLM 5.2 läuft.
- Requires: PROJ-14 (PROJ-1-Härtung: Limit + Persistenz) — der persistierte Session-Snapshot (`_row()`), der um Resume-State erweitert wird.
- Verwandt: PROJ-33 (Session-Lifecycle-Härtung), PROJ-17 (Recovery über den Vault), PROJ-45 (Reanimierungs-Budget), PROJ-49 (WebSocket-Event-Replay).

## User Stories
- Als **Nutzer einer Codex-Session** möchte ich, dass der Agent nach einem Backend-Neustart (z.B. nach einem Deploy) weiterweiß, was wir vorher besprochen haben, damit ich nicht den ganzen Kontext neu erklären muss.
- Als **Nutzer einer GLM-5.2-Session** möchte ich, dass ein fälschlich als „hängend" reanimierter Turn die bisherige Konversation behält, statt in einem leeren Chat weiterzumachen.
- Als **Nutzer jeder Nicht-Claude-Engine** möchte ich, dass eine Session, die abbricht und wieder aufgenommen wird, denselben Kontext-Faden fortführt wie bei Claude — Engine-Wahl darf keinen Kontextverlust bedeuten.
- Als **Betreiber** möchte ich, dass ein Deploy laufende Codex-/GLM-Sessions nicht inhaltlich zerstört, damit ich ohne Angst vor Datenverlust deployen kann.
- Als **Nutzer** möchte ich im Cockpit erkennen, ob eine Session nach einem Abbruch mit vollem Kontext oder als Neustart fortgesetzt wurde, damit ich Überraschungen einordnen kann.

## Acceptance Criteria

### Codex (generic-CLI, self-resume)
- [ ] Die von der Engine gelieferte `resume_id`/`thread_id` wird **persistiert** (im Session-Snapshot `_row()` bzw. der Session-Persistenz), nicht nur im RAM gehalten.
- [ ] Nach einem **Backend-Restart** wird eine Codex-Session mit der persistierten `resume_id` über das **`resume_argv_template`** fortgesetzt — der Agent hat den vorherigen Kontext.
- [ ] Der Manager-`_resume`-Pfad verwendet für Codex das **Resume-argv** (nicht mehr pauschal `resume=is_claude=False`), sofern eine `resume_id` vorliegt.
- [ ] Wird ein **RUNNING**-Codex-Turn reanimiert, wird der Thread über `resume_id` fortgesetzt statt neu gestartet.
- [ ] Fehlt eine `resume_id` (echter Erststart / Engine hat noch keine geliefert), verhält sich das System wie bisher sauber (kein Crash, klarer Erststart).

### GLM 5.2 / OpenRouter (HTTP-OpenAIDriver)
- [ ] Der **Konversationsverlauf** (`messages`) einer OpenAI/OpenRouter-Session wird persistiert (Session-Persistenz/Vault), sodass er einen Treiber-Neubau übersteht.
- [ ] Beim `_resume`/Neuaufbau eines `OpenAIDriver` wird die persistierte History in den frischen Treiber **replayed**, sodass der nächste Turn den vollen Kontext mitschickt.
- [ ] Nach **Backend-Restart** führt eine GLM-Session den bisherigen Gesprächsfaden fort (Beweis: der Agent referenziert korrekt eine Aussage aus einem Turn vor dem Restart).
- [ ] Eine **fälschlich reanimierte** GLM-Session (Auslöser 2) verliert die Konversation nicht.

### Übergreifend
- [ ] Die drei Auslöser (Restart · Reanimierung · `_resume`) führen bei **Codex und GLM** nachweislich **nicht** mehr zu Kontextverlust (je ein reproduzierbarer Testfall).
- [ ] **Claude bleibt unverändert** — kein Regress im bestehenden langlebigen-Prozess-Pfad (`claude --resume` nur bei totem Prozess).
- [ ] Der Token-Mehrverbrauch durch History-Replay (GLM) bzw. Thread-Resume (Codex) ist **erwartungskonform** und wird nicht als Overspend-Bug fehlinterpretiert (analog zum Claude-`--resume`-Fixkostenblock, siehe PROJ-45).
- [ ] Persistierte Resume-Artefakte (thread_id, messages) enthalten **keine Secrets** und respektieren die bestehende Pfad-Sandbox der Session-Persistenz.
- [ ] Das Verhalten ist **konfigurierbar bzw. transparent**: erkennbar (Log/Statusfeld), ob eine Session mit Kontext-Resume oder als kontextloser Neustart fortgesetzt wurde.

## Edge Cases
- **Codex liefert nie ein `thread.started`/`resume_token`-Event** (CLI-Version ohne thread-Support): Was ist das erwartete Fallback-Verhalten — sauberer kontextloser Neustart mit sichtbarer Warnung, kein stiller „so tun als ob"?
- **GLM-History wird sehr groß** (viele Turns): Replay der vollen `messages` kann Token-/Kontextfenster sprengen. Braucht es ein Trimming/Kondensieren (verweist auf PROJ-5 Handover / PROJ-19 RAG) oder reicht „voll bis Limit, dann Fehler"?
- **`resume_id` persistiert, aber die CLI-seitige Session ist serverseitig abgelaufen/gelöscht** (Codex-Thread nicht mehr auffindbar): sauberer Fallback auf Neustart statt Hard-Error.
- **Backend-Restart mitten in einem laufenden Turn** (Prozess/HTTP-Call bricht ab): Der zuletzt begonnene, unvollständige Turn darf den persistierten Verlauf nicht korrumpieren (kein halber Assistant-Turn in `messages`).
- **Parallele Reanimierung + eintreffender neuer User-Input**: Race — es darf nicht zu doppeltem Resume oder verworfenem Kontext kommen.
- **Wechsel des Modells innerhalb derselben Engine** (z.B. GLM 5.2 → anderes OpenRouter-Modell): Wird die bestehende History übernommen oder als neuer Faden behandelt? Definieren.
- **Vault-Transcript (`_write_session_log`) vs. Resume-`messages`**: sicherstellen, dass die neue Resume-Persistenz nicht mit dem bestehenden Historie-Log kollidiert oder ihn dupliziert.
- **Migration bestehender laufender Sessions**: Sessions, die vor diesem Feature gestartet wurden, haben keine persistierte `resume_id`/History — dürfen nicht crashen, sondern degradieren sauber.

## Technical Requirements (optional)
- **Betroffene Stellen (Ausgangspunkt, keine Vorgabe der Lösung):**
  - `backend/app/engine/generic_cli_driver.py` — `_resume_id` (RAM-only, `:80`), resume-argv-Bau (`:109`, `:148-168`), resume_token-Abfang (`:217-221`).
  - `backend/app/engine/openai_driver.py` — `_messages` (`:56`), append (`:110`/`:142`), fehlendes Resume (`:10-13`).
  - `backend/app/engine/manager.py` — `_resume` (`:1550-1591`, insb. `resume=is_claude` `:1573`), `send_input` (`:1536`), `_reanimate_once` (`:1634-1642`), Snapshot `_row()` (`:1163-1191`), rehydrate (`:1239`/`:1302`).
- **Persistenz:** Resume-State (Codex `thread_id`; OpenAI/OpenRouter `messages`) muss den bestehenden Snapshot-/Persistenz-Mechanismus aus PROJ-14 nutzen (kein neuer Store, wenn vermeidbar) und Backend-Restarts überleben.
- **Kein Claude-Regress:** Der langlebige-Prozess-Pfad bleibt der Default; `--resume` weiterhin nur bei totem Prozess.
- **Security:** Persistierte Artefakte ohne Secrets; Pfad-Sandbox der Session-Persistenz respektieren.
- **Beobachtbarkeit:** Log/Statusfeld „Resume mit Kontext" vs. „kontextloser Neustart" für die drei Auslöser.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-04 · **Stack:** Backend-only (FastAPI + Engine-Layer + Postgres `session_index`-Store) · Frontend nur read-only Statusfeld · **Branch:** dev

### Kernidee in einem Satz
Wir geben jeder Engine eine **eigene Strategie, wie sie ihren Gesprächskontext wiederherstellt**, und **persistieren den dafür nötigen Zustand** dauerhaft — damit Codex und GLM nach Abbruch/Restart/Reanimierung genauso weiterreden wie Claude heute schon.

### Warum es heute bricht (verdichtet)
- **Claude** hat serverseitigen Kontext, adressierbar über die Session-ID → billiges Resume. Funktioniert.
- **Codex** hat serverseitigen Kontext (`thread_id`), aber die ID lebt nur im Arbeitsspeicher und der Wiederaufnahme-Pfad startet fälschlich einen neuen, leeren Thread.
- **GLM/OpenRouter** hat **keinen** serverseitigen Kontext — der Verlauf existiert nur im Arbeitsspeicher des Treibers. Bei jedem Treiber-Neubau ist er weg.

### A) Restaurations-Fluss (statt UI-Baum — das ist Backend-Logik)
```
SessionManager._resume(runtime)         ← wird engine-bewusst
├── Claude            → nativer --resume über Session-ID        [unverändert]
├── Codex/generic_cli → Neustart über resume_argv + persistierte resume_id
│                        └── Fallback: keine ID → frischer Start, Status "kontextlos (Grund)"
└── GLM/openai        → neuer Treiber → persistierten Verlauf zurückspielen (gedeckelt)
                         └── Fallback: kein Verlauf → frischer Start

Zustand SICHERN (in den PROJ-14-Store)
├── Codex: sobald das "thread.started"/resume_token-Event kommt → resume_id speichern
├── GLM:   nach JEDEM vollständig abgeschlossenen Turn → Verlauf speichern
└── Restart/rehydrate → gespeicherten Zustand in den frisch gebauten Treiber laden

BEOBACHTBARKEIT
└── Session bekommt ein Feld "context_status": "mit Kontext" | "kontextlos (Grund)"
```

Drei bestehende Auslöser bleiben gleich (Restart `rehydrate`/`auto_resume_drained`, Reanimierung `_reanimate_once`, `send_input`-`_resume`) — sie laufen künftig alle durch denselben engine-bewussten Restaurations-Fluss.

### B) Datenmodell (Klartext, kein SQL)
Der bestehende **`session_index`-Store (PROJ-14, Postgres)** wird erweitert — konsequent mit dem dort schon genutzten leichten „Spalte-nachziehen"-Migrationsmuster:

1. **Codex-Wiederaufnahme-ID** — eine kleine Text-Spalte auf `session_index` (z. B. `resume_id`). Klein, ändert sich selten (einmal pro Thread), passt in den bestehenden Metadaten-Upsert.
2. **GLM-Gesprächsverlauf** — als **eigener Store `session_context`** (Schlüssel = `session_id`), NICHT als Spalte auf `session_index`:
   - Enthält den geordneten Verlauf (Rolle + Inhalt je Turn) im Treiber-Format, plus „aktualisiert am".
   - Eigene Tabelle, weil der Verlauf groß werden kann und nur bei **Turn-Abschluss** geschrieben wird — so bleibt der heiße Metadaten-Upsert von `session_index` (feuert bei jedem Zustandswechsel) leicht.
3. **`context_status`** — kleines Textfeld auf `session_index` (mit Kontext / kontextlos + Grund), rein informativ.

Kein MinIO (alles Text). Keine RLS-Sonderfälle über den bestehenden Jupiter-Rahmen hinaus (Jupiter ist Single-Owner; siehe Stack-Overrides — kein Mandanten-RLS im MVP).

### C) API-Form (Endpunkte)
- **Keine neuen öffentlichen REST-Endpunkte.** Der gesamte Fix liegt im Engine-Manager + Treibern + Persistenz.
- **Eine Erweiterung:** die bestehende Session-Detail/-Listen-Antwort bekommt das **read-only Feld `context_status`**, damit das Cockpit „mit Kontext / kontextlos fortgesetzt" anzeigen kann.
- Reanimierung/Resume bleiben interne Vorgänge (keine neue Steuer-API).

### D) Tech-Entscheidungen (WARUM, für Nicht-Techniker)
- **Zwei Strategien, eine Abstraktion:** Codex/Claude merken sich den Verlauf serverseitig — wir müssen nur eine **ID** aufheben und mitschicken (billig). GLM/OpenRouter vergisst alles — der einzige Weg zu „Erinnerung" ist, den **ganzen Verlauf zu speichern und erneut mitzusenden**. Deshalb behandeln wir sie unterschiedlich, aber hinter einer gemeinsamen „Kontext wiederherstellen"-Schnittstelle.
- **Verlauf in die DB, nicht in MinIO:** Es ist Text, klein bis mittel, und wird zusammen mit der Session gelesen. MinIO ist für binäre Dateien.
- **Verlauf getrennt von den Metadaten (`session_context` statt Spalte):** Die Metadaten-Zeile wird sehr häufig geschrieben; ein großer Verlaufs-Blob dort würde jedes Mal mitkopiert. Getrennt = billiger und sauberer.
- **Speichern bei Turn-Abschluss (GLM):** Ein Restart (z. B. Deploy) kann jederzeit passieren — nur ein vollständig gespeicherter Turn übersteht ihn. Halbe/abgebrochene Turns werden NICHT gespeichert, damit der Verlauf nie korrumpiert.
- **Gedeckeltes Zurückspielen:** Ein unbegrenzter Verlauf würde das Token-/Kontextfenster sprengen und Kosten explodieren lassen (genau die PROJ-45-Overspend-Sorge). Wir spielen bis zu einer **konfigurierbaren Obergrenze** zurück; darüber wird der älteste Teil gekürzt und sichtbar markiert (spätere Verdichtung ist Sache von PROJ-5/PROJ-19, nicht dieses Tickets).
- **Vault-Log bleibt getrennt:** Das bestehende Vault-Transkript (`_write_session_log`) ist ein anhängendes **Wissens-/Historien-Log** (kann N Reload-Dopplungen enthalten). Die neue Resume-Kopie ist die **saubere, kanonische** Konversation zum Zurückspielen — die beiden werden bewusst nicht vermischt.
- **Claude unangetastet:** Der langlebige-Prozess-Pfad bleibt Default; nativer `--resume` nur bei totem Prozess. Kein Regressionsrisiko.
- **Best-effort-Degradation:** Fehlt eine ID / ist der Thread serverseitig abgelaufen / ist die DB nicht erreichbar → sauberer kontextloser Neustart mit sichtbarem Status, nie ein Crash (konsistent mit dem bestehenden „In-Memory gewinnt"-Prinzip von PROJ-14).

### E) Abhängigkeiten (Pakete)
- **Keine neuen Pakete.** Wiederverwendet: bestehende Postgres-Persistenz (`session_index`-Repo + Migrationsmuster), die vorhandenen Treiber (`generic_cli_driver`, `openai_driver`) und den Engine-Manager. Reine Erweiterung bestehender Bausteine.

### Betroffene Bausteine (Umsetzungs-Startpunkte, keine Lösungsvorgabe)
- `backend/app/engine/manager.py` — `_resume` engine-bewusst (`:1550-1591`, statt `resume=is_claude`), Zustand laden in `rehydrate`/`auto_resume_drained` (`:1218`/`:1284`), Sichern in `_persist`/`_row` (`:1163-1204`).
- `backend/app/engine/generic_cli_driver.py` — `resume_id` aus RAM (`:80`) in den Store heben; Resume-argv im Manager-Pfad nutzen.
- `backend/app/engine/openai_driver.py` — Verlauf (`_messages`, `:56`) persistierbar machen + beim Neubau zurückspielen.
- `backend/app/db/session_index.py` — `resume_id`- + `context_status`-Spalte via `_MIGRATIONS`; neuer `session_context`-Store (analoges Repo-Muster).

### Grobe Umsetzungsreihenfolge (für /abc-backend)
1. Persistenz-Fundament: `resume_id`/`context_status`-Spalten + `session_context`-Store + Repo.
2. Codex-Pfad: resume_id persistieren + engine-bewusster `_resume` mit Resume-argv (+ Fallback).
3. GLM-Pfad: Verlauf bei Turn-Abschluss persistieren + Replay beim Treiber-Neubau (+ Deckel).
4. Beobachtbarkeit: `context_status` setzen + in Session-Antwort ausspielen.
5. Tests je Auslöser (Restart · Reanimierung · `_resume`) × je Engine (Codex, GLM) + Claude-Regressionscheck.

## Implementation Notes (Backend, 2026-07-05)
Umgesetzt auf `dev` (backend-only, keine neuen Pakete). Wichtige Abweichung zur Design-Annahme: Der PROJ-14-Store ist **SQLite** (host-nativ, `session_index.db`), nicht Postgres — Single-Owner-Jupiter, daher kein RLS/mandant. Umgesetzt entlang des Design-Plans:

**1. Persistenz (`backend/app/db/session_index.py`)**
- Zwei Nachzügler-Spalten auf `session_index`: `resume_id`, `context_status` (via `_MIGRATIONS` + `COLUMNS` + `SCHEMA_SQL` — idempotentes ADD COLUMN).
- Neuer **`session_context`**-Store (Tabelle in derselben DB-Datei): `save_context(session_id, messages_json)` / `load_context(session_id)`; `delete()` räumt den Verlauf mit ab. No-op-Varianten im `NullSessionIndexRepository`. Repo-Protocol erweitert.

**2. Treiber-Interface (`base.py`)**
- `EngineDriver`: neue Properties `resume_id` (default None), `conversation_history` (default None), Methode `load_history()` (default No-op). `LaunchSpec.resume_id` ergänzt.

**3. Codex (`generic_cli_driver.py`)**
- `resume_id`-Property (spiegelt `_resume_id`).
- `start()` ist jetzt resume-aware: `spec.resume` + `supports_self_resume` + `spec.resume_id` → **primt** nur die ID und spawnt KEINEN frischen Thread; der nächste `send_input` nimmt den Codex-Thread über das Resume-argv auf. Fehlt die ID → bewusster Frischstart (kontextlos).

**4. GLM/OpenRouter (`openai_driver.py`)**
- `conversation_history` exponiert `_messages`; `load_history()` spielt persistierten Verlauf zurück; `start()` hängt den System-Prompt nur bei leerem Verlauf an → **keine Dublette** beim Resume.

**5. Manager (`manager.py`)**
- `SessionState`: `resume_id`, `context_status` (+ in `to_read()`/`_row()`/`_state_from_row()`; `_row` synct eine frisch aufgefangene Treiber-`resume_id` in den State).
- `_persist()`: sichert `conversation_history` **nur bei SETTLED-Status** (`WAITING`/`DONE`) → nie ein halber Turn. Helfer `_safe_save_context()`.
- **`_resume()` engine-bewusst**: Claude = nativer `--resume` (unverändert) · Codex = persistierte `resume_id` durchreichen · GLM = persistierten Verlauf gedeckelt (`_cap_history`, `openai_resume_max_messages=40`) via `load_history` replayen. Setzt `context_status` ("mit Kontext" / "…(Verlauf gekürzt)" / "kontextlos (<Grund>)").
- Config: `openai_resume_max_messages` (Cap gegen Overspend, PROJ-45-Sorge).

**Tests:** `backend/tests/test_proj56_context_persistence.py` — 13 Tests, alle grün (Store-Roundtrip + Migration, Codex-Primen mit/ohne ID, OpenAI load_history/kein Doppel-System, `_resume` je Engine mit/ohne Kontext, `_persist` nur settled, `_cap_history`). Volle Suite: **1024 passed** (der eine Fehlschlag `test_proj50_codex_abc::…no_drift` ist ein pre-existing Drift der `~/.codex`-Skill-Spiegelung außerhalb des Repos, unabhängig von PROJ-56).

**Offen für QA:** reale End-to-End-Prüfung mit echter Codex-CLI + echtem OpenRouter/GLM-Key gegen die drei Auslöser (Restart · Reanimierung · `_resume`); Edge Cases „Thread serverseitig abgelaufen" und „sehr großer Verlauf" (Cap greift, Verdichtung bleibt PROJ-5/19).

## QA Test Results (2026-07-05)
**Tester:** QA/Red-Team · **Branch:** dev · **Automatisiert:** `backend/tests/test_proj56_context_persistence.py` (17 Tests, grün) + 122 grün über resume-nahe Suites (proj18/proj48/proj33/proj27/proj45/proj16/manager/proj1). Volle Suite zuvor 1024 passed.

**Testart-Grenze:** Rein automatisiert/deterministisch (FakeDriver + echte GenericCli/OpenAI-Treiber + tmp-SQLite). Ein **Live-E2E mit echter Codex-CLI + echtem OpenRouter/GLM-Key** war in dieser Umgebung nicht möglich (kein Key/Subprozess; Codex braucht zudem `danger-full-access`/netns, siehe [[codex-sandbox-netns]]). → als Deploy-Smoke empfohlen, unten als Residual gelistet. Kein UI-Anteil (nur read-only `context_status`-Feld) → kein Flutter/Responsive-Test nötig.

### Acceptance Criteria
**Codex**
- [x] `resume_id` persistiert (nicht nur RAM) — `_row` synct Treiber-ID → `session_index`; Roundtrip-Test.
- [~] Restart → Fortsetzung via `resume_argv` mit Kontext — Unit-belegt (`_resume` codex-Zweig reicht ID durch; Driver-Priming ohne Fresh-Thread). *Live-Smoke offen.*
- [x] `_resume` nutzt Resume-argv (nicht mehr `resume=is_claude`).
- [~] RUNNING-Reanimierung setzt Thread fort — Unit-belegt (`_reanimate_once`→`_resume`→codex-Zweig). *Live-Smoke offen.*
- [x] Fehlende `resume_id` → sauberer Erststart, kein Crash (`context_status="kontextlos (keine Resume-ID der Engine)"`).

**GLM / OpenRouter**
- [x] Verlauf persistiert (`session_context`-Store), übersteht Treiber-Neubau.
- [x] Replay in frischen Treiber via `load_history` (kein doppelter System-Prompt).
- [~] Restart führt Faden fort — Unit-belegt (rehydrate→`send_input`→`_resume`→Replay). *Live-Smoke offen.*
- [x] Reanimierte GLM-Session verliert Konversation nicht (gleicher `_resume`-Pfad).

**Übergreifend**
- [x] Kein Kontextverlust bei den 3 Auslösern × 2 Engines — Unit je Auslöser (`_resume` direkt; via `send_input`; via `_reanimate_once`).
- [x] Claude unverändert — Regressionstest (`resume=True`, `resume_id=None`, `context_status="mit Kontext"`); 122 resume-nahe Tests grün.
- [x] Token-Erwartung kein Overspend-Fehlalarm — `_cap_history` (`openai_resume_max_messages=40`), System-Prompt bewahrt, ältester Teil gekürzt + `context_status="…(Verlauf gekürzt)"`.
- [x] Keine Secrets in persistierten Artefakten — Red-Team-Test (kein Key/`Authorization`/`Bearer` im Verlauf; Key nur im HTTP-Header). Store liegt in der bestehenden `session_index_db_path`-Sandbox.
- [x] Beobachtbar/transparent — `context_status` in `to_read()` (Cockpit) + Log-Grund.

### Edge Cases
- [x] Kaputter/manipulierter Verlauf-JSON → kontextloser Neustart, kein Crash.
- [x] Halber Turn (RUNNING/ERROR) wird NICHT persistiert (nur SETTLED = waiting/done).
- [x] Sehr großer Verlauf → Cap greift (System bewahrt, neuester Teil bleibt).
- [~] Codex-Thread serverseitig abgelaufen → Resume-Spawn scheitert → Fehler sichtbar, Neustart möglich. *Nur Live prüfbar — Residual.*
- [ ] Race Reanimierung + gleichzeitiger User-Input — nicht gezielt getestet (Low; bestehende Card-/Status-Guards greifen). *Residual.*
- [ ] Modellwechsel innerhalb derselben Engine (GLM→anderes OpenRouter-Modell): Verlauf wird übernommen (kein Neu-Faden) — bewusst nicht gesondert behandelt; Design-offen (Low).

### Security-Audit (Red Team)
- Persistierter Verlauf enthält nur Chat-Text — **keine** API-Keys/Header (verifiziert). `resume_id` = nicht-geheime Thread-ID.
- Kein Cross-Session-Leak: `session_context` PK = `session_id`, `load_context` liefert nur die eigene Zeile. Single-Owner-Jupiter (kein Mandant/RLS by design).
- `delete()` räumt den Verlauf mit ab → kein verwaister Kontext nach Session-Löschung (PROJ-21).
- Persistenz ist best-effort → DB-Ausfall blockiert den Hot-Path nicht (In-Memory gewinnt).

### Bugs
**Keine Critical/High/Medium/Low gefunden.** Der eine rote Test der Gesamtsuite (`test_proj50_codex_abc::…no_drift`) ist ein **pre-existing** Drift der `~/.codex`-Skill-Spiegelung außerhalb des Repos — von PROJ-56 unabhängig, kein Bug dieses Features.

### Residuals (kein Blocker — Empfehlung: Deploy-Smoke)
1. Live-E2E mit echter Codex-CLI + echtem OpenRouter/GLM-Key gegen Restart · Reanimierung · `_resume`.
2. Codex „Thread abgelaufen"-Fallback live prüfen.
3. Race Reanimierung+Input (Low) bei Gelegenheit härten.

### Production-Ready
**READY** — keine Critical/High-Bugs; Kernlogik unit-verifiziert, Claude regressionsfrei. Empfehlung: vor/direkt nach Deploy einen kurzen Live-Smoke der zwei Engines fahren (Residual 1).

## Deployment
_To be added by /deploy_
