# PROJ-22: Multi-Agent-Dispatch-Schicht + Vertrag-zuerst/Koordinator

## Status: In Progress
**Created:** 2026-06-23
**Last Updated:** 2026-06-25
**Baustein:** #17, #18
**Prio:** P2 (Phase 2 — Skalierung)

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — der Koordinator startet/steuert mehrere Spezialisten-Sessions über dasselbe Treiber-Modell.
- Requires: PROJ-3 (Cockpit/Kanban) — die dispatchten Sessions müssen als zusammengehörige Flotte sichtbar sein (Eltern-/Kind-Beziehung).
- Requires: PROJ-4 (Decision Cards) — bei Konflikten/Eskalation erzeugt der Koordinator eine Card statt selbst zu entscheiden.
- Requires: PROJ-2 (Vault-Anbindung) — der API-Vertrag (#18) wird als Vault-Artefakt abgelegt und von allen Spezialisten gelesen.
- Requires: PROJ-9 (Smart Launcher) — der Koordinator nutzt dieselbe „nächste-Phase/Rolle/Skill"-Logik, um Tickets dem richtigen Spezialisten zuzuweisen.
- Verwandt: PROJ-10 (Trust-Policy) — Koordinator-Aktionen (Sessions starten, Tickets verteilen) unterliegen derselben Policy.
- Verwandt: PROJ-23 (Cross-Agent-Review) — baut auf der hier entstehenden Dispatch-Schicht + dem Vertrags-Artefakt auf.

## Beschreibung
Heute ist die „Hauptsession" (der Mensch bzw. ein Workflow) der einzige Orchestrator: du zerlegst Tickets und verteilst sie von Hand an Coordinator → Product Architect → Backend/Frontend → QA (siehe `rules/agents/README.md`). Dieses Feature **materialisiert die Dispatch-Rolle in Jupiter**: ein **Koordinator-Modus** liest Tickets aus `features/INDEX.md`, verteilt sie an Spezialisten-Sessions, überwacht deren Fortschritt und vermittelt bei Konflikten.

Zwei Bausteine in einem Feature, weil sie nur zusammen funktionieren:
- **#17 Dispatch-Schicht** — der Koordinator startet pro Ticket eine Spezialisten-Session (richtige Rolle/Skill/Engine), hält die Eltern-Kind-Beziehung und aggregiert Status.
- **#18 Vertrag-zuerst + Schiedsrichter** — der Architect legt zuerst den **API-Vertrag** als Vault-Artefakt fest; alle Spezialisten bauen **gegen dieses Dokument**. Bei Widerspruch (z. B. Frontend erwartet ein Feld, das Backend nicht liefert) vermittelt der Koordinator anhand des Vertrags; löst sich das nicht auf, eskaliert er als Decision Card an den Menschen.

**Grundhaltung:** Das **Dokument ist der objektive Schiedsrichter**, der Agent nur Vermittler. Der Mensch bleibt an den Schaltstellen (Card-Eskalation), nicht im Klein-Klein.

## User Stories
- Als Nutzer möchte ich einen **Koordinator-Modus** starten, der offene Tickets aus `features/INDEX.md` liest und mir einen Verteilungsplan (Ticket → Spezialist/Engine) vorschlägt, bevor er Sessions startet.
- Als Nutzer möchte ich, dass der Koordinator pro Ticket eine **Spezialisten-Session** mit passender Rolle/Skill/Engine startet und ich die ganze Gruppe als **eine Flotte** im Cockpit sehe.
- Als Nutzer möchte ich, dass der **API-Vertrag** als Vault-Artefakt festgehalten wird und alle Spezialisten nachweislich dagegen bauen.
- Als Nutzer möchte ich, dass der Koordinator bei einem Vertrags-Konflikt zwischen zwei Sessions **automatisch vermittelt** und mir nur das Unlösbare als Decision Card vorlegt.
- Als Nutzer möchte ich jederzeit sehen, **welches Ticket bei welcher Session** liegt und in welchem abc-Phasen-Zustand es ist.
- Als Nutzer möchte ich den Koordinator **anhalten/übersteuern** können (manuell ein Ticket umverteilen oder eine Kind-Session direkt übernehmen).

## Acceptance Criteria
- [ ] Es gibt einen **Koordinator-Modus**, der `features/INDEX.md` liest und offene Tickets (Status ≠ Deployed/Approved nach Wahl) als verteilbare Arbeit erkennt.
- [ ] Vor dem Start zeigt der Koordinator einen **Verteilungsplan** (Ticket → Rolle/Skill/Engine + Reihenfolge unter Beachtung der `Abhängigkeiten`-Spalte); der Nutzer gibt ihn frei (Human-in-the-Loop).
- [ ] Der Koordinator **startet Spezialisten-Sessions** über das Treiber-Modell (PROJ-1) und hält je Kind-Session die Zuordnung `ticket_id` + `parent_coordinator_id`.
- [ ] Das Cockpit zeigt die Koordinator-Session und ihre Kind-Sessions als **zusammengehörige Gruppe** (Eltern-Kind sichtbar, nicht als lose Einzelkacheln).
- [ ] Der **API-Vertrag** wird als Vault-Artefakt abgelegt (Pfad/Konvention dokumentiert); Spezialisten-Sessions erhalten einen **Pointer** darauf (kein Volltext-Duplikat).
- [ ] Bei einem erkannten **Konflikt gegen den Vertrag** versucht der Koordinator zuerst eine **automatische Vermittlung** (verweist beide Seiten auf den Vertrag); erst wenn das scheitert, entsteht eine **Decision Card** (PROJ-4) mit dem Konflikt + relevantem Ausschnitt.
- [ ] Der Nutzer kann den Koordinator **pausieren**, ein Ticket **manuell umverteilen** und eine Kind-Session **direkt übernehmen**.
- [ ] Koordinator-Aktionen unterliegen der **Trust-Policy** (PROJ-10): „Session starten" / „Ticket verteilen" sind policy-gegatete Aktionen.
- [ ] Die Abhängigkeits-Reihenfolge wird respektiert: ein Ticket wird **nicht** dispatcht, solange ein `Requires`-Ticket nicht im erforderlichen Zustand ist.
- [ ] Alle Texte deutsch.

## Edge Cases
- **Zirkuläre/fehlende Abhängigkeit** in `INDEX.md` → Koordinator meldet es als Warnung und dispatcht nur den auflösbaren Teilgraphen, statt zu blockieren oder zu raten.
- **Spezialisten-Session stirbt/hängt** (Amok, Crash) → Koordinator markiert das Ticket als „blockiert", erzeugt Card; nutzt Watchdog (PROJ-16) falls vorhanden.
- **Zwei Sessions ändern dasselbe Artefakt** → Vertrag entscheidet; ist das Artefakt nicht vom Vertrag gedeckt → Card.
- **Vertrag ändert sich mitten im Lauf** → laufende Spezialisten erhalten ein Update-Signal (Pointer bleibt gleich, Inhalt neu); offene Arbeit gegen die alte Version wird als potenziell veraltet markiert.
- **Koordinator selbst läuft Amok** (verteilt endlos) → eigene Limits/Watchdog greifen wie bei jeder Session.
- **Kein freier Engine-Slot** (Limit paralleler Sessions, PROJ-14) → Koordinator reiht Tickets ein statt sie fallen zu lassen.
- **Nutzer übersteuert, während der Koordinator dispatcht** → manuelle Aktion gewinnt; Koordinator rechnet seinen Plan auf dem neuen Stand neu.
- **Ticket ohne klare Rolle/Skill** (kein abc-Bezug) → Koordinator schlägt eine Default-Rolle vor, dispatcht aber erst nach Bestätigung.

## Technical Requirements (optional)
- Baut auf der bestehenden In-memory-Session-/Treiber-Architektur (PROJ-1) auf; Koordinator = spezielle Session mit Kind-Referenzen, kein eigener Parallel-Stack.
- Vertrags-Artefakt im Vault (MD), referenziert per **Pointer** (konsistent mit der Pointer-statt-Volltext-Linie #23).
- Eltern-Kind-Beziehung im Live-Index (Postgres/in-memory) abgelegt; Wahrheit/Recovery weiterhin über den Vault (PROJ-17).
- Single-User-MVP-Linie bleibt: kein JWT/RLS in diesem Feature (kommt mit PROJ-25); `owner`-Feld wird mitgeführt.
- Koordinator-Logik nutzt vorhandene Mechaniken wieder (Smart-Launcher-Vorschlag, Decision-Card-Future, Phasensignal) statt neue Parallelpfade.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js (Cockpit) + FastAPI (Engine) + Vault (MD) · **Branch:** dev

### 0. Codebasis-Abgleich (warum dieses Design ggü. der Spec angepasst ist)
Die Spec wurde am 2026-06-23 geschrieben; die Codebasis hat sich seither weiterentwickelt.
Re-Validierung gegen den heutigen Stand (CodeGraph + Explore) ergibt **drei Korrekturen**,
die das Feature **vereinfachen** statt erschweren:

1. **Live-Index ist rein in-memory, nicht „Postgres/in-memory".** Sessions (`SessionManager`-
   Registry) und Decision Cards (`decisions.py`) leben im Speicher; Wahrheit/Recovery laufen
   über den Vault (PROJ-17). → **Kein neues DB-Schema.** Die Fleet-Beziehung wird als Feld am
   bestehenden `SessionState` geführt, Recovery wie gehabt über den Vault.
2. **Eltern-Kind existiert bereits (1:1).** Der „Staffelstab" aus PROJ-5 nutzt
   `parent_session_id` / `child_session_id`. → Neu ist nur die **1:N-Flotte**
   (ein Koordinator → viele Spezialisten): ein zusätzliches `child_session_ids`-Listenfeld
   + ein `ticket_id` je Kind. Kein Parallel-Stack.
3. **INDEX.md-Parsing + Rollen-Mapping existieren bereits.** `launcher.parse_index_features()`
   liest Status/Prio, `launcher.suggest()` mappt Ticket-Status → abc-Phase → Skill/Engine.
   → Wiederverwenden; **neu** ist nur das Auslesen der **`Abhängigkeiten`-Spalte** für die
   topologische Dispatch-Reihenfolge.

**Fazit:** Architektur bleibt wie in der Spec skizziert (Koordinator = spezielle Session mit
Kind-Referenzen). Die einzige inhaltliche Anpassung ggü. der Spec ist Punkt 1 (kein Postgres
für den Live-Index — das `**Live-Index (Postgres/in-memory)**` der Technical Requirements ist
heute „in-memory + Vault-Recovery").

### A) Komponenten-Struktur (Cockpit)
```
CockpitScreen
├── KoordinatorBar (neuer Modus-Einstieg)
│   ├── "Koordinator starten"-Button  → liest INDEX.md
│   └── VerteilungsplanDialog (Human-in-the-Loop, Freigabe vor Dispatch)
│       ├── PlanTabelle (Ticket → Rolle/Skill/Engine → Reihenfolge)
│       ├── AbhängigkeitsWarnung (zirkulär/fehlend → nur auflösbarer Teilgraph)
│       └── [Freigeben] / [Abbrechen]
├── KanbanBoard (bestehend, components/cockpit/kanban-board.tsx)
│   └── FleetGroup (NEU: Koordinator-Kachel + eingerückte Kind-Kacheln / Swimlane)
│       ├── KoordinatorTile (Eltern, Aggregat-Status)
│       └── SpezialistTile[] (je Kind: ticket_id-Badge + abc-Phase + Ampel)
├── KoordinatorControls (pro Fleet)
│   ├── Pausieren
│   ├── TicketUmverteilenMenu (manuell Rolle/Engine wechseln)
│   └── "Kind übernehmen" (Direktzugriff auf Kind-Session)
└── DecisionCardPanel (bestehend) — zeigt Konflikt-Cards des Koordinators
```

### B) Datenmodell (Klartext, kein Schema)
Erweiterung des **bestehenden** `SessionState` (in-memory), keine neue Tabelle:
```
Koordinator-Session (= normale Session mit role="coordinator"):
- child_session_ids: Liste der dispatchten Kind-Sessions      (NEU, 1:N-Flotte)
- contract_pointer:  Vault-Pointer auf das API-Vertrag-Artefakt (NEU)
- dispatch_plan:     freigegebener Plan (Ticket → Rolle/Engine/Reihenfolge)

Kind-Session (Spezialist):
- parent_coordinator_id: Rück-Referenz auf den Koordinator       (NEU; nutzt parent_session_id-Muster)
- ticket_id:             "PROJ-X" das diese Session bearbeitet   (NEU)
- contract_pointer:      derselbe Pointer wie der Koordinator     (Pointer, kein Volltext)

API-Vertrag (Vault-Artefakt, MD):
- Pfad-Konvention: <vault>/Agentic OS/Jupiter/Knowledge/contracts/PROJ-X-contract.md
- Inhalt: Endpunkte/Felder/Datenformen, vom Architect zuerst festgelegt
- wird von allen Spezialisten per Pointer referenziert (RAG-Fenster, kein Duplikat)

Konflikt → Decision Card (bestehendes in-memory PendingDecision):
- card_type = "contract_conflict" (NEU)
- context: welche zwei Sessions, welches Feld/Artefakt, relevanter Vertrags-Ausschnitt (Pointer)
```
Speicherort: in-memory `SessionManager`; **Wahrheit/Recovery über den Vault** (PROJ-17) —
konsistent mit dem heutigen Stand.

### C) API-Shape (nur Endpunkte, kein Code)
Aufgesetzt auf den bestehenden `routes/sessions.py`:
```
- POST /coordinator/plan            → liest INDEX.md, gibt Verteilungsplan zurück (dispatcht NICHT)
- POST /coordinator/dispatch        → startet freigegebenen Plan: Kind-Sessions je Ticket (policy-gegatet)
- GET  /coordinator/{id}/fleet      → Koordinator + Kinder + je Ticket/Phase/Ampel (Cockpit-Gruppe)
- POST /coordinator/{id}/pause      → Dispatch pausieren
- POST /coordinator/{id}/reassign   → Ticket manuell umverteilen (Rolle/Engine)  → Plan-Neuberechnung
- POST /coordinator/{id}/contract   → API-Vertrag im Vault ablegen/aktualisieren  → Update-Signal an Kinder
- (bestehend) POST /sessions/{id}/decisions/{decision_id} → Konflikt-Card auflösen
```
Single-User-MVP: kein JWT/RLS (kommt mit PROJ-25); `owner` wird mitgeführt.

### D) Tech-Entscheidungen (WARUM, PM-lesbar)
- **Koordinator = spezielle Session, kein neuer Dienst.** Wir hängen die Flotten-Logik an das
  bestehende Session-/Treiber-Modell (PROJ-1/PROJ-14) statt einen Parallel-Stack zu bauen —
  Recovery, Limits, Watchdog und Liveness gelten dann automatisch auch für Koordinator + Kinder.
- **Das Dokument ist der Schiedsrichter, nicht der Agent.** Der API-Vertrag liegt als Vault-MD;
  Spezialisten bauen nachweislich dagegen (Pointer im Prompt). Bei Widerspruch verweist der
  Koordinator beide Seiten auf den Vertrag; nur das objektiv Unentscheidbare wird Decision Card.
  So bleibt der Mensch an den Schaltstellen, nicht im Klein-Klein.
- **Pointer statt Volltext.** Der Vertrag wird referenziert (RAG-Fenster wie in `vault.py`),
  nicht in jeden Spezialisten-Prompt kopiert — spart Tokens und hält eine einzige Quelle.
- **Plan vor Dispatch (Human-in-the-Loop).** `/coordinator/plan` zeigt erst den Verteilungsplan;
  gestartet wird erst nach Freigabe — und „Session starten"/„Ticket verteilen" sind
  Trust-Policy-gegatete Aktionen (PROJ-10).
- **Abhängigkeits-Reihenfolge per Topo-Sort.** Die `Abhängigkeiten`-Spalte aus INDEX.md wird
  ausgelesen; ein Ticket wird erst dispatcht, wenn seine `Requires` im Zielzustand sind.
  Zirkulär/fehlend → Warnung + nur auflösbarer Teilgraph (statt blockieren/raten).
- **Kein freier Slot / Amok.** Bei vollem Engine-Limit (PROJ-14) reiht der Koordinator Tickets
  ein statt sie fallen zu lassen; läuft er selbst Amok, greift derselbe Watchdog (PROJ-16).

### E) Wiederverwendung (was schon da ist) vs. NEU
| Baustein | Status | Quelle |
|---|---|---|
| Session-Modell + Treiber-Launch | **da** | `backend/app/engine/manager.py`, `engine/base.py` |
| Eltern-Kind (1:1 Staffelstab) | **da** | `manager.py` (`parent_session_id`/`child_session_id`) |
| Decision Cards (in-memory) | **da** | `engine/decisions.py`, `routes/sessions.py` |
| Vault read/write + Pointer/RAG | **da** | `engine/vault.py` |
| INDEX.md-Parsing + Skill/Engine-Mapping | **da** | `engine/launcher.py` (`parse_index_features`, `suggest`) |
| Trust-Policy- + Watchdog-Gates | **da** | `engine/policy.py`, `engine/watchdog.py` |
| **1:N-Flotte (`child_session_ids`, `ticket_id`)** | **NEU** | Felder an `SessionState` |
| **Koordinator-Logik (plan/dispatch/pause/reassign)** | **NEU** | neuer `engine/coordinator.py` + `routes/coordinator.py` |
| **`Abhängigkeiten`-Spalte parsen + Topo-Sort** | **NEU** | Erweiterung in `launcher.parse_index_features` |
| **API-Vertrag-Artefakt + `contract_conflict`-Card-Typ** | **NEU** | Vault-Konvention + `decisions.py`-Erweiterung |
| **Fleet-Gruppierung im Kanban** | **NEU** | `nextjs_app/components/cockpit/kanban-board.tsx` |

### F) Dependencies (Pakete)
- Backend: **keine neuen** — alles (Treiber, Vault, Policy, Watchdog, INDEX-Parsing) existiert.
- Frontend: **keine neuen** — Fleet-Gruppierung ist eine Komposition bestehender Cockpit-Komponenten.

## Frontend-Implementierung (2026-06-25, Branch `dev`)
Frontend-first gegen den dokumentierten Vertrag (Abschnitt C/D) gebaut; das Backend
zieht mit `/abc-backend` nach. Keine neuen npm-Pakete.

**Neu:**
- `nextjs_app/components/cockpit/coordinator/coordinator-panel.tsx` — neuer **Koordinator**-Tab
  im Cockpit: Einstieg (Projektpfad → „Verteilungsplan erstellen") + Live-Sicht aller Flotten.
  Flotten werden aus dem **bestehenden** `/sessions`-Poll (sessions-provider) abgeleitet
  (`role==="coordinator"` + Kinder via `parent_coordinator_id`) → **kein zweiter Poll**.
  Letzter Projektpfad in localStorage (Lazy-Initializer, SSR-sicher).
- `…/coordinator/dispatch-plan-dialog.tsx` — Verteilungsplan-Dialog (Human-in-the-Loop):
  lädt `POST /coordinator/plan`, zeigt Ticket → Rolle/Skill/Engine + topologische Reihenfolge
  + Abhängigkeits-Warnungen, dispatcht nur den nicht-blockierten Teil per `POST /coordinator/dispatch`.
- `…/coordinator/fleet-view.tsx` — Eltern-Kind-Gruppe: Koordinator-Kachel (Ampel, Aggregat,
  Pausieren/Fortsetzen, Vertrag-Link → `/doku`) über eingerückten Kind-`SessionTile`s
  (Klick = „Kind übernehmen"); Inline-`ReassignForm` (Rolle/Engine) je Ticket.

**Geändert:**
- `lib/types.ts` — `Session` um Fleet-Felder erweitert (`parent_coordinator_id`, `ticket_id`,
  `child_session_ids`, `contract_pointer`); `card_type` um `"contract_conflict"`;
  neue Interfaces `CoordinatorPlan(Item)`, `CoordinatorFleet`.
- `lib/api.ts` — `getCoordinatorPlan`, `dispatchCoordinator`, `getCoordinatorFleet`,
  `setCoordinatorPaused`, `reassignTicket`, `setCoordinatorContract`.
- `components/cockpit/decision-card.tsx` — `contract_conflict` gerendert (indigo, „Vertrags-Konflikt", Scale-Icon).
- `app/(cockpit)/page.tsx` — neuer Tab „Koordinator".
- 6 Test-Fixtures um die neuen `Session`-Pflichtfelder ergänzt.

**Verifiziert:** `tsc --noEmit` (nur 1 vorbestehender, unabhängiger Fehler in `md-tree.test.ts`),
`eslint` der neuen Dateien sauber, `vitest run` der berührten Fixtures **71/71 grün**.

**Offen fürs Backend (`/abc-backend`):** `routes/coordinator.py` (plan/dispatch/fleet/pause/reassign/contract),
`engine/coordinator.py` (Dispatch + Vertrags-Schiedsrichter + `contract_conflict`-Card),
Fleet-Felder an `SessionState`, `Abhängigkeiten`-Spalte in `launcher.parse_index_features` + Topo-Sort,
Vertrags-Konvention im Vault. **Vertrag = Abschnitt C/D dieses Designs.**

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
