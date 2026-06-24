# PROJ-18: Weitere Engines (Codex/Gemini/GLM/Ollama) + iFrame/Launch

## Status: In Review
**Created:** 2026-06-23
**Last Updated:** 2026-06-24
**Baustein:** #13

## Dependencies
- Requires: PROJ-1 (Engine-Treiber-Modell) — das Treiber-Interface ist die Abstraktion, gegen die neue Engines gebaut werden.
- Verwandt: PROJ-22 (Modell-Routing) und P2 Cross-Agent-Review (#30), das Multi-Engine voraussetzt.

## Beschreibung
Das Integrations-Spektrum aus drei Tiefen — **Treiber → iFrame → Startknopf** — macht Integration zu keinem Alles-oder-nichts: ein **HTTP-API-Treiber** für OpenAI-kompatible Engines (**OpenAI** als erste Test-Engine, **OpenRouter** als zweite) und ein generischer **CLI-Adapter** für CLI-Engines (Codex/Gemini/GLM/Ollama), das **Einbetten** fremder Web-Apps als iFrame, und ein simpler **Launch-Button** für alles andere. Nach oben sehen alle Engines gleich aus (gleiche Session-Sicht).

## User Stories
- Als Nutzer möchte ich beim Session-Start neben Claude Max weitere Engines wählen können (sofern konfiguriert).
- Als Nutzer möchte ich eine fremde Engine über einen **generischen CLI-Adapter** einbinden, ohne Jupiters Kern zu ändern.
- Als Nutzer möchte ich eine fremde Web-App (z. B. ein Tool) als **iFrame** in Jupiter einbetten.
- Als Nutzer möchte ich für nicht integrierbare Tools einen einfachen **Startknopf** (öffnet/launcht extern).
- Als Nutzer möchte ich, dass eine Nicht-Claude-Session in Cockpit/Kanban genauso erscheint wie eine Claude-Session.

## Acceptance Criteria
- [ ] Ein **generischer CLI-Treiber** implementiert dasselbe Treiber-Interface wie der Claude-Treiber (start/lesen/steuern/stop) und kann per Konfiguration auf andere CLI-Engines gemappt werden.
- [ ] **OpenAI (API)** ist als **erste Test-Engine** lauffähig integriert (HTTP-Treiber-Tiefe) und **OpenRouter** als **zweite Test-Engine** (OpenAI-API-kompatibel → derselbe Treiber, nur anderer `api_base`/`auth_env`) — als Nachweis der Abstraktion über zwei Anbieter mit nur einem Treiber.
- [ ] **iFrame-Einbettung**: eine konfigurierte URL wird als eingebettete App angezeigt (mit DSGVO-/CSP-konformer Konfiguration).
- [ ] **Launch-Button**: konfigurierbarer Eintrag, der ein externes Tool öffnet/startet.
- [ ] Session-Sicht (Status/Ampel/Kanban) ist **engine-agnostisch**; engine-spezifische Felder degradieren sauber (z. B. kein Token-Füllstand bei Engines ohne Usage).
- [ ] Engine-Auswahl im Smart Launcher (PROJ-9); Claude Max bleibt Default.
- [ ] Fehlende/fehlkonfigurierte Engine → klare Meldung, kein Crash, Claude bleibt nutzbar.
- [ ] Alle Texte deutsch.

## Edge Cases
- **Engine liefert kein Stream-JSON** (anderes Protokoll) → Adapter normalisiert oder degradiert sichtbar (eingeschränkte Live-Sicht).
- **iFrame verweigert Einbettung** (X-Frame-Options) → klarer Hinweis + Fallback Launch-Button.
- **Engine ohne Modell-Routing/Usage** → betroffene Anzeigen als „n/v" statt 0/Fehler.
- **Auth/Key fehlt** für eine API-Engine → Setup-Hinweis, Engine ausgegraut.
- **Mehrere Engines gleichzeitig** → Limit-/Watchdog-Logik (PROJ-14/16) gilt engine-übergreifend.

## Technical Requirements (optional)
- Treiber-Interface aus PROJ-1 bleibt die einzige Kopplung; neue Engines als Plug-in/Adapter.
- iFrame/CSP DSGVO-konform (keine US-CDNs erzwingen); Secrets nie im Frontend.
- Konfiguration der Engines zentral (Settings), ohne Codeänderung pro Engine-Variante.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** Next.js/React + FastAPI + Postgres-Live-Index + Hal-Vault · **Branch:** dev

### Leitidee — drei Integrations-Tiefen, eine Session-Sicht
Integration ist **kein Alles-oder-nichts**. Drei abgestufte Tiefen, je nach dem, wie sehr sich ein fremdes Werkzeug öffnen lässt:

| Tiefe | Was | Wann | Erscheint im Cockpit als |
|---|---|---|---|
| **1 · Treiber** | HTTP-API-Treiber (OpenAI, OpenRouter) **oder** generischer CLI-Adapter — fremde Engine läuft als HTTP-Stream bzw. gesteuerter Subprozess wie Claude | Engine hat eine HTTP-API (OpenAI/OpenRouter) **oder** eine steuerbare CLI (Codex, Gemini, GLM, Ollama) | **Vollwertige Session** (Status/Ampel/Kanban), Live-Sicht ggf. eingeschränkt |
| **2 · iFrame** | Fremde Web-App wird eingebettet angezeigt | Tool ist eine Web-App, erlaubt Einbettung | **Eingebettete Kachel/Tab** — kein Session-Lifecycle |
| **3 · Startknopf** | Konfigurierbarer Button öffnet/startet ein externes Tool | Alles andere (kein CLI, keine Einbettung) | **Launch-Eintrag** — reiner Absprung |

Der Kern bleibt unangetastet: Die **`EngineDriver`-Abstraktion aus PROJ-1** (`base.py:38`) ist die **einzige Kopplung**. Neue Engines sind Plug-ins/Adapter, kein Eingriff in den Manager.

### Was schon trägt (aus PROJ-1/14/16 — kein Neubau nötig)
Die Architektur wurde bewusst engine-offen gebaut. Diese Teile sind **bereits engine-agnostisch** und werden unverändert wiederverwendet:
- **`EngineDriver`-ABC + `LaunchSpec`** (`base.py:38`, `:19`) — keine Claude-Annahmen; `driver_factory` ist schon injizierbar (`manager.py:912`).
- **Watchdog/Limits** (PROJ-16) — überwacht Tool-Aufrufe (Name+Input), nicht Claude-Metriken → gilt engine-übergreifend.
- **Persistenz/Rehydrierung** (PROJ-14) — speichert nur Metadaten (id/status/pid), `DeadDriver` rehydriert jede Engine.
- **Decision Cards / Trust-Policy** (PROJ-4/10) — Tool-Gating ist engine-unabhängig.
- **Graceful-Degradation-Haken existieren schon:** `context_known` (Bool) → Gauge zeigt „—" statt %; `rate_limit` nullbar; `total_cost_usd` als Float.

### Was Claude-hartverdrahtet ist (das eigentliche PROJ-18-Werk)
1. **Modell-Validierung** — `VALID_MODELS = {haiku,sonnet,opus}` (`config.py:20`) ist Claude-only.
2. **Stream-Parsing** — `events.py` nimmt Claudes `stream-json`-Form an (`message.content[]`, `modelUsage[]`, `rate_limit_event`).
3. **Verbrauchs-/Kosten-Extraktion** — Schlüssel wie `input_tokens`, `contextWindow`.
4. **CLI-Aufruf** — `build_argv()` baut Claude-spezifische Flags.
5. **Es gibt keine Engine-Registry** — Engines/iFrames/Launch-Einträge sind nirgends zentral konfigurierbar.

### A) Komponenten-Struktur

**Backend (Engine-Layer):**
```
engine/
├── base.py            EngineDriver-ABC + LaunchSpec        (UNVERÄNDERT — die eine Kopplung)
├── claude_driver.py   ClaudeCodeDriver                     (bleibt Default)
├── openai_driver.py   ★ NEU — OpenAIDriver (HTTP-API)      (Tiefe 1 — 1. Test-Engine OpenAI;
│     └── deckt auch OpenRouter ab: OpenAI-API-kompatibel → derselbe Treiber, nur anderer api_base/auth_env)
├── generic_cli_driver.py   ★ NEU — GenericCliDriver        (Tiefe 1 — fremde CLIs: Codex/Gemini/GLM/Ollama)
│     └── nutzt ein Engine-Profil (argv-Vorlage + Adapter) aus der Registry
├── adapters.py        ★ NEU — Strom→StreamEvent-Normalisierung je Protokoll
│     ├── claude     (bestehende events.py-Logik, herausgezogen)
│     ├── jsonl      generisch: 1 JSON/Zeile → Text/Result
│     └── plaintext  Engine ohne JSON → reine Textzeilen (Live-Sicht eingeschränkt)
├── registry.py        ★ NEU — EngineRegistry (lädt engines.yaml, mtime-watch)
│     └── Muster identisch zu PolicyStore/WatchdogStore (live-reload)
└── manager.py         driver_factory wählt Treiber je Engine-Profil  (kleine Erweiterung)
```

**Frontend:**
```
new-session-dialog.tsx   + Engine-Auswahl (Default „Claude Max")     (PROJ-9-Integration)
session-tile.tsx         Felder degradieren: kein Token/Kosten → „n/v"  (Härtung bestehender Anzeige)
components/embed/
├── EmbedTab.tsx         ★ NEU — iFrame-Kachel/Tab (Tiefe 2)
└── LaunchButton.tsx     ★ NEU — Startknopf (Tiefe 3)
ToolsPanel / Launcher    listet konfigurierte iFrames + Launch-Einträge aus /engines
```

### B) Datenmodell (Klartext)

**Engine-Profil** (zentral in `engines.yaml`, kein Code je Engine):
- `key` (z. B. `openai`, `openrouter`) · `label` (Anzeige, deutsch) · `kind` (`engine` | `iframe` | `launch`)
- Für `kind: engine` zusätzlich `driver` (`claude` | `openai` | `generic_cli`):
  - `driver: openai` (HTTP-API — **1. Test-Engine OpenAI**; **OpenRouter** ist OpenAI-API-kompatibel → **derselbe Treiber**, nur anderer `api_base`/`auth_env`): `api_base`, `api_path`, `auth_env` (Name der Key-Variable, **nie der Key selbst**), `models`, `default_model`, `context_window`, `capabilities` (z. B. `usage`, `multi_turn`)
  - `driver: generic_cli` (fremde CLI): `bin`/`argv_template` (Platzhalter für model/session_id/prompt/cwd), `adapter` (`claude`|`jsonl`|`plaintext`), `models`, `auth_env`, `capabilities`
- Für `iframe`: `url`, `sandbox`/CSP-Hinweise
- Für `launch`: `target` (URL oder lokaler Befehl/Absprung)

**Session** (Erweiterung des Live-Index um **ein** Feld):
- neu: `engine` (Default `claude`) — alle übrigen Felder unverändert
- engine-spezifische Felder (`tokens_used`, `context_fill_pct`, `total_cost_usd`, `rate_limit`) werden **nullbar/„n/v"** behandelt, wenn das Profil die Capability nicht hat.

Secrets (API-Keys für API-Engines) liegen **nur** serverseitig in `.env`, referenziert über `auth_env` — nie im Frontend, nie in `engines.yaml`.

### C) API-Form (nur Endpunkte)
```
GET   /engines                → konfigurierte Engines/iFrames/Launch-Einträge (für Launcher + Selector)
                                je Eintrag: key, label, kind, verfügbar?(Key/bin vorhanden), capabilities
POST  /sessions               → + Feld `engine` (Default „claude"); validiert Modell gegen das Engine-Profil
GET/POST /sessions/{id}/...    → unverändert (start/input/pause/stop/transcript/stream) — engine-agnostisch
```
- iFrame & Launch brauchen **keinen** Session-Lifecycle — sie werden allein über `GET /engines` beschrieben und im Frontend gerendert.
- `GET /engines` meldet je Engine `available: true|false` + Grund (fehlender Key/`bin`) → Frontend graut aus statt zu crashen.

### D) Tech-Entscheidungen (warum)
- **OpenAI (API) als erste Test-Engine, OpenRouter als zweite — beide über *einen* HTTP-Treiber.** Eine echte API-Engine ist der aussagekräftigste Abstraktions-Nachweis: sie liefert echte Usage (`prompt/completion_tokens`) → Token-/Kontext-Anzeige funktioniert ohne Sonderfall. **OpenRouter ist OpenAI-API-kompatibel** (gleiches `/chat/completions`, SSE-Stream) → es genügt ein zweites Profil mit anderem `api_base`/`auth_env`, **kein neuer Code**. Damit beweist *ein* `OpenAIDriver` die Treiber-Abstraktion über **zwei Anbieter** — stärker als ein lokaler Einzelfall (Ollama). Ollama/Codex bleiben als `generic_cli`-Beispiele erhalten, sind aber nicht mehr die Referenz-Test-Engine.
- **Generischer CLI-Treiber + Adapter-Schicht statt je-Engine-Treiber-Klasse.** Ein `GenericCliDriver` liest sein Verhalten aus dem Engine-Profil; die **Strom-Normalisierung** kapselt ein austauschbarer Adapter. So kommt eine neue Engine i. d. R. **ohne Code** dazu (nur `engines.yaml`) — und erfüllt AC „Konfiguration ohne Codeänderung pro Variante".
- **Drei Adapter decken das Spektrum:** `claude` (bestehend, nur herausgezogen), `jsonl` (viele CLIs streamen 1 JSON/Zeile), `plaintext` (Fallback — Live-Sicht degradiert sichtbar statt zu crashen). Erfüllt Edge-Case „kein Stream-JSON".
- **Registry nach bewährtem Muster (PolicyStore/WatchdogStore).** YAML + mtime-Watch, live nachladbar — konsistent mit PROJ-10/16, kein neues Infra-Konzept.
- **Engine als eigenes Feld, nicht aus dem Modellnamen abgeleitet.** Explizit > implizit; vermeidet Namenskollisionen (z. B. „gemini-pro") und hält die Modell-Validierung sauber pro Profil.
- **iFrame defensiv:** Einbettung kann scheitern (`X-Frame-Options`/CSP der Fremdseite — das kontrollieren **wir nicht**). Daher: iFrame versuchen, bei Verweigerung **klarer Hinweis + automatischer Fallback auf Launch-Button**. CSP/`frame-src` DSGVO-konform pflegen, keine US-CDNs erzwingen.
- **Degradation ist Pflicht, nicht Kür.** Fehlende Engine/Key/Capability → „n/v" bzw. ausgegraut + deutsche Meldung; **Claude bleibt immer nutzbar** (Default, isolierter Pfad). Watchdog/Limit gilt engine-übergreifend (PROJ-14/16).
- **Claude bleibt Default & unverändert.** Der `ClaudeCodeDriver` ist ein Spezialfall des generischen Wegs (eigenes Profil), kein Bruch — Rückwärtskompatibilität by design.

### E) Abhängigkeiten
- **Backend:** keine neuen Pflicht-Pakete — `pyyaml` (bereits für Policy/Watchdog vorhanden), `asyncio.subprocess` (stdlib), `httpx` (bereits vorhanden) für den OpenAI/OpenRouter-HTTP-Treiber. **Kein Anbieter-SDK** nötig: OpenAI *und* OpenRouter laufen über die rohe OpenAI-kompatible HTTP-API.
- **Frontend:** keine neuen — iFrame ist nativ; Launch-Button native Navigation/Window-Open.
- **Extern (optional, je nach aktivierter Engine):** für die HTTP-Test-Engines genügt **ein API-Key** (`OPENAI_API_KEY` bzw. `OPENROUTER_API_KEY`) in der Server-Umgebung — keine CLI-Installation. Für `generic_cli`-Engines muss die jeweilige CLI (`codex`, `gemini`, `ollama`, …) auf dem VPS installiert/eingeloggt sein; sonst meldet `/engines` die Engine als nicht verfügbar.

### Abgrenzung / Scope
- **Im Scope:** HTTP-API-Treiber + generischer CLI-Treiber + **zwei exemplarische Test-Engines** als Nachweis der Abstraktion — **OpenAI (API)** als erste und **OpenRouter** als zweite (OpenAI-kompatibel → derselbe Treiber, nur anderer `api_base`) —, iFrame-Einbettung, Launch-Button, Engine-Selector im Launcher, engine-agnostische Session-Sicht mit Degradation, deutsche Texte.
- **Nicht im Scope (Folge-Features):** Modell-Routing-Strategie über Engines hinweg (PROJ-22), engine-übergreifender Cross-Review (PROJ-23), Vault als geteilter Dienst für eingebettete Apps (PROJ-24). PROJ-18 liefert nur die **Voraussetzung** (Multi-Engine-Fähigkeit).

### Zuständigkeiten (Handoff)
- **Backend:** `registry.py`, `openai_driver.py` (HTTP-Treiber für OpenAI **und** OpenRouter), `generic_cli_driver.py`, `adapters.py`, `events.py`-Refaktor (Claude-Logik in den `claude`-Adapter ziehen), `manager.py`-driver_factory-Erweiterung, `engine`-Feld + `GET /engines`, `engines.yaml` (OpenAI- + OpenRouter-Profil).
- **Frontend:** Engine-Selector im `new-session-dialog`, `EmbedTab`, `LaunchButton`, „n/v"-Degradation in `session-tile`, Ausgrau-/Fehlermeldungslogik aus `/engines`.

## Implementierung (Backend) — 2026-06-24
**Branch:** dev · **Status:** Backend steht, Tests grün (26 PROJ-18-Tests, Gesamtsuite 475 passed).

**Neu:**
- `engine/registry.py` — `EngineRegistry` (YAML, live mtime-reload nach PolicyStore-Muster); Claude immer eingebaut → rückwärtskompatibel. Defekte Einträge/Datei degradieren auf „nur Claude" + Warnung, kein Crash.
- `engine/openai_driver.py` — HTTP-Treiber (`OpenAIDriver`). **Erste Test-Engine OpenAI**; **OpenRouter** läuft über **denselben** Treiber (OpenAI-API-kompatibel → nur anderer `api_base`/`auth_env`). SSE-Streaming → Claude-förmige Events; Usage → Token-/Kontext-Anzeige; Key nur serverseitig aus `auth_env`.
- `engine/generic_cli_driver.py` + `engine/adapters.py` (`claude`/`jsonl`/`plaintext`) — fremde CLIs (Codex/Gemini/GLM/Ollama) ohne Code pro Engine.
- `routes/engines.py` + `schemas/engines.py` — `GET /engines` (secret-frei, `available` + deutscher `unavailable_reason`).
- `config/engines.example.yaml` — OpenAI (1.) + OpenRouter (2.) als Test-Engines; Ollama/Codex als `generic_cli`-Beispiele.

**Geändert:**
- `engine/manager.py` — `engine`-Feld an `SessionState`; `driver_factory` wählt Treiber je Profil (`_make_driver`); Verfügbarkeit + Modell-Validierung pro Profil; neue `EngineUnavailableError`.
- `schemas/sessions.py` — `engine`-Feld in `SessionCreate`/`SessionRead`; strikte Claude-Modell-Whitelist nur noch für `engine=claude`.
- `routes/sessions.py` — `engine` durchgereicht; `EngineUnavailableError` → **HTTP 503**, unbekannte Engine/Modell → **400**.
- `main.py` — `create_app(engine_factory=…)` als Test-Seam (symmetrisch zu `driver_factory`).

**Verifizierte AC:** generischer Treiber (✓), zwei Test-Engines exemplarisch lauffähig — OpenAI + OpenRouter über *einen* Treiber (✓), engine-agnostische Session-Sicht + Degradation (✓), Engine-Auswahl in `POST /sessions`, Claude bleibt Default (✓), fehlende Engine/Key → klare Meldung, kein Crash (✓), deutsche Texte (✓).
**Offen (nicht im Backend-Scope):** Frontend — Engine-Selector im `new-session-dialog`, `EmbedTab` (iFrame), `LaunchButton`, „n/v"-Degradation im `session-tile`. Realer Smoke-Turn gegen echte OpenAI-/OpenRouter-Keys (`/abc-qa-e2e`).

## Implementierung (Frontend) — 2026-06-24
**Branch:** dev · **Stack:** Next.js 16 + shadcn/ui (Base UI) + Tailwind · **Status:** Frontend steht, `tsc`/ESLint/`next build` grün, 64 Vitest-Tests grün.

**Neu:**
- `components/cockpit/launch-button.tsx` — Tiefe 3: Startknopf. Web-URL → neuer Tab (`rel=noopener`); lokaler Befehl (keine URL) → „Befehl kopieren" (im Browser nicht ausführbar).
- `components/cockpit/embed-tab.tsx` — Tiefe 2: iFrame-Einbettung mit `sandbox` aus dem Profil; persistenter Fallback „In neuem Tab öffnen" + deutscher Hinweis, falls die Fremdseite die Einbettung verweigert (X-Frame-Options/CSP — von uns nicht erkennbar, daher immer Fallback).
- `components/cockpit/tools-panel.tsx` — lädt `GET /engines`, rendert iFrame-Apps + Startknöpfe; zeigt Registry-`warning`; leer-/Fehler-Zustand mit Hinweis auf `config/engines.yaml`.

**Geändert:**
- `lib/types.ts` — `engine` an `Session` (Pflicht) + `engine?` an `SessionCreate`; neue Typen `EngineKind`/`EngineRead`/`EnginesOverview`; `SessionCreate.model` von `ModelName` auf `string` gelockert (Fremd-Engine-Modelle).
- `lib/api.ts` — `getEngines()` (`GET /engines`).
- `lib/status.ts` — `engineShowsCost()` + `costLabel()` (nur Claude liefert echte Kosten → sonst „n/v").
- `components/cockpit/new-session-dialog.tsx` — Engine-Selector (Default „Claude Max"); nicht verfügbare Engines ausgegraut + deutscher Setup-Hinweis; Modell-Liste folgt dem Engine-Profil; `engine` wird an `createSession` durchgereicht; Submit blockiert bei nicht verfügbarer Engine. Fällt ohne Backend-Antwort sauber auf den Claude-Fallback zurück.
- `components/cockpit/session-tile.tsx` — „n/v"-Degradation der Kosten + Engine-Badge für Nicht-Claude-Sessions (engine-agnostische Sicht; PROJ-27-Heartbeat-Zeilen unberührt).
- `app/(cockpit)/page.tsx` — neuer Tab „Werkzeuge" (`ToolsPanel`).
- Test-Fixtures (`lib/status.test.ts`, `gantt-chart.test.tsx`) um `engine: "claude"` ergänzt.

**Bekannte Einschränkung:** Der „Werkzeuge"-Tab liegt innerhalb des Session-Boards und ist daher nur sichtbar, wenn ≥1 Session existiert (Empty-State zeigt vorher nur den Start-Hinweis). Reicht für die AC; ein immer sichtbares Panel wäre ein kleiner Folge-Schliff.

## QA Test Results — Runde 1 (Backend)

**Tested:** 2026-06-24
**Backend:** pytest gegen den **committeten** Stand (HEAD `1c9c5a7`, isolierte Worktree) — env `Dashboard`
**Frontend:** nicht getestet — die Frontend-Deliverables (iFrame-Tab, Launch-Button, Engine-Selector, „n/v"-Degradation) sind laut Backend-Implementierungsnotiz **noch nicht gebaut** (offener Handoff).
**Tester:** QA Engineer (AI)
**Scope:** Backend-Lieferumfang von PROJ-18 (Registry, OpenAI-/OpenRouter-HTTP-Treiber, generischer CLI-Treiber, Adapter, `GET /engines`, `engine`-Feld in `POST /sessions`).

### ⚠️ Blocker am `dev`-Arbeitsbaum (NICHT PROJ-18)
Der **uncommittete** Arbeitsbaum von `dev` ist **nicht lauffähig**: `backend/app/schemas/settings.py:125` enthält einen **Syntaxfehler** (Fremd-Feature **PROJ-27 Liveness**, WIP). Ein ASCII-`"` schließt den String vorzeitig:
```
progress_timeout_seconds: int = Field(..., gt=0, description="Kein Fortschritt > X s → „hängt".")
                                                                                            ^ ASCII-" statt „…"
```
→ `SyntaxError: unterminated string literal` ⇒ **das gesamte Backend importiert nicht**, keine Tests/kein `uvicorn` laufen im Arbeitsbaum. PROJ-18 selbst ist davon nicht betroffen (sauber committet); QA erfolgte daher gegen HEAD in einer separaten Worktree. **Muss vor jedem Deploy/QA-Lauf auf `dev` gefixt werden** (PROJ-27-Owner), siehe BUG-1.

### Automatisierte Tests
- **PROJ-18-Suite** `tests/test_proj18_engines.py`: **26 passed** (Registry, Adapter, OpenAIDriver für beide Anbieter, `GET /engines`, `POST /sessions`).
- **Gesamtsuite Backend: 475 passed** (keine Regression durch PROJ-18).

### Acceptance Criteria Status (Backend-Scope)

#### AC-1: Generischer CLI-Treiber, gleiches Interface, per Konfig gemappt
- [x] `GenericCliDriver` erfüllt `EngineDriver` (start/send_input/pause/stop/is_alive/pid)
- [x] Verhalten (argv, prompt_via, input_format, adapter) kommt aus `engines.yaml` — kein Code pro Engine

#### AC-2: OpenAI (1.) + OpenRouter (2.) über *einen* HTTP-Treiber
- [x] Ein `OpenAIDriver` fährt beide Anbieter (parametrisierter Test über `api_base`/`auth_env`)
- [x] SSE-Stream → Claude-förmige Events; Usage → Token-/Kontext-Anzeige; Key nur serverseitig

#### AC-3: iFrame-Einbettung (DSGVO/CSP)
- [~] Backend liefert iFrame-Profile (`kind: iframe`, `url`, `sandbox`) über `GET /engines` (verifiziert). **Rendering/CSP im Frontend nicht gebaut** → AC nur backendseitig erfüllt.

#### AC-4: Launch-Button
- [~] Backend liefert Launch-Einträge (`kind: launch`, `target`). **Button im Frontend nicht gebaut.**

#### AC-5: Engine-agnostische Session-Sicht + saubere Degradation
- [x] `engine`-Feld an `SessionState`/`SessionRead`; Usage nullbar → „n/v"-Haken vorhanden (Backend)
- [~] „n/v"-Anzeige im `session-tile` (Frontend) nicht gebaut

#### AC-6: Engine-Auswahl im Smart Launcher; Claude bleibt Default
- [x] `POST /sessions` akzeptiert `engine` (Default `claude`, verifiziert)
- [~] Selector im `new-session-dialog` (Frontend) nicht gebaut

#### AC-7: Fehlende/fehlkonfigurierte Engine → klare Meldung, kein Crash, Claude nutzbar
- [x] Unbekannte Engine → 400; fehlender Key/CLI → 503 mit deutschem Hinweis; kaputtes/fehlendes YAML → nur Claude + Warnung
- [x] Claude läuft auf isoliertem Pfad (Default), unabhängig von defekten Profilen

#### AC-8: Alle Texte deutsch
- [x] Alle Treiber-/Registry-/Route-Meldungen deutsch

### Edge Cases Status
- [x] **EC-1** Engine ohne Stream-JSON → `plaintext`-Adapter degradiert sichtbar (kein Crash)
- [x] **EC-2** iFrame verweigert Einbettung → Profil trägt `sandbox`; Fallback-Rendering ist Frontend-Aufgabe (nicht testbar)
- [x] **EC-3** Engine ohne Usage → result-Event ohne `usage`/`modelUsage` → Anzeige „n/v"
- [x] **EC-4** Auth/Key fehlt → Engine ausgegraut (`available:false` + Grund), Start → 503
- [x] **EC-5** Defekter Einzel-Eintrag wird übersprungen, Rest lädt (mit Warnung)

### Security Audit Results
- [x] **Secret-frei:** `GET /engines` und `EngineProfile.to_read()` enthalten **kein** `auth_env`/`bin`/`argv` (Test verifiziert). API-Keys nur serverseitig aus `os.environ`.
- [x] **Keine Shell-Injection:** `GenericCliDriver` nutzt `create_subprocess_exec(*argv)` (kein Shell), `{prompt}`/`{model}`-Substitution landet als einzelnes argv-Element — keine Shell-Interpretation.
- [x] **Kein SQL/DB-Schreibpfad** in diesem Feature (Registry ist read-only YAML; Live-Index-Persistenz nutzt bestehende parametrisierte Helfer).
- [x] **Auth/Tenant:** unverändert zum MVP (kein JWT/RLS im MVP, siehe Stack-Overrides) — kein neuer Angriffsvektor.
- [i] **iFrame-URL-Schema wird nicht validiert** (`url: javascript:…` würde übernommen). Quelle ist die *server-seitige, operator-kontrollierte* `engines.yaml` (kein User-Input) → kein praktischer Vektor; dennoch sollte das Frontend `frame-src`/CSP strikt setzen und nur `https:` erlauben. Informativ.

### Bugs Found

#### BUG-1: `dev`-Arbeitsbaum nicht lauffähig — Syntaxfehler in `schemas/settings.py` (Fremd-Feature PROJ-27) — ✅ BEHOBEN (2026-06-24)
- **Severity:** Critical (build-breaking) — **gehörte zu PROJ-27, nicht PROJ-18**
- **Steps to Reproduce:**
  1. Auf `dev` (Arbeitsbaum) `conda run -n Dashboard python -m pytest backend/tests` ausführen
  2. Erwartet: Tests laufen
  3. Tatsächlich: `SyntaxError: unterminated string literal` in `backend/app/schemas/settings.py:125` → Collection bricht ab, Backend importiert nicht
- **Fix:** Zeile auf ASCII-sauberen Text geändert (`"Kein Fortschritt seit > X s gilt als haengt."`) — vom PROJ-27-Owner. Verifiziert: `ast.parse` OK, Gesamtsuite collected wieder vollständig (498 passed).
- **Priority:** Fix before deployment ✅ erledigt

#### BUG-2: `generic_cli` mit `argv_template` ohne `bin` ist dauerhaft „nicht verfügbar" — ✅ BEHOBEN (2026-06-24)
- **Severity:** Low
- **Steps to Reproduce:**
  1. In `engines.yaml` eine `driver: generic_cli`-Engine **nur** mit `argv_template` (Binary als erstes Element), **ohne** `bin`, konfigurieren — der Registry-Parser (`_coerce_profile`) **akzeptiert** das (`bin` ODER `argv_template` genügt)
  2. `build_generic_argv` baut korrekt ein lauffähiges argv (z. B. `['/bin/echo','hi']`)
  3. Erwartet: Engine ist verfügbar/startbar
  4. Tatsächlich (vorher): `EngineProfile.availability()` prüfte nur `self.bin` → lieferte immer `(False, "CLI „?" nicht im PATH gefunden.")` → `GET /engines` graut aus, `POST /sessions` → 503. Die Engine konnte nie starten.
- **Fix:** `availability()` (registry.py) fällt nun auf `argv_template[0]` zurück, wenn `bin` fehlt — konsistent mit `_coerce_profile` und `build_generic_argv`. Regressionstest `test_generic_cli_without_bin_uses_argv_template_head` hinzugefügt.
- **Priority:** Fix in next sprint ✅ vorgezogen erledigt

### Empfehlung Real-Smoke (für `/abc-qa-e2e`)
- Echter Turn gegen reale `OPENAI_API_KEY`/`OPENROUTER_API_KEY`-Schlüssel (Stream + Usage end-to-end).
- OpenRouter empfiehlt die Header `HTTP-Referer` + `X-Title`; der Treiber sendet sie nicht. Ohne sie funktioniert OpenRouter i. d. R., kann aber Einschränkungen erfahren — beim Real-Smoke prüfen, ggf. als kleine Treiber-Ergänzung nachziehen.

### Summary (Backend)
- **Acceptance Criteria (Backend-Scope):** 5/8 voll bestanden (AC-1,2,5*,7,8); 3 teilweise (AC-3,4,6) — backendseitig erfüllt; Frontend-Anteil siehe Runde 2.
- **Bugs Found:** 2 — **beide behoben (2026-06-24)**. BUG-1 (Critical, *außerhalb* PROJ-18 / PROJ-27) ✅, BUG-2 (Low, PROJ-18) ✅ inkl. Regressionstest.
- **Tests nach Fix:** PROJ-18-Suite **27 passed**.
- **Security:** Pass (secret-frei, keine Shell-Injection, kein neuer DB-/Auth-Vektor).
- **Production Ready (Backend):** solide, grün, ohne offene Bugs.

---

## QA Test Results — Runde 2 (Frontend)

**Tested:** 2026-06-24 · **Stack:** Next.js 16 + shadcn/ui (Base UI) · **Tester:** QA Engineer (AI)
**Scope:** PROJ-18-Frontend (Engine-Selector, iFrame-Tab, Launch-Button, „n/v"-Degradation, Werkzeuge-Tab).

### Automatisierte Tests
- **Frontend (Vitest): 75 passed** (64 vorher + **11 neue PROJ-18-Tests**): `costLabel`/`engineShowsCost` (2), `LaunchButton` (3), `EmbedTab` (3), `SessionTile`-Degradation (3).
- **`next build` grün** (TypeScript + Lint im Build), **ESLint** der geänderten Dateien sauber, `tsc --noEmit` ohne neue Fehler (einziger Rest: vorbestehender, fremder `md-tree.test.ts`).
- **PROJ-18-Backend-Suite weiterhin 27/27 grün** — keine Regression durch die Frontend-Arbeit.

### Acceptance Criteria (Frontend) — jetzt erfüllt
- [x] **AC-3 iFrame:** `EmbedTab` rendert iFrame mit `src` + `sandbox` aus dem Profil; **immer** Launch-Fallback („In neuem Tab öffnen") für X-Frame-Options/CSP-Verweigerung (Render-Test verifiziert).
- [x] **AC-4 Launch-Button:** Web-URL → neuer Tab (`rel=noopener`); lokaler Befehl → „Befehl kopieren"; `javascript:`-Ziel wird **nicht** als Link geöffnet (Test verifiziert).
- [x] **AC-5 Degradation:** Fremd-Engine → Kosten „n/v" + Engine-Badge; Claude unverändert ($-Betrag, kein Badge); Engine ohne Token-Daten → Kontext „unbekannt" (Render-Tests verifiziert).
- [x] **AC-6 Engine-Auswahl im Launcher:** Selector im „Neue Session"-Dialog (Default „Claude Max"); nicht verfügbare Engines ausgegraut + deutscher Setup-Hinweis; Modell-Liste folgt dem Profil; Fallback auf Claude bei `/engines`-Fehler.

### Security-Review (Frontend)
- [x] **Kein Secret im Client:** Engine-Selector/Tools nutzen nur `GET /engines` (secret-frei); kein API-Key erreicht das Frontend.
- [x] **Kein XSS-Absprung über Launch:** nur `http(s)`-Ziele werden geöffnet; `javascript:`/Befehle landen im Kopier-Pfad (Test).
- [i] **iFrame-`sandbox` optional:** fehlt `sandbox` im Profil, läuft die eingebettete App ohne Sandbox. Quelle ist die operator-kontrollierte `engines.yaml` (kein User-Input) → kein praktischer Vektor; Empfehlung: im Beispiel/Doku `sandbox` als Best Practice führen.

### Bugs / Befunde (Frontend)
- **Keine Critical/High/Medium.**
- **BUG-3 (Low, Known Limitation):** Der „Werkzeuge"-Tab liegt innerhalb des Session-Boards → nur sichtbar, wenn ≥1 Session existiert. Reicht für die AC; ein immer sichtbares Panel wäre ein Folge-Schliff.

### ⚠️ Branch-weite Regression (NICHT PROJ-18 — gehört zu PROJ-27)
Beim Gesamt-Suite-Lauf auf `dev` fallen **3 stabile Tests** — **alle in PROJ-27** (Liveness), PROJ-18 ist sauber:
- `test_proj27_liveness.py::test_put_liveness_live` — **`PUT /settings/liveness` liefert 422 statt 200** (echter PROJ-27-Bug: Schema/Route weist eine gültige Nutzlast ab).
- `test_proj27_qa.py::test_bug1_long_toolcall_*` (2×) — `xfail(strict)`-Tests, die **nichtdeterministisch XPASSen** → Test-Isolations-/Reihenfolge-Problem (PROJ-27; eigentlicher Fix als **PROJ-32** geplant). Bei zufälliger Reihenfolge eskaliert die Pollution auf bis zu ~23 Fehler quer durch fremde Dateien (z. B. `test_proj8_gantt`), die isoliert grün sind.

→ **Aktion für den PROJ-27-Owner**, nicht PROJ-18. Blockiert aber einen sauberen Branch-weiten Suite-Lauf/Deploy, solange offen.

### Empfehlung
- **PROJ-18 (Backend + Frontend) ist abgenommen** — keine Critical/High/Medium-Bugs; Code-Level grün.
- **Vor Deploy:** `/abc-qa-e2e` (realer Turn gegen echte `OPENAI_API_KEY`/`OPENROUTER_API_KEY` — die Unit-/Integrationstests mocken HTTP) **und** die PROJ-27-Reds fixen (sonst ist `dev` nicht sauber deploybar).

---

## Gesamtbewertung PROJ-18 (nach Runde 2)
- **Acceptance Criteria gesamt:** 8/8 erfüllt (Backend + Frontend), durch Tests verifiziert.
- **Bugs:** BUG-1 (PROJ-27) ✅, BUG-2 (PROJ-18) ✅ — beide behoben; **keine offenen Critical/High/Medium in PROJ-18**. BUG-3 (Low, Werkzeuge-Tab-Sichtbarkeit) als Folge-Schliff notiert.
- **Tests:** Backend PROJ-18 **27/27**, Frontend **75/75** (inkl. 11 neue).
- **Production-Ready:** **PROJ-18 abgenommen (Approved).** Vor einem `dev`-Deploy noch nötig (nicht PROJ-18): `/abc-qa-e2e` (Real-Smoke gegen echte Keys) **und** die 3 PROJ-27-Reds (`PUT /settings/liveness` 422 + xfail-strict-Flakiness).

## Deployment
_To be added by /abc-deploy_
