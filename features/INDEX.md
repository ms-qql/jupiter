# Feature Index — Jupiter

**Next Available ID:** PROJ-34

Status-Werte: Planned → Architected → In Progress → In Review → Approved → Deployed

## Phase 0 — MVP

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-1 | Engine-Treiber: Claude-Max-Session headless | P0 | Approved | — | [Spec](PROJ-1-engine-treiber-claude-headless.md) |
| PROJ-2 | Vault-Anbindung als Dienst | P0 | Approved | — | [Spec](PROJ-2-vault-anbindung-dienst.md) |
| PROJ-3 | Cockpit: Mission Control + Kanban + Ampel-Kacheln | P0 | Approved | PROJ-1, PROJ-2 | [Spec](PROJ-3-cockpit-mission-control-kanban.md) |
| PROJ-4 | Decision Cards (Freigabe-Flow) | P0 | Deployed | PROJ-1, PROJ-3 | [Spec](PROJ-4-decision-cards.md) |
| PROJ-5 | Context-Management & Handover | P0 | Deployed | PROJ-1, PROJ-2, PROJ-3 | [Spec](PROJ-5-context-management-handover.md) |
| PROJ-6 | Knappheits-Konstitution | P0 | Approved | PROJ-1 | [Spec](PROJ-6-knappheits-konstitution.md) |
| PROJ-7 | MD-Reader | P0 | Deployed | PROJ-2 | [Spec](PROJ-7-md-reader.md) |
| PROJ-8 | ABC-Workflow-Gantt (Phasen-Fortschritt je Session) | P0 | Deployed | PROJ-3, PROJ-1 | [Spec](PROJ-8-abc-workflow-gantt.md) |

## Phase 1 — Ausbau

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-9 | Smart Launcher (mitdenkender Session-Start) | P1 | Deployed | PROJ-3, PROJ-1 | [Spec](PROJ-9-smart-launcher.md) |
| PROJ-10 | Trust-Policy (abgestuft, konfigurierbar) + Phasen-Gate | P1 | Deployed | PROJ-4, PROJ-6, PROJ-8 | [Spec](PROJ-10-trust-policy.md) |
| PROJ-11 | Fileexplorer + Drag-and-Drop | P1 | Deployed | PROJ-1, PROJ-3 | [Spec](PROJ-11-fileexplorer.md) |
| PROJ-12 | MD-Editor (voll, Obsidian-DNA) | P1 | Deployed | PROJ-7 | [Spec](PROJ-12-md-editor.md) |
| PROJ-13 | Git-Branch-Handling (in-App, abc-konform) | P1 | Planned | PROJ-3 | [Spec](PROJ-13-git-branch-handling.md) |
| PROJ-14 | PROJ-1-Härtung: Limit + Persistenz | P1 | Deployed | PROJ-1 | [Spec](PROJ-14-engine-haertung-limit-persistenz.md) |
| PROJ-15 | Vault Stufe 3 (lebendes Gehirn + Kuratierung) | P1 | Deployed | PROJ-2, PROJ-4, PROJ-5 | [Spec](PROJ-15-vault-stufe-3.md) |
| PROJ-16 | Amok-Watchdog + Limits | P1 | Deployed | PROJ-1, PROJ-4, PROJ-10 | [Spec](PROJ-16-amok-watchdog.md) |
| PROJ-17 | Recovery über den Vault | P1 | Deployed | PROJ-2, PROJ-5, PROJ-14 | [Spec](PROJ-17-recovery-vault.md) |
| PROJ-18 | Weitere Engines + iFrame/Launch | P1 | Deployed | PROJ-1 | [Spec](PROJ-18-weitere-engines.md) |
| PROJ-19 | Effizienz-Ausbau (RAG/Späher/Caching/Token-Dashboard) | P1 | Architected | PROJ-1, PROJ-2, PROJ-5 | [Spec](PROJ-19-effizienz-ausbau.md) |
| PROJ-20 | Spracheingabe / Push-to-Talk (abo-frei) | P1 | Planned | PROJ-9, PROJ-4 | [Spec](PROJ-20-spracheingabe.md) |
| PROJ-21 | Session-Löschen / Cockpit-Aufräumen | P1 | Deployed | PROJ-1, PROJ-14, PROJ-3 | [Spec](PROJ-21-session-loeschen-cockpit-aufraeumen.md) |

## Phase 1.5 — Fixes & Verfeinerungen (Live-Betrieb)

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-27 | Verifizierter Liveness-Indikator + Reanimieren hängender Sessions | P1 | Deployed | PROJ-1, PROJ-3, PROJ-14, PROJ-16 | [Spec](PROJ-27-liveness-reanimieren.md) |
| PROJ-28 | Fileexplorer Drei-Spalten-Layout (Sidebar · Panel · Ansicht) | P1 | Planned | PROJ-11, PROJ-7 | [Spec](PROJ-28-fileexplorer-drei-spalten.md) |
| PROJ-29 | Eingabefeld-Höhe symmetrisch zu den 3 Buttons | P2 | Planned | PROJ-3, PROJ-11 | [Spec](PROJ-29-eingabefeld-hoehe-symmetrie.md) |
| PROJ-30 | Kanban-Phasenerkennung im Bypass-Mode (QA/Deploy) | P1 | Planned | PROJ-8, PROJ-1 | [Spec](PROJ-30-kanban-phasen-bypass.md) |
| PROJ-31 | Spec-Links im MD-Reader auflösen (Doku führt ins Leere) | P1 | Planned | PROJ-7, PROJ-12 | [Spec](PROJ-31-md-reader-spec-links.md) |
| PROJ-32 | Fortschritts-Signal aus Tool-Aktivität (kein False-„hängt" bei langen Tools) | P1 | Deployed | PROJ-16, PROJ-27, PROJ-4 | [Spec](PROJ-32-fortschritt-aus-tool-aktivitaet.md) |
| PROJ-33 | Session-Lifecycle-Härtung (Restart-Resilienz + prozess-verifiziertes Liveness) | P1 | Deployed | PROJ-1, PROJ-14, PROJ-27, PROJ-17 | [Spec](PROJ-33-session-lifecycle-haertung.md) |

## Phase 2 — Skalierung (Orchestrierung & Team)

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-22 | Multi-Agent-Dispatch-Schicht + Vertrag-zuerst/Koordinator | P2 | Planned | PROJ-1, PROJ-3, PROJ-4, PROJ-2, PROJ-9 | [Spec](PROJ-22-multi-agent-dispatch.md) |
| PROJ-23 | Cross-Agent-Review / Challenge (engine-übergreifend) | P2 | Planned | PROJ-18, PROJ-22, PROJ-4, PROJ-2 | [Spec](PROJ-23-cross-agent-review.md) |
| PROJ-24 | Vault als geteilter Dienst (auch für eingebettete Apps) | P2 | Planned | PROJ-2, PROJ-15, PROJ-18 | [Spec](PROJ-24-vault-geteilter-dienst.md) |
| PROJ-25 | Echtes Auth (JWT) + Scope/RLS auf `owner` | P2 | Planned | PROJ-2, PROJ-24 | [Spec](PROJ-25-auth-jwt-scope-rls.md) |
| PROJ-26 | Marktplatz/Registry für Rollen/Skills/Agenten | P2 | Planned | PROJ-6, PROJ-1, PROJ-10, PROJ-25 | [Spec](PROJ-26-marktplatz-registry.md) |

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
