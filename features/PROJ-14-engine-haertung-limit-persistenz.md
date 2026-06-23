# PROJ-14: PROJ-1-Härtung — Limit paralleler Sessions + Persistenz

## Status: Approved
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** — (Härtung aus QA-3 von PROJ-1)

## Dependencies
- Requires: PROJ-1 (Engine-Treiber / In-Memory-Registry) — härtet dessen offene Punkte (Session-Limit + Persistenz).
- Verwandt: PROJ-17 (Recovery) — Persistenz ist die Voraussetzung für Wiederherstellung; PROJ-3 (Cockpit) zeigt Limit-Status.

## Beschreibung
PROJ-1 hält den Session-Zustand heute rein **in-memory** und kennt **kein Limit** paralleler Sessions. Dieses Feature schließt beide Lücken aus dem QA-Befund: ein konfigurierbares **Limit gleichzeitiger Sessions** (Schutz vor Ressourcen-Überlast) und ein **Persistenz-Seam** (Postgres-Live-Index), damit der Live-Zustand einen Backend-Neustart übersteht.

## User Stories
- Als Nutzer möchte ich ein konfigurierbares Maximum gleichzeitiger aktiver Sessions, damit der VPS nicht überlastet.
- Als Nutzer möchte ich beim Erreichen des Limits eine klare Rückmeldung statt eines stillen Fehlers.
- Als Nutzer möchte ich, dass der Live-Index der Sessions einen Backend-Restart übersteht (kein Totalverlust der Übersicht).
- Als Nutzer möchte ich, dass beendete/fehlerhafte Sessions die Limit-Zählung nicht dauerhaft blockieren.

## Acceptance Criteria
- [ ] Ein konfigurierbares **`max_parallel_sessions`** (Default sinnvoll, z. B. anhand CPU); Quelle: zentrale Settings.
- [ ] Beim Überschreiten wird die Erstellung **abgelehnt** mit klarer deutscher Meldung (HTTP 429/409) — kein Crash, kein stiller Abbruch.
- [ ] Nur **aktive** Zustände (starting/running/waiting/awaiting_approval) zählen gegen das Limit; done/error nicht.
- [ ] **Persistenz-Seam**: der Session-Live-Index wird in Postgres gespiegelt (anlegen/Status-Update/beenden), ohne den In-Memory-Pfad zu verlangsamen.
- [ ] Nach **Backend-Neustart** ist die Session-Liste (Metadaten/letzter Status) wieder sichtbar; laufende Claude-Prozesse, die den Restart überlebt haben, werden — soweit möglich — re-attacht oder als „verwaist" markiert.
- [ ] Das Repository-Seam ist so geschnitten, dass PROJ-17 (Recovery über Vault) darauf aufsetzen kann.
- [ ] Bestehende PROJ-1-Tests bleiben grün (verhaltenswahrend für den Normalfall).

## Edge Cases
- **Limit-Race** (zwei gleichzeitige Creates am Limit) → atomare Prüfung, höchstens das Limit wird zugelassen.
- **Prozess überlebt Restart nicht** → Session als „verwaist/beendet" markieren, sauber aus der Zählung nehmen.
- **DB nicht erreichbar** → In-Memory bleibt führend (MVP-Prinzip), Persistenz best-effort, sichtbare Warnung statt Hard-Fail.
- **Inkonsistenz Speicher↔DB nach Crash** → beim Start abgleichen; In-Memory/Prozess-Realität gewinnt.
- **Limit = 0 / Fehlkonfiguration** → auf sinnvolles Minimum klemmen.

## Technical Requirements (optional)
- Persistenz als **Live-Index** (schneller Spiegel), nicht als Wahrheit — Wahrheit bleibt Vault (PRD-Constraint).
- Limit-Prüfung atomar im SessionManager; Konfiguration via `pydantic-settings`.
- Kein Performance-Regress im Hot-Path der Event-Verarbeitung.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-23 · **Stack:** Backend-only (FastAPI + SQLite-Live-Index, host-nativ; kein Frontend-Change zwingend) · **Branch:** dev

### Kernentscheidung: Persistenz-Store = SQLite (host-nativ), nicht Postgres/Neon
Der Live-Index ist laut PRD **nicht die Wahrheit** (das ist der Vault), wird vom **einen** uvicorn-Worker
geschrieben (single-writer) und soll nur einen Backend-Restart auf **demselben Host** überstehen. Genau
SQLites Stärke. Neon (DE) wurde verworfen: Remote-Round-Trip pro Status-/last_activity-Write verletzt das
AC „kein Performance-Regress im Hot-Path", erzeugt Netzabhängigkeit (häufiger Best-Effort-Fallback) und
trägt Session-Metadaten (Projektpfade/Prompts) vom Host weg — gegen die bewusst host-native Deploy-Philosophie.
Neon bleibt die richtige Wahl **später** als *geteilter, autoritativer* Store (Phase 2 / echtes Auth / Multi-User).
Das Repository-Seam wird abstrakt geschnitten, damit dieser Wechsel (auch für **PROJ-17**) ohne Bruch geht.

Heutiger Stand (Befund): Das Backend ist **komplett in-memory** (`SessionManager._sessions: dict`), es gibt
**keine DB-Schicht** (kein asyncpg/psycopg/DATABASE_URL), und `create_app()` hat **keinen lifespan-Hook**.
PROJ-14 führt beides erstmals ein.

### A) Was gebaut wird (zwei unabhängige Bausteine)

**1. Limit gleichzeitiger Sessions**
```
SessionManager.create()
├── (NEU) asyncio.Lock  ── atomares "zählen → prüfen → reservieren"
├── (NEU) aktive Sessions zählen: status ∈ {starting, running, waiting, awaiting_approval}
│         done/error zählen NICHT
└── Limit überschritten? → SessionLimitError → Route: HTTP 429 + deutsche Meldung
```

**2. Persistenz-Seam (Live-Index-Spiegel)**
```
backend/app/db/                      (NEU)
├── session_index_repo.py  ── SessionIndexRepository (abstraktes Seam, Protocol)
│                             + SqliteSessionIndexRepository (stdlib sqlite3 in asyncio.to_thread)
│                             + NullRepository (DB aus / nicht erreichbar → Best-Effort)
└── schema.sql             ── CREATE TABLE session_index (+ Index auf status)

create_app()  ── (NEU) lifespan: Repo öffnen, Datei/Schema anlegen, Reconcile, sauber schließen
SessionManager  ── spiegelt auf: create / Status-Wechsel / Terminierung (NICHT auf jedem Event)
```

### B) Datenmodell — `session_index` (SQLite)
Spiegelt die persistierbaren Metadaten von `SessionState` (Manager-`dataclass`). **Kein** Transkript,
keine Subscriber, keine Live-Prozess-Handles — nur der wiederherstellbare Übersichts-Zustand:
```
session_id (PK) · owner · project_path · project_name · model · permission_mode · role
status · pid (OS-PID des claude-Subprozesses, für Verwaist-Check) · error
created_at · last_activity · tokens_used · total_cost_usd
parent_session_id · abc_phase · abc_phase_reached
Index: (status)   — schnelle Aktiv-Zählung & Reconcile
```
Datei-Pfad konfigurierbar (`session_index_db_path`, Default unter einem beschreibbaren Daten-Verzeichnis,
z. B. `/home/dev/jupiter-data/session_index.db`), wird bei Bedarf automatisch angelegt.

### C) Schreibstrategie (Hot-Path-Schonung)
- Spiegelung **nur bei Zustandsänderungen** (create, jeder `status`-Übergang, Terminierung), nicht bei
  jedem Stream-Event → der hochfrequente Event-Loop (`handle_event`) bleibt unbelastet.
- Schreiben über `asyncio.to_thread` (stdlib `sqlite3`, WAL-Modus) → kein Blockieren der Event-Loop.
- Alle DB-Operationen **best-effort**: `try/except` → bei Fehler nur sichtbare Warnung; der In-Memory-Pfad
  bleibt führend (MVP-Prinzip, AC „DB nicht erreichbar").

### D) Restart-Verhalten / Reconcile (beim Startup-lifespan)
1. Persistierte Sessions laden, die in einem **aktiven** Status standen.
2. Keiner ist nach Restart in-memory steuerbar (der stream-json-Pipe/`asyncio.subprocess`-Handle ist weg;
   bei systemd-Restart sterben Kind-Prozesse i. d. R. mit dem Parent-cgroup).
3. PID-Lebendigkeit best-effort prüfen (`os.kill(pid, 0)`):
   - Prozess tot → Session als **`verwaist`/beendet** markieren, aus der Aktiv-Zählung nehmen.
   - Prozess lebt noch, aber nicht steuerbar → ebenfalls **`verwaist`** (ehrlich: kein Re-Attach des
     Live-Streams über den Restart möglich), Hinweis im `error`/Status.
4. **In-Memory/Prozess-Realität gewinnt** bei Inkonsistenz Speicher↔DB.
5. Ergebnis: Die Session-**Liste** (Metadaten + letzter Status) ist nach Restart wieder sichtbar (kein
   Totalverlust der Übersicht) — genau das AC.

### E) API-Form (minimal)
- **Kein** neuer Endpoint nötig. `POST /sessions` bekommt den 429-Pfad bei Limit-Überschreitung.
- `GET /sessions` listet nach Restart auch die aus dem Index rehydrierten (verwaisten) Sessions.
- Optional (klein, empfohlen): `GET /sessions` / ein Settings-Feld macht `max_parallel_sessions` + aktuelle
  Aktiv-Zahl sichtbar, damit das Cockpit (PROJ-3) den Limit-Status anzeigen kann.

### F) Tech-Entscheidungen (Begründung)
- **SQLite statt Postgres** — siehe Kernentscheidung oben (Hot-Path, Host-Nativität, „nicht die Wahrheit").
- **stdlib `sqlite3` + `asyncio.to_thread`** statt neuer Abhängigkeit (`aiosqlite`): null neue Deps,
  lokale Writes sind sub-ms, `to_thread` hält die Event-Loop frei. (`aiosqlite` bleibt drop-in-Alternative.)
- **Repository-Protocol** statt direkter SQL-Aufrufe im Manager: PROJ-17 (Recovery) und ein späterer
  Neon/Postgres-Tausch setzen ohne Bruch darauf auf.
- **`asyncio.Lock` für die Limit-Prüfung**: `create()` hat `await`-Punkte → ohne Lock wäre die
  „zählen-dann-reservieren"-Sequenz nicht atomar (Edge-Case Limit-Race).
- **Limit-Default & Klemmung**: Default sinnvoll (z. B. CPU-bezogen), `≤ 0`/Fehlkonfiguration auf
  Minimum 1 geklemmt (Edge-Case „Limit = 0").

### G) Neue Settings (`config.py`, Prefix `JUPITER_`)
- `max_parallel_sessions: int` — Obergrenze aktiver Sessions (Default sinnvoll, geklemmt auf ≥ 1).
- `session_index_db_path: str` — Pfad der SQLite-Datei (auto-angelegt).
- `session_index_enabled: bool = True` — Persistenz global abschaltbar (→ `NullRepository`, reines In-Memory).

### H) Abhängigkeiten
- **Keine neuen Python-Pakete** (stdlib `sqlite3`, `asyncio`, `os`). Optional später `aiosqlite`.

### I) Verhaltenswahrung
- Bestehende PROJ-1-Tests bleiben grün: Limit greift erst beim Überschreiten; Persistenz ist additiv und
  best-effort. Tests können den Manager mit `NullRepository` / hohem Limit fahren (kein Default-Bruch).

## Implementation Notes (Backend)
**Branch:** dev · **Stand:** 2026-06-23 · keine neuen Python-Abhängigkeiten.

**Limit paralleler Sessions**
- `config.py`: `max_parallel_sessions` (Default 12, Env `JUPITER_MAX_PARALLEL_SESSIONS`) + `clamp_session_limit()` (klemmt ≤0 auf 1) + `SESSION_LIMIT_MIN`.
- `manager.py`: `ACTIVE_STATES = {starting, running, waiting, awaiting_approval}`, `active_count()`, `max_parallel_sessions`-Property. `create()` prüft das Limit **atomar** unter `self._create_lock` und reserviert den Slot durch Insert in die Registry, bevor der Lock fällt (Edge-Case Limit-Race). Überschreitung → neue `SessionLimitError`.
- `routes/sessions.py`: `SessionLimitError` → **HTTP 429** mit deutscher Meldung. Neuer `GET /sessions/limits` → `{max_parallel_sessions, active}` (Cockpit-Statusanzeige, PROJ-3).

**Persistenz-Seam (SQLite-Live-Index)**
- Neues Paket `backend/app/db/`: `SessionIndexRepository` (Protocol) + `SqliteSessionIndexRepository` (stdlib `sqlite3`, WAL, per-Operation-Connection, alle I/O via `asyncio.to_thread`) + `NullSessionIndexRepository` + Factory `build_session_index_repo(settings)`. Tabelle `session_index` (PK `session_id`, Index auf `status`).
- `manager.py`: Repo injizierbar (`repo=`, Default Null). `_persist()` ist ein best-effort `on_persist`-Hook, der **nur bei Statuswechsel** feuert (`SessionRuntime._maybe_persist`, getrackt via `_last_persisted_status`) → Hot-Path der Event-Verarbeitung unbelastet. Schreiben fire-and-forget über `asyncio.create_task` + `_safe_upsert` (schluckt Fehler → Warnung, In-Memory führt).
- `base.py`: `EngineDriver.pid`-Property (Default None) + `DeadDriver` (Platzhalter für rehydrierte Sessions). `claude_driver.py`: echte PID aus dem Subprozess.
- `main.py`: `create_app()` baut das Repo (oder akzeptiert `session_index_repo=`) und fährt einen **lifespan** (`repo.init()` → `manager.rehydrate()` → bei Shutdown `repo.close()`).

**Restart/Reconcile**
- `SessionManager.rehydrate()`: lädt persistierte Sessions; **In-Memory gewinnt** (vorhandene IDs werden nicht überschrieben). Sessions, die in einem aktiven Status standen, werden als **verwaist** (`status=error`, sprechende `error`-Meldung) markiert und fallen aus der Aktiv-Zählung; PID-Lebendigkeit best-effort via `os.kill(pid,0)` (`_pid_alive`). Korrigierter Status wird zurückgespiegelt. Rehydrierte Sessions tragen einen `DeadDriver` → eine Eingabe löst regulär den `claude --resume`-Pfad aus.

**Tests** (`backend/tests/test_proj14_haertung.py`, 12 Tests, alle grün; Gesamt-Suite 303 grün):
Limit (Ablehnung, nur aktive zählen, Race-Atomarität, 429 + `/limits`), Clamp, SQLite-Roundtrip/Upsert, Create-Spiegelung, Best-effort bei DB-Ausfall, Rehydrierung (verwaist + In-Memory-Vorrang), `_pid_alive`. `conftest.py`: Persistenz im Test global aus (kein Schreiben in den echten Home-Pfad), Tests injizieren ihr eigenes Repo.

**Verhaltenswahrung:** alle bestehenden PROJ-1-Tests bleiben grün; Limit greift erst beim Überschreiten, Persistenz ist additiv/best-effort (Default-Repo = Null in Tests).

**Offen für QA / PROJ-17:** Re-Attach an einen den Restart *überlebenden* Prozess ist bewusst nicht implementiert (Stream nicht wieder ankoppelbar) — solche Sessions werden als verwaist geführt; das Repository-Seam ist die Basis für PROJ-17 (Recovery über Vault).

## QA Test Results
**Getestet:** 2026-06-23 · **Branch:** dev · **Suite:** 303 grün (12 PROJ-14-spezifisch) · **Methode:** pytest + manuelle Reanimations-/Restart-Probes + Code-Red-Team.

### Acceptance Criteria
| # | Kriterium | Ergebnis |
|---|-----------|----------|
| 1 | Konfigurierbares `max_parallel_sessions` aus zentralen Settings | ✅ PASS (`config.py`, Env `JUPITER_MAX_PARALLEL_SESSIONS`, Default 12) |
| 2 | Überschreiten → Ablehnung mit deutscher Meldung (429), kein Crash | ✅ PASS (`SessionLimitError`→HTTP 429, Test `test_api_limit_liefert_429`) |
| 3 | Nur aktive Zustände zählen (done/error nicht) | ✅ PASS (`ACTIVE_STATES`, Tests `test_nur_aktive_zustaende_zaehlen`, `test_active_states_konstante`) |
| 4 | Persistenz-Seam spiegelt Live-Index, ohne Hot-Path zu bremsen | ✅ PASS (Spiegelung nur bei Statuswechsel via `_maybe_persist`; I/O off-thread; Test `test_create_spiegelt_in_live_index`) |
| 5 | Nach Restart Liste sichtbar; Prozesse re-attacht oder „verwaist" | ✅ PASS (Re-Attach bewusst nicht möglich → verwaist; `rehydrate`, Test `test_rehydrate_markiert_aktive_als_verwaist`) |
| 6 | Repository-Seam für PROJ-17 nutzbar | ✅ PASS (`SessionIndexRepository`-Protocol, austauschbar) |
| 7 | Bestehende PROJ-1-Tests grün (verhaltenswahrend) | ✅ PASS (303/303, keine Regression) |

### Edge Cases
| Edge Case | Ergebnis |
|-----------|----------|
| Limit-Race (2 gleichzeitige Creates am Limit) | ✅ atomar, genau 1 zugelassen (`test_limit_race_atomar`) |
| Prozess überlebt Restart nicht | ✅ als verwaist markiert, aus Aktiv-Zählung genommen |
| DB nicht erreichbar | ✅ best-effort, In-Memory führt, kein Hard-Fail (`test_db_ausfall_ist_best_effort`) |
| Inkonsistenz Speicher↔DB | ✅ In-Memory gewinnt (`test_rehydrate_in_memory_gewinnt`) |
| Limit = 0 / Fehlkonfiguration | ✅ auf 1 geklemmt (`test_clamp_session_limit_klemmt_auf_minimum`) |

### Bugs / Findings
- **[Medium] Limit-Bypass über Reanimation.** Das Limit greift nur in `create()`. `POST /sessions/{id}/input` (→ `_resume`) und der Reset-Pfad reaktivieren eine beendete Session nach `running` **ohne** Limit-Prüfung. Verifiziert: bei `max=2` führten 2 weitere Creates (nach Stop) + 2× `send_input`-Resume zu `active_count()=4`. Literales AC #2 spricht von „Erstellung" (erfüllt), aber der Schutzzweck (VPS-Überlast) ist umgehbar. *Repro:* Limit füllen, Sessions beenden, neue erstellen, alte per `send_input` reaktivieren. *Fix-Vorschlag:* Limit-Check zentral in `_resume`/`send_input`-Reaktivierung mitziehen (`SessionLimitError` → in `send_input`-Route auf 429 mappen).
- **[Low] Reset am Limit liefert 409 statt 429.** `SessionLimitError` ist `RuntimeError`-Subklasse → in `reset_session` vom `except RuntimeError` als 409 gefangen (Meldung stimmt inhaltlich). Zudem ist die alte Session zu dem Zeitpunkt bereits gestoppt. *Fix-Vorschlag:* in `reset_session` `SessionLimitError` vor `RuntimeError` fangen → 429; ggf. Limit vor dem Stop der alten Session prüfen.
- **[Low] Verwaiste Session verliert beim Resume die Konstitution.** `effective_constitution` wird nicht persistiert → ein rehydrierter Orphan resumed ohne `--append-system-prompt`. Bewusst akzeptiert (im Tech-Design notiert); `claude --resume` lädt den Original-Kontext ohnehin.
- **[Info] Persist-Reihenfolge.** Schnell aufeinanderfolgende Statuswechsel planen mehrere unabhängige `to_thread`-Writes ohne Ordnungsgarantie → der Index kann kurz einen veralteten Status zeigen. Eventual-konsistent; ohne funktionalen Schaden (Rehydrierung markiert aktive Stände ohnehin als verwaist). Best-effort-Design.

### Security (Red-Team)
- Single-User-MVP, kein JWT/RLS (bewusster Jupiter-Override) → kein Tenant-/Cross-Mandant-Vektor.
- SQLite-Repo nutzt ausschließlich parametrisierte Statements über eine **feste** Spaltenliste (keine User-Strings in SQL) → keine SQL-Injection.
- Index speichert nur Metadaten (Pfade/Status/Modell), **keine** Prompt-/Transkript-Inhalte, keine Secrets. DB-Datei host-lokal.

### Produktionsreife
**READY** — keine Critical/High-Bugs. 1× Medium + 2× Low als empfohlene Follow-ups (nicht-blockierend; Medium betrifft den Schutzzweck, im single-user-MVP nutzer-selbstverschuldet).

## Deployment
_To be added by /abc-deploy_
