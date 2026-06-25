# PROJ-22: Multi-Agent-Dispatch-Schicht + Vertrag-zuerst/Koordinator

## Status: Approved
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

## Backend-Implementierung (2026-06-25, Branch `dev`)
In-memory + Vault, **kein Postgres/RLS/JWT** (MVP-Linie, Tech-Design Abschnitt 0). Keine neuen Pakete.

**Neu:**
- `backend/app/engine/coordinator.py` — `build_plan(project_path)` (Topo-Sort über die
  `Abhängigkeiten`-Spalte via Kahn; blocked = wartet-auf-offene-Deps oder Zyklus; Warnungen
  bei zirkulärer/fehlender Abhängigkeit; nur der auflösbare Teilgraph wird verteilbar markiert)
  + `CoordinatorService` (dispatch → Koordinator-Session `role="coordinator"` + je Ticket eine
  Spezialisten-Session mit `parent_coordinator_id`+`ticket_id`; fleet; set_paused; reassign =
  altes Kind stoppen+lösen, neues starten; set_contract → Vault-`curated`-Notiz, Pointer am
  Koordinator + allen Kindern). `PHASE_TO_ROLE`-Mapping. Slot-Limit (PROJ-14) → Rest nicht
  fallen lassen, Dispatch bricht sauber ab.
- `backend/app/routes/coordinator.py` — `POST /coordinator/plan` · `POST /coordinator/dispatch`
  (201) · `GET /coordinator/{id}/fleet` · `POST …/pause` · `POST …/reassign` · `POST …/contract`.
  Status: 400 (Pfad) · 404 (kein Koordinator / Ticket) · 429 (Slot-Limit) · 503 (Engine/Vault).
- `backend/app/schemas/coordinator.py` — Plan/Item/Fleet/Dispatch/Pause/Reassign/Contract.
- `backend/tests/test_proj22_coordinator.py` — 15 Tests (Plan-Topo/blocked/Zyklus/missing,
  Dispatch-Flotte, Fleet-404, Pause, Reassign, Contract-Pointer).

**Geändert:**
- `engine/manager.py` — `SessionState`: `parent_coordinator_id`, `ticket_id`,
  `child_session_ids`, `contract_pointer`, `coordinator_paused` (+ in `to_read`); `create()`
  um die drei Fleet-Kwargs erweitert.
- `engine/launcher.py` — `parse_index_features` liest jetzt die `Abhängigkeiten`-Spalte
  (Header-erkannt, robust; Feature-Spalten-ID wird nicht als Dep fehlinterpretiert).
- `schemas/sessions.py` — `SessionRead` um die 4 Fleet-Felder (Frontend-Vertrag erfüllt).
- `main.py` — `app.state.coordinator` + Router registriert.

**Bug gefunden & gefixt:** Reassign reuste `old.state.model`, das der Treiber beim Start auf
die volle Modell-ID (`claude-haiku-4-5-…`) überschreibt → 400 an der Claude-Whitelist. Fix:
`model=None` → Engine-Default.

**Bewusst beim Agenten (nicht deterministisch im Backend):** die *automatische Vermittlung*
eines Vertrags-Konflikts ist Laufzeit-Verhalten der Koordinator-Session (Prompt/Konstitution).
Das Backend stellt das Gerüst + den `contract_conflict`-Card-Typ über den bestehenden
Decision-Card-Flow bereit.

**Verifiziert:** `pytest backend/tests/` → **697 passed** (15 neu, 0 Regression).

## QA Test Results
**Getestet:** 2026-06-25 · **Branch:** dev · **Tester:** QA Engineer
**Automatisierte Tests:** Backend `pytest` **713 passed** (24 für PROJ-22, inkl. M1/M3-Fixes), Frontend `vitest` **169 passed**, 0 Regression.
**Stack-Kontext:** Single-User-MVP — kein JWT/RLS/Mandanten (bewusst, kommt mit PROJ-25). Red-Team daher auf
Pfad-Scope, Fremd-Steuerung, Injection in INDEX-Parsing/Vault-Pfade, Input-Limits statt Tenant-Isolation.

### Acceptance Criteria
| # | Kriterium | Ergebnis | Beleg |
|---|-----------|----------|-------|
| 1 | Koordinator-Modus liest INDEX.md, offene Tickets (≠ Deployed/Approved) | ✅ Pass | `test_plan_excludes_deployed_and_approved`, `build_plan` |
| 2 | Verteilungsplan vor Start (Ticket→Rolle/Skill/Engine + Reihenfolge), HITL-Freigabe | ✅ Pass | `POST /coordinator/plan` (dispatcht nicht); Frontend `DispatchPlanDialog` startet erst auf Klick |
| 3 | Startet Spezialisten-Sessions, je Kind `ticket_id` + `parent_coordinator_id` | ✅ Pass | `test_dispatch_creates_fleet` |
| 4 | Cockpit zeigt Koordinator + Kinder als zusammengehörige Gruppe | ✅ Pass (Logik/Typen) · ⚠ visueller Smoke offen | `FleetView` + `groupFleets` aus `/sessions`; Browser-Smoke empfohlen (hier nicht ausführbar) |
| 5 | API-Vertrag als Vault-Artefakt + Pointer (kein Volltext) | ✅ Pass | `test_contract_writes_pointer_to_fleet` (Pointer an Koordinator + allen Kindern) |
| 6 | Konflikt → erst Auto-Vermittlung, sonst Decision Card | ✅ Pass (Verhalten verankert) | `contract_conflict`-Card-Typ (FE+BE) **+ Koordinator-Rollen-Konstitution** `backend/constitution/roles/coordinator.md` (Vertrag-zuerst → vermitteln → nur Unlösbares als Card). Die Vermittlung *läuft* zur Laufzeit der Koordinator-Session (per Konstitution), das Gerüst ist deterministisch getestet |
| 7 | Pausieren · manuell umverteilen · Kind übernehmen | ✅ Pass | `test_pause`, `test_reassign_replaces_child`; „übernehmen" = FE-Link auf die Detailroute |
| 8 | Koordinator-Aktionen unter Trust-Policy (PROJ-10) | ✅ Pass (M1 gefixt) | Dispatch läuft jetzt durch `policy_store.evaluate("CoordinatorDispatch", role=coordinator)` → **deny-Regel ⇒ 403** (`test_dispatch_denied_by_policy_403`); `card`/`auto-allow` degradieren bewusst zur HITL-Plan-Freigabe. Jede Kind-Session ist zusätzlich voll policy-gegatet |
| 9 | Abhängigkeits-Reihenfolge respektiert (kein Dispatch bei offenem Requires) | ✅ Pass | `test_plan_topo_order_und_blocking`, `test_dispatch_skips_blocked_items` |
| 10 | Alle Texte deutsch | ✅ Pass | UI + Fehlermeldungen durchgängig deutsch |

### Edge Cases
| Fall | Ergebnis | Beleg/Notiz |
|------|----------|-------------|
| Zirkuläre/fehlende Abhängigkeit → Warnung + nur auflösbarer Teilgraph | ✅ Pass | `test_plan_circular_dependency_warns`, `test_plan_missing_dependency_warns_but_not_blocks` |
| Spezialist stirbt/hängt → Watchdog/Liveness | ✅ Pass (geerbt) · 🟡 Card-Automatik agenten-seitig | Jedes Kind erbt Watchdog (PROJ-16) + Liveness (PROJ-27); das deterministische „Ticket=blockiert + Card" ist Koordinator-Laufzeit (M2) |
| Zwei Sessions ändern dasselbe Artefakt → Vertrag entscheidet | 🟡 by design | Agenten-Verhalten gegen den Vertrag (M2) |
| Vertrag ändert sich mitten im Lauf → Update-Signal an Kinder | ✅ Pass (Pointer-Propagation) | `set_contract` setzt Pointer an Koordinator + allen Kindern; „veraltet-Markierung" offener Arbeit ist agenten-seitig |
| Koordinator läuft Amok → eigene Limits/Watchdog | ✅ Pass (geerbt) | Koordinator ist eine normale Session → Watchdog/Limit greifen |
| Kein freier Engine-Slot (PROJ-14) | ✅ Pass (M3 gefixt) | Resttickets werden **eingereiht** (`queued_tickets`) und vom Hintergrund-Drain (`drain_all`, 5-s-Tick) + nach `reassign` automatisch nachgerückt, sobald ein Slot frei wird; pausierte Flotten rücken nicht nach. `test_queue_and_drain`, `test_drain_skips_paused`. Sichtbar als „N eingereiht"-Badge |
| Nutzer übersteuert während Dispatch → manuelle Aktion gewinnt | ✅ Pass | `reassign` ersetzt Kind live; FE rechnet Flotte aus `/sessions` neu |
| Ticket ohne klare Rolle/Skill → Default + erst nach Bestätigung | ✅ Pass | `role/skill=None` im Plan, Dispatch nur nach Plan-Freigabe |

### Red-Team / Security-Audit
| Vektor | Ergebnis | Beleg |
|--------|----------|-------|
| Pfad-Traversal in `plan`/`dispatch` (project_path außerhalb Roots) | ✅ Abgewehrt (400) | `validate_project_path`; `test_plan_path_outside_roots_raises`, `test_dispatch_path_outside_roots_400` |
| Fremd-Steuerung: pause/reassign/contract auf Nicht-Koordinator-Session | ✅ Abgewehrt (404) | `test_mutations_reject_non_coordinator_session` |
| Injection über INDEX-`Abhängigkeiten`-Zelle | ✅ Sicher | nur `PROJ-\d+`-Regex-Matches werden übernommen; Feature-Spalten-ID wird nicht als Dep fehlinterpretiert |
| Vault-Pfad-Injection über Contract-`title`/`session_id` | ✅ Sicher | `slugify(title)` + `safe_id_segment(session_id)` (keine `../`) |
| Input-Limits (Contract-Body, leerer Plan) | ✅ 422 | `test_contract_body_too_long_422`, `test_dispatch_requires_items` |
| Modell-Whitelist umgehen (Reassign reuste volle Modell-ID) | ✅ Gefixt im Backend-Schritt | jetzt `model=None`→Engine-Default; `test_reassign_replaces_child` |

### Fix-Runde (2026-06-25) — M1–M3 geschlossen
- **M1 (AC8) ✅ gefixt:** `dispatch` läuft durch die Trust-Policy (`DISPATCH_ACTION="CoordinatorDispatch"`,
  `role=coordinator`); eine `deny`-Regel ⇒ **403** (`DispatchDeniedError`). `card`/`auto-allow` ⇒ bewusst
  die bereits vorgeschaltete HITL-Plan-Freigabe (kein zweites Gate ohne laufende Session).
  Test: `test_dispatch_denied_by_policy_403`.
- **M2 (AC6) ✅ verankert:** Rollen-Konstitution `backend/constitution/roles/coordinator.md` macht
  „Vertrag-zuerst → vermitteln → nur Unlösbares als `contract_conflict`-Card" zum tatsächlichen
  Laufzeit-Verhalten der Koordinator-Session. Card-Typ + Flow + Konstitution sind deterministisch da;
  die *Korrektheit der Vermittlung* ist LLM-Verhalten (Live-Beobachtung statt Unit-Test).
- **M3 (Slot-Limit) ✅ gefixt:** echte Warteschlange (`queued_tickets`) + Hintergrund-Drain (`drain_all`,
  `coordinator_drain_interval_seconds=5 s`) + Nachrücken nach `reassign`; pausierte Flotten rücken nicht
  nach; „N eingereiht"-Badge im Cockpit. Tests: `test_queue_and_drain`, `test_drain_skips_paused`.

### Verbleibend (Low, nicht blockierend)
- AC4 (visuelle Flotten-Gruppierung): Logik/Typen/Badge getestet; kurzer Browser-Smoke empfohlen.
- Korrektheit der KI-Konfliktvermittlung: verhaltensbasiert → Live-Beobachtung.

### Regression
- Backend **713/713**, Frontend **169/169** grün (24 PROJ-22-Tests). Geänderte Shared-Flächen
  (`SessionState`/`SessionRead`/`launcher`/`main`/`config`) ohne Bruch; parallele PROJ-23-`challenge`-
  und PROJ-43-`terminal`-Routen auf `dev` koexistieren konfliktfrei.

### Production-Ready-Empfehlung
**READY** — keine Critical/High/Medium offen; alle 10 AC erfüllt (M1–M3 geschlossen), Security-Audit sauber,
0 Regression. Vor Deploy nur noch ein kurzer Browser-Smoke der Cockpit-Flotten-Gruppierung (AC4) empfohlen.

## Deployment
_To be added by /abc-deploy_
