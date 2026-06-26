# PROJ-50: abc-Workflow für die Codex-Engine (portierte Skills + Phasen-Signal)

## Status: Planned
**Created:** 2026-06-26
**Last Updated:** 2026-06-26

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
- **⚠️ Noch zu verifizieren (Architektur-Spike):** welche konkreten `item`-Events Codex beim Lauf einer Skill emittiert (Skill-Name im Stream?), damit das Phasen-Signal sauber andocken kann.

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
_To be added by /abc-architecture_
