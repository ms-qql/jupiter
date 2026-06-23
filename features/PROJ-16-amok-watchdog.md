# PROJ-16: Amok-Watchdog + Limits

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #19 (kritischstes Failure-Szenario)

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — überwacht den Live-Event-Stream der Session.
- Requires: PROJ-4 (Decision Cards) — eine pausierte Session erzeugt eine Card.
- Requires: PROJ-10 (Trust-Policy) — Watchdog nutzt dieselbe Policy/Limits als Reißleine.

## Beschreibung
Autonomie braucht eine **Reißleine**: Token-/Zeit-/Aktions-**Limits** plus ein **Watchdog**, der Endlosschleifen und wildes Schreiben erkennt und die Session **pausiert (nicht killt)** → Decision Card. So bleibt der Fortschritt erhalten und der Nutzer entscheidet (weiterlaufen / abbrechen / korrigieren).

## User Stories
- Als Nutzer möchte ich, dass eine durchdrehende Session automatisch pausiert wird, bevor sie Schaden anrichtet oder Tokens verbrennt.
- Als Nutzer möchte ich beim Pausieren eine Decision Card mit dem Grund (welches Limit/Muster) und Handlungsoptionen sehen.
- Als Nutzer möchte ich Limits (Tokens/min, Laufzeit, wiederholte identische Aktionen, Schreibrate) konfigurieren.
- Als Nutzer möchte ich eine pausierte Session gezielt **fortsetzen, abbrechen oder mit Korrektur** weiterführen.

## Acceptance Criteria
- [ ] Konfigurierbare Limits: **Tokens/Zeitfenster**, **max. Laufzeit ohne Fortschritt**, **wiederholte identische Tool-Calls**, **Schreibrate** (Writes/Zeitfenster).
- [ ] Bei Überschreiten wird die Session **pausiert** (Prozess nicht getötet) und in einen klar erkennbaren Zustand „pausiert/Watchdog" versetzt.
- [ ] Es wird eine **Decision Card** erzeugt: Grund (welche Metrik), relevanter Ausschnitt, Aktionen **Fortsetzen / Abbrechen / Mit Kommentar korrigieren**.
- [ ] Die Erkennung läuft live auf dem Event-Stream und unterscheidet **Schleife** (identische Wiederholung) von legitimer Iteration.
- [ ] Watchdog **sticht auto-allow** (PROJ-10): selbst autonom erlaubte Aktionen werden bei Alarm pausiert.
- [ ] Fortsetzen setzt die Zähler des ausgelösten Limits zurück (kein sofortiges Re-Trigger).
- [ ] Schwellen sind zentral konfigurierbar; sinnvolle Defaults aus PRD-Offenpunkt #4.
- [ ] Alle Texte deutsch.

## Edge Cases
- **False Positive** (legitime lange Aufgabe) → Fortsetzen muss reibungslos sein; Schwellen anpassbar; „diesmal erlauben".
- **Mehrfach-Alarm** in Folge → keine Card-Flut; nach Fortsetzen Cooldown.
- **Session stirbt während Pause** → Card wird obsolet (wie PROJ-4-Abandon).
- **Schreibrate-Spike legitim** (z. B. Codegen) → unterscheidbar von „wildem Schreiben" über Pfad-/Wiederholungsmuster.
- **Limit-Konfig fehlt** → konservative Defaults greifen, nie „kein Watchdog".

## Technical Requirements (optional)
- Erkennung im Event-Verarbeitungs-Pfad des SessionManagers (geringe Latenz, kein Hot-Path-Regress).
- „Pausieren" = Stream/Prozess anhalten ohne Kill; sauber fortsetzbar.
- Metriken pro Session zählbar in Sliding Windows; Defaults konfigurierbar via Settings.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
