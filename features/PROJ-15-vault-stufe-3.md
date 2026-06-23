# PROJ-15: Vault Stufe 3 — lebendes Gehirn + roh↔kuratiert + Kuratierung

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Bausteine:** #9, #10, #11

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung als Dienst) — baut auf lesen/schreiben/suchen im Hal-Vault auf.
- Requires: PROJ-4 (Decision Cards) — die Kuratierung nutzt denselben Freigabe-Flow.
- Verwandt: PROJ-5 (Handover) — Handovers sind eine Quelle kuratierten Wissens; PROJ-17 (Recovery) liest aus denselben Schichten.

## Beschreibung
Der Vault wird vom passiven Log-Ablageort zum **lebenden Gehirn**: Agenten lesen aktiv aus dem Vault und schreiben strukturierte Spuren zurück, projektübergreifend durchsuchbar — und bleibt offenes, lesbares MD. Zwei Schichten werden klar getrennt: **rohe Logs** (vollständig, Audit) ↔ **kuratiertes Wissen** (Entscheidungen, Lösungen, Sackgassen, Muster). **Kuratierung** ist ereignisgetrieben: ein Trigger (Bug gelöst, ADR gefallen, Sackgasse verworfen) erzeugt einen **Wissens-Vorschlag**, den der Nutzer per Card freigibt/editiert.

## User Stories
- Als Nutzer möchte ich, dass Agenten relevantes Vault-Wissen aktiv lesen, damit Lösungen nicht doppelt erarbeitet werden.
- Als Nutzer möchte ich rohe Session-Logs und kuratiertes Wissen klar getrennt im Vault haben, damit der „Kopf-Index" sauber bleibt.
- Als Nutzer möchte ich, dass aus erkannten Ereignissen (Bug gelöst, ADR, Sackgasse) automatisch ein **Wissens-Vorschlag** entsteht.
- Als Nutzer möchte ich jeden Wissens-Vorschlag per Decision Card **freigeben, editieren oder verwerfen**, bevor er ins kuratierte Wissen wandert.
- Als Nutzer möchte ich projektübergreifend im kuratierten Wissen suchen können.

## Acceptance Criteria
- [ ] **Zwei Schichten** mit fester Vault-Struktur: rohe Logs (vollständig) vs. kuratiertes Wissen (destilliert); beide offenes MD, direkt les-/editierbar.
- [ ] Agenten können Vault-Inhalte **lesen und strukturierte Spuren zurückschreiben** (über den PROJ-2-Dienst), ohne Bestehendes zu überschreiben.
- [ ] **Kuratierungs-Trigger** (mind.: Bug gelöst, ADR/Entscheidung gefallen, Sackgasse verworfen) erzeugen einen Wissens-Vorschlag.
- [ ] Ein Vorschlag erscheint als **Decision Card** (PROJ-4-Flow) mit Aktionen Freigeben / Editieren / Verwerfen.
- [ ] Freigegebenes Wissen landet als kuratierte MD-Notiz an definierter Stelle; verworfenes wird nicht geschrieben (nur im Roh-Log dokumentiert).
- [ ] **Suche** über kuratiertes Wissen liefert projektübergreifende Treffer mit Pfad/Backlink.
- [ ] Vault-Schreibvorgänge sind nachvollziehbar (owner-Feld, Zeitstempel) und idempotent.
- [ ] Alle Texte deutsch.

## Edge Cases
- **Doppelter Wissens-Vorschlag** (gleiches Thema) → Duplikat erkennen, an bestehende Notiz anhängen statt neu anlegen.
- **Trigger feuert zu oft** (Geschwätzigkeit) → Entprellung/Schwelle, damit keine Card-Flut entsteht.
- **Nutzer editiert Vorschlag** → editierte Fassung wird geschrieben, Original-Roh-Log bleibt unverändert.
- **Konflikt mit manuell editierter Notiz** → nicht blind überschreiben; anhängen/nachfragen.
- **Vault temporär nicht schreibbar** → Vorschlag in Warteschlange, sichtbarer Hinweis, kein Verlust.
- **Sehr großes Roh-Log** → Pointer/Ausschnitt statt Volltext im kuratierten Wissen (zahlt auf PROJ-19/#23 ein).

## Technical Requirements (optional)
- Nutzt den PROJ-2-Vault-Dienst (lesen/schreiben/suchen); Struktur passt ins bestehende Hal-PARA-Layout.
- Kuratierung ereignisgetrieben über erkannte Marker im Session-Stream; Entprellung serverseitig.
- Suche: einfacher Index über kuratierte Notizen (Volltext/Frontmatter), erweiterbar Richtung RAG (PROJ-19).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
