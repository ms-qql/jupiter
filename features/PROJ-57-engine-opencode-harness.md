# PROJ-57: Engine — OpenCode als Harness (OpenRouter-Modelle über OpenCode statt Direkt-HTTP)

## Status: Planned
**Created:** 2026-07-05
**Last Updated:** 2026-07-05

## Problem / Motivation
OpenRouter (Modell **GLM 5.2**) ist heute über den rohen HTTP-`OpenAIDriver` eingebunden (`backend/app/engine/openai_driver.py`). Das ist **keine vollwertige Agenten-Harness**: kein Tool-Loop, kein Datei-/Shell-Zugriff, kein Agenten-/Command-Konzept. Dadurch lassen sich u. a. die **Claude-Skills / der abc-Workflow nicht übernehmen**, und die Nicht-Claude-Sessions bleiben funktional dünn.

**OpenCode** (`opencode` CLI) ist eine vollwertige, provider-agnostische Coding-Agent-Harness mit Tool-Loop, Sessions und OpenRouter-Support. Ziel: OpenCode als **wählbare Engine** in Jupiter integrieren — genau wie Claude, Codex und Swisscom — und **OpenRouter-Modelle künftig über OpenCode laufen lassen** statt über den rohen HTTP-Pfad. Der Nutzer wählt dann eine von vier Engines: **Codex · Claude · Swisscom · OpenCode**, und bei OpenCode danach ein OpenCode-Modell.

**Verifizierte Fakten (2026-07-05):**
- OpenCode-CLI ist auf dem VPS **noch nicht installiert** (`which opencode` leer) → Install + Auth-Verifikation ist ein Prerequisite-Spike (analog PROJ-1/48).
- `opencode run -m <provider/model> --format json <prompt>` → **non-interaktiver JSON-Event-Stream** auf stdout (Adapter-Ziel, wie beim Codex-Adapter).
- Resume: `--session <id>` (bzw. `-c` = letzte Session) → passt direkt auf das bestehende `resume_argv_template` + `resume_id`-Muster des `generic_cli`-Treibers → **PROJ-56-Persistenz greift**.
- `-m openrouter/z-ai/glm-5.2` → OpenRouter-Modelle laufen über die Harness. Auth via `OPENROUTER_API_KEY` (Key liegt bereits in `/etc/jupiter-backend.env`) bzw. `~/.local/share/opencode/auth.json`.
- `--agent` zur Agentenwahl — Hebel für die spätere Skill-/abc-Übernahme (eigenes Folge-Ticket).

## Dependencies
- Requires: PROJ-18 (Weitere Engines + iFrame/Launch) — Engine-Registry (`engines.yaml`, live mtime-Reload), `generic_cli`-Treiber, Adapter-Schicht. **Hier dockt OpenCode an.**
- Requires: PROJ-48 (Engine — OpenAI Codex CLI) — Blaupause für eine `generic_cli`-Harness mit JSON-Adapter + Resume-über-Session-ID (`resume_argv_template`).
- Requires: PROJ-56 (Kontext-Persistenz & Resume für Nicht-Claude-Engines) — der persistierte `resume_id`/`context_status`-Mechanismus, der für OpenCode gelten muss.
- Requires: PROJ-51 (Engine- und Modellverwaltung in den App-Einstellungen) — OpenCode-Engine + Modell-Liste erscheinen in der bestehenden Engine-/Modellverwaltung.
- Verwandt: PROJ-50 (abc-Workflow für Codex) — Vorbild für die **spätere** Skill-/abc-Portierung auf OpenCode (bewusst NICHT Teil dieses Tickets).
- **Degradiert bewusst** (wie Codex/hermes): `generic_cli` hat keinen PreToolUse-Hook → **keine** Decision Cards (PROJ-4), **kein** Phasen-Gate (PROJ-10/30), **kein** Amok-Watchdog am Tool-Gate (PROJ-16). OpenCodes eigene Permission-Config ist die Leitplanke.

## Scope-Abgrenzung (bewusst)
- **In Scope:** OpenCode als vollwertige Harness-Engine; OpenRouter-Modelle laufen über OpenCode; Ablösung des rohen OpenRouter-HTTP-Pfads; PROJ-56-Kontext-Persistenz vollständig anwendbar auf OpenCode.
- **NICHT in Scope (Folge-Ticket):** tatsächliche Portierung der Claude-Skills / des abc-Workflows in OpenCode-Agents/-Commands (analog PROJ-50 für Codex). Dieses Ticket schafft nur die technische Harness-Grundlage dafür.
- **Unberührt:** **Swisscom** bleibt als eigene Top-Level-Engine auf dem HTTP-`OpenAIDriver`. **Claude** und **Codex** bleiben unverändert.

## User Stories
- Als Nutzer möchte ich im Neue-Session-Dialog **„OpenCode"** als Engine wählen und danach ein OpenCode-Modell (GLM 5.2, MiniMax M3, Kimi K2.7, Qwen 3.7, DeepSeek v4) auswählen, um eine Session genauso zu starten wie mit Claude/Codex.
- Als Nutzer möchte ich, dass meine **OpenRouter/GLM-Arbeit über eine echte Harness** läuft (Tool-Loop, Datei-/Shell-Zugriff), damit die Session nicht mehr funktional dünn ist wie der rohe HTTP-Chat.
- Als Nutzer möchte ich OpenCodes **Antworten live im Cockpit** sehen (Assistenten-Text) und ein korrektes **Turn-Ende/„wartet"** + Token-/Kontext-Anzeige, soweit OpenCode Usage liefert.
- Als Nutzer einer OpenCode-Session möchte ich, dass **Kontext einen Backend-Restart, eine Reanimierung und jeden Resume-Pfad übersteht** (PROJ-56), damit ein Deploy meine Session nicht inhaltlich zerstört.
- Als Nutzer möchte ich, dass die **frühere OpenRouter-Direkt-Auswahl verschwindet** und OpenRouter/GLM nur noch als OpenCode-Modell erscheint, damit es genau einen klaren Weg gibt.
- Als Betreiber möchte ich, dass OpenCode meinen bereits vorhandenen **OpenRouter-Key** nutzt (kein zweiter Secret-Ort), und dass keine Secrets in persistierte Artefakte oder die Engine-Liste gelangen.

## Acceptance Criteria

### Engine-Integration & Auswahl
- [ ] **OpenCode wählbar + startbar:** Registry-Eintrag (`engines.yaml`, gitignored, live-Reload) macht OpenCode im Launcher wählbar; eine Session startet über den `generic_cli`-Treiber (`opencode run … --format json`, Prompt via stdin oder arg) und läuft.
- [ ] **Vier Engines im Dialog:** Der Neue-Session-Dialog / die Engine-Auswahl bietet **Codex · Claude · Swisscom · OpenCode** an. Nach Wahl von OpenCode ist genau die kuratierte OpenCode-Modell-Liste wählbar.
- [ ] **Modell-Liste:** GLM 5.2, MiniMax M3, Kimi K2.7, Qwen 3.7, DeepSeek v4 sind als OpenCode-Modelle auswählbar (OpenRouter-Slugs am Live-System/Architektur verifiziert). Ein Default-Modell ist gesetzt.
- [ ] **OpenCode erscheint in der Engine-/Modellverwaltung** (PROJ-51, `GET/PUT /settings/engines`) wie die übrigen Engines; Modelle editierbar über den bestehenden Weg.

### Ablösung des OpenRouter-Direkt-Pfads
- [ ] Die bisherige **OpenRouter-HTTP-Engine** (roher `OpenAIDriver`, `key: openrouter`) wird als wählbare Engine **entfernt/deaktiviert** — OpenRouter/GLM ist nur noch über OpenCode erreichbar.
- [ ] **Swisscom bleibt unverändert** als eigene Engine auf dem HTTP-`OpenAIDriver` (Regressionscheck: Swisscom startet/streamt weiter).
- [ ] Bestehende, vor der Ablösung gestartete OpenRouter-HTTP-Sessions **crashen nicht** (sauberes Degradieren; siehe Edge Cases „Migration").

### Streaming, Status & Adapter (der Code-Kern)
- [ ] **OpenCode-Adapter:** Ein Adapter (in `adapters.py`, wählbar via `adapter: opencode`) mappt OpenCodes `--format json`-Stream → Jupiter-StreamEvents: Assistenten-Text sichtbar; Turn-Ende → `result`/„wartet"; Usage (falls geliefert) → Token-/Kontext-Gauge; unbekannte Event-Typen werden **ignoriert** (kein Hard-Fail, wie bei Codex/jsonl).
- [ ] **Live-Text:** OpenCode-Antworten erscheinen im Cockpit-Transkript; die Session ist nicht „stumm".
- [ ] **Turn-Ende/Status:** nach Turn-Abschluss wechselt der Status korrekt `running → wartet`, kein Steckenbleiben auf „Arbeitet".
- [ ] **Tool-Aktivität sichtbar (soweit möglich):** wenn OpenCode Tool-/Datei-Events streamt, erscheinen sie nachvollziehbar im Transkript (kein stiller Stillstand bei langen Läufen).

### Kontext-Persistenz & Resume (PROJ-56 gilt vollständig)
- [ ] **Session-ID als `resume_id`:** die von OpenCode gelieferte Session-ID wird aus dem Stream abgefangen und **persistiert** (Session-Snapshot / `session_index`), nicht nur im RAM.
- [ ] **Resume über `--session <id>`:** Folge-Turns und der Manager-`_resume`-Pfad nutzen das **`resume_argv_template`** mit der persistierten Session-ID (self-resume, kein kontextloser Neustart).
- [ ] **Die drei Auslöser** (Backend-Restart · Reanimierung eines RUNNING-Turns · `_resume` bei totem Treiber) führen bei OpenCode **nicht** zu Kontextverlust (je ein reproduzierbarer Testfall) — der Agent referenziert korrekt eine Aussage aus einem Turn vor dem Auslöser.
- [ ] **Fehlende Session-ID** (Erststart / Engine hat noch keine geliefert) → sauberer, sichtbar als „kontextlos" markierter Start, **kein Crash**.
- [ ] **`context_status`** wird für OpenCode-Sessions gesetzt und im Cockpit ausgespielt („mit Kontext" / „kontextlos (Grund)"), genau wie für Codex/GLM.

### Auth, Sicherheit & Degradation
- [ ] **Auth über vorhandenen OpenRouter-Key:** OpenCode nutzt `OPENROUTER_API_KEY` aus `/etc/jupiter-backend.env` (bzw. den OpenCode-Auth-Store) — **kein zweiter Secret-Ort**, kein Key im Repo.
- [ ] **Keine Secrets exponiert:** weder in `GET /engines`/`to_read()` (kein `bin`/`argv_template`/`auth_env`) noch in persistierten Resume-Artefakten (Session-ID + Verlauf ohne Key/Header).
- [ ] **Sandbox/Permission = Editieren im Projektordner** (bewusst gewählt, Variante A): OpenCodes Permission-Config erlaubt Lesen+Editieren im Projektverzeichnis, aber keinen unbeschränkten System-/Netzzugriff; die Policy ist im Config-Eintrag sichtbar dokumentiert.
- [ ] **Degradation dokumentiert + sauber:** ohne Decision Cards/Phasen-Gate/Watchdog läuft die Session stabil (wie Codex/hermes); das UI zeigt diese Engine-Grenzen nachvollziehbar.

### Qualität / Regression
- [ ] **Claude, Codex und Swisscom bleiben unverändert** — kein Regress (bestehende Engine-Suites grün).
- [ ] Tests grün (Adapter-Mapping mit echtem OpenCode-JSON-Sample, Engine-Registrierung, Resume-argv, PROJ-56-Auslöser für OpenCode); deutsche Texte/Logs.

## Edge Cases
- **`opencode` nicht installiert / falsche CLI-Version:** Engine erscheint als **unavailable** mit klarer Begründung (analog `availability()` bei fehlendem Binär), statt beim Start zu crashen.
- **OpenCode-`--format json`-Schema weicht vom Erwarteten ab / ändert sich mit Update:** Adapter defensiv (unbekannte Felder/Events ignorieren); die getestete OpenCode-Version wird als Referenz notiert.
- **OpenCode liefert keine Session-ID im Stream** (CLI-Variante ohne Session-Ausgabe): erwartetes Fallback = sauberer kontextloser Neustart mit sichtbarer Warnung, kein stilles „so tun als ob" (analog PROJ-56 Codex-`thread_id`-Fallback).
- **Persistierte Session-ID, aber OpenCode-Session serverseitig/lokal nicht mehr auffindbar** (`--session <id>` schlägt fehl): sauberer Fallback auf Neustart statt Hard-Error, `context_status` markiert „kontextlos".
- **Backend-Restart mitten im Turn:** ein unvollständiger Turn darf den persistierten Verlauf/Status nicht korrumpieren (kein halber Assistant-Turn) — gleiche Garantie wie PROJ-56.
- **OpenCode liefert keine/teilweise Usage:** Token-/Kontext-Gauge zeigt „n/v" oder Teilwerte, ohne zu untertreiben oder als Bug fehlinterpretiert zu werden (Subscription/Key-Engine ohne USD-Routing).
- **Modell-Slug ungültig** (OpenRouter kennt das Modell nicht → 404, bekannte Falle aus dem Engines-Setup): Fehler ist im Transkript sichtbar, Session bricht sauber ab statt still zu hängen; Slug-Liste ist am Live-System verifiziert.
- **Migration bestehender OpenRouter-HTTP-Sessions:** vor der Ablösung gestartete Sessions haben keinen OpenCode-Resume-Zustand — dürfen nicht crashen, sondern sauber degradieren (kontextlos oder read-only Abschluss).
- **Sehr großer Verlauf über viele Turns:** OpenCode hält den Kontext serverseitig an der Session-ID (self-resume) → kein Verlauf-Replay nötig; die PROJ-56-GLM-Deckelung (`openai_resume_max_messages`) ist hier **nicht** relevant. Falls doch ein Replay-Pfad entsteht, greift der bestehende Deckel.

## Technical Requirements (optional)
- **Prerequisite-Spike (vor/in der Architektur):** `opencode` auf dem VPS installieren, mit OpenRouter-Key einloggen, und am Live-System verifizieren: (a) exaktes `--format json`-Event-Schema, (b) ob/wie eine **Session-ID** im Stream erscheint (Grundlage für Resume), (c) Auth-Vererbung über `HOME`/Env wie bei Codex/Claude.
- **Kein neuer Treiber erwartet:** OpenCode läuft über den bestehenden `generic_cli`-Treiber (`driver: generic_cli`), wenn `--format json` per-argv passt (Codex-Blaupause). Wahrscheinlichster Code-Anteil: **ein `opencode`-Adapter** in `backend/app/engine/adapters.py` + Registrierung; ggf. Feinschliff am `resume_argv_template`-Pfad.
- **Config-Eintrag** in `backend/config/engines.yaml` (gitignored, live-Reload): `key: opencode`, `driver: generic_cli`, `bin`, `argv_template` (`run -m {model} --format json …`), `resume_argv_template` (`--session {resume_id}`), `adapter: opencode`, `oneshot: true`, `models: [GLM 5.2, MiniMax M3, Kimi K2.7, Qwen 3.7, DeepSeek v4]` (mit verifizierten OpenRouter-Slugs), `default_model`, `capabilities`. Vorlage in `engines.example.yaml` spiegeln.
- **Persistenz:** OpenCode-Session-ID nutzt den PROJ-56-`resume_id`-Pfad (`session_index`), `context_status` wie dort. Kein neuer Store.
- **Ablösung:** OpenRouter-HTTP-Eintrag (`key: openrouter`, `driver: openai`) deaktivieren/entfernen; Swisscom-HTTP-Eintrag bleibt.
- **Security:** kein Key im Repo/`to_read()`; persistierte Artefakte ohne Secrets; bestehende Pfad-Sandbox der Session-Persistenz respektieren.
- **Kein Frontend-Ticket erwartet:** Cockpit/Launcher/Engine-Verwaltung sind engine-agnostisch (Engine + Modelle kommen aus der Registry-Snapshot-Antwort). Falls die Engine-Auswahl UI-seitig eine feste Reihenfolge/Labels braucht, ist das ein kleiner Frontend-Zusatz.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung |
|---|---|
| **PROJ-18 (Engines)** | Neuer `opencode`-Adapter + Registry-Eintrag; **OpenRouter-HTTP-Eintrag entfällt**; claude/codex/swisscom/hermes unberührt. |
| **PROJ-56 (Kontext-Persistenz)** | Muss vollständig für OpenCode gelten (Session-ID als `resume_id`, drei Auslöser, `context_status`). |
| **PROJ-51 (Engine-/Modellverwaltung)** | OpenCode + Modell-Liste erscheinen/editierbar; OpenRouter-Direkt-Eintrag verschwindet. |
| **PROJ-19 (Token-Dashboard)** | OpenCode-Usage (falls geliefert) fließt in Token/Kontext; sonst „n/v". |
| **PROJ-4/10/16/30 (Cards/Gate/Watchdog)** | Greifen bei `generic_cli` **nicht** — bekannte, dokumentierte Grenze; OpenCode-Permission-Config ist die Leitplanke. |
| **PROJ-50 (abc-Workflow)** | **Folge-Ticket**: Skill-/abc-Portierung auf OpenCode-Agents/-Commands (nicht in diesem Ticket). |

## Offene Design-Fragen (für /abc-architecture)
1. **Modell-Slugs:** exakte OpenRouter-Slugs für MiniMax M3, Kimi K2.7, Qwen 3.7, DeepSeek v4 am Live-System verifizieren (GLM 5.2 = `z-ai/glm-5.2` bekannt). 404-Falle vermeiden.
2. **Provider-Präfix:** benötigt OpenCode `-m openrouter/<slug>` oder einen konfigurierten Provider in `opencode.json`? Entscheidet, ob ein OpenCode-Config-File (global `~/.config/opencode/opencode.json`) mit ausgerollt werden muss.
3. **Session-ID-Quelle:** aus welchem Stream-Event kommt die Session-ID (für `resume_id`)? Falls keine im `run`-Stream → Alternative (`--print-logs`, `serve`/ACP-Modus) bewerten oder kontextlos degradieren.
4. **Permission-Config:** wie setzt man OpenCodes „Editieren im Projektordner, kein freier System-/Netzzugriff" (Konfig-Feld/Flag) sichtbar im Eintrag?
5. **Nachnutzung PROJ-56-Deckelung:** self-resume (Session-ID) vermeidet Verlauf-Replay → GLM-Deckel irrelevant; bestätigen, dass kein OpenAI-`messages`-Replay-Pfad für OpenCode entsteht.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-05 · **Stack:** Backend-only (FastAPI Engine-Subsystem) · kein Frontend-Code (Launcher/Cockpit/Engine-Verwaltung sind engine-agnostisch) · **Branch:** dev

> **Live am VPS verifiziert (2026-07-05, `opencode` v1.17.13).** Der User hat OpenCode installiert, OpenRouter voreingestellt + Key hinterlegt, MiniMax M3 gewählt. Das Design ist auf echten CLI-Läufen geerdet, nicht auf Annahmen — alle offenen Design-Fragen der Spec sind damit beantwortet (siehe Abschnitt G).

### Kernaussage
OpenCode ist — wie Codex — **kein neuer Treiber**, sondern eine Engine auf dem bestehenden **`generic_cli`**-Treiber. Es fehlen genau **drei** Bausteine: (1) ein **`opencode`-Adapter**, der OpenCodes `--format json`-Events in Jupiter-StreamEvents übersetzt, (2) ein **Config-Eintrag** in der Laufzeit-`engines.yaml`, (3) das **Entfernen des rohen OpenRouter-HTTP-Eintrags**. Die PROJ-56-Persistenz greift **automatisch**, weil OpenCode eine Session-ID liefert, die exakt auf den vorhandenen `resume_id`-Pfad passt (self-resume, wie Codex). Decision Cards/Phasen-Gate/Watchdog greifen bei `generic_cli` bewusst nicht.

### A) Wo es andockt (Modul-Landkarte, kein Code)
```
backend/app/engine/
├── adapters.py          → NEU: opencode_parse_line() + Registry-Key "opencode"
│                          (Vertrag: Zeile-String → StreamEvent | None, wie codex_parse_line)
├── registry.py          → UNVERÄNDERT im Code — "opencode" folgt automatisch aus _ADAPTERS;
│                          generic_cli + resume_argv_template sind bereits zugelassen
├── generic_cli_driver.py→ UNVERÄNDERT — fängt resume_id über system/resume_token ab (PROJ-48-Pfad)
└── manager.py           → UNVERÄNDERT — engine-bewusster _resume (PROJ-56) deckt self-resume ab

backend/config/
├── engines.yaml         → NEU: opencode-Eintrag · ENTFERNT: openrouter-Eintrag (Ablösung)
└── engines.example.yaml → gespiegelt (opencode-Beispiel, ohne Secrets)

backend/tests/
└── test_proj57_opencode.py → NEU (Blaupause: test_proj48_codex.py + test_proj56_context_persistence.py)
```
**Bemerkenswert:** Der reine Code-Anteil ist **ein Adapter + ein YAML-Eintrag** — kein Treiber-, Registry- oder Manager-Code. Die Engine-Schicht wurde durch PROJ-48/56 genau für diesen Fall generisch gemacht.

### B) Datenfluss — was beim Senden passiert (Klartext)
```
Turn 1 (Session-Start)
  Launcher → start(spec) → opencode run --format json -m openrouter/<slug> --auto <prompt>   (cwd = Projektpfad, oneshot)
    OpenCode-JSON → opencode_parse_line → StreamEvents → Cockpit-Transkript + Status
        step_start (enthält sessionID) → system/resume_token → resume_id merken (nicht sichtbar)
        text (part.text)               → assistant-Text (sichtbar)
        tool (part.tool/state)         → tool_use (Aktivität sichtbar; Grundlage abc, PROJ-50-Folge)
        step_finish (tokens + cost)    → result/success inkl. Usage → Status running→wartet, Token/€-Gauge
  Prozess endet (oneshot)

Turn 2..n (Folge-Eingabe / Resume)
  send_input → NEUER Prozess: opencode run --format json -s <sessionID> --auto <prompt>
        → gleicher Adapter, gleicher Fluss; serverseitiger Kontext bleibt an der Session-ID (live verifiziert: „77" erinnert)
```
Wie Codex ist OpenCode **oneshot pro Turn**; der Kontext liegt serverseitig (OpenCodes eigene SQLite `~/.local/share/opencode/opencode.db`) an der `sessionID`. Es gibt **keinen** Verlauf-Replay wie beim rohen OpenAIDriver → die PROJ-56-GLM-Deckelung (`openai_resume_max_messages`) ist hier irrelevant.

### C) Der OpenCode-Adapter (Mapping-Tabelle, kein Code)
| OpenCode-JSON-Event | → Jupiter-StreamEvent | Sichtbar? |
|---|---|---|
| `step_start` (`sessionID`) | `system/resume_token` (Session-ID einmalig merken) | nein |
| `text` (`part.type=text`, `part.text`) | `assistant` | **ja** (Transkript) |
| `tool` (`part.tool`, `part.state.status`) | `tool_use` | ja (Aktivität) |
| `step_finish` (`part.tokens`, `part.cost`, `reason=stop`) | `result/success` **inkl. `raw["usage"]` + `raw["cost"]`** | Turn-Ende + Token/€-Gauge |
| `reasoning`/`step_start`-Folge/unbekannt | `None` (übersprungen) | nein — defensiv, kein Hard-Fail |

Reine Funktion analog `codex_parse_line`, robust gegen unbekannte Felder (OpenCode 1.17.13 als Referenz notiert). Session-ID wird nur **einmal** je Session als `resume_token` emittiert (der Treiber unterdrückt Folge-Dopplungen ohnehin, da `resume_id` gesetzt bleibt).

**Usage-Mapping (analog Codex, Cache separat):** `input_tokens = tokens.input`, `cache_read_input_tokens = tokens.cache.read`, `output_tokens = tokens.output + tokens.reasoning`. Der Kontext-Füllstand nutzt per-Turn-Usage (`context_is_per_turn`-Marker wie bei Codex), da OpenCodes `tokens.input` je Turn den aktuellen Konversationsumfang widerspiegelt.

### D) Ablösung des rohen OpenRouter-HTTP-Pfads
- Der Eintrag `key: openrouter` (`driver: openai`) wird **aus `engines.yaml` entfernt** → OpenRouter/GLM ist nur noch über OpenCode wählbar.
- Die Treiberwahl im Manager ist **key-agnostisch** (verzweigt auf `driver`, nicht auf den Key) → kein Code bricht. Hartkodierte `"openrouter"`-Literale existieren nur in Anzeige-/Sortierlisten (Registry-Prioritäten) und überspringen einen fehlenden Key sauber.
- **Swisscom bleibt unangetastet** (eigener `openai`-Eintrag) — der `OpenAIDriver` bleibt also im Code erhalten, nur ohne OpenRouter-Nutzung.
- **Bestandsschutz:** vor der Ablösung gestartete OpenRouter-HTTP-Sessions laufen über den (weiter existierenden) `OpenAIDriver`-Code zu Ende bzw. degradieren beim nächsten Restart kontextlos — kein Crash.

### E) API/Schnittstellen-Form
**Keine neuen HTTP-Endpoints.** OpenCode erscheint automatisch über die bestehende Registry-Snapshot-Antwort (`GET /engines`, `GET/PUT /settings/engines`, PROJ-51) → Launcher-Dropdown + Engine-/Modellverwaltung. Der bestehende `context_status` (PROJ-56, read-only) wird für OpenCode-Sessions gesetzt. Vertrag bleibt: `StreamEvent(type, subtype, raw)` + Usage-Reader.

### F) Tech-Entscheidungen (WARUM, für PM)
- **Adapter statt Spezialtreiber:** OpenCode „spricht nur eine andere JSON-Sprache" auf stdout — exakt die Aufgabe der Adapter-Schicht. Ein eigener Treiber wäre Duplizierung des erprobten Codex-Pfads.
- **Self-Resume über Session-ID (statt Verlauf-Replay):** OpenCode hält den Kontext serverseitig (eigene DB). Wir merken uns nur die **ID** und reichen sie mit `-s` durch — billig, kein Token-Overspend durch Replay (die PROJ-45-Sorge entfällt hier ganz). Live verifiziert.
- **Auth ohne Key im Repo:** Subprozesse erben `HOME=/home/dev` → OpenCode nutzt seinen eigenen Auth-Store (`auth.json`, OpenRouter-Key) — genau wie Codex/Claude. **Kein** `auth_env`, kein Key in Jupiters Config.
- **Echte USD-Kosten (Novum):** Anders als Claude Max / Codex (Subscription, „n/v") liefert OpenRouter über OpenCode **echte `cost` je Turn**. → `engine_shows_cost = true` möglich; Token-Dashboard (PROJ-19) / Budget-Monitor (PROJ-52) können für diese Engine echte € statt „n/v" zeigen. **Design-Entscheidung nötig** (siehe G4).
- **`generic_cli`-Degradation akzeptiert (User-Entscheidung 4A):** keine Decision Cards/Gate/Watchdog. Leitplanke = Betrieb als User `dev` mit auf den Projektpfad gepinntem `cwd` (siehe G3 — Sandbox-Realität).

### G) Offene Design-Fragen — jetzt entschieden (live verifiziert)
1. **Modell-Slugs** ✅ am Live-System (`opencode models`) verifiziert: `openrouter/z-ai/glm-5.2`, `openrouter/minimax/minimax-m3`, `openrouter/moonshotai/kimi-k2.7-code`, `openrouter/qwen/qwen3.7-plus` (Default; `qwen3.7-max` als stärkere Alternative verfügbar), `openrouter/deepseek/deepseek-v4-pro` (Default; `deepseek-v4-flash` als schnelle Alternative). Default-Modell des Eintrags = `minimax/minimax-m3` (vom User gewählt).
2. **Provider-Präfix** ✅ `-m openrouter/<slug>` funktioniert direkt (OpenRouter ist in OpenCode als Provider konfiguriert + Key in `auth.json`). **Kein** Ausrollen einer `opencode.json` nötig.
3. **Session-ID-Quelle** ✅ `sessionID` steht in **jedem** Event (schon im ersten `step_start`) → trivial abfangbar, kein `--print-logs`/ACP-Modus nötig. Fehlt sie ausnahmsweise → sauberer kontextloser Start (bestehender PROJ-56-Fallback).
4. **Sandbox-Realität (WICHTIG, braucht kurze User-Bestätigung):** OpenCode hat — anders als Codex (`-s workspace-write` = OS-Sandbox) — **keine OS-Sandbox**. Im Headless-`run` müssen Permissions non-blocking sein, sonst hängt der Turn. Vorschlag: `--auto` (Permissions auto-approven) + `cwd` fest auf den Projektpfad + Betrieb als `dev`. Das entspricht praktisch Codex `danger-full-access` — die Leitplanke ist „Projektpfad + kein Root", nicht ein echter Syscall-Sandbox. **Ehrliche Einordnung:** minimal schwächer als Codex' `workspace-write`. Alternative (strenger, aber komplexer): eine Jupiter-verwaltete OpenCode-Permission-Config mit `edit: allow`, `bash: deny` — schränkt Shell-Zugriff ein, kann aber legitime Agenten-Arbeit blockieren. **→ Empfehlung: `--auto` + cwd-Pinning; kurz bestätigen.**
5. **PROJ-56-Deckelung** ✅ self-resume → kein `messages`-Replay-Pfad für OpenCode; der GLM-Deckel bleibt allein für Swisscom/etwaige HTTP-Engines relevant.

### H) Abhängigkeiten (Pakete)
**Keine neuen.** Alles vorhanden: `generic_cli`-Treiber, Adapter-Schicht, Registry-Loader, Usage-Pfad, PROJ-56-Persistenz. `opencode` (v1.17.13) ist auf dem VPS installiert + mit OpenRouter-Key eingeloggt (verifiziert).

### I) Risiken / Grenzen (dokumentiert)
- **Keine OS-Sandbox** (siehe G4) — bewusste, dokumentierte Grenze; Leitplanke = Projektpfad-`cwd` + Non-Root.
- **Keine Tool-Gate-Signale** (`generic_cli` ohne PreToolUse-Hook) → Decision Cards/Gate/Watchdog/`tool_in_flight` greifen nicht; langer Lauf ohne Output kann als „hängt" fehlbewertet werden — bekannte `generic_cli`-Grenze (wie Codex/hermes). OpenCode streamt jedoch `tool`-Events → als `tool_use` sichtbar, was die Fehlbewertung mildert.
- **Schema-Drift bei OpenCode-Update:** Adapter defensiv (unbekannte Events ignorieren); v1.17.13 als Referenz notiert.
- **Regression:** Adapter-Registry rein additiv; OpenRouter-Entfernung ist YAML-only und key-agnostisch → claude/codex/swisscom/hermes unberührt.

### J) Umsetzungsreihenfolge (für /abc-backend)
1. `opencode_parse_line`-Adapter + Registrierung (`_ADAPTERS`) — mit echtem OpenCode-JSON-Sample als Testfixture.
2. Usage-Mapping (`tokens{input,output,reasoning,cache}` → Claude-Form; `cost` durchreichen) + `context_is_per_turn`-Marker.
3. `engines.yaml`-Eintrag (`opencode`, `generic_cli`, absolutes `bin`, `argv_template` + `resume_argv_template`, `adapter: opencode`, `oneshot: true`, `--auto`, Modell-Liste + Default) · `openrouter`-Eintrag entfernen · `engines.example.yaml` spiegeln.
4. `engine_shows_cost`-Entscheidung (G4/Kosten) umsetzen.
5. Tests: Adapter-Mapping (Sample), Registrierung, Fake-OpenCode-CLI für Resume-argv, PROJ-56-Auslöser (Restart · Reanimierung · `_resume`) für OpenCode, Regressionscheck Codex/Claude/Swisscom.

### Routing (welcher Specialist baut was)
- **Backend Developer:** Adapter + Usage + `engines.yaml`-Eintrag + OpenRouter-Entfernung + Tests. → `/abc-backend`
- **QA Engineer:** Acceptance-Criteria (Live-Text, Turn-Ende, Token/€-Anzeige, Resume-Kontext ≥2 Turns, Auth-ohne-Key, drei PROJ-56-Auslöser), Regression Codex/Claude/Swisscom, Red-Team (kein Key in `to_read()`/Persistenz). → `/abc-qa`
- **Kein Frontend-Ticket** nötig (Launcher/Cockpit/Engine-Verwaltung engine-agnostisch). Falls eine feste Engine-Reihenfolge/Labels im Dialog gewünscht ist → kleiner Frontend-Zusatz.

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
