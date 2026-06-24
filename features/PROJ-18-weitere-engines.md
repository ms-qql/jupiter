# PROJ-18: Weitere Engines (Codex/Gemini/GLM/Ollama) + iFrame/Launch

## Status: Architected
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

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
