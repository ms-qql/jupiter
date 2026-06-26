# PROJ-48: Engine — OpenAI Codex CLI (Pro-Subscription) als Jupiter-Agent

## Status: Planned
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

## Offene Design-Fragen (für /abc-architecture — mit Default-Vorschlag)
1. **Modell:** *Default-Vorschlag:* Codex-Default verwenden (kein `-m`) oder explizit das aktuell verfügbare Codex-Modell setzen; Modellnamen vor dem Deploy gegen `codex` verifizieren (TUI-Hinweis nennt `gpt-5.5`; `engines.example.yaml` nennt `gpt-5-codex` — vor Festschreibung prüfen).
2. **Usage-Detailtiefe:** *Default-Vorschlag:* `input+output+reasoning` als „tokens_used", `cached_input` separat ausweisen (Cache-Sicht analog Claude).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_
