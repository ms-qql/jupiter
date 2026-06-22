# PROJ-5: Context-Management & Handover

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — Token-/Kontext-Daten je Session
- Requires: PROJ-2 (Vault-Anbindung) — Handover-MD in den Vault schreiben
- Requires: PROJ-3 (Cockpit) — Budget-Gauge auf der Kachel anzeigen

## Beschreibung
Der Token-Disziplin-Kern: Jupiter überwacht den Kontextfenster-Füllstand je Session (#25), warnt an einer Schwelle und schlägt ein **Handover** vor. Handover (#8) wird manuell (Button) und automatisch (abc-Phasenübergang, #7) erzeugt, als MD in den Vault geschrieben und kann eine Session frisch neu starten. Geplanter Staffelstab statt Notbremsen-Crash.

## User Stories
- Als Nutzer möchte ich pro Session den Kontext-Füllstand + Token-Verbrauch sehen, um Bloat früh zu erkennen.
- Als Nutzer möchte ich bei Erreichen einer Schwelle einen Handover-Vorschlag bekommen.
- Als Nutzer möchte ich auf Knopfdruck (und automatisch an Phasenübergängen) ein Handover-MD erzeugen lassen.
- Als Nutzer möchte ich eine Session mit dem Handover als Startkontext frisch neu starten (Reset).

## Acceptance Criteria
- [ ] Pro Session werden Kontextfenster-Füllstand (%) + kumulierter Token-Verbrauch angezeigt (Gauge auf der Kachel, #25; Daten aus PROJ-1).
- [ ] Bei Überschreiten einer **konfigurierbaren Schwelle** erscheint eine Schwellenwarnung + Handover-Vorschlag.
- [ ] Handover ist **manuell** (Button) und **automatisch** (abc-Phasenübergang) auslösbar.
- [ ] Handover-MD enthält: Wo stehen wir? / Erledigt / Offen / Fallstricke / **Pointer** (statt Volltext).
- [ ] Handover wird über PROJ-2 in den Vault geschrieben.
- [ ] „Session zurücksetzen": neue Session startet mit Handover-MD als Startkontext; alte Session wird als abgeschlossen archiviert.

## Edge Cases
- Token-Daten vom Treiber fehlen/verzögert → Gauge zeigt „unbekannt" statt irreführend 0.
- Handover ausgelöst, während Session arbeitet → erst nach dem aktuellen Schritt, nicht mitten im Tool-Call.
- Reset bei sehr kurzer Session → erlaubt, aber Hinweis „wenig Kontext".
- Schwelle 0/100 % oder unsinnig konfiguriert → auf sinnvolle Grenzen geklemmt.

## Technical Requirements (optional)
- Schwellenwert konfigurierbar (pro Session / global).
- abc-Phasenübergang aus dem Workflow ableitbar (Skill-/Statuswechsel) als Auto-Trigger.
- Pointer-statt-Volltext im Handover zahlt auf #23 (RAG, P1) ein.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
