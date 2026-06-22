# PROJ-1: Engine-Treiber — Claude-Max-Session headless

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

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
- [ ] Backend startet eine Claude-Code-headless-Session als Subprozess (`claude -p`, Stream-JSON I/O) mit **Subscription-Auth** (kein API-Key).
- [ ] Eine Session ist mit initialem Prompt + Arbeitsverzeichnis (Projektpfad) startbar.
- [ ] Eingehende Stream-JSON-Events (assistant text, tool_use, result) werden geparst und als strukturierte Events nach oben gereicht.
- [ ] Weitere Eingaben können an eine laufende Session gesendet werden (multi-turn).
- [ ] Das Modell ist pro Session über `--model` setzbar (haiku/sonnet/opus); Default = Sonnet.
- [ ] Session lässt sich sauber **stoppen** (Prozess beendet, kein Zombie) und **pausieren** (keine neuen Eingaben verarbeitet).
- [ ] Session-Status ist über die API abfragbar: `starting / running / waiting / done / error`.
- [ ] Token-/Kontext-Verbrauch wird aus den result-Events extrahiert und bereitgestellt (Datenquelle für PROJ-5 / #25).
- [ ] **Einfügen (Paste):** beliebiger Text-/Code-Inhalt (auch mehrzeilig/groß) kann als Eingabe an eine laufende Session übergeben werden.
- [ ] **Herauskopieren (Copy):** der Session-Inhalt (vollständiges Transkript bzw. eine einzelne Nachricht/Ausgabe) ist als Klartext abrufbar, sodass er kopiert werden kann.
- [ ] _(UI-Hinweis: die eigentlichen Copy/Paste-Affordanzen im Session-Fenster rendert die Session-Detailansicht in PROJ-3; PROJ-1 stellt nur die Eingabe-/Ausgabe-Schnittstelle bereit.)_

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

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
