# Feature Index — Jupiter

**Next Available ID:** PROJ-8

Status-Werte: Planned → Architected → In Progress → In Review → Approved → Deployed

## Phase 0 — MVP

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-1 | Engine-Treiber: Claude-Max-Session headless | P0 | Planned | — | [Spec](PROJ-1-engine-treiber-claude-headless.md) |
| PROJ-2 | Vault-Anbindung als Dienst | P0 | Planned | — | [Spec](PROJ-2-vault-anbindung-dienst.md) |
| PROJ-3 | Cockpit: Mission Control + Kanban + Ampel-Kacheln | P0 | Planned | PROJ-1, PROJ-2 | [Spec](PROJ-3-cockpit-mission-control-kanban.md) |
| PROJ-4 | Decision Cards (Freigabe-Flow) | P0 | Planned | PROJ-1, PROJ-3 | [Spec](PROJ-4-decision-cards.md) |
| PROJ-5 | Context-Management & Handover | P0 | Planned | PROJ-1, PROJ-2, PROJ-3 | [Spec](PROJ-5-context-management-handover.md) |
| PROJ-6 | Knappheits-Konstitution | P0 | Planned | PROJ-1 | [Spec](PROJ-6-knappheits-konstitution.md) |
| PROJ-7 | MD-Reader | P0 | Planned | PROJ-2 | [Spec](PROJ-7-md-reader.md) |

## Empfohlene Bau-Reihenfolge (Phase 0)
1. **PROJ-1** — Engine-Treiber (riskantester Unbekannter; Verifikations-Spike zuerst)
2. **PROJ-6** — Konstitution (früh, weil sie das Verhalten aller Sessions prägt)
3. **PROJ-2** — Vault-Anbindung
4. **PROJ-3** — Cockpit
5. **PROJ-4** — Decision Cards
6. **PROJ-5** — Context-Management & Handover
7. **PROJ-7** — MD-Reader

## Roadmap (noch ohne Spec — siehe docs/PRD.md)
- **P1:** Smart Launcher #12 · Trust-Policy #5 · Fileexplorer #15 · MD-Editor #16 · Vault Stufe 3 #9/#10/#11 · Watchdog #19 · Recovery #20 · weitere Engines #13 · RAG/Späher/Caching/Token-Dashboard #23/#26/#27/#28 · Spracheingabe #29
- **P2:** Multi-Agent-Dispatch #17/#18 · Cross-Agent-Review #30 · Vault als geteilter Dienst #14 · echtes Auth/RLS #21 · Registry
