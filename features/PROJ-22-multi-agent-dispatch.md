# PROJ-22: Multi-Agent-Dispatch-Schicht + Vertrag-zuerst/Koordinator

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
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
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
