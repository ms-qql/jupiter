# PROJ-18: Weitere Engines (Codex/Gemini/GLM/Ollama) + iFrame/Launch

## Status: Architected
**Created:** 2026-06-23
**Last Updated:** 2026-06-24
**Baustein:** #13

## Dependencies
- Requires: PROJ-1 (Engine-Treiber-Modell) — das Treiber-Interface ist die Abstraktion, gegen die neue Engines gebaut werden.
- Verwandt: PROJ-22 (Modell-Routing) und P2 Cross-Agent-Review (#30), das Multi-Engine voraussetzt.

## Beschreibung
Das Integrations-Spektrum aus drei Tiefen — **Treiber → iFrame → Startknopf** — macht Integration zu keinem Alles-oder-nichts: ein generischer **CLI-Adapter** für weitere Engines (Codex/Gemini/GLM/Ollama), das **Einbetten** fremder Web-Apps als iFrame, und ein simpler **Launch-Button** für alles andere. Nach oben sehen alle Engines gleich aus (gleiche Session-Sicht).

## User Stories
- Als Nutzer möchte ich beim Session-Start neben Claude Max weitere Engines wählen können (sofern konfiguriert).
- Als Nutzer möchte ich eine fremde Engine über einen **generischen CLI-Adapter** einbinden, ohne Jupiters Kern zu ändern.
- Als Nutzer möchte ich eine fremde Web-App (z. B. ein Tool) als **iFrame** in Jupiter einbetten.
- Als Nutzer möchte ich für nicht integrierbare Tools einen einfachen **Startknopf** (öffnet/launcht extern).
- Als Nutzer möchte ich, dass eine Nicht-Claude-Session in Cockpit/Kanban genauso erscheint wie eine Claude-Session.

## Acceptance Criteria
- [ ] Ein **generischer CLI-Treiber** implementiert dasselbe Treiber-Interface wie der Claude-Treiber (start/lesen/steuern/stop) und kann per Konfiguration auf andere CLI-Engines gemappt werden.
- [ ] Mindestens eine zweite Engine ist exemplarisch lauffähig integriert (Treiber-Tiefe), als Nachweis der Abstraktion.
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
| **1 · Treiber** | Generischer CLI-Adapter — fremde Engine läuft als gesteuerter Subprozess wie Claude | Engine hat eine steuerbare CLI (Codex, Gemini, GLM, Ollama) | **Vollwertige Session** (Status/Ampel/Kanban), Live-Sicht ggf. eingeschränkt |
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
├── generic_cli_driver.py   ★ NEU — GenericCliDriver        (Tiefe 1)
│     └── nutzt ein Engine-Profil (argv-Vorlage + Adapter) aus der Registry
├── adapters/          ★ NEU — Strom→StreamEvent-Normalisierung je Protokoll
│     ├── claude_adapter   (bestehende events.py-Logik, herausgezogen)
│     ├── jsonl_adapter    generisch: 1 JSON/Zeile → Text/Result
│     └── plaintext_adapter  Engine ohne JSON → reine Textzeilen (Live-Sicht eingeschränkt)
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
- `key` (z. B. `ollama`, `gemini`) · `label` (Anzeige, deutsch) · `kind` (`cli` | `iframe` | `launch`)
- Für `cli`: `bin`/`argv_template` (Platzhalter für model/session_id/prompt/cwd), `adapter` (`claude`|`jsonl`|`plaintext`), `models` (erlaubte Modell-Namen), `auth_env` (Name der erwarteten Key-Variable, **nie der Key selbst**), `capabilities` (z. B. `usage`, `resume`, `multi_turn`)
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
- **Generischer CLI-Treiber + Adapter-Schicht statt je-Engine-Treiber-Klasse.** Ein `GenericCliDriver` liest sein Verhalten aus dem Engine-Profil; die **Strom-Normalisierung** kapselt ein austauschbarer Adapter. So kommt eine neue Engine i. d. R. **ohne Code** dazu (nur `engines.yaml`) — und erfüllt AC „Konfiguration ohne Codeänderung pro Variante".
- **Drei Adapter decken das Spektrum:** `claude` (bestehend, nur herausgezogen), `jsonl` (viele CLIs streamen 1 JSON/Zeile), `plaintext` (Fallback — Live-Sicht degradiert sichtbar statt zu crashen). Erfüllt Edge-Case „kein Stream-JSON".
- **Registry nach bewährtem Muster (PolicyStore/WatchdogStore).** YAML + mtime-Watch, live nachladbar — konsistent mit PROJ-10/16, kein neues Infra-Konzept.
- **Engine als eigenes Feld, nicht aus dem Modellnamen abgeleitet.** Explizit > implizit; vermeidet Namenskollisionen (z. B. „gemini-pro") und hält die Modell-Validierung sauber pro Profil.
- **iFrame defensiv:** Einbettung kann scheitern (`X-Frame-Options`/CSP der Fremdseite — das kontrollieren **wir nicht**). Daher: iFrame versuchen, bei Verweigerung **klarer Hinweis + automatischer Fallback auf Launch-Button**. CSP/`frame-src` DSGVO-konform pflegen, keine US-CDNs erzwingen.
- **Degradation ist Pflicht, nicht Kür.** Fehlende Engine/Key/Capability → „n/v" bzw. ausgegraut + deutsche Meldung; **Claude bleibt immer nutzbar** (Default, isolierter Pfad). Watchdog/Limit gilt engine-übergreifend (PROJ-14/16).
- **Claude bleibt Default & unverändert.** Der `ClaudeCodeDriver` ist ein Spezialfall des generischen Wegs (eigenes Profil), kein Bruch — Rückwärtskompatibilität by design.

### E) Abhängigkeiten
- **Backend:** keine neuen Pflicht-Pakete — `pyyaml` (bereits für Policy/Watchdog vorhanden), `asyncio.subprocess` (stdlib). Optionale API-Engines (Gemini/GLM) brauchen **kein** SDK, wenn per CLI integriert; sonst pro Engine separat (außerhalb des Kerns).
- **Frontend:** keine neuen — iFrame ist nativ; Launch-Button native Navigation/Window-Open.
- **Extern (optional, je nach aktivierter Engine):** die jeweilige CLI (`codex`, `gemini`, `ollama`, …) muss auf dem VPS installiert/eingeloggt sein; sonst meldet `/engines` die Engine als nicht verfügbar.

### Abgrenzung / Scope
- **Im Scope:** generischer CLI-Treiber + ≥1 zweite Engine exemplarisch (Nachweis der Abstraktion, z. B. **Ollama** — lokal, kein Key, schnellster Nachweis), iFrame-Einbettung, Launch-Button, Engine-Selector im Launcher, engine-agnostische Session-Sicht mit Degradation, deutsche Texte.
- **Nicht im Scope (Folge-Features):** Modell-Routing-Strategie über Engines hinweg (PROJ-22), engine-übergreifender Cross-Review (PROJ-23), Vault als geteilter Dienst für eingebettete Apps (PROJ-24). PROJ-18 liefert nur die **Voraussetzung** (Multi-Engine-Fähigkeit).

### Zuständigkeiten (Handoff)
- **Backend:** `registry.py`, `generic_cli_driver.py`, `adapters/*`, `events.py`-Refaktor (Claude-Logik in `claude_adapter` ziehen), `manager.py`-driver_factory-Erweiterung, `engine`-Feld + `GET /engines`, `engines.yaml`.
- **Frontend:** Engine-Selector im `new-session-dialog`, `EmbedTab`, `LaunchButton`, „n/v"-Degradation in `session-tile`, Ausgrau-/Fehlermeldungslogik aus `/engines`.

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
