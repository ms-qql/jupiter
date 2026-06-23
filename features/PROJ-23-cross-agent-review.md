# PROJ-23: Cross-Agent-Review / Challenge (adversariell, engine-übergreifend)

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #30
**Prio:** P2 (Phase 2 — Skalierung)

## Dependencies
- Requires: PROJ-18 (Weitere Engines) — Cross-Agent-Review lebt von **Modell-Diversität**; ein zweiter Treiber (Codex/Gemini/GLM/Ollama) ist Voraussetzung, sonst reviewt nur Claude sich selbst.
- Requires: PROJ-22 (Dispatch-Schicht + Vertrag) — die Challenge startet eine **Reviewer-Session** über die Dispatch-Schicht; das Vertrags-/Architektur-Artefakt (#18) ist das Prüfobjekt.
- Requires: PROJ-4 (Decision Cards) — die Kritik des Reviewers kommt als **Review-Notiz / Decision Card** zurück.
- Requires: PROJ-2 (Vault-Anbindung) — geprüfte Artefakte (Architektur-Doku, ADR, Diff) und Review-Ergebnisse liegen im Vault.
- Verwandt: PROJ-1 (Engine, `--model`-Routing) — Reviewer bevorzugt eine **andere Engine/anderes Modell** als der Autor.

## Beschreibung
Selbst-Review eines einzelnen Modells übersieht systematische blinde Flecken. Dieses Feature lässt das **Ergebnis eines Agenten von einem anderen Agenten herausfordern** — bevorzugt mit **anderer Engine/anderem Modell**. Beispiel: eine via `/abc-architecture` von **Claude Opus** entworfene Architektur wird von **Codex** (oder Gemini/GLM) gechallengt.

Integration **nativ in den Flow**: Auf einem erzeugten Artefakt (Architektur-Doku, ADR, Diff/Code) gibt es eine **„Challenge"-Aktion**. Sie startet eine **Reviewer-Session** mit (möglichst) anderer Engine, die das Artefakt adversariell prüft. Das Review-Ergebnis (Schwachstellen, Risiken, Gegenvorschläge) kommt als **Review-Notiz bzw. Decision Card** (#4) zurück — der Mensch entscheidet, was übernommen wird.

**Grundhaltung:** Diversität der Modelle fängt Fehler, die ein einzelnes Modell nicht sieht. Der Challenger **bewertet und schlägt vor**, er ändert das Artefakt nicht selbst (analog zur QA-Rolle: finden + vorschlagen, nicht fixen).

## User Stories
- Als Nutzer möchte ich auf einem erzeugten Artefakt (Architektur-Doku, ADR, Diff) eine **„Challenge"-Aktion** auslösen, um eine unabhängige Zweitmeinung zu bekommen.
- Als Nutzer möchte ich, dass der Challenger **standardmäßig eine andere Engine/ein anderes Modell** als der Autor nutzt, um echte Diversität zu erhalten.
- Als Nutzer möchte ich die Kritik als **strukturierte Review-Notiz** (Schweregrad, Fundstelle, Gegenvorschlag) erhalten, nicht als langes Fließtext-Log.
- Als Nutzer möchte ich pro Befund entscheiden: **übernehmen / verwerfen / mit Kommentar zurück an den Autor** (gleiche Aktionen wie bei einer Decision Card).
- Als Nutzer möchte ich sehen, **welche Engine/welches Modell** den Review erstellt hat (Nachvollziehbarkeit der Diversität).
- Als Nutzer möchte ich die Challenge auch dann nutzen können, wenn nur Claude verfügbar ist — dann mit explizitem Hinweis „gleiche Engine, eingeschränkte Diversität".

## Acceptance Criteria
- [ ] Auf einem prüfbaren Artefakt (mind. Architektur-Doku/ADR + Diff/Code) gibt es eine **„Challenge"-Aktion** in der UI.
- [ ] Die Challenge startet eine **Reviewer-Session** über die Dispatch-Schicht (PROJ-22) mit dem Artefakt als **Pointer**-Prüfobjekt (kein Volltext-Duplikat).
- [ ] Der Reviewer nutzt **standardmäßig eine andere Engine/anderes Modell** als der Autor; ist keine andere verfügbar, läuft die Challenge mit Warnhinweis auf derselben Engine.
- [ ] Das Review-Ergebnis ist **strukturiert** (Liste aus: Befund + Schweregrad + Fundstelle/Bezug + Gegenvorschlag) und kommt als **Review-Notiz/Decision Card** (PROJ-4) zurück.
- [ ] Pro Befund kann der Nutzer **übernehmen / verwerfen / mit Kommentar zurück** wählen; „mit Kommentar zurück" reicht den Befund an die Autor-Session.
- [ ] Jeder Review nennt **Autor-Engine/-Modell** und **Reviewer-Engine/-Modell**.
- [ ] Der Reviewer **ändert das Artefakt nicht** — er liefert nur Befunde (Trennung Finden/Umsetzen).
- [ ] Review-Ergebnisse werden im **Vault** abgelegt (Audit-Spur, projektübergreifend auffindbar).
- [ ] Alle Texte deutsch.

## Edge Cases
- **Nur eine Engine installiert** → Challenge läuft mit deutlichem Hinweis „eingeschränkte Diversität (gleiche Engine)" statt blockiert zu sein.
- **Artefakt zu groß fürs Reviewer-Kontextfenster** → es wird der relevante Ausschnitt/Diff gechallengt (Pointer/RAG-Linie #23), nicht stumm abgeschnitten.
- **Reviewer findet nichts** → explizite „keine Befunde"-Notiz (nicht stilles Verschwinden), inkl. genutztem Modell.
- **Reviewer halluziniert Befunde** → Befunde sind Vorschläge; der Mensch entscheidet; „verwerfen" schließt sie ohne Artefakt-Änderung.
- **Challenge auf ein veraltetes Artefakt** (inzwischen geändert) → Review wird gegen die Version markiert, gegen die er lief; Warnung bei Versions-Drift.
- **Reviewer-Session stirbt/timeoutet** → Befund „Review unvollständig", Artefakt bleibt unverändert; Retry möglich.
- **Endlos-Challenge-Schleife** (Autor ↔ Reviewer streiten endlos) → Rundenlimit; danach Eskalation als Decision Card an den Menschen.

## Technical Requirements (optional)
- Setzt **mehrere Treiber** voraus (PROJ-18); Engine-Auswahl des Reviewers über das vorhandene Routing (`--model` / Treiber-Wahl).
- Nutzt die **Dispatch-Schicht** (PROJ-22) zum Starten/Verfolgen der Reviewer-Session und das **Vertrags-/Artefakt-Modell** als Prüfobjekt.
- Befunde als strukturierte Notiz an die bestehende Decision-Card-Mechanik (PROJ-4) angedockt — kein separater Review-Stack.
- Artefakt-Referenzen als **Pointer** in den Vault (konsistent mit #23), Review-Ergebnis als kuratiertes Wissen ablegbar (PROJ-15).
- Single-User-MVP-Linie: kein JWT/RLS hier; `owner` wird mitgeführt.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
