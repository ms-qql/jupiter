# PROJ-1: Engine-Treiber — Claude-Max-Session headless

## Status: Approved
**Created:** 2026-06-22
**Last Updated:** 2026-06-22 (Backend + QA abgeschlossen; QA-1/QA-2 behoben)

## Dependencies
- None — **Fundament** des MVP (ersetzt bewusst die übliche „Auth = PROJ-1"-Regel; Auth ist MVP-Non-Goal, single-user).

## Beschreibung
Der Motor von Jupiter: ein Backend-Dienst, der **eine** Claude-Max-Session über **Claude Code headless** (`claude -p`, Stream-JSON I/O) startet, mitliest, steuert und beendet — mit **Subscription-Auth**, nicht über die rohe Anthropic-API. Treiber-Modell #6; Treiber-Seite des Modell-Routings #22 (`--model`-Flag).

## User Stories
- Als Solo-Entwickler möchte ich eine Claude-Max-Session headless aus Jupiter heraus starten, um meine Subscription ohne Terminal zu nutzen.
- Als Nutzer möchte ich der Session einen Auftrag (Prompt) senden und ihre Ausgabe live mitlesen, um den Fortschritt zu verfolgen.
- Als Nutzer möchte ich pro Session das Modell wählen (Haiku/Sonnet/Opus), um Kosten und Leistung je Aufgabe zu steuern.
- Als Nutzer möchte ich eine laufende Session pausieren und sauber stoppen können, um die Kontrolle zu behalten.
- Als Nutzer möchte ich beliebige Inhalte (Logs, Code, Fehlermeldungen) in das Session-Fenster **einfügen** und die Session-Ausgabe **herauskopieren**, um schnell Daten rein- und rauszubekommen.

## Acceptance Criteria
- [x] Backend startet eine Claude-Code-headless-Session als Subprozess (`claude -p`, Stream-JSON I/O) mit **Subscription-Auth** (kein API-Key).
- [x] Eine Session ist mit initialem Prompt + Arbeitsverzeichnis (Projektpfad) startbar.
- [x] Eingehende Stream-JSON-Events (assistant text, tool_use, result) werden geparst und als strukturierte Events nach oben gereicht.
- [x] Weitere Eingaben können an eine laufende Session gesendet werden (multi-turn).
- [x] Das Modell ist pro Session über `--model` setzbar (haiku/sonnet/opus); Default = Sonnet.
- [x] Session lässt sich sauber **stoppen** (Prozess beendet, kein Zombie) und **pausieren** (keine neuen Eingaben verarbeitet).
- [x] Session-Status ist über die API abfragbar: `starting / running / waiting / done / error`.
- [x] Token-/Kontext-Verbrauch wird aus den result-Events extrahiert und bereitgestellt (Datenquelle für PROJ-5 / #25).
- [x] **Einfügen (Paste):** beliebiger Text-/Code-Inhalt (auch mehrzeilig/groß) kann als Eingabe an eine laufende Session übergeben werden.
- [x] **Herauskopieren (Copy):** der Session-Inhalt (vollständiges Transkript bzw. eine einzelne Nachricht/Ausgabe) ist als Klartext abrufbar, sodass er kopiert werden kann.
- ℹ️ _(UI-Hinweis: die eigentlichen Copy/Paste-Affordanzen im Session-Fenster rendert die Session-Detailansicht in PROJ-3; PROJ-1 stellt nur die Eingabe-/Ausgabe-Schnittstelle bereit — erledigt.)_

## Edge Cases
- `claude` nicht eingeloggt / Subscription abgelaufen → klare deutsche Fehlermeldung, Status = `error`.
- Subprozess stürzt ab / OOM → Status = `error`, letzter Stand bleibt lesbar.
- Ungültiger/fehlender Projektpfad → Start wird mit Begründung abgelehnt.
- Mehrere parallele Sessions → jede mit isoliertem Prozess + eigenem `cwd`.
- Unparsebare Stream-JSON-Zeile → geloggt, Session läuft weiter (kein Hard-Fail).
- Sehr großer Paste-Inhalt → kein Crash; ggf. Hinweis/Limit, statt das Kontextfenster blind zu fluten (Zusammenspiel mit PROJ-5 / #25).

## Technical Requirements (optional)
- **Verifikations-Spike zuerst** (Brainstorm offener Punkt #1): bestätigen, dass `claude -p` mit Stream-JSON + Subscription-Auth headless steuerbar ist, bevor weitergebaut wird.
- Cross-Provider (Codex/Gemini/GLM/Ollama) = je eigener Treiber (P1, #13) — Architektur muss die Treiber-Abstraktion offenhalten.
- Ein Subprozess pro Session; Lifecycle-Management im Backend.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-22 · **Stack:** Next.js/React (UI später, PROJ-3) + FastAPI + Postgres + Hal-Vault · **Branch:** dev

### Spike-Status (riskantester Unbekannter — weitgehend grün)
Die headless-Steuerbarkeit ist gegen die installierte CLI (`claude` v2.1.185) verifiziert. Die nötigen Schalter existieren:

| Flag | Rolle in Jupiter |
|---|---|
| `-p --output-format stream-json` | Live-Ausgabe der Session streamen |
| `--input-format stream-json` | Multi-turn-Eingabe (Paste-in) |
| `--model haiku\|sonnet\|opus` | Modell-Routing #22 |
| `--session-id <uuid>` | **Eigene** ID → 1:1-Mapping Jupiter-DB ↔ Claude-Session |
| `--resume / --continue` | Multi-turn + Grundlage Recovery #20 |
| `--append-system-prompt` | Knappheits-Konstitution #24 (PROJ-6) einspeisen |
| `--permission-mode` (+ `--permission-prompt-tool`) | Freigabe-Verhalten → bahnt Decision Cards (PROJ-4) |
| `--add-dir` | Projekt-/Verzeichnis-Scope |

**Verbleibender Spike (erster Build-Schritt):** ein echter Auth-Round-Trip auf dem VPS — `claude` ist als Max-Subscription eingeloggt und ein `claude -p --output-format stream-json`-Aufruf liefert verwertbare Events. Auth nutzt die Subscription (`claude login`), **kein** API-Key.

### A) Komponenten-Struktur (Backend — UI ist PROJ-3)
```
Engine-Layer (FastAPI-Backend)
├── EngineDriver (abstrakte Treiber-Schnittstelle)   ← hält #13 (weitere Engines) offen
│   └── ClaudeCodeDriver  (Claude Code headless)
│       ├── Prozess-Lifecycle      start / pause / stop  (1 Subprozess je Session)
│       ├── Stream-JSON-Parser      Events: assistant-text / tool_use / result
│       ├── Eingabe-Kanal (stdin)   Multi-turn + Paste-in
│       └── Verbrauchs-Extraktor    Tokens + Kontext-Füllstand → Datenquelle PROJ-5/#25
├── Session-Manager   In-Memory-Registry aller laufenden Sessions (Prozess-Handles)
├── Session-API       REST (Steuern) + WebSocket (Live-Stream)
└── Persistenz-Hook   schreibt Status in Postgres (Live) + Transkript via PROJ-2 (Vault)
```

### B) Datenmodell (Klartext)
Eine **Session** (Live-Index in Postgres, dauerhafte Wahrheit im Vault über PROJ-2):
- `session_id` (UUID — identisch mit `--session-id` der CLI)
- `owner` (heute immer du, #21) · `project_path` (cwd, beschränkt auf `/home/dev/projects/*` + `/home/dev/tools/*`)
- `model` (haiku/sonnet/opus, Default sonnet) · `permission_mode` (MVP: `default`)
- `status` (starting / running / waiting / done / error)
- `tokens_used`, `context_fill_pct` (laufend, aus result-Events)
- `created_at`, `last_activity`

Das **rohe Transkript** wird nicht dauerhaft in Postgres gehalten, sondern live im Speicher gestreamt und über **PROJ-2** als MD in den Vault geschrieben (Trennung Live-Zustand ↔ Wahrheit, beantwortet Brainstorm-Offenpunkt #2 für PROJ-1).

### C) API-Form (nur Endpunkte, kein Code)
```
POST  /sessions                  → Session starten (project_path, model, optional initialer Prompt) → session_id
GET   /sessions                  → laufende Sessions auflisten (vom Cockpit PROJ-3 genutzt)
GET   /sessions/{id}             → Status + Metadaten + aktuelles Transkript
POST  /sessions/{id}/input       → Eingabe senden / Inhalt einfügen (multi-turn, Paste-in)
POST  /sessions/{id}/pause       → pausieren (keine neuen Eingaben verarbeiten)
POST  /sessions/{id}/stop        → sauber beenden (Prozess terminieren)
GET   /sessions/{id}/transcript  → vollständiges Transkript als Klartext (Copy-out)
WS    /sessions/{id}/stream      → Live-Events: Text-Deltas, tool_use, Statuswechsel, Token/Kontext-Updates
```
MVP single-user → **kein JWT**; `owner` wird serverseitig gestempelt (bewusste Abweichung von „JWT überall", da Auth MVP-Non-Goal #21).

### D) Tech-Entscheidungen (warum)
- **Treiber = Claude Code CLI, nicht die rohe Anthropic-API.** Nutzt die Max-Subscription-Auth (kein API-Key, keine API-Zusatzkosten). Konsequenz: Routing über `--model`; Fremd-Provider = je eigener Treiber (P1, #13).
- **Eigene `--session-id` vergeben.** Jupiter-DB-Record und Claude-Session teilen dieselbe UUID → einfaches Mapping, sauberes `--resume` und spätere Recovery (#20).
- **WebSocket statt Polling für den Stream.** Token-für-Token-Ausgabe + bidirektional (Eingabe), passt zu „live mitlesen". Steuer-Aktionen laufen über REST, der Live-Strom über WS.
- **Ein Subprozess pro Session, isoliertes `cwd`.** Echte Parallelität, klare Ressourcengrenzen, ein Absturz trifft nur eine Session.
- **`permission-mode=default` im MVP.** Schreib-/Shell-Aktionen laufen nicht unbeaufsichtigt; bahnt PROJ-4 (Cards via `--permission-prompt-tool`) vor.
- **`--append-system-prompt` für die Konstitution reserviert.** Treiber muss den System-Prompt-Hook beim Start akzeptieren (PROJ-6).
- **Session-Manager lebt in einem langlebigen Prozess.** Die Registry hält Subprozess-Handles im Speicher → MVP läuft mit **einem** uvicorn-Worker (bzw. dediziertem Supervisor), nicht über mehrere Worker verteilt. Wichtige Betriebs-Randbedingung.

### E) Abhängigkeiten (Pakete)
- **Backend (Python):** `fastapi`, `uvicorn[standard]` (WebSocket), `pydantic` v2, `pydantic-settings`; `asyncio.subprocess` (stdlib) für die Prozess-Steuerung; Postgres-Zugriff via Projekt-Helper `run_query_m`/`run_command_m`. **Kein** `anthropic`-SDK (wir nutzen die CLI).
- **Extern:** `claude` CLI (vorhanden, v2.1.185) — muss als **Max-Subscription** eingeloggt sein (`claude login`).
- **Frontend:** keins in PROJ-1 (UI = PROJ-3); optional ein minimaler Test-Harness zum Verifizieren.

### Implementation Notes (Backend Developer)
**Datum:** 2026-06-22 · **Branch:** dev · **Env:** conda `Dashboard` (Python 3.10) · **Stand:** Backend fertig, QA ausstehend.

**Gebaute Module** (`backend/app/`):
- `engine/events.py` — Parser für den `stream-json`-Strom; gegen die **real verifizierten** Events gebaut. `UsageSnapshot` berechnet Kontext-Füllstand (#25) aus `(input + cache_read + cache_creation) / contextWindow`.
- `engine/base.py` — `EngineDriver`-Abstraktion + `LaunchSpec` (hält weitere Engines #13 offen).
- `engine/claude_driver.py` — `ClaudeCodeDriver`: Subprozess-Lifecycle, stdin-Multi-turn, stdout-Reader, stderr-Erfassung. `build_argv()` + `classify_exit()` sind reine, unit-getestete Funktionen.
- `engine/manager.py` — `SessionManager` (In-Memory-Registry) + `SessionRuntime` (Zustand, Transkript, WS-Fan-out). Pfad-Scope-Validierung gegen `/home/dev/projects/*` + `/home/dev/tools/*`.
- `schemas/sessions.py` — Pydantic-v2-Modelle. `routes/sessions.py` — REST + WebSocket. `main.py` — `create_app(driver_factory)` (injizierbar für Tests).

**Live-Spike-Befunde (verifiziert gegen `claude` v2.1.185):**
- `apiKeySource:"none"` + `total_cost_usd` → **Subscription-Auth bestätigt** (kein API-Key).
- `-p --output-format stream-json` benötigt `--verbose`. Multi-turn-Eingabe (Initial-Prompt + Folge-Turns) läuft über **stdin als stream-json-User-Message** (kein Positional-Prompt) — end-to-end getestet (`scripts/smoke_driver.py`, Exit 0, sauberer Stop).
- Kontextfenster (`modelUsage[...].contextWindow`) = 200000.

**Im Test gefundener & behobener Bug:** Ein durch uns ausgelöster Stop (SIGTERM → Exit `-15`) wurde fälschlich als Fehler gewertet → Session-Status kippte nach `error`. Fix: `classify_exit(returncode, stopping, stderr)` unterscheidet gewollten Stop von echtem Crash (Unit-Test deckt beide Fälle ab).

**Bewusste Abweichungen / offene Punkte für QA & Folge-Features:**
- **Kein JWT/RLS/mandant_id** (Auth = MVP-Non-Goal); `owner` serverseitig aus `JUPITER_DEFAULT_OWNER` gestempelt.
- **Persistenz in-memory** — Postgres-Live-Index + Vault-Transkript kommen via Infra/PROJ-2 (Repository-Seam vorhanden). Sessions überleben aktuell keinen Neustart.
- **Betrieb mit EINEM uvicorn-Worker** (Registry hält Prozess-Handles im Speicher).
- `permission-mode=default`: genehmigungspflichtige Tools werden headless auto-verweigert, bis PROJ-4 ein `--permission-prompt-tool` liefert.
- **Tests:** `backend/tests/` — 23 grün (`pytest`), nutzen einen `FakeDriver` (keine echte Session/Quota). Live-Test manuell via `scripts/smoke_driver.py` (verbraucht Quota, nicht in CI).

## QA Test Results
**Getestet:** 2026-06-22 · **Branch:** dev · **Tester:** QA Engineer · **Suite:** `backend/tests/` → **42 grün** (`pytest`, inkl. Fix-Verifikation QA-1/QA-2).

### Akzeptanzkriterien (10/10 bestanden)
| # | Kriterium | Ergebnis | Nachweis |
|---|-----------|----------|----------|
| 1 | Headless-Start, Subscription-Auth (kein API-Key) | ✅ PASS | Live-Smoke: `apiKeySource:"none"` + Kosten |
| 2 | Start mit Initial-Prompt + Projektpfad | ✅ PASS | `test_create_session_ok` + Smoke |
| 3 | Stream-JSON-Events geparst | ✅ PASS | `test_events.py` (reale Events) |
| 4 | Multi-turn-Eingabe | ✅ PASS | `test_input_flow` + Smoke |
| 5 | Modell pro Session (`--model`), Default Sonnet | ✅ PASS | Schema-Literal + `build_argv` |
| 6 | Sauber stoppen + pausieren | ✅ PASS | Smoke (Exit 0, sauberer Stop) + `test_pause_blocks_input` |
| 7 | Status starting/running/waiting/done/error | ✅ PASS | `test_manager.py` |
| 8 | Token-/Kontext-Verbrauch extrahiert (#25) | ✅ PASS | `test_extract_usage_and_context_fill` (18.1 %) |
| 9 | Einfügen (Paste) | ✅ PASS | `test_input_flow` |
| 10 | Herauskopieren (Copy/Transkript) | ✅ PASS | `test_input_flow` (transcript_text) |

### Security-Audit (Red-Team) — Pfad-Scope hält
- ✅ **Pfad-Traversal** (`../../etc`), **Prefix-Attacke** (`projects-evil`), **Elternverzeichnis** (`/home/dev`), **Symlink-Escape** (Symlink in Root → `/etc`) — **alle abgelehnt** (`realpath` + `startswith(root+sep)`).
- ✅ Ungültiges Modell / permission_mode → 422; leere Eingabe → 422; unbekannte Session → 404; Eingabe nach Stop → 409; WS auf unbekannte Session → Close 4404.
- ✅ Prozess-Isolation: je Session eigener Subprozess + eigenes `cwd`/`session_id`.
- N/A: JWT/RLS/Mandant-Isolation, Flutter-UI, Responsive — bewusste MVP-Non-Goals bzw. UI in PROJ-3.

### Findings & Behebung
| ID | Sev | Befund | Status |
|----|-----|--------|--------|
| **QA-1** | Medium | API akzeptierte `bypassPermissions` vom Client → Safety-Net abschaltbar. | ✅ **Behoben** — MVP auf `{default, acceptEdits}` beschränkt (Schema-Literal + Manager → 422; Test `test_unsafe_permission_modes_rejected`). |
| **QA-2** | Low | Kein Größenlimit für `initial_prompt`/`input.text`. | ✅ **Behoben** — `max_length = MAX_INPUT_CHARS` (100k) an allen Eingabe-Feldern (Tests `test_oversized_*`). |
| **QA-3** | Low | Kein Limit für parallele Sessions (Single-User mindert Risiko). | ➡️ **P1-Härtung** (Roadmap; mit Persistenz/Infra). |

Hinweis (kein Bug, dokumentierte Scope-Grenze): Sessions sind In-Memory → überleben keinen Neustart (Persistenz via PROJ-2/Infra).

### Produktionsreife-Entscheidung
**READY / Approved** — keine Critical/High-Bugs; alle 10 AC bestanden; QA-1/QA-2 behoben und per Test abgesichert (42 grün). QA-3 als P1-Härtung eingeplant.

## Deployment
_To be added by /deploy_
