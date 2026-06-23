# PRD — Jupiter

**Stand:** 2026-06-22
**Status:** Phase-0-MVP spezifiziert
**Referenz-Messlatte:** [Wayland](https://github.com/FerroxLabs/wayland)
**Brainstorm-Grundlage:** [docs/Brainstorm-jupiter.md](Brainstorm-jupiter.md) (30 Bausteine, 3 Phasen)

---

## Vision

Jupiter ist eine **selbstgehostete Kommandozentrale**, die deine KI-Agenten — allen voran **Claude Max** — als überwachbare, token-sparsame Flotte orchestriert. Der **Hal-Vault** ist das gemeinsame Gedächtnis, der **abc-Workflow** das native Betriebssystem. Jupiter ersetzt das heutige Terminal-+-Tailscale-Setup durch eine Web-GUI, in der mehrere Sessions parallel laufen, sichtbar sind und an Schaltstellen freigegeben werden.

**Drei Grundprinzipien:**
1. **Cockpit-first, nicht Chat-first** — du steuerst eine Flotte, statt in ein leeres Feld zu tippen.
2. **Autonom by default, Eingriff nur an Schaltstellen** — Agenten laufen allein, du entscheidest das Wichtige.
3. **Token-Sparsamkeit by Design** — kein Geschnatter, das richtige Modell für die richtige Aufgabe.

---

## Zielnutzer

| Nutzer | Bedürfnis / Pain Point |
|---|---|
| **Solo-Entwickler (du, heute)** | Mehrere Claude-Max-Sessions parallel steuern ohne Terminal-Jonglage; Kontext-Bloat & Token-Verschwendung vermeiden; Wissen/Doku an einem Ort. |
| **Team (später, Phase 2)** | Mehrere Personen teilen dieselbe Kommandozentrale; Zuordnung von Sessions/Wissen zu Eigentümern; Rollen/Rechte. |

MVP-Annahme: **single-user**. Jedes Artefakt trägt ein `owner`-Feld (heute immer du), damit die spätere Team-Migration billig bleibt (Baustein #21).

---

## Roadmap

Legende Priorität: **P0** = MVP (jetzt spezifiziert) · **P1** = Ausbau · **P2** = Skalierung.

| ID | Feature | Prio | Bausteine | Status |
|----|---------|------|-----------|--------|
| PROJ-1 | Engine-Treiber: Claude-Max-Session headless | P0 | #6, #22 | Planned |
| PROJ-2 | Vault-Anbindung als Dienst | P0 | #8, #9, #14, #21 | Planned |
| PROJ-3 | Cockpit: Mission Control + Session-Kanban + Ampel-Kacheln | P0 | #1, #2, #3, #22 | Planned |
| PROJ-4 | Decision Cards (Freigabe-Flow) | P0 | #4 | Planned |
| PROJ-5 | Context-Management & Handover | P0 | #7, #8, #25 | Planned |
| PROJ-6 | Knappheits-Konstitution | P0 | #24 | Planned |
| PROJ-7 | MD-Reader | P0 | #16 | Planned |
| PROJ-8 | ABC-Workflow-Gantt (Phasen-Fortschritt je Session) | P0 | Cockpit-Ausbau | In Progress |
| PROJ-9 | Smart Launcher (liest features/INDEX.md) | P1 | #12 | Planned |
| PROJ-10 | Trust-Policy / Konstitution (konfigurierbar) | P1 | #5 | Planned |
| PROJ-11 | Fileexplorer + Drag-and-Drop | P1 | #15 | Planned |
| PROJ-12 | MD-Editor mit Obsidian-Features (voll) | P1 | #16 | Planned |
| PROJ-13 | Git-Branch-Handling (in-App, abc-konform: main ↔ dev, Feature-Branches, Promote) | P1 | #31 | Planned |
| PROJ-14 | PROJ-1-Härtung: Limit paralleler Sessions + Persistenz (QA-3) | P1 | — | Planned |
| PROJ-15 | Vault Stufe 3: lebendes Gehirn + roh↔kuratiert + Kuratierung | P1 | #9, #10, #11 | Planned |
| PROJ-16 | Amok-Watchdog + Limits | P1 | #19 | Planned |
| PROJ-17 | Recovery über den Vault | P1 | #20 | Planned |
| PROJ-18 | Weitere Engines (Codex/Gemini/GLM/Ollama) + iFrame/Launch | P1 | #13 | Planned |
| PROJ-19 | Effizienz-Ausbau: Pointer/RAG, Späher-Agenten, Prompt-Caching, Token-Dashboard | P1 | #23, #26, #27, #28 | Planned |
| PROJ-20 | Spracheingabe / Push-to-Talk (abo-frei) | P1 | #29 | Planned |
| — | Multi-Agent: Dispatch-Schicht + Vertrag-zuerst/Koordinator | P2 | #17, #18 | Roadmap |
| — | Cross-Agent-Review / Challenge (engine-übergreifend) | P2 | #30 | Roadmap |
| — | Vault als geteilter Dienst (auch für eingebettete Apps) | P2 | #14 | Roadmap |
| — | Echtes Auth (JWT) + Scope/RLS auf `owner` | P2 | #21 | Roadmap |
| — | Marktplatz/Registry für Rollen/Skills/Agenten | P2 | — | Roadmap |

---

## Success Metrics

- **Ablösung:** Du steuerst deine Claude-Max-Arbeit vollständig aus Jupiter statt aus dem Terminal.
- **Parallelität:** ≥ 3 Sessions parallel ohne Übersichtsverlust managebar.
- **Token-Disziplin:** Kontext-Füllstand pro Session jederzeit sichtbar; Handover greift, bevor das Fenster überläuft.
- **Entscheidungs-Latenz:** Eine wartende Session ist in < 5 s aus der Decision Card heraus entscheidbar.
- **Gedächtnis:** Jede Session hinterlässt ein lesbares MD-Artefakt im Hal-Vault.

---

## Constraints

- **Frontend:** Next.js 16 (App Router) + React + Tailwind + shadcn/ui (Default-Stack Option B). Web-first über Tailscale; Desktop-App später.
- **Backend:** FastAPI (Python 3.11+), raw SQL via `run_query_m`/`run_command_m`, Pydantic v2; Conda-Env `Dashboard`.
- **DB:** Postgres (Dokploy-gehostet) als schneller **Live-Index** des flüchtigen Session-Zustands.
- **Wahrheit/Persistenz:** Hal-Vault (`/home/dev/tools/Hal`, Obsidian, PARA-Struktur) als **persistente Wahrheit/Recovery-Quelle** — offenes MD.
- **Engine MVP:** ausschließlich Claude Max via **Claude Code headless** (`claude -p`, Stream-JSON, Subscription-Auth, **kein** API-Key). Modell-Routing über `--model`.
- **DSGVO:** keine US-CDNs; Web-Fonts via Bunny Fonts; Spracheingabe (P1) self-hosted/EU, **kein** Browser-Web-Speech-API.
- **Deploy:** Dokploy via `docker-compose.yml` (human-gated).

---

## Non-Goals (MVP / Phase 0)

- **Kein echtes Auth/RLS** — single-user; nur `owner`-Feld (#21).
- **Keine Fremd-Engines** — nur Claude Max; Codex/Gemini/GLM/Ollama erst P1 (#13).
- **Kein MD-Editor** — nur Reader (#16 voll = P1).
- **Kein Fileexplorer/Drag-and-Drop** (#15 = P1).
- **Kein Multi-Agent-Dispatch / Cross-Agent-Review** (#17/#18/#30 = P2).
- **Keine konfigurierbare Trust-Policy** — MVP nutzt einen fixen konservativen Freigabe-Trigger (#5 konfigurierbar = P1).
- **Kein Amok-Watchdog / keine Vault-Recovery** (#19/#20 = P1).

---

## Offene Punkte (vor/in der Architektur-Phase zu klären)

1. **🔑 Claude-Max-Engine technisch verifizieren** — `claude -p` headless mit Stream-JSON + Subscription-Auth steuerbar? (PROJ-1, riskantester Unbekannter.)
2. **🗄️ Live-Zustand vs. Wahrheit** — Datenmodell-Grenze Postgres (Live) ↔ Vault (Wahrheit).
3. **🧭 Vault-Struktur** — Ordner-/Namenskonvention für Jupiter-Artefakte innerhalb des bestehenden PARA-Layouts (`02 Projects/…` bzw. `Agentic OS/…`), ohne Bestehendes zu stören.
4. **🛑 Watchdog-Metriken** — konkrete Amok-Schwellen (P1, #19).
