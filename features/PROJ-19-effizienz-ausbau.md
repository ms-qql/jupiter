# PROJ-19: Effizienz-Ausbau — Pointer/RAG, Späher-Agenten, Prompt-Caching, Token-Dashboard

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Bausteine:** #23, #26, #27, #28

> **Hinweis Granularität:** Dieser Eintrag bündelt vier verwandte Effizienz-Mechanismen (PRD-Roadmap-Eintrag). Falls die Architektur-Phase einen davon als zu groß einstuft, kann er in eine eigene Spec ausgegliedert werden (z. B. Token-Dashboard als separate UI-Spec).

## Dependencies
- Requires: PROJ-1 (Engine) — Späher-Agenten + Caching greifen in den Treiber-/Modell-Pfad.
- Requires: PROJ-2 / PROJ-15 (Vault) — Pointer/RAG lädt Ausschnitte aus dem Vault.
- Verwandt: PROJ-5/#25 (Kontext-Budget) und #22 (Modell-Routing) — das Token-Dashboard schließt deren Regelkreis.

## Beschreibung
Vier Querschnitts-Mechanismen, die den Token-Verbrauch senken, ohne Informationsverlust:
- **#23 Pointer statt Volltext (Vault-RAG):** Agenten bekommen Links zu Vault-Dateien; nur relevante Ausschnitte werden geladen.
- **#26 Billige Späher-Agenten:** „Lies viele Dateien, gib nur das Fazit"-Aufgaben gehen an günstige Explorer (Haiku); die teure Hauptsession bleibt schlank.
- **#27 Prompt-Caching:** wiederkehrende Rollen-/Skill-Prompts + stabiler Projektkontext werden gecacht statt neu gesendet.
- **#28 Token-/Kosten-Dashboard:** Verbrauch heute/pro Projekt/pro Modell sichtbar; erkennt token-fressende Rollen/Tasks.

## User Stories
- Als Nutzer möchte ich, dass Agenten statt Volltext-Dumps nur relevante Vault-Ausschnitte geladen bekommen, um Kontext schlank zu halten.
- Als Nutzer möchte ich Such-/Lese-Schwerarbeit an billige Späher-Agenten delegieren, damit die teure Hauptsession nicht zumüllt.
- Als Nutzer möchte ich, dass stabile Rollen-/Skill-Prompts gecacht werden, um wiederkehrende Kosten zu senken.
- Als Nutzer möchte ich ein Dashboard mit Verbrauch pro Tag/Projekt/Modell, um Token-Fresser zu erkennen.

## Acceptance Criteria
- [ ] **Pointer/RAG:** Ein Mechanismus liefert statt Volltext eine Auswahl relevanter Ausschnitte aus dem Vault (Pfad + Snippet); messbar geringerer Kontextverbrauch gegenüber Volltext.
- [ ] **Späher-Agenten:** „Fazit-Aufgaben" können an eine günstige Engine/Modell (Haiku) delegiert werden; die Hauptsession erhält nur das verdichtete Ergebnis.
- [ ] **Prompt-Caching:** wiederkehrende, stabile Prompt-Bestandteile werden über Aufrufe hinweg wiederverwendet; Cache-Treffer sind messbar/sichtbar.
- [ ] **Token-Dashboard:** zeigt Verbrauch und Kosten **heute / pro Projekt / pro Modell** mit Drilldown auf Rollen/Tasks.
- [ ] Alle vier Mechanismen sind **einzeln abschaltbar** und brechen bei Fehlern auf das heutige Verhalten zurück (kein Hard-Fail).
- [ ] Das Dashboard nutzt vorhandene Usage-Daten (aus PROJ-5/#25) ohne Extra-Erhebungslast.
- [ ] Alle Texte deutsch; Lade-/Fehler-/Leer-Zustände explizit.

## Edge Cases
- **RAG verfehlt relevanten Ausschnitt** → Fallback auf größeren Ausschnitt/Volltext mit sichtbarem Hinweis.
- **Späher-Ergebnis unbrauchbar** → Hauptsession kann eskalieren (teureres Modell), nachvollziehbar.
- **Cache veraltet** (Rolle/Skill geändert) → Invalidierung; kein Servieren veralteter Prompts.
- **Engine ohne Usage-Daten** (PROJ-18) → Dashboard zeigt „n/v" statt falscher Nullen.
- **Kosten-Schätzung vs. Ist** → klar als Schätzung kennzeichnen, wenn keine echten Kosten vorliegen (Subscription-Auth).

## Technical Requirements (optional)
- RAG: einfacher Ausschnitts-Index über Vault-Notizen (erweiterbar); Späher nutzt das Treiber-/Routing-Modell (#22).
- Caching nutzt die Caching-Fähigkeiten der jeweiligen Engine (z. B. Prompt-Caching der Claude-CLI), wo verfügbar.
- Dashboard aggregiert die bereits erfassten Token/Kosten pro Session; performant für viele Sessions.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
