# PROJ-10: Trust-Policy — abgestuftes, konfigurierbares Vertrauen

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #5

## Dependencies
- Requires: PROJ-4 (Decision Cards) — die Policy entscheidet, was eine Card erzeugt (erweitert die heutige fixe `engine/policy.py`).
- Requires: PROJ-6 (Knappheits-Konstitution / Rollen) — Policy ist pro Rolle/Skill/Projekt konfigurierbar.
- Verwandt: PROJ-16 (Watchdog) — nutzt dieselbe Policy als Reißleine.

## Beschreibung
Im MVP gibt es einen **fixen, konservativen** Freigabe-Trigger (jede schreibende Aktion → Card). Dieses Feature macht Vertrauen zu einer **konfigurierbaren Richtlinie pro Kontext**: Pro Rolle/Skill/Projekt wird festgelegt, was **autonom** läuft (Auto-Approve), was eine **Decision Card** erzeugt und was **hart verboten** ist. Default bleibt „möglichst autonom, aber sicher".

## User Stories
- Als Nutzer möchte ich pro Rolle/Skill festlegen, welche Tool-Klassen autonom laufen dürfen, um vertraute Abläufe nicht ständig freigeben zu müssen.
- Als Nutzer möchte ich bestimmte Aktionen (z. B. `rm -rf`, force-push, Schreiben außerhalb des Projekts) **hart verbieten**, unabhängig vom Kontext.
- Als Nutzer möchte ich eine projektweite Default-Policy plus rollen-/skillspezifische Übersteuerungen pflegen.
- Als Nutzer möchte ich sehen, **welche Regel** eine konkrete Decision Card ausgelöst hat (Nachvollziehbarkeit).
- Als Nutzer möchte ich Policy-Änderungen ohne Backend-Neustart wirksam machen.

## Acceptance Criteria
- [ ] Es gibt drei Vertrauensstufen pro Regel: **auto-allow**, **card** (Freigabe nötig), **deny** (hart verboten).
- [ ] Regeln können nach **Tool-Klasse** (Bash/Edit/Write/…) und **Kontext** (Rolle, Skill, Projekt) gematcht werden; spezifischere Regel schlägt allgemeinere.
- [ ] Eine **deny**-Regel verhindert die Aktion und erzeugt eine ablehnende Card-Notiz mit Begründung — die Aktion wird nie ausgeführt.
- [ ] Der Default (keine passende Regel) ist konservativ: schreibende/destruktive Tools → **card**, Lesezugriffe → **auto-allow** (= heutiges Verhalten).
- [ ] Jede erzeugte Card nennt die **auslösende Regel** (welche Stufe, welcher Match).
- [ ] Policy ist als Konfiguration editierbar (UI oder Settings) und wird **live** neu geladen, ohne Sessions zu unterbrechen.
- [ ] Bestehende PROJ-4-Cards funktionieren unverändert, wenn keine Policy gepflegt ist (Rückwärtskompatibilität).
- [ ] Alle Texte deutsch.

## Edge Cases
- **Widersprüchliche Regeln** (eine auto-allow, eine deny für denselben Match) → die restriktivere (deny) gewinnt; Konflikt wird geloggt.
- **Policy-Datei kaputt/ungültig** → Fallback auf konservativen Default, sichtbare Warnung, kein Crash.
- **Neue, unbekannte Tool-Klasse** → Default-Stufe (card), nie versehentlich auto-allow.
- **Auto-allow trotz Watchdog-Alarm** (PROJ-16) → Watchdog kann eine auto-allow-Aktion dennoch pausieren (Reißleine sticht Komfort).
- **Rolle ohne Policy** → projektweiter Default greift.

## Technical Requirements (optional)
- Erweitert `backend/app/engine/policy.py` (heute fixe `AUTO_ALLOW_TOOLS`).
- Konfig versioniert/serverseitig; Secrets/Pfade nie aus Client-Payload.
- Auswertung pro Tool-Call < 5 ms (im Permission-Hook-Pfad).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
