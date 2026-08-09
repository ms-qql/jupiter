# Feature Index — Jupiter

**Next Available ID:** PROJ-78

Status-Werte: Planned → Architected → In Progress → In Review → Approved → Deployed

## Phase 0 — MVP

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-1 | Engine-Treiber: Claude-Max-Session headless | P0 | Deployed | — | [Spec](PROJ-1-engine-treiber-claude-headless.md) |
| PROJ-2 | Vault-Anbindung als Dienst | P0 | Deployed | — | [Spec](PROJ-2-vault-anbindung-dienst.md) |
| PROJ-3 | Cockpit: Mission Control + Kanban + Ampel-Kacheln | P0 | Deployed | PROJ-1, PROJ-2 | [Spec](PROJ-3-cockpit-mission-control-kanban.md) |
| PROJ-4 | Decision Cards (Freigabe-Flow) | P0 | Deployed | PROJ-1, PROJ-3 | [Spec](PROJ-4-decision-cards.md) |
| PROJ-5 | Context-Management & Handover | P0 | Deployed | PROJ-1, PROJ-2, PROJ-3 | [Spec](PROJ-5-context-management-handover.md) |
| PROJ-6 | Knappheits-Konstitution | P0 | Deployed | PROJ-1 | [Spec](PROJ-6-knappheits-konstitution.md) |
| PROJ-7 | MD-Reader | P0 | Deployed | PROJ-2 | [Spec](PROJ-7-md-reader.md) |
| PROJ-8 | ABC-Workflow-Gantt (Phasen-Fortschritt je Session) | P0 | Deployed | PROJ-3, PROJ-1 | [Spec](PROJ-8-abc-workflow-gantt.md) |

## Phase 1 — Ausbau

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-9 | Smart Launcher (mitdenkender Session-Start) | P1 | Deployed | PROJ-3, PROJ-1 | [Spec](PROJ-9-smart-launcher.md) |
| PROJ-10 | Trust-Policy (abgestuft, konfigurierbar) + Phasen-Gate | P1 | Deployed | PROJ-4, PROJ-6, PROJ-8 | [Spec](PROJ-10-trust-policy.md) |
| PROJ-11 | Fileexplorer + Drag-and-Drop | P1 | Deployed | PROJ-1, PROJ-3 | [Spec](PROJ-11-fileexplorer.md) |
| PROJ-12 | MD-Editor (voll, Obsidian-DNA) | P1 | Deployed | PROJ-7 | [Spec](PROJ-12-md-editor.md) |
| PROJ-13 | Git-Branch-Handling (in-App, abc-konform) | P1 | Deployed | PROJ-3 | [Spec](PROJ-13-git-branch-handling.md) |
| PROJ-14 | PROJ-1-Härtung: Limit + Persistenz | P1 | Deployed | PROJ-1 | [Spec](PROJ-14-engine-haertung-limit-persistenz.md) |
| PROJ-15 | Vault Stufe 3 (lebendes Gehirn + Kuratierung) | P1 | Deployed | PROJ-2, PROJ-4, PROJ-5 | [Spec](PROJ-15-vault-stufe-3.md) |
| PROJ-16 | Amok-Watchdog + Limits | P1 | Deployed | PROJ-1, PROJ-4, PROJ-10 | [Spec](PROJ-16-amok-watchdog.md) |
| PROJ-17 | Recovery über den Vault | P1 | Deployed | PROJ-2, PROJ-5, PROJ-14 | [Spec](PROJ-17-recovery-vault.md) |
| PROJ-18 | Weitere Engines + iFrame/Launch | P1 | Deployed | PROJ-1 | [Spec](PROJ-18-weitere-engines.md) |
| PROJ-19 | Effizienz-Ausbau (RAG/Späher/Caching/Token-Dashboard) | P1 | Deployed | PROJ-1, PROJ-2, PROJ-5 | [Spec](PROJ-19-effizienz-ausbau.md) |
| PROJ-20 | Spracheingabe / Push-to-Talk (abo-frei) | P1 | Deployed | PROJ-9, PROJ-4 | [Spec](PROJ-20-spracheingabe.md) |
| PROJ-21 | Session-Löschen / Cockpit-Aufräumen | P1 | Deployed | PROJ-1, PROJ-14, PROJ-3 | [Spec](PROJ-21-session-loeschen-cockpit-aufraeumen.md) |

## Phase 1.5 — Fixes & Verfeinerungen (Live-Betrieb)

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-27 | Verifizierter Liveness-Indikator + Reanimieren hängender Sessions | P1 | Deployed | PROJ-1, PROJ-3, PROJ-14, PROJ-16 | [Spec](PROJ-27-liveness-reanimieren.md) |
| PROJ-28 | Fileexplorer Drei-Spalten-Layout (Sidebar · Panel · Ansicht) | P1 | Deployed | PROJ-11, PROJ-7 | [Spec](PROJ-28-fileexplorer-drei-spalten.md) |
| PROJ-29 | Eingabefeld-Höhe symmetrisch zu den 3 Buttons | P2 | Deployed | PROJ-3, PROJ-11 | [Spec](PROJ-29-eingabefeld-hoehe-symmetrie.md) |
| PROJ-30 | Kanban-Phasenerkennung im Bypass-Mode (QA/Deploy) | P1 | Deployed | PROJ-8, PROJ-1 | [Spec](PROJ-30-kanban-phasen-bypass.md) |
| PROJ-31 | Spec-Links im MD-Reader auflösen (Doku führt ins Leere) | P1 | Deployed | PROJ-7, PROJ-12 | [Spec](PROJ-31-md-reader-spec-links.md) |
| PROJ-32 | Fortschritts-Signal aus Tool-Aktivität (kein False-„hängt" bei langen Tools) | P1 | Deployed | PROJ-16, PROJ-27, PROJ-4 | [Spec](PROJ-32-fortschritt-aus-tool-aktivitaet.md) |
| PROJ-33 | Session-Lifecycle-Härtung (Restart-Resilienz + prozess-verifiziertes Liveness) | P1 | Deployed | PROJ-1, PROJ-14, PROJ-27, PROJ-17 | [Spec](PROJ-33-session-lifecycle-haertung.md) |
| PROJ-34 | Chat-Modus im Neue-Session-Dialog (freies Chatfenster ohne ABC-Bezug) | P1 | Deployed | PROJ-3, PROJ-9, PROJ-1 | [Spec](PROJ-34-chat-modus-neue-session.md) |
| PROJ-35 | Session-Titel = eingegebener Projektname (Sidebar + Header) statt „jupiter" | P1 | Deployed | PROJ-3, PROJ-9 | [Spec](PROJ-35-session-titel-projektname-anzeigen.md) |
| PROJ-36 | Eingabe-Buttons auf drei Reihen (Senden · Mikro+Büroklammer · Stop) | P2 | Deployed | PROJ-3, PROJ-20, PROJ-11, PROJ-29 | [Spec](PROJ-36-eingabe-buttons-drei-reihen.md) |
| PROJ-37 | Fileexplorer: kein leeres Vorschau-Fenster — aktives Fenster (Session) bleibt | P1 | Deployed | PROJ-28, PROJ-11, PROJ-3 | [Spec](PROJ-37-fileexplorer-aktives-fenster-bleibt.md) |
| PROJ-38 | Sidebar-Sektionen + Konfig-Panel (Sichtbarkeit · Reorder · RESET) | P1 | Deployed | PROJ-3 | [Spec](PROJ-38-sidebar-sektionen-konfig-panel.md) |
| PROJ-39 | Sidebar-Sektion „Orchestration" — Fremd-Apps per iFrame (Paperclip, Wayland) | P1 | Deployed | PROJ-38, PROJ-3, PROJ-18 | [Spec](PROJ-39-sidebar-orchestration-iframe-apps.md) |
| PROJ-40 | Sidebar-Sektion „Micro-Apps" + Excalidraw-Migration aus „Werkzeuge" | P1 | Deployed | PROJ-38, PROJ-3, PROJ-18 | [Spec](PROJ-40-sidebar-micro-apps-excalidraw-migration.md) |
| PROJ-41 | Video Summary (native Micro-App: URL-Queue → `hal-video-summary` → Hal) | P1 | Deployed | PROJ-40, PROJ-1, PROJ-2 | [Spec](PROJ-41-video-summatizer-microapp.md) |
| PROJ-42 | VPS-Admin — Dashboard (native Micro-App: Metriken + Sidebar-Ampel) | P1 | Deployed | PROJ-40, PROJ-3, PROJ-38 | [Spec](PROJ-42-vps-admin-dashboard.md) |
| PROJ-43 | VPS-Admin — Terminal (ttyd-iFrame Shell-Zugriff) | P1 | Deployed | PROJ-42, PROJ-40, PROJ-3 | [Spec](PROJ-43-vps-admin-terminal.md) |
| PROJ-44 | Video Summary — Standard-Ordner · Bibliotheks-Kachel · Modellwahl | P1 | Deployed | PROJ-41, PROJ-2, PROJ-7 | [Spec](PROJ-44-video-summary-standardordner-bibliothek-modellwahl.md) |
| PROJ-45 | Auto-Reanimierungs-Budget — Endlosschleife & False-„hängt" abstellen (Token-Überspend) | P1 | Deployed | PROJ-27, PROJ-32, PROJ-16 | [Spec](PROJ-45-reanimierung-budget-endlosschleife-fix.md) |
| PROJ-46 | Live-Aktivitäts-Ticker — sehen, was der Agent gerade tut (Bypass-Mode) | P1 | Deployed | PROJ-4, PROJ-1, PROJ-3, PROJ-27 | [Spec](PROJ-46-live-aktivitaets-ticker-bypass.md) |
| PROJ-47 | Stream-Reader-Stall — verwaister Subprozess & eingefrorene Session-Anzeige | P1 | Deployed | PROJ-1, PROJ-14, PROJ-27 | [Spec](PROJ-47-stream-reader-stall-output-sync.md) |
| PROJ-48 | Engine — OpenAI Codex CLI (Pro-Subscription) als Jupiter-Agent | P1 | Deployed | PROJ-18, PROJ-1, PROJ-19 | [Spec](PROJ-48-engine-openai-codex-cli.md) |
| PROJ-49 | WebSocket-Flapping zum Browser — Stabilität + Event-Replay bei Reconnect | P1 | Deployed | PROJ-3, PROJ-1, PROJ-25 | [Spec](PROJ-49-websocket-flapping-event-replay.md) |
| PROJ-50 | abc-Workflow für die Codex-Engine (portierte Skills + Phasen-Signal) | P1 | Deployed | PROJ-48, PROJ-9, PROJ-8 | [Spec](PROJ-50-abc-workflow-codex-engine.md) |
| PROJ-51 | Engine- und Modellverwaltung in den App-Einstellungen | P1 | Deployed | PROJ-18, PROJ-48, PROJ-50, PROJ-9 | [Spec](PROJ-51-engine-modellverwaltung-einstellungen.md) |
| PROJ-52 | Sidebar Token-Budget-Monitor für Claude und Codex | P1 | Deployed | PROJ-3, PROJ-19, PROJ-48, PROJ-51 | [Spec](PROJ-52-sidebar-token-budget-monitor.md) |
| PROJ-53 | Buch-Nuggets (native Micro-App: Buch-Upload/URL → KI-Kurzform inkl. Contra → Hal) | P1 | Deployed | PROJ-40, PROJ-1, PROJ-2, PROJ-11, PROJ-51 | [Spec](PROJ-53-buch-nuggets-microapp.md) |
| PROJ-54 | Fable 5 als wählbares Claude-Modell (temporär, nur Neue-Session-Dialog) | P1 | Deployed | PROJ-1, PROJ-51 | [Spec](PROJ-54-fable-5-modellauswahl.md) |
| PROJ-55 | Session-Kondensierung — Wochen-Sweep alter Sessions in Hal-Knowledge | P1 | Deployed | PROJ-2, PROJ-1, PROJ-15 | [Spec](PROJ-55-session-kondensierung-hal-knowledge.md) |
| PROJ-56 | Kontext-Persistenz & Resume für Nicht-Claude-Engines (Codex, GLM/OpenRouter) | P1 | Deployed | PROJ-48, PROJ-18, PROJ-14 | [Spec](PROJ-56-kontext-persistenz-nicht-claude-engines.md) |
| PROJ-57 | Engine — OpenCode als Harness (OpenRouter-Modelle über OpenCode statt Direkt-HTTP) | P1 | Deployed | PROJ-18, PROJ-48, PROJ-56, PROJ-51 | [Spec](PROJ-57-engine-opencode-harness.md) |
| PROJ-58 | Bugfix: OpenCode-Stdin-Race — falsches „Wartet auf dich" + Transport-Fehler bei Folge-Eingabe | P1 | Deployed | PROJ-57, PROJ-48, PROJ-56 | [Spec](PROJ-58-opencode-stdin-race-wartet-auf-dich.md) |
| PROJ-59 | Bugfix: OpenCode-Session hängt nach „Stopp" in „Aktive Sessions" | P1 | Deployed | PROJ-57, PROJ-48, PROJ-56 | [Spec](PROJ-59-opencode-stop-haengt-in-aktive-sessions.md) |
| PROJ-60 | Bugfix: OpenCode-Session hängt lautlos in „Arbeitet" nach Absturz hinter Tool-Zwischenschritt | P1 | Deployed | PROJ-57, PROJ-58, PROJ-48 | [Spec](PROJ-60-opencode-lautloser-haenger-nach-absturz.md) |
| PROJ-61 | Live-Aktivitäts-Ticker fehlt im Connect-Snapshot (OpenCode/Codex wirken eingefroren) | P1 | Deployed | PROJ-46, PROJ-49 | [Spec](PROJ-61-live-aktivitaets-ticker-bei-connect.md) |
| PROJ-62 | Bugfix: OpenCode-Session endet lautlos ohne Transkript und ohne Fehler bei Tool-Only-Turn | P1 | Deployed | PROJ-57, PROJ-58, PROJ-60 | [Spec](PROJ-62-opencode-leeres-transkript-tool-only-turn.md) |
| PROJ-63 | Tmux-Session-Transport für stabile Jupiter-Agenten | P1 | Deployed | PROJ-1, PROJ-14, PROJ-27, PROJ-33, PROJ-56 | [Spec](PROJ-63-tmux-session-transport.md) |
| PROJ-64 | Bugfix: tmux-Transport-503 (BUG-4-Nachfolger) — Reaping-Race entschärfen statt nur sichtbar machen | P0 | Deployed | PROJ-63, PROJ-1, PROJ-27 | [Spec](PROJ-64-tmux-reaping-race-503-haertung.md) |
| PROJ-65 | Bugfix: Frisch erstellte tmux-Session zeigt sofort „beendet" statt aktiv (Status-Race bei schnellen Oneshot-Turns) | P0 | Planned | PROJ-63, PROJ-64, PROJ-56, PROJ-58, PROJ-60 | [Spec](PROJ-65-tmux-oneshot-status-race-nach-spawn.md) |
| PROJ-66 | Bugfix: Session-Transkript von Oneshot-Engines geht bei Backend-Neustart dauerhaft verloren | P0 | Deployed | PROJ-56, PROJ-58, PROJ-60, PROJ-63, PROJ-64 | [Spec](PROJ-66-transkript-persistenz-oneshot-engines-nach-neustart.md) |
| PROJ-67 | Peppermint Dashboard + automatische Frontdesk-Triage | P1 | Deployed | PROJ-40, PROJ-1, PROJ-48, PROJ-50, PROJ-14, PROJ-16 | [Spec](PROJ-67-peppermint-dashboard-frontdesk-triage.md) |
| PROJ-68 | Peppermint Ticket-Bedienung und Lösungs-Session | P1 | Deployed | PROJ-67, PROJ-9, PROJ-34, PROJ-1, PROJ-48, PROJ-50 | [Spec](PROJ-68-peppermint-ticket-bedienung-und-loesungs-session.md) |
| PROJ-69 | Clipboard (native Micro-App: geräteübergreifender Datei-Clipboard mit HAL Inbox) | P1 | Approved | PROJ-40, PROJ-2, PROJ-11 | [Spec](PROJ-69-clipboard-microapp.md) |
| PROJ-70 | Bugfix: Claude-Engine dupliziert Fragekarten nach jedem Resume (bis zu 6 gleiche Frageboxen) | P1 | Deployed | PROJ-48, PROJ-63, PROJ-27, PROJ-66 | [Spec](PROJ-70-claude-duplizierte-frageboxen-nach-resume.md) |
| PROJ-71 | Effort-Level (Reasoning-Effort) im Neue-Session-Dialog | P1 | Architected | PROJ-1, PROJ-18, PROJ-48, PROJ-57, PROJ-56, PROJ-51 | [Spec](PROJ-71-effort-level-neue-session.md) |
| PROJ-72 | Bugfix: Claude-Engine dupliziert Nachrichten (und Fragekarten) nach Resume/Restart — Replay eliminieren (Seek-to-End + DB-Transkript) | P1 | Deployed | PROJ-63, PROJ-66, PROJ-70, PROJ-27 | [Spec](PROJ-72-claude-transkript-dubletten-nach-resume.md) |
| PROJ-73 | Token Savings — globales, engine-übergreifendes Optimierungsprofil | P1 | Deployed | PROJ-1, PROJ-9, PROJ-48, PROJ-51, PROJ-52, PROJ-56, PROJ-57 | [Spec](PROJ-73-token-savings-profile.md) |
| PROJ-74 | Bugfix: Backend-Neustart orphaniert lebende tmux-Sessions unnötig (rehydrate() ignoriert echte Prozess-Liveness) | P1 | Deployed | PROJ-63, PROJ-27, PROJ-33, PROJ-66 | [Spec](PROJ-74-rehydrate-tmux-liveness-haertung.md) |
| PROJ-75 | Bugfix-Verifikation: PROJ-72-Transkript-Replay nach wiederholtem Resume in Produktion nicht restlos ausgeschlossen | P1 | Planned | PROJ-72, PROJ-63, PROJ-66, PROJ-70 | [Spec](PROJ-75-proj72-replay-produktionsverifikation.md) |
| PROJ-76 | Textdateien im Fileexplorer bearbeiten | P1 | In Review | PROJ-11, PROJ-12, PROJ-28, PROJ-37 | [Spec](PROJ-76-textdateien-im-fileexplorer-bearbeiten.md) |
| PROJ-77 | masterskill-creator — agenten-unabhängige Master-Skills in Hal + Pointer-Stubs je CLI | P1 | In Review | PROJ-50, PROJ-2 | [Spec](PROJ-77-masterskill-creator.md) |

## Phase 2 — Skalierung (Orchestrierung & Team)

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-22 | Multi-Agent-Dispatch-Schicht + Vertrag-zuerst/Koordinator | P2 | Deployed | PROJ-1, PROJ-3, PROJ-4, PROJ-2, PROJ-9 | [Spec](PROJ-22-multi-agent-dispatch.md) |
| PROJ-23 | Cross-Agent-Review / Challenge (engine-übergreifend) | P2 | Deployed | PROJ-18, PROJ-22, PROJ-4, PROJ-2 | [Spec](PROJ-23-cross-agent-review.md) |
| PROJ-24 | Vault als geteilter Dienst (auch für eingebettete Apps) | P2 | Deployed | PROJ-2, PROJ-15, PROJ-18 | [Spec](PROJ-24-vault-geteilter-dienst.md) |
| PROJ-25 | Echtes Auth (JWT) + Scope/RLS auf `owner` | P2 | Deployed | PROJ-2, PROJ-24 | [Spec](PROJ-25-auth-jwt-scope-rls.md) |
| PROJ-26 | Marktplatz/Registry für Rollen/Skills/Agenten | P2 | Deployed | PROJ-6, PROJ-1, PROJ-10, PROJ-25 | [Spec](PROJ-26-marktplatz-registry.md) |

## Empfohlene Bau-Reihenfolge (Phase 0)
1. **PROJ-1** — Engine-Treiber (riskantester Unbekannter; Verifikations-Spike zuerst)
2. **PROJ-6** — Konstitution (früh, weil sie das Verhalten aller Sessions prägt)
3. **PROJ-2** — Vault-Anbindung
4. **PROJ-3** — Cockpit
5. **PROJ-4** — Decision Cards
6. **PROJ-5** — Context-Management & Handover
7. **PROJ-7** — MD-Reader

## Empfohlene Bau-Reihenfolge (Phase 1)
Abhängigkeits-getrieben; grob: Härtung/Resilienz zuerst, dann Komfort, dann Effizienz.
1. **PROJ-14** — PROJ-1-Härtung (Limit + Persistenz) — Fundament für Recovery/Watchdog
2. **PROJ-10** — Trust-Policy — Voraussetzung für den Watchdog
3. **PROJ-16** — Amok-Watchdog (Reißleine)
4. **PROJ-17** — Recovery über den Vault
5. **PROJ-9** — Smart Launcher
6. **PROJ-13** — Git-Branch-Handling · **PROJ-11** — Fileexplorer · **PROJ-12** — MD-Editor
7. **PROJ-15** — Vault Stufe 3
8. **PROJ-18** — Weitere Engines · **PROJ-19** — Effizienz-Ausbau · **PROJ-20** — Spracheingabe

## Empfohlene Bau-Reihenfolge (Phase 2)
Abhängigkeits-getrieben: Orchestrierungs-Unterbau zuerst, dann Diversität/Review, dann Team/Teilen.
1. **PROJ-22** — Dispatch-Schicht + Vertrag (Orchestrierungs-Fundament)
2. **PROJ-18** — Weitere Engines (Voraussetzung für Modell-Diversität; Phase-1-Feature, vor PROJ-23 nötig)
3. **PROJ-23** — Cross-Agent-Review (braucht Dispatch + zweite Engine)
4. **PROJ-24** — Vault als geteilter Dienst
5. **PROJ-25** — echtes Auth (JWT) + Scope/RLS auf `owner`
6. **PROJ-26** — Marktplatz/Registry
