# PROJ-50: abc-Workflow für die Codex-Engine (portierte Skills + Phasen-Signal)

## Status: In Progress
**Created:** 2026-06-26
**Last Updated:** 2026-06-26

## Implementierungs-Notizen (Backend, 2026-06-26)
Umgesetzt auf Branch `dev`, aufbauend auf PROJ-48 (codex-Adapter/Resume).

**Was gebaut wurde**
- **Skill-Generator** `scripts/gen_codex_skills.py` (+ optionale Overlays unter `scripts/codex_skill_overlays/`): leitet aus `~/.claude/skills/abc-*` reproduzierbar/idempotent **alle 15** Codex-Varianten nach `~/.codex/skills/abc-*` ab. Frontmatter bereinigt (Claude-only-Keys raus, `metadata.short-description` ergänzt), Claude-Ismen per Regelwerk ersetzt/markiert, Codex-Präambel vorangestellt, optionales Per-Skill-Overlay. Modi: `--check` (CI-Drift), `--dry-run`. **0 tote `/home/dev/.claude`-Pfade** in der Ausgabe.
- **codex-Adapter** (`adapters.py`): `item.completed`/`file_change` → generisches **`tool_use`**-StreamEvent (`name=Write|Edit`, `input.file_path`), auch bei `status:failed` (Pfad steht im Stream).
- **`handle_event`** (`manager.py`): neuer `tool_use`-Zweig speist die **unveränderte** engine-agnostische `detect_phase_signal`/`_apply_phase` an einem **zweiten** Punkt (Output-Stream statt Claude-PreToolUse-Gate) → Feature-Erkennung + Live-Ticker (PROJ-46) für alle stream-basierten Engines. Claude nutzt den Pfad nicht → keine Regression.
- **Launcher-Seeding** (`manager.create`): für abc-Engines **ohne** Claude-Hook (Codex) wird ein reiner `/abc-…`-Trigger in die **Skill-benennende** Form umgeschrieben **und** die Phase aus dem Prompt geseedet (`abc_phase/_reached/_feature`) → Kanban/Gantt ab Start korrekt.
- **Launcher engine-bewusst** (`launcher.py` + `GET /projects/suggestion?engine=`): Codex bekommt Skill-benennende Anstoß-Prompts, Claude unverändert `/abc-…`.
- **Capability `abc`** an Codex (`engines.yaml`/`.example.yaml`) und builtin-Claude (`registry.py`).
- Neue abc_phases-Helfer: `phase_from_prompt`, `seed_triple_from_prompt`, `phase_trigger_prompt`, `rewrite_trigger_for_engine`.

**Spike-Ergebnis (entscheidend):** Codex emittiert **kein** Skill-Event → Phase via Launcher-Seeding, Feature/Fortschritt via `file_change`-Stream (s. „Verifizierte Befunde" + Tech-Design E).

**Tests:** `backend/tests/test_proj50_codex_abc.py` (18 Tests: Adapter, handle_event-Phasenpfad, Seeding-/Trigger-Helfer, Launcher-Naming, Capability, Generator-Idempotenz/Frontmatter). **Volle Suite: 895 grün, keine Regression.**

**Realer Codex-E2E (Stream-Pipeline):** Codex zieht die portierte `abc-document`-Skill per Name; `file_change`→`tool_use`→`detect_phase_signal` ergibt phase=document/feature=1. Datei-Schreiben scheiterte nur am **verschachtelten Sandkasten der Test-Shell** (bwrap-in-bwrap) — kein Produktdefekt; voller Cockpit-E2E gehört in `abc-qa` auf dem laufenden Backend.

**Offen für QA/Deploy:** (1) voller Cockpit-Durchlauf einer Phase mit sichtbarem Kanban + geschriebener Spec/INDEX auf dem echten Backend; (2) Degradations-Hinweis im UI (überwiegend aus PROJ-48); (3) Generator-`--check` als optionaler CI-Schritt.

## Dependencies
- Requires: **PROJ-48** (Engine — OpenAI Codex CLI) — liefert Codex als lauffähige Engine (generic_cli + `codex`-Adapter + Multi-Turn via resume). **Erst danach sinnvoll.**
- Requires: PROJ-9 (Smart Launcher) — Quelle der Phasen-Prompts (`/abc-{phase} {nr}`); hier kommt die engine-bewusste Prompt-Variante rein.
- Requires: PROJ-8 / PROJ-30 (ABC-Phasen-Erkennung, Kanban/Gantt) — keyt auf das `Skill`-Invocation-Signal; muss aus dem Codex-Stream gespeist werden.
- Verwandt: PROJ-18 (Engine-Registry/Adapter) — der Codex-Adapter wird um Skill-Signal-Mapping erweitert.
- **Degradiert bewusst** (wie alle generic_cli-Engines): kein PreToolUse-Hook → **keine** Decision Cards (PROJ-4), **kein** Phasen-Gate (PROJ-10/30-Gate), **kein** Amok-Watchdog am Tool-Gate (PROJ-16). Die Human-in-the-Loop-Checkpoints der abc-Skills greifen nur über das Selbst-Pausieren des Modells; Sandbox `workspace-write` bleibt die Leitplanke.

## Kontext / Ziel
Der Nutzer will den **abc-Workflow** (`/abc-requirements`, `/abc-architecture`, `/abc-frontend`, `/abc-backend`, `/abc-qa`, `/abc-document`, … — alle abc-Skills) nicht nur mit Claude, sondern **auch mit der Codex-Engine** (PROJ-48) fahren: Session mit Codex starten, eine abc-Phase auslösen, Codex arbeitet die SKILL.md-Anweisungen ab, und Jupiter erkennt die Phase korrekt (Kanban/Gantt), genau wie bei Claude.

## Verifizierte Befunde (2026-06-26, am Live-System geprüft — nicht erneut suchen)
- **Codex hat ein eigenes Skill-System:** `~/.codex/skills/` mit **demselben SKILL.md-Format** wie Claude Code (YAML-Frontmatter `name`/`description`/`metadata` + Markdown-Body). System-Skills liegen unter `~/.codex/skills/.system/` (skill-installer, skill-creator, …). Eigene Skills kommen in `$CODEX_HOME/skills/<name>/SKILL.md`. Codex meldet nach Skill-Install: „Restart Codex to pick up new skills."
- **Skill-Auswahl bei Codex:** über **Description-Matching** (Modell wählt anhand der `description`), **nicht** über `/slash`-Syntax. Der heutige Launcher-Prompt `/abc-architecture 8` triggert die Codex-Skill daher nicht zuverlässig.
- **Die abc-Skills sind Claude-Code-spezifisch:** ihre SKILL.md referenzieren Claude-Tools (`Agent`/`Explore`-Subagenten, `AskUserQuestion`, Skill-Chaining über das `Skill`-Tool, CodeGraph-MCP) und **absolute Pfade** `/home/dev/.claude/skills/...`. Codex hat ein anderes Tool-/Sub-Agent-Modell (shell-basiert). Ein reiner Symlink würde diese Claude-Ismen mitschleppen.
- **Phasen-Erkennung ist im Prinzip engine-agnostisch:** `detect_phase_signal` keyt auf `tool_name == "Skill"` + `tool_input.skill` ([abc_phases.py:178](backend/app/engine/abc_phases.py#L178)), gemappt via `phase_for_skill()`. Sie braucht aber, dass die **Engine dieses Signal emittiert** — bei Codex muss der Adapter (PROJ-48) Codex' Skill-Invocation-Events darauf mappen.
- **abc-Workflow ist nicht capability-gegated:** heute für alle Engines unconditional verfügbar; kein `has_capability("abc")`-Check.
- **Modell:** Codex läuft auf `gpt-5.5` (aus `~/.codex/config.toml`, s. PROJ-48).
- **✅ Architektur-Spike aufgelöst (2026-06-26, codex-cli 0.142.2, `codex exec --json`):** Codex emittiert **KEIN** Skill-Invocation-Event. Der Stream kennt nur `thread.started`, `turn.started/completed` und `item.started/completed` mit `item.type ∈ {agent_message, file_change, …}`. Der Skill-Inhalt fließt unsichtbar in den Modell-Kontext; **der Skill-Name taucht nicht im Stream auf**. → Der im Spec angenommene primäre Skill-Event-Pfad ist **nicht realisierbar**. Verwertbar ist `item.completed` mit `item.type=file_change` (trägt `changes[].path`, sogar bei `status:failed`). Konsequenz (s. Tech-Design, Abschnitt „Spike-Korrektur"): **Phase = launcher-seeded** (Launcher kennt die angeforderte Phase ohnehin), **Feature/Fortschritt = aus `file_change`-Pfaden** des Streams.

## Geklärte Design-Entscheidungen (2026-06-26, mit Nutzer)
1. **Skill-Quelle → eigene Codex-Variante** ✅ (gewählt). Es werden **gepflegte Codex-Varianten** der abc-Skills unter `~/.codex/skills/abc-*` angelegt — **kein** Symlink auf `~/.claude/skills`. Begründung: die Claude-Ismen (Agent/Explore, AskUserQuestion, Skill-Chaining, absolute `.claude`-Pfade) stören Codex; eine eigene Variante ist sauber an Codex' Tool-/Sub-Agent-Modell angepasst. (Verworfen: Symlink = eine Quelle, aber kaputte Tool-Referenzen.) **Trade-off bewusst akzeptiert:** doppelte Pflege der SKILL.md-Inhalte.
2. **Umfang → alle abc-Skills** ✅ (gewählt). Portiert werden **alle** `abc-*`-Skills (requirements, architecture, brainstorm, challenge, clarification, deploy, document, dokploy-data, frontend, fullstack, launch-app, qa, qa-e2e, refactor), nicht nur der Kern. (Verworfen: erst nur architecture/backend/qa.)

## User Stories
- Als Nutzer möchte ich eine **Codex-Session** starten und **jede abc-Phase** (`/abc-…`) auslösen, sodass Codex die jeweilige SKILL.md-Anweisung abarbeitet — analog Claude.
- Als Nutzer möchte ich, dass **Kanban/Gantt die Phase korrekt anzeigt**, auch wenn die Phase von Codex (statt Claude) bearbeitet wird.
- Als Nutzer möchte ich, dass der **Smart Launcher** mir Codex-Sessions mit der richtigen Phasen-Auslösung vorbereitet (Codex versteht die Skill-Auswahl).
- Als Nutzer möchte ich, dass die **abc-Skill-Inhalte für Codex funktionieren** (keine toten Claude-Tool-/Pfad-Referenzen, die Codex ins Leere laufen lassen).
- Als Nutzer möchte ich **nachvollziehbar sehen**, wo der abc-Workflow mit Codex anders/eingeschränkt ist (keine Decision Cards/Gate/Watchdog).

## Acceptance Criteria
- [ ] **Codex-abc-Skills installiert:** alle `abc-*`-Skills liegen als Codex-Variante unter `~/.codex/skills/abc-*/SKILL.md` (gültiges Frontmatter, Codex erkennt sie nach Neustart). Bereitstellung reproduzierbar (Skript/Make-Target, nicht handgeklöppelt).
- [ ] **Claude-Ismen übersetzt/entfernt:** in den Codex-Varianten sind Claude-spezifische Tool-Aufrufe (`Agent`/`Explore`, `AskUserQuestion`, Skill-Chaining via `Skill`-Tool) und absolute `/home/dev/.claude/...`-Pfade durch Codex-taugliche Äquivalente ersetzt oder klar als „in Codex nicht verfügbar" markiert. Die fachliche Phasen-Logik (Was/Warum, Akzeptanzkriterien, Status-Update-Contract, INDEX.md-Pflege) bleibt erhalten.
- [ ] **Engine-bewusster Launcher-Prompt:** der Smart Launcher erzeugt für Codex-Sessions eine Prompt-Variante, die Codex die Skill **zuverlässig wählen lässt** (z. B. „Nutze die Skill »abc-architecture« für Feature 50 …"), statt nur `/abc-architecture 50`. Für Claude bleibt das heutige Verhalten unverändert.
- [ ] **Phasen-Signal aus Codex-Stream:** wenn Codex eine abc-Skill ausführt, mappt der Codex-Adapter das auf das vorhandene `Skill`-Signal (`phase_for_skill`), sodass `detect_phase_signal` greift → Kanban/Gantt zeigen die richtige Phase. Mind. eine Phase (z. B. `architecture`) end-to-end nachgewiesen.
- [ ] **End-to-End-Lauf:** mindestens **eine vollständige abc-Phase** (Vorschlag: `/abc-architecture` oder `/abc-document`) läuft mit Codex durch — Skill greift, Output im Cockpit, Phase im Kanban, Spec/INDEX korrekt aktualisiert.
- [ ] **Degradation dokumentiert + sichtbar:** ohne Decision Cards/Gate/Watchdog läuft die Codex-abc-Session stabil; das UI macht die Engine-Grenzen nachvollziehbar (analog generic_cli-Engines / PROJ-48).
- [ ] **Keine Regression:** Claude-abc-Workflow, Phasen-Erkennung für Claude und andere Engines (hermes/ollama) unverändert. Tests grün; deutsche Texte/Logs.

## Edge Cases
- **Codex wählt die falsche/keine Skill:** Description-Matching ist unscharf → Launcher-Prompt muss die Skill eindeutig benennen; Fallback wenn Codex keine Skill zieht (Phase bleibt None — wie heute bei stummen Engines, kein Hard-Fail).
- **Skill ruft eine andere Skill auf (Chaining):** in Claude über das `Skill`-Tool; in Codex evtl. nicht verfügbar → in der Codex-Variante als sequenzielle Nutzer-/Prompt-Schritte umformulieren statt automatischem Chaining.
- **Sub-Agent-Schritte (Explore/CodeGraph) in Skills:** Codex hat kein Jupiter-Explore-Agent-Modell → in der Codex-Variante durch direkte Shell-/Such-Anweisungen ersetzen oder weglassen; CodeGraph-MCP-Aufrufe kennzeichnen.
- **Skill-Update driftet:** Claude- und Codex-Variante können auseinanderlaufen → Quelle der Wahrheit + Sync-Mechanismus festlegen (s. offene Frage).
- **`AskUserQuestion`-Checkpoints:** in Codex nicht als Tool vorhanden → als normale Rückfrage im Text formulieren (Mensch antwortet im nächsten Turn; Multi-Turn aus PROJ-48 nötig).
- **Codex-Neustart nötig:** neue/aktualisierte Skills greifen erst nach Codex-Reload → Bereitstellungs-Schritt muss das berücksichtigen (Sessions neu starten).

## Technical Requirements (optional)
- **Skill-Bereitstellung:** reproduzierbares Skript/Target, das die abc-Skills als Codex-Variante nach `~/.codex/skills/` schreibt (Transformations-/Generierungsschritt, nicht nur Kopie).
- **Adapter-Erweiterung (PROJ-48-`codex`-Adapter):** Skill-/Tool-Invocation-Events aus dem Codex-JSONL auf das `Skill`-Signal mappen (Skill-Name extrahieren → `phase_for_skill`). Hängt am Architektur-Spike (welche `item`-Events Codex liefert).
- **Launcher (PROJ-9):** engine-bewusste Prompt-Erzeugung (Claude: `/abc-…`; Codex: Skill-benennende Formulierung). Möglichst datengetrieben (kein if-Wust).
- **Optionale capability:** Engines könnten `capabilities: [abc]` führen, um die abc-Auslösung im Launcher pro Engine sauber zu steuern (heute ungated) — Designentscheidung in /abc-architecture.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung |
|---|---|
| **PROJ-48 (Codex-Engine)** | `codex`-Adapter wird um Skill-Signal-Mapping erweitert; sonst unberührt. |
| **PROJ-8/30 (Phasen-Erkennung/Kanban)** | Bekommt Phasen-Signal jetzt auch aus Codex-Sessions; Logik selbst unverändert (engine-agnostisch). |
| **PROJ-9 (Smart Launcher)** | Engine-bewusste Phasen-Prompt-Variante für Codex. |
| **PROJ-4/10/16 (Cards/Gate/Watchdog)** | Greifen bei Codex/generic_cli **nicht** — bekannte, dokumentierte Grenze. |
| **abc-Skills (extern, `~/.claude/skills`)** | Quelle für die Codex-Varianten; Claude-Originale bleiben unverändert. |

## Offene Design-Fragen (für /abc-architecture — mit Default-Vorschlag)
1. **Sync-Strategie Claude→Codex-Variante:** *Default-Vorschlag:* ein Generator-Skript, das aus den Claude-SKILL.md eine Codex-taugliche Variante ableitet (Claude-Ismen per Regelwerk übersetzen), damit Updates nicht doppelt von Hand gepflegt werden. Alternative: einmalige manuelle Codex-Skills, danach getrennt gepflegt.
2. **Phasen-Signal-Quelle bei Codex:** *Default-Vorschlag:* primär über das Codex-Skill-Event (sobald der Spike das Event-Schema bestätigt); Fallback über Datei-Touches auf `features/PROJ-X-*.md` (vorhandener Fallback in `abc_phases.py`), falls Codex kein eindeutiges Skill-Event liefert.
3. **capability-Gate `abc`:** *Default-Vorschlag:* einführen (`capabilities: [abc]`), damit der Launcher pro Engine sauber entscheidet, ob/wie er abc-Phasen anbietet — statt unconditional für alle.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-26 · **Stack:** Backend FastAPI (Engine-Adapter + Launcher) · Skill-Generator (Python-Skript/Make-Target) · Frontend nur Hinweis-Anzeige (überwiegend aus PROJ-48) · **Branch:** dev

### Leitidee (in einem Satz)
Codex bekommt **eigene, gepflegte Varianten der abc-Skills** (kein Symlink), der **Codex-Adapter übersetzt** Codex' Skill-Aufruf-Event in dasselbe interne `Skill`-Signal, und der **Smart Launcher** formuliert den Phasen-Anstoß so, dass Codex die richtige Skill **per Description** zieht — alles über die bereits engine-agnostische Phasen-Logik, ohne sie zu verändern.

### Architektur-Befund, der das Design trägt (am Live-Code geprüft)
- Die Phasen-Erkennung (`detect_phase_signal` / `phase_for_skill`) ist **engine-agnostisch** und bleibt **unverändert**. Sie erwartet ein Tool-Signal der Form *Tool-Name `Skill` + `tool_input.skill = "abc-…"`* (+ optionales Feature-Argument).
- **Aber:** dieses Signal wird heute **nur im PreToolUse-Gate** ausgewertet (`manager.py:633`, im `_handle_tool`-Pfad). Diesen Hook hat **nur Claude**. Der generische Stream-Pfad `handle_event` (`manager.py:445`) verarbeitet bisher nur `system/assistant/result/rate_limit` — **kein Tool-/Skill-Event**.
- Folgerung: Für Codex (und alle generic_cli-Engines) muss das Phasen-Signal aus dem **Output-Stream** gespeist werden. Das ist die zentrale neue Verdrahtung dieses Features — und sie verallgemeinert sauber auf alle stream-basierten Engines, nicht nur Codex.
- Adapter-Muster steht bereit: ein Adapter ist genau eine Funktion `Zeile → StreamEvent | None` (`adapters.py`, Registry `claude/jsonl/plaintext`). PROJ-48 liefert den `codex`-Adapter; PROJ-50 erweitert ihn um die Skill-Event-Übersetzung.
- `EngineProfile` hat bereits ein `capabilities`-Feld + `has_capability()` (`registry.py:26/102`) — heute z. B. `[usage, multi_turn]`. Eine `abc`-Capability ist **nur Konfiguration + eine Launcher-Abfrage**, keine neue Infrastruktur.
- Der Launcher baut den Anstoß-Prompt in `_feature_suggestion` (`launcher.py:188`) heute **engine-blind** als `"/abc-{phase} {nr}"`.

### A) Bausteine & Verantwortung (was wird gebaut)
```
1. Skill-Generator (Tooling, Backend-Dev)
   scripts/gen_codex_skills.py  +  scripts/codex_skill_rules.yaml
   └── liest  ~/.claude/skills/abc-*/SKILL.md   (Quelle der Wahrheit)
   └── transformiert Claude-Ismen → Codex-tauglich (Regelwerk + Overlay)
   └── schreibt ~/.codex/skills/abc-*/SKILL.md   (gültiges Frontmatter)
   └── Make-/CLI-Target „codex-skills“ (reproduzierbar, idempotent)

2. Codex-Adapter-Erweiterung (Backend-Dev)
   backend/app/engine/adapters.py   (codex-Adapter aus PROJ-48)
   └── erkennt Codex' Skill-Invocation-Item  →  emittiert ein internes
       „Skill“-Signal (Name + Feature-Arg)
   └── normalisiert Codex' Datei-Schreib-Tool  →  Write/Edit  (Fallback-Pfad)

3. Stream-seitige Phasen-Verdrahtung (Backend-Dev)
   backend/app/engine/manager.py  (handle_event)
   └── NEU: bei Skill-/Tool-Signal aus dem Stream  →  detect_phase_signal()
       + _apply_phase()  (dieselbe Logik wie im Gate, nur anderer Einspeise-Punkt)

4. Engine-bewusster Launcher (Backend-Dev)
   backend/app/engine/launcher.py  (_feature_suggestion)
   └── Engine hat capability „abc“  →  prompt-Variante je Engine:
       Claude  : "/abc-architecture 50"          (unverändert)
       Codex   : "Nutze die Skill »abc-architecture« für Feature 50 …"

5. Capability-Konfig (Backend-Dev)
   backend/config/engines.yaml
   └── claude: capabilities += [abc]    codex: capabilities += [abc]

6. Degradations-Hinweis (Frontend, minimal)
   └── „Diese Engine: keine Decision Cards / kein Gate / kein Watchdog“
       — möglichst denselben generic_cli-Hinweis wie PROJ-48 wiederverwenden.
```

### B) Datenfluss (Phase landet im Kanban)
```
Smart Launcher  ──(capability abc?)──►  engine-bewusster Anstoß-Prompt
        │                                   │
        ▼                                   ▼
   Claude: /abc-…                     Codex wählt Skill per Description
        │                                   │  arbeitet ~/.codex/skills/abc-…/SKILL.md ab
   PreToolUse-Gate                     Codex-Stream-Item „skill invoked: abc-architecture“
   (Skill-Signal)                            │
        │                              codex-Adapter übersetzt → internes Skill-Signal
        ▼                                   ▼
   detect_phase_signal  ◄───────────────────┘   (EINE engine-agnostische Funktion)
        │
        ▼
   _apply_phase  →  Kanban/Gantt zeigen „architecture“  (PROJ-8/30, unverändert)
```
Fallback, falls Codex kein eindeutiges Skill-Item liefert: Datei-Touch auf `features/PROJ-X-*.md` (vorhandener Write/Edit-Zweig in `detect_phase_signal`) — dafür normalisiert der Adapter Codex' Schreib-Tool-Namen auf `Write/Edit`.

### C) Keine neuen Schnittstellen / DB / MinIO
- **Keine** neuen HTTP-Endpunkte, **keine** DB-Tabellen, **kein** MinIO. Reine Engine-/Tooling-Änderung hinter den bestehenden Session-APIs.
- Externe Berührungspunkte: das Dateisystem `~/.codex/skills/` (Generator-Output) und Codex' Stream-Format (vom Adapter gelesen).

### D) Entscheidungen zu den offenen Design-Fragen
1. **Sync-Strategie Claude→Codex (Frage 1): Generator-Skript mit Regelwerk + Overlay.** Quelle der Wahrheit bleiben die Claude-Originale (`~/.claude/skills/abc-*`). Ein Generator wendet ein **Regelwerk** an (absolute `/home/dev/.claude/...`-Pfade neutralisieren, Claude-Tool-Referenzen `Agent`/`Explore`/`AskUserQuestion`/`Skill`-Chaining übersetzen oder als „in Codex nicht verfügbar“ markieren) und mischt pro Skill ein optionales **Overlay** (Hand-Patch für Stellen, die echte Umformulierung brauchen — z. B. Explore→Shell-Suche). Begründung: ein reiner Automat übersetzt die Claude-Ismen nicht zuverlässig, reine Handarbeit driftet; das Overlay kapselt nur das Nicht-Automatisierbare. (Verworfen: einmalig manuell — laut Spec doppelte Pflege.)
2. **Phasen-Signal-Quelle (Frage 2): primär Codex-Skill-Event, Fallback Datei-Touch.** Primär das übersetzte Skill-Signal aus dem Stream; Fallback der vorhandene `Write/Edit`+`features/PROJ-X-*.md`-Zweig. Beide laufen über **dieselbe** `detect_phase_signal` — kein Zweitpfad in der Logik.
3. **Capability-Gate `abc` (Frage 3): einführen.** `capabilities: [abc]` an Codex **und** Claude; der Launcher entscheidet datengetrieben (`has_capability("abc")`), ob/wie er den Phasen-Anstoß formuliert — statt unconditional. Engines ohne `abc` (z. B. reine Chat-Engines) bekommen keinen abc-Anstoß mehr aufgedrängt.

### E) Spike-Korrektur (durchgeführt 2026-06-26) — Phasen-Signal real
Der Spike (s. „Verifizierte Befunde") zeigt: **Codex liefert kein Skill-Event**. Das ursprüngliche „Adapter mappt Skill-Event → `Skill`-Signal" ist damit gegenstandslos. Realisiertes Design:
- **Phase: launcher-seeded.** Der engine-bewusste Launcher kennt die angeforderte Phase (`abc-architecture` → `architecture`) und das Feature; `manager.create` **seedet** `abc_phase/_reached/_feature` direkt in den Session-State, sobald die Engine die `abc`-Capability hat und **kein** Claude-PreToolUse-Skill-Signal liefert (also generic_cli/Codex). Claude bleibt bei Stream/Hook-Erkennung — keine Regression.
- **Feature/Fortschritt: aus dem Stream.** Der `codex`-Adapter mappt `item.completed`/`file_change` → ein generisches **`tool_use`-StreamEvent** (`name=Write`, `input.file_path`). `handle_event` bekommt einen neuen `tool_use`-Zweig, der den Aktivitäts-Ticker (PROJ-46) füttert **und** `detect_phase_signal`/`_apply_phase` aufruft → `feature_from_path` hält die Feature-Nummer frisch. Generalisiert sauber auf alle stream-basierten Engines; Claude nutzt diesen Pfad nicht (Hook-basiert) → keine Regression.
- Das `Skill`-Signal-Mapping im Adapter entfällt; die engine-agnostische `detect_phase_signal` bleibt **unverändert** und wird nur an einem zweiten Punkt (Stream statt Gate) eingespeist.

### F) Bewusste Grenzen (Degradation — wie generic_cli/PROJ-48)
Kein PreToolUse-Hook bei Codex → **keine** Decision Cards (PROJ-4), **kein** Phasen-Gate (PROJ-10/30-Gate), **kein** Tool-Gate-Watchdog (PROJ-16). Human-in-the-Loop greift nur über das **Selbst-Pausieren** des Modells (abc-Checkpoints als Klartext-Rückfrage, dank Multi-Turn aus PROJ-48); Sandbox `workspace-write` bleibt die harte Leitplanke. Das UI macht diese Grenze sichtbar (selber Hinweis wie PROJ-48).

### G) Abhängigkeiten / Pakete
- **Keine neuen Python-Pakete.** Generator nutzt Standardbibliothek (+ ggf. das bereits vorhandene YAML) für das Regelwerk.
- Voraussetzung: PROJ-48 ist gebaut (codex-Adapter + Multi-Turn vorhanden). PROJ-50 setzt darauf auf.

### H) Bau-Reihenfolge & Routing
1. **Spike** (Codex-Stream-Item-Schema) → *Backend-Dev*  ⟵ Gate für alles Weitere
2. **Skill-Generator** + Regelwerk/Overlay + Make-Target → *Backend-Dev (Tooling)*
3. **Codex-Adapter**: Skill-Event-Übersetzung + Schreib-Tool-Normalisierung → *Backend-Dev*
4. **handle_event**-Verdrahtung (Stream → `detect_phase_signal`) → *Backend-Dev*
5. **Launcher** engine-bewusst + **engines.yaml** `capabilities:[abc]` → *Backend-Dev*
6. **Frontend**: Degradations-Hinweis (falls nicht schon aus PROJ-48 da) → *Frontend-Dev (minimal)*
7. **QA/E2E**: eine Phase (`abc-architecture` oder `abc-document`) end-to-end mit Codex; Regression Claude/hermes/ollama → *QA-Engineer*

> Schwerpunkt **Backend**; Frontend nur ein kleiner Hinweis. Kein UI-Feature im engeren Sinn → `/abc-frontend` entfällt fast vollständig, direkt `/abc-backend`.
