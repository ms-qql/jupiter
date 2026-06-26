# PROJ-48: Engine — OpenAI Codex CLI (Pro-Subscription) als Jupiter-Agent

## Status: Architected
**Created:** 2026-06-26
**Last Updated:** 2026-06-26

## Dependencies
- Requires: PROJ-18 (Weitere Engines + iFrame/Launch) — liefert die Engine-Registry (`engines.yaml`, live mtime-Reload), den `generic_cli`-Treiber (`backend/app/engine/generic_cli_driver.py`) und die Adapter-Schicht (`backend/app/engine/adapters.py`). **Hier dockt Codex an.**
- Requires: PROJ-1 (Engine-Treiber) — die Treiber-Schnittstelle (`start`/`send_input`/`stop`/Event-Strom), die `generic_cli` erfüllt.
- Verwandt: PROJ-19 (Effizienz/Token-Dashboard) — Codex liefert **echte** Usage (s. u.), die in die Token-/Kontext-Anzeige fließen kann.
- Verwandt: PROJ-9 (Smart Launcher) — Codex erscheint als wählbare Engine im Neue-Session-Dialog wie die übrigen.
- **Degradiert bewusst** (wie `hermes`): generic_cli hat **keinen** PreToolUse-Hook → **keine** Decision Cards (PROJ-4), **kein** Phasen-Gate (PROJ-10/30), **kein** Amok-Watchdog am Tool-Gate (PROJ-16). Bei Codex ist die **Sandbox-Policy die einzige Leitplanke** (s. „Offene Design-Fragen").

## Kontext / Ziel
Der Nutzer hat eine **OpenAI-Codex-Pro-Subscription** und die `codex`-CLI auf dem VPS installiert + eingeloggt. Ziel: Codex als **wählbare Engine** in Jupiter nutzen — genauso gestartet/gesteuert wie die anderen Agenten (Smart Launcher → Session → Cockpit/Kanban/Liveness/Persistenz greifen engine-agnostisch).

## Verifizierte Befunde (2026-06-26, am Live-System geprüft — nicht erneut suchen)
- **Auth steht:** `codex login status` → „Logged in using ChatGPT"; Credentials in `~/.codex/auth.json`. Jupiter spawnt Subprozesse als User `dev` mit `HOME=/home/dev` → Codex nutzt **dieselbe Subscription-Auth wie Claude Max**. **Kein API-Key/`auth_env` nötig.**
- **CLI:** `codex-cli 0.142.2`, Binär `/home/dev/.local/bin/codex`. Non-interaktiv: `codex exec [PROMPT]`.
  - Prompt via **arg ODER stdin** (`-`/piped). `-m, --model <MODEL>`. `-s, --sandbox {read-only|workspace-write|danger-full-access}`. `--json` → **Events als JSONL auf stdout**. `codex exec resume --last` → vorige Session fortsetzen (Multi-Turn).
- **Treiber vorhanden + erprobt:** `generic_cli`-Treiber existiert; `hermes` läuft produktiv darüber (oneshot, `prompt_via: arg`, `plaintext`-Adapter). Es gibt einen **vorbereiteten `codex`-Beispiel-Eintrag** in `engines.example.yaml` (Ausgangspunkt, aber unvollständig — s. nächster Punkt).
- **⚠️ Adapter-Lücke (der eigentliche Code-Anteil):** der generische `jsonl`-Adapter (`adapters.py`) erwartet Text in **Top-Level**-Keys (`text/content/output/response/delta/token`) und `done`-Marker (`done/stop/completed/final`). Codex liefert aber **verschachtelt**:
  - Text: `{"type":"item.completed","item":{"type":"agent_message","text":"…"}}` (Text unter `item.text`).
  - Turn-Ende + Usage: `{"type":"turn.completed","usage":{"input_tokens":…,"cached_input_tokens":…,"output_tokens":…,"reasoning_output_tokens":…}}`.
  - Weitere: `thread.started` (enthält `thread_id` → für `resume`), `turn.started`.
  → Mit dem aktuellen `jsonl`-Adapter würde **kein Codex-Text angezeigt, kein Turn-Ende erkannt, keine Usage** erfasst. Es braucht einen kleinen **`codex`-Adapter**.
- **Echte Usage verfügbar:** anders als andere Subscription-/CLI-Engines liefert Codex Token-Zahlen je Turn → Token-/Kontext-Anzeige kann **echt** sein (statt „n/v").
- **Multi-Turn:** `codex exec` ist **oneshot**. Echtes Multi-Turn nur über `exec resume --last` (`thread_id` aus `thread.started`).

## User Stories
- Als Nutzer möchte ich im Neue-Session-Dialog **„OpenAI Codex"** als Engine wählen und eine Session genauso starten wie mit Claude/Hermes.
- Als Nutzer möchte ich Codex' **Antworten live im Cockpit sehen** (Assistenten-Text), damit die Session nicht „stumm" ist.
- Als Nutzer möchte ich, dass **Turn-Ende, Status („wartet") und Token-/Kontext-Anzeige** korrekt funktionieren (Codex liefert echte Usage).
- Als Nutzer möchte ich, dass Codex meine **Pro-Subscription** nutzt (kein API-Key), genau wie Claude Max.
- Als Nutzer möchte ich eine **bewusste, sichere Sandbox-Voreinstellung**, da bei generic_cli die Decision Cards/Watchdog nicht greifen.

## Acceptance Criteria
- [ ] **Codex wählbar + startbar:** Eintrag in der Laufzeit-`engines.yaml` (gitignored) macht Codex im Launcher wählbar; eine Session startet über den `generic_cli`-Treiber und läuft (`codex exec --json`, Prompt via stdin).
- [ ] **`codex`-Adapter:** neuer Adapter (in `adapters.py`, wählbar via `adapter: codex`) mappt Codex-JSONL → Jupiter-StreamEvents: `item.completed/agent_message` → Assistenten-Text; `turn.completed` → result/Turn-Ende **inkl. Usage** (input/cached/output/reasoning); unbekannte Event-Typen werden ignoriert (kein Hard-Fail, wie bei Claude/jsonl).
- [ ] **Live-Text:** Codex-Antworten erscheinen im Cockpit-Transkript.
- [ ] **Turn-Ende/Status:** nach `turn.completed` wechselt der Status korrekt (`running → wartet`); kein Steckenbleiben auf „Arbeitet".
- [ ] **Token-/Kontext-Anzeige:** Usage aus `turn.completed` füllt `tokens_used`/Kontext-Gauge (Kosten bleiben „none/partial" wie bei Subscription-Engines — kein USD-Routing nötig).
- [ ] **Auth ohne Key:** funktioniert über die eingeloggte ChatGPT-Auth (`~/.codex/auth.json`, geerbtes `HOME`) — **kein** `auth_env`/API-Key im Config-Eintrag.
- [ ] **Sandbox = `workspace-write` (geklärt):** der `engines.yaml`-Eintrag setzt explizit `-s workspace-write` — Codex darf im Projektverzeichnis lesen+editieren, aber nicht beliebig ins System/Netz. Die Policy ist im Config-Eintrag sichtbar dokumentiert.
- [ ] **Degradation dokumentiert + sauber:** ohne Decision Cards/Phasen-Gate/Watchdog läuft die Session stabil (wie hermes); das UI zeigt diese Engine-Grenzen nachvollziehbar (analog bestehender generic_cli-Engines).
- [ ] **Multi-Turn via `resume` (geklärt):** der Kontext bleibt über mehrere Turns erhalten. Erster Turn `codex exec --json … ` (+ `thread_id` aus `thread.started` merken); Folge-Turns `codex exec resume --last --json …` (bzw. per `thread_id`). Implementiert + getestet (Kontext-Erhalt über ≥ 2 Turns nachgewiesen).
- [ ] Tests (Adapter-Mapping inkl. echtem Codex-Sample, Engine-Registrierung) grün; deutsche Texte/Logs; keine Regression in PROJ-18/Adaptern/anderen Engines.

## Edge Cases
- **Reasoning-Tokens:** `reasoning_output_tokens` sinnvoll in die Usage einrechnen (Teil der Output-Last), damit der Kontext-Gauge nicht untertreibt.
- **`thread.started`/`turn.started`:** keine Anzeige-Events; aber `thread_id` ggf. für `resume` merken (nur bei Multi-Turn-Variante).
- **Sandbox blockiert eine Aktion:** Codex meldet das im Stream → soll als normaler Text sichtbar sein (kein stiller Stillstand).
- **Langer Lauf ohne Output:** Liveness/`tool_in_flight` greift nicht (kein PreToolUse-Hook bei generic_cli) → ggf. „hängt"-Fehlbewertung; Abgrenzung zu PROJ-32/45 dokumentieren (generic_cli-Engines haben generell keine Tool-Gate-Signale).
- **Oneshot + Folge-Eingabe:** bei Variante (a) re-spawnt jeder Turn ohne Kontext — im UI klar kommunizieren (oder Variante (b) wählen).
- **`codex`-Update ändert Event-Schema:** Adapter defensiv (unbekannte Felder ignorieren); Version 0.142.2 als Referenz notieren.

## Technical Requirements (optional)
- **Adapter** in `backend/app/engine/adapters.py` + Registrierung in `get_adapter` (Schlüssel `codex`); reine Funktion `codex_parse_line` analog `jsonl_parse_line`.
- **Config-Eintrag** in `backend/config/engines.yaml` (gitignored, live-Reload) — Vorlage in `engines.example.yaml` entsprechend korrigieren (`adapter: codex`, Sandbox-Flag, korrektes Modell, `--json`, `prompt_via: stdin`).
- **Treiber-Zusatz für Multi-Turn (jetzt in Scope):** `generic_cli_driver` braucht einen **Resume-/Folge-argv-Pfad** — heute beendet der oneshot-Modus den Prozess nach dem Turn; der nächste `send_input` muss einen neuen Prozess mit `exec resume --last` (bzw. `resume <thread_id> `) spawnen. `thread_id` aus `thread.started` je Session merken. Konfig-Feld z. B. `resume_argv_template` (oneshot bleibt, aber mit Resume-Folge-Aufruf). Minimaler, generischer Zusatz (auch anderen oneshot-CLIs nützlich), kein Codex-Spezialfall im Treiber.
- **Usage-Mapping** in den vorhandenen Usage-Pfad (`usage.py`) einklinken; `engine_shows_cost` bleibt `false` (kein USD), aber Token zählen.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung |
|---|---|
| **PROJ-18 (Engines)** | Neuer `codex`-Adapter + Registry-Eintrag; bestehende Engines (claude/openai/hermes/…) **unberührt**. |
| **PROJ-19 (Token-Dashboard)** | Codex liefert echte Usage → Token/Kontext echt statt „n/v". |
| **PROJ-4/10/16/30 (Cards/Gate/Watchdog)** | Greifen bei generic_cli **nicht** (keine PreToolUse-Signale) — bekannte, dokumentierte Grenze; Sandbox ist die Leitplanke. |
| **PROJ-9 (Launcher)** | Codex als zusätzliche Engine-Auswahl. |

## Geklärte Design-Entscheidungen (2026-06-26, mit Nutzer)
1. **Sandbox-Policy → `workspace-write`** ✅ (gewählt). Codex darf im Projektverzeichnis lesen+editieren, nicht beliebig ins System/Netz. (Verworfen: `read-only` = kein Editieren; `danger-full-access` = zu riskant ohne Cards/Watchdog.)
2. **Multi-Turn → `exec resume --last`** ✅ (gewählt, gleich vollwertig statt erst oneshot). Kontext bleibt über Turns erhalten; `thread_id` aus `thread.started` je Session merken. (Verworfen: oneshot-Single-Turn als Zwischenschritt.)

## Geklärte Design-Fragen (Nachtrag /abc-architecture, 2026-06-26)
1. **Modell → `gpt-5.5`** ✅ (am Live-System verifiziert). `~/.codex/config.toml` listet unter `[tui.model_availability_nux]` `"gpt-5.5"` als verfügbares Modell; `gpt-5-codex` aus der Beispiel-YAML ist **veraltet**. Festschreibung: `default_model: gpt-5.5`. Alternativ darf `{model}`/`-m` ganz entfallen (Codex-Default), aber da das reale Slug nun bekannt ist, wird es explizit gesetzt. → `engines.example.yaml` von `gpt-5-codex` auf `gpt-5.5` korrigieren.
2. **Usage-Detailtiefe:** *Default-Vorschlag:* `input+output+reasoning` als „tokens_used", `cached_input` separat ausweisen (Cache-Sicht analog Claude).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-26 · **Stack:** Backend-only (FastAPI Engine-Subsystem) · kein Frontend-Code (Cockpit ist engine-agnostisch) · **Branch:** dev

> **Befund-Abgleich mit dem echten Code (Explore, 2026-06-26).** Das Design ist auf den vorhandenen Strukturen geerdet — keine neuen Subsysteme, nur ein Adapter, ein Config-Eintrag und ein generischer Treiber-Zusatz.

### Kernaussage
Codex ist **kein neuer Treiber**, sondern eine Engine, die auf dem bestehenden `generic_cli`-Treiber läuft (wie `hermes`/`ollama`). Es fehlen genau drei Bausteine: (1) ein **Codex-Adapter**, der den verschachtelten JSONL-Strom in Jupiter-StreamEvents übersetzt, (2) ein **Config-Eintrag** in der Laufzeit-`engines.yaml`, (3) ein **generischer Resume-Pfad** im Treiber, damit Folge-Turns Kontext behalten. Decision Cards/Phasen-Gate/Watchdog greifen bei `generic_cli` bewusst nicht — die **Sandbox-Policy ist die Leitplanke**.

### A) Wo es andockt (Modul-Landkarte, kein Code)
```
backend/app/engine/
├── adapters.py          → NEU: codex_parse_line() + Registry-Key "codex"
│                          (Vertrag: Zeile-String → StreamEvent | None, wie jsonl_parse_line)
├── registry.py          → ERWEITERT: optionales Feld resume_argv_template;
│                          "codex" in VALID_ADAPTERS (folgt automatisch aus _ADAPTERS)
├── generic_cli_driver.py→ ERWEITERT: Folge-Turn spawnt neuen Prozess mit Resume-argv;
│                          thread_id je Session merken
├── events.py            → UNVERÄNDERT (StreamEvent type/subtype/raw bleibt der Vertrag)
└── usage.py             → UNVERÄNDERT im Pfad; Codex-Usage fließt über raw["usage"] ein

backend/config/
├── engines.yaml         → NEU: Codex-Eintrag (gitignored, live mtime-Reload)
└── engines.example.yaml → KORRIGIERT: adapter: codex, -s workspace-write, resume_argv_template
```

### B) Datenfluss — was passiert beim Senden (plain language)
```
Turn 1 (Session-Start)
  Launcher → start(spec)  →  codex exec -s workspace-write --json  (Prompt via stdin, oneshot)
        Codex-JSONL  →  codex_parse_line  →  StreamEvents  →  Cockpit-Transkript + Status
            thread.started      → thread_id merken (kein Anzeige-Event)
            item.completed/agent_message → Assistenten-Text (sichtbar)
            turn.completed      → Turn-Ende + Usage → Status running→wartet, Token-Gauge
  Prozess endet (oneshot)

Turn 2..n (Folge-Eingabe)
  send_input → NEUER Prozess:  codex exec resume --last --json  (bzw. resume <thread_id>)
        → gleicher Adapter, gleicher Event-Fluss, Kontext bleibt erhalten
```
Kernpunkt: Codex selbst ist **oneshot pro Turn** — Kontext liegt serverseitig am `thread_id`. Es gibt also **keinen** „stdin offen halten"-Sonderfall; jeder Turn ist ein sauberer Re-Spawn. `oneshot: true` bleibt; der Resume-Pfad wählt nur ein anderes argv-Template für Folge-Turns.

### C) Der Codex-Adapter (Mapping-Tabelle, kein Code)
| Codex-JSONL-Event | → Jupiter-StreamEvent | Sichtbar? |
|---|---|---|
| `thread.started` (`thread_id`) | — (thread_id je Session speichern) | nein |
| `turn.started` | — (ignoriert) | nein |
| `item.completed` / `item.type=agent_message` (Text unter `item.text`) | `assistant` | **ja** (Transkript) |
| `turn.completed` (`usage{input,cached_input,output,reasoning_output}`) | `result/success` **inkl. `raw["usage"]`** | Turn-Ende + Token-Gauge |
| Sandbox-Block / sonstiger Text | `assistant` (normaler Text) | **ja** (kein stiller Stillstand) |
| unbekannter `type` | `None` (übersprungen) | nein — defensiv, kein Hard-Fail |

Reine Funktion analog `jsonl_parse_line`, robust gegen unbekannte Felder (Codex 0.142.2 als Referenz notiert).

### D) Treiber-Zusatz: generischer Resume-Pfad
- Neues **optionales** Config-Feld `resume_argv_template` neben `argv_template`. Fehlt es, verhält sich der Treiber wie heute (keine Regression für hermes/ollama).
- Logik: Erster Turn → `argv_template`. Folge-Turn (`send_input` nach Turn-Ende) → `resume_argv_template`, falls gesetzt; sonst heutiges Verhalten.
- `thread_id` wird im Session-State je Session gemerkt (aus `thread.started`), für `resume <thread_id>` als robustere Alternative zu `--last` (verhindert Verwechslung bei parallelen Sessions).
- **Bewusst minimal & generisch** — nützlich für jede oneshot-CLI mit Resume, kein Codex-Spezialcode im Treiber.

### E) API/Schnittstellen-Form
Keine neuen HTTP-Endpoints. Codex erscheint automatisch über die bestehende Engine-Liste (Registry → Launcher-Dropdown). Token-/Kontext-Anzeige nutzt den vorhandenen Usage-Pfad. **Vertrag bleibt:** `StreamEvent(type, subtype, raw)` und der Usage-Reader (`tokens_used`, optionale `cache_*`-Felder).

### F) Tech-Entscheidungen (WARUM, für PM)
- **Adapter statt Spezialtreiber:** Codex spricht „nur eine andere Sprache" auf stdout — das ist genau die Aufgabe der Adapter-Schicht. Ein eigener Treiber wäre Duplizierung des erprobten `generic_cli`-Pfads.
- **`workspace-write` als Sandbox (geklärt):** Codex darf im Projektordner editieren, aber nicht beliebig ins System/Netz. Da Decision Cards/Watchdog hier nicht greifen, ist die Sandbox die einzige Leitplanke — `read-only` wäre nutzlos (kein Editieren), `danger-full-access` zu riskant. Policy steht **sichtbar** im Config-Eintrag.
- **Resume statt oneshot-Single-Turn (geklärt):** Echtes Multi-Turn von Anfang an; Kontext über `thread_id`. Kein Wegwerf-Zwischenschritt.
- **Auth ohne Key:** Subprozesse erben `HOME=/home/dev` → `~/.codex/auth.json` (eingeloggte ChatGPT-Pro-Subscription), genau wie Claude Max. **Kein** `auth_env`/API-Key im Eintrag.
- **Echte Usage:** Codex liefert Token je Turn → Token-/Kontext-Anzeige wird echt (statt „n/v"). `engine_shows_cost` bleibt `false` (keine USD-Kosten, da Subscription).

### G) Offene Design-Fragen — entschieden
1. **Modell → `gpt-5.5`** (am Live-System verifiziert, 2026-06-26): `~/.codex/config.toml` → `[tui.model_availability_nux] "gpt-5.5" = 1`. Beispiel-YAML-Slug `gpt-5-codex` ist veraltet. Eintrag setzt `default_model: gpt-5.5`; `engines.example.yaml` entsprechend korrigieren.
2. **Usage-Detailtiefe:** `input + output + reasoning_output` → `tokens_used` (Reasoning zählt zur Output-Last, damit der Gauge nicht untertreibt); `cached_input_tokens` separat als Cache-Sicht (analog Claude `cache_*`).

### H) Abhängigkeiten (Pakete)
**Keine neuen.** Alles vorhanden: `generic_cli`-Treiber, Adapter-Schicht, Registry-Loader, Usage-Pfad. `codex`-CLI ist auf dem VPS installiert + eingeloggt (verifiziert).

### I) Risiken / Grenzen (dokumentiert)
- **Keine Tool-Gate-Signale:** kein PreToolUse-Hook bei `generic_cli` → Decision Cards/Phasen-Gate/Watchdog greifen nicht; Liveness/`tool_in_flight` (PROJ-32/45) fehlt → langer Lauf ohne Output kann als „hängt" fehlbewertet werden. Bekannte, generische `generic_cli`-Grenze — im UI nachvollziehbar wie bei hermes/ollama.
- **Schema-Drift bei Codex-Update:** Adapter defensiv (unbekannte Felder ignorieren); Version 0.142.2 als Referenz.
- **Regression:** `resume_argv_template` ist optional → hermes/ollama/claude unberührt; Adapter-Registry rein additiv.

### Routing (welcher Specialist baut was)
- **Backend Developer:** `codex_parse_line` + Registry-Key, `resume_argv_template`-Pfad im Treiber, `thread_id`-Session-Merken, `engines.yaml`-Eintrag + `engines.example.yaml`-Korrektur, Usage-Einklinkung, Tests (Adapter-Mapping mit echtem Codex-Sample + Registrierung). → `/abc-backend`
- **QA Engineer:** Acceptance-Criteria durchgehen (Live-Text, Turn-Ende, Token-Anzeige, Multi-Turn-Kontext ≥2 Turns, Auth-ohne-Key, Sandbox), Regression PROJ-18/andere Engines. → `/abc-qa`
- **Kein Frontend-Ticket** nötig (Cockpit/Launcher engine-agnostisch).
