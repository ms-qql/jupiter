# Feature Index — Jupiter

**Next Available ID:** PROJ-21

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
| PROJ-7 | MD-Reader | P0 | Approved | PROJ-2 | [Spec](PROJ-7-md-reader.md) |
| PROJ-8 | ABC-Workflow-Gantt (Phasen-Fortschritt je Session) | P0 | Approved | PROJ-3, PROJ-1 | [Spec](PROJ-8-abc-workflow-gantt.md) |

## Phase 1 — Ausbau

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-9 | Smart Launcher (mitdenkender Session-Start) | P1 | Planned | PROJ-3, PROJ-1 | [Spec](PROJ-9-smart-launcher.md) |
| PROJ-10 | Trust-Policy (abgestuft, konfigurierbar) | P1 | Planned | PROJ-4, PROJ-6 | [Spec](PROJ-10-trust-policy.md) |
| PROJ-11 | Fileexplorer + Drag-and-Drop | P1 | Architected | PROJ-1, PROJ-3 | [Spec](PROJ-11-fileexplorer.md) |
| PROJ-12 | MD-Editor (voll, Obsidian-DNA) | P1 | Planned | PROJ-7 | [Spec](PROJ-12-md-editor.md) |
| PROJ-13 | Git-Branch-Handling (in-App, abc-konform) | P1 | Planned | PROJ-3 | [Spec](PROJ-13-git-branch-handling.md) |
| PROJ-14 | PROJ-1-Härtung: Limit + Persistenz | P1 | Planned | PROJ-1 | [Spec](PROJ-14-engine-haertung-limit-persistenz.md) |
| PROJ-15 | Vault Stufe 3 (lebendes Gehirn + Kuratierung) | P1 | Planned | PROJ-2, PROJ-4, PROJ-5 | [Spec](PROJ-15-vault-stufe-3.md) |
| PROJ-16 | Amok-Watchdog + Limits | P1 | Planned | PROJ-1, PROJ-4, PROJ-10 | [Spec](PROJ-16-amok-watchdog.md) |
| PROJ-17 | Recovery über den Vault | P1 | Planned | PROJ-2, PROJ-5, PROJ-14 | [Spec](PROJ-17-recovery-vault.md) |
| PROJ-18 | Weitere Engines + iFrame/Launch | P1 | Planned | PROJ-1 | [Spec](PROJ-18-weitere-engines.md) |
| PROJ-19 | Effizienz-Ausbau (RAG/Späher/Caching/Token-Dashboard) | P1 | Planned | PROJ-1, PROJ-2, PROJ-5 | [Spec](PROJ-19-effizienz-ausbau.md) |
| PROJ-20 | Spracheingabe / Push-to-Talk (abo-frei) | P1 | Planned | PROJ-9, PROJ-4 | [Spec](PROJ-20-spracheingabe.md) |

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

## Roadmap (noch ohne Spec — siehe docs/PRD.md)
- **P2:** Multi-Agent-Dispatch #17/#18 · Cross-Agent-Review #30 · Vault als geteilter Dienst #14 · echtes Auth/RLS #21 · Registry
