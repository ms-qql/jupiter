# PROJ-1: Engine-Treiber — Claude-Max-Session headless

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- None — **Fundament** des MVP (ersetzt bewusst die übliche „Auth = PROJ-1"-Regel; Auth ist MVP-Non-Goal, single-user).

## Beschreibung
Der Motor von Jupiter: ein Backend-Dienst, der **eine** Claude-Max-Session über **Claude Code headless** (`claude -p`, Stream-JSON I/O) startet, mitliest, steuert und beendet — mit **Subscription-Auth**, nicht über die rohe Anthropic-API. Treiber-Modell #6; Treiber-Seite des Modell-Routings #22 (`--model`-Flag).

## User Stories
- Als Solo-Entwickler möchte ich eine Claude-Max-Session headless aus Jupiter heraus starten, um meine Subscription ohne Terminal zu nutzen.
- Als Nutzer möchte ich der Session einen Auftrag (Prompt) senden und ihre Ausgabe live mitlesen, um den Fortschritt zu verfolgen.
- Als Nutzer möchte ich pro Session das Modell wählen (Haiku/Sonnet/Opus), um Kosten und Leistung je Aufgabe zu steuern.
- Als Nutzer möchte ich eine laufende Session pausieren und sauber stoppen können, um die Kontrolle zu behalten.
- Als Nutzer möchte ich beliebige Inhalte (Logs, Code, Fehlermeldungen) in das Session-Fenster **einfügen** und die Session-Ausgabe **herauskopieren**, um schnell Daten rein- und rauszubekommen.

## Acceptance Criteria
- [ ] Backend startet eine Claude-Code-headless-Session als Subprozess (`claude -p`, Stream-JSON I/O) mit **Subscription-Auth** (kein API-Key).
- [ ] Eine Session ist mit initialem Prompt + Arbeitsverzeichnis (Projektpfad) startbar.
- [ ] Eingehende Stream-JSON-Events (assistant text, tool_use, result) werden geparst und als strukturierte Events nach oben gereicht.
- [ ] Weitere Eingaben können an eine laufende Session gesendet werden (multi-turn).
- [ ] Das Modell ist pro Session über `--model` setzbar (haiku/sonnet/opus); Default = Sonnet.
- [ ] Session lässt sich sauber **stoppen** (Prozess beendet, kein Zombie) und **pausieren** (keine neuen Eingaben verarbeitet).
- [ ] Session-Status ist über die API abfragbar: `starting / running / waiting / done / error`.
- [ ] Token-/Kontext-Verbrauch wird aus den result-Events extrahiert und bereitgestellt (Datenquelle für PROJ-5 / #25).
- [ ] **Einfügen (Paste):** beliebiger Text-/Code-Inhalt (auch mehrzeilig/groß) kann als Eingabe an eine laufende Session übergeben werden.
- [ ] **Herauskopieren (Copy):** der Session-Inhalt (vollständiges Transkript bzw. eine einzelne Nachricht/Ausgabe) ist als Klartext abrufbar, sodass er kopiert werden kann.
- [ ] _(UI-Hinweis: die eigentlichen Copy/Paste-Affordanzen im Session-Fenster rendert die Session-Detailansicht in PROJ-3; PROJ-1 stellt nur die Eingabe-/Ausgabe-Schnittstelle bereit.)_

## Edge Cases
- `claude` nicht eingeloggt / Subscription abgelaufen → klare deutsche Fehlermeldung, Status = `error`.
- Subprozess stürzt ab / OOM → Status = `error`, letzter Stand bleibt lesbar.
- Ungültiger/fehlender Projektpfad → Start wird mit Begründung abgelehnt.
- Mehrere parallele Sessions → jede mit isoliertem Prozess + eigenem `cwd`.
- Unparsebare Stream-JSON-Zeile → geloggt, Session läuft weiter (kein Hard-Fail).
- Sehr großer Paste-Inhalt → kein Crash; ggf. Hinweis/Limit, statt das Kontextfenster blind zu fluten (Zusammenspiel mit PROJ-5 / #25).

## Technical Requirements (optional)
- **Verifikations-Spike zuerst** (Brainstorm offener Punkt #1): bestätigen, dass `claude -p` mit Stream-JSON + Subscription-Auth headless steuerbar ist, bevor weitergebaut wird.
- Cross-Provider (Codex/Gemini/GLM/Ollama) = je eigener Treiber (P1, #13) — Architektur muss die Treiber-Abstraktion offenhalten.
- Ein Subprozess pro Session; Lifecycle-Management im Backend.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
