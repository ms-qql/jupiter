# PROJ-48: Engine — OpenAI Codex CLI (Pro-Subscription) als Jupiter-Agent

## Status: Approved
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
> Backend implementiert + am Live-System (codex-cli 0.142.2) end-to-end verifiziert (2026-06-26). Checkboxen unten = Implementierungsstand; finale QA via `/abc-qa`.
- [x] **Codex wählbar + startbar:** Eintrag in der Laufzeit-`engines.yaml` (gitignored) macht Codex im Launcher wählbar; eine Session startet über den `generic_cli`-Treiber und läuft (`codex exec --json`, Prompt via stdin).
- [x] **`codex`-Adapter:** neuer Adapter (in `adapters.py`, wählbar via `adapter: codex`) mappt Codex-JSONL → Jupiter-StreamEvents: `item.completed/agent_message` → Assistenten-Text; `turn.completed` → result/Turn-Ende **inkl. Usage** (input/cached/output/reasoning); unbekannte Event-Typen werden ignoriert (kein Hard-Fail, wie bei Claude/jsonl).
- [x] **Live-Text:** Codex-Antworten erscheinen im Cockpit-Transkript.
- [x] **Turn-Ende/Status:** nach `turn.completed` wechselt der Status korrekt (`running → wartet`); kein Steckenbleiben auf „Arbeitet".
- [x] **Token-/Kontext-Anzeige:** Usage aus `turn.completed` füllt `tokens_used`/Kontext-Gauge (Kosten bleiben „none/partial" wie bei Subscription-Engines — kein USD-Routing nötig).
- [x] **Auth ohne Key:** funktioniert über die eingeloggte ChatGPT-Auth (`~/.codex/auth.json`, geerbtes `HOME`) — **kein** `auth_env`/API-Key im Config-Eintrag.
- [x] **Sandbox = `workspace-write` (geklärt):** der `engines.yaml`-Eintrag setzt explizit `-s workspace-write` — Codex darf im Projektverzeichnis lesen+editieren, aber nicht beliebig ins System/Netz. Die Policy ist im Config-Eintrag sichtbar dokumentiert.
- [x] **Degradation dokumentiert + sauber:** ohne Decision Cards/Phasen-Gate/Watchdog läuft die Session stabil (wie hermes); das UI zeigt diese Engine-Grenzen nachvollziehbar (analog bestehender generic_cli-Engines).
- [x] **Multi-Turn via `resume` (geklärt):** der Kontext bleibt über mehrere Turns erhalten. Erster Turn `codex exec --json … ` (+ `thread_id` aus `thread.started` merken); Folge-Turns `codex exec resume --last --json …` (bzw. per `thread_id`). Implementiert + getestet (Kontext-Erhalt über ≥ 2 Turns nachgewiesen).
- [x] Tests (Adapter-Mapping inkl. echtem Codex-Sample, Engine-Registrierung) grün; deutsche Texte/Logs; keine Regression in PROJ-18/Adaptern/anderen Engines.

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

---

## Implementation Notes (Backend Developer, 2026-06-26)

**Branch:** `dev`. Umgesetzt wie im Tech-Design — ein Adapter, ein generischer Treiber-Zusatz, ein Config-Eintrag; keine neuen Subsysteme/HTTP-Endpoints, kein Frontend-Code.

### Geänderte Dateien
- `backend/app/engine/adapters.py` — **neu** `codex_parse_line` (+ Helper `_codex_result_event`), Registry-Key `codex`. Mapping: `thread.started`→`system/resume_token` (nicht sichtbar), `item.completed` mit `item.text`→assistant-Text, `turn.completed`→`result/success` inkl. gemappter Usage, `turn.started`/unbekannt→`None`.
- `backend/app/engine/registry.py` — neues optionales Feld `resume_argv_template` (+ Coercion für `generic_cli`). Fehlt es → Verhalten wie bisher (keine Regression für hermes/ollama).
- `backend/app/engine/generic_cli_driver.py` — `build_generic_argv` um `{resume_id}`-Platzhalter + `resume=`-Schalter erweitert; `start`/`_spawn`/`_write_stdin` refaktoriert; `send_input` re-spawnt einen toten oneshot-Prozess mit dem Resume-argv (Kontext bleibt am `resume_id`); `_read_stdout` fängt `resume_token` ab (merkt `self._resume_id`, unterdrückt Anzeige) und emittiert nach einem sauberen, resumefähigen Turn **kein** `closed` (Session bleibt „wartet" statt „done"); neue Property `supports_self_resume`.
- `backend/app/engine/base.py` — Default-Property `supports_self_resume=False` auf `EngineDriver`.
- `backend/app/engine/manager.py` — (1) `send_input` löst den `_resume`-Pfad **nicht** aus, wenn der Treiber `supports_self_resume`; (2) `_apply_usage` füllt den Kontext-Füllstand auch aus `result`-Usage, wenn `raw["context_is_per_turn"]` (Codex liefert keine assistant-Usage je Turn). Beides Claude-neutral.
- `backend/config/engines.yaml` (gitignored, live) — Codex-Eintrag ergänzt. `backend/config/engines.example.yaml` — alten `codex`-Beispieleintrag korrigiert (`adapter: codex`, `-s workspace-write`, `--skip-git-repo-check`, `resume_argv_template`, `gpt-5.5`).
- `backend/tests/test_proj48_codex.py` — **neu**, 12 Tests (Adapter-Mapping mit echtem Sample, Usage-Mapping, argv-Resume, Registry, Treiber-Multi-Turn gegen eine Fake-Codex-CLI, Regression nicht-resumefähiger oneshot, Fehlerfall ohne resume_id).

### Usage-Mapping (wichtige Entscheidung)
Codex `turn.completed.usage` → Claude-Form **analog Claude** (cached als separate Sicht, NICHT in `input_tokens`): `input_tokens = input − cached`, `cache_read_input_tokens = cached`, `output_tokens = output + reasoning`. So ist der Kontext-Füllstand der **echte Prompt-Umfang** (kein Doppelzählen des Cache) und die abgerechneten Tokens sind cross-engine konsistent. `context_is_per_turn`-Marker im result-`raw` erlaubt dem Manager, den Gauge aus per-Turn-Usage zu füllen (Codex' `input_tokens` wächst je Turn = aktueller Konversations-Kontext, anders als Claudes kumulative result-Usage).

### Resume-Mechanik (am Live-System verifiziert)
- Initial-argv: `codex exec -m gpt-5.5 -s workspace-write --skip-git-repo-check --json -` (Prompt via stdin, `-`).
- Folge-argv: `codex exec … --json resume <thread_id> -` (Sandbox-/exec-Optionen MÜSSEN **vor** dem `resume`-Subcommand stehen; `<thread_id>` + `-` sind Positionale von `resume`).
- `thread_id` (= `resume_id`) je Session im Treiber gemerkt → robust gegen parallele Sessions (statt `--last`).

### Live-Verifikation (codex-cli 0.142.2, echte Subscription-Auth)
2-Turn-Lauf über den echten Treiber gegen das echte `codex`-Binary: Turn 1 „Merke dir 13"→„OK" (billed=1972, ctx=11567, cache=9600); Turn 2 nach Resume „Welche Zahl?"→**„13"** → **Kontext erhalten**; zwischen den Turns kein `closed` → Status „wartet". Auth ohne Key (geerbtes `HOME`) bestätigt.

### Bekannte Grenzen (unverändert dokumentiert)
Keine Decision Cards/Phasen-Gate/Watchdog/`tool_in_flight` (generic_cli ohne PreToolUse-Hook); Sandbox `workspace-write` ist die Leitplanke. Backend-Restart mitten in einer Codex-Session → `DeadDriver` → regulärer `_resume`-Pfad startet kontextlos frisch (degradiert, wie andere generic_cli-Engines; `thread_id` wird nicht persistiert). Kontextfenster-Gauge nutzt den 200 000er-Default (Codex meldet kein `contextWindow`).

### Tests
`conda run -n Dashboard --no-capture-output python -m pytest backend/tests` → **875 passed** (inkl. 12 neue PROJ-48-Tests; PROJ-18/26/40-Engine-Suites grün — keine Regression).

---

## QA Test Results (QA Engineer, 2026-06-26)

**Branch:** `dev` · **Build:** Backend-pytest + Live-Verifikation gegen echtes `codex` (codex-cli 0.142.2, ChatGPT-Pro-Auth). Kein Frontend-Code (Cockpit/Launcher engine-agnostisch) → keine responsive/Browser-Matrix nötig.

### Akzeptanzkriterien (10/10 bestanden)
| # | Kriterium | Ergebnis | Nachweis |
|---|---|---|---|
| 1 | Codex wählbar + startbar | ✅ PASS | Registry lädt `codex`, `availability()=(True, None)`, keine Warnung; `default_model=gpt-5.5`. |
| 2 | `codex`-Adapter (JSONL→StreamEvents) | ✅ PASS | `test_proj48_codex.py`: thread.started→resume_token, agent_message→Text, turn.completed→result+Usage, turn.started/unbekannt→None. |
| 3 | Live-Text im Transkript | ✅ PASS | Manager-Integrationstest: `hi:erste` im Transkript; Live „OK"/„13". |
| 4 | Turn-Ende/Status `running→wartet` | ✅ PASS | Manager-Test asserted `status==WAITING` (Race-sicher, nicht DONE); kein `closed` zwischen Turns. |
| 5 | Token-/Kontext-Anzeige aus Usage | ✅ PASS | `tokens_used>0`, `context_known`, `context_fill_pct>0`, `cache_read_tokens` gefüllt; akkumuliert über Turns. |
| 6 | Auth ohne Key | ✅ PASS | Kein `auth_env`; Live-Lauf nutzte Subscription-Auth (geerbtes HOME). |
| 7 | Sandbox `workspace-write` | ✅ PASS | `-s workspace-write` im argv (initial + resume), sichtbar in `engines.yaml`. |
| 8 | Degradation dokumentiert + sauber | ✅ PASS | Keine Cards/Gate/Watchdog (generic_cli), Session stabil; konsistent zu hermes/ollama. |
| 9 | Multi-Turn via `resume` (Kontext ≥2 Turns) | ✅ PASS | Live: Turn 2 nach `resume <thread_id>` antwortete „13" (Merk-Zahl erhalten); Fake-CLI-Test echot resume_id zurück. |
| 10 | Tests grün, deutsch, keine Regression | ✅ PASS | **877 passed** (14 PROJ-48 + Rest); PROJ-18/26/40 grün. |

### Security / Red-Team
- **Secret-Exposure:** `to_read()` (GET /engines) enthält **keine** Internals — `bin`/`argv_template`/`resume_argv_template`/`auth_env` werden nicht exponiert. ✅
- **Kein API-Key im Repo:** Codex-Eintrag hat kein `auth_env`; `engines.yaml` gitignored. ✅
- **Sandbox-Eingrenzung:** `-s workspace-write` (nicht `danger-full-access`) ist die einzige Leitplanke — bewusste, dokumentierte Entscheidung; bei generic_cli greifen Cards/Watchdog konstruktionsbedingt nicht. ✅
- **Command-Injection:** argv wird als Liste (`create_subprocess_exec`, kein Shell) gebaut; Platzhalter-Substitution ohne Shell-Interpolation. Prompt geht via stdin, nicht als argv. ✅
- **Tenant-Isolation:** für dieses Feature n/a (kein DB-/RLS-Pfad; reine Engine-Subprozess-Steuerung).

### Gefundene Punkte (alle Low/Info — kein Blocker) → **alle behoben (2026-06-26)**
- **[Low/UX] ✅ FIXED — Liveness-Badge zeigte zwischen Turns „tot".** `derive_liveness` (manager.py) stuft eine WAITING-Session mit totem Prozess jetzt als **ACTIVE** ein, **wenn** der Treiber `supports_self_resume` ist (Codex zwischen Turns) — geprüft **vor** der „kein Prozess → tot"-Regel. Gegenprobe: nicht-resumefähige oneshots (hermes/ollama) bleiben korrekt DEAD. Tests: `test_liveness_resumable_between_turns_is_active_not_dead`, `…non_resumable_dead_process_still_dead`.
- **[Low] ✅ FIXED — Manuelles „Reaktivieren" startete kontextlos.** Folgt direkt aus dem Liveness-Fix: `reanimate()` lehnt eine ACTIVE-Session mit `SessionAliveError` ab → kein versehentlicher kontextloser Neustart der gesunden Between-Turns-Session; der reguläre Weg (Nachricht senden) resumed mit Kontext.
- **[Info] ✅ FIXED — Sandbox nun als UI-Badge.** `_sandbox_from_argv` leitet die Policy aus dem `-s`/`--sandbox`-Flag des argv ab (EINE Quelle der Wahrheit = das real laufende argv); `to_read().sandbox` liefert für Codex jetzt `"workspace-write"`. Tests: `test_registry_exposes_sandbox_badge`, `test_sandbox_from_argv_helper_edge_cases`.

### Hinweis (Cross-Feature)
PROJ-50 (abc-Workflow für Codex) wird **parallel** auf `dev` entwickelt und hat uncommittete Änderungen in `adapters.py` (file_change→tool_use), `manager.py`, `abc_phases.py` sowie die `abc`-Capability am Codex-Eintrag. Die volle Suite lief **mit** diesen Änderungen grün → keine Wechselwirkungs-Regression mit PROJ-48. Diese Dateien gehören zu PROJ-50 und sind **nicht** Teil dieses QA-Commits.

### Production-Ready: **JA** (Approved)
Keine Critical/High-Bugs. Die drei Low/Info-Punkte sind Anzeige-/UX-Feinheiten innerhalb der bewusst gewählten generic_cli-Grenzen. Empfehlung: deploybar via `/abc-deploy`.
