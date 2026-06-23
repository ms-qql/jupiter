# PROJ-20: Spracheingabe / Push-to-Talk (abo-frei, DSGVO-konform)

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #29

## Dependencies
- Requires: PROJ-9 (Smart Launcher) — Diktat fürs Auftrag-/Prompt-Feld beim Session-Start.
- Requires: PROJ-4 (Decision Cards) — Diktat für Card-Antworten/Kommentare.

## Beschreibung
**Push-to-Talk-Diktat** statt Tippen — für das Auftrag-Feld im Smart Launcher (#12) und für Decision-Card-Antworten (#4). **Kein Monats-Abo** (kein WhisperFlow) und **DSGVO-konform**: Standard ist **self-hosted Whisper auf dem VPS** (`faster-whisper`/`whisper.cpp`, lokal, keine laufenden Kosten); optionaler Schnell-Fallback **Groq Whisper** (pay-per-use). Die **Browser Web Speech API ist verworfen** (sendet Audio an Google → kollidiert mit der DSGVO-Linie).

## User Stories
- Als Nutzer möchte ich per Push-to-Talk meinen Auftrag ins Smart-Launcher-Feld diktieren, statt zu tippen.
- Als Nutzer möchte ich Decision-Card-Kommentare/Antworten diktieren können.
- Als Nutzer möchte ich, dass die Transkription standardmäßig **lokal auf dem VPS** läuft, damit keine Audiodaten das System verlassen.
- Als Nutzer möchte ich optional einen schnelleren Cloud-Fallback (Groq) aktivieren, wenn ich das bewusst will.
- Als Nutzer möchte ich das Transkript vor dem Absenden sehen und korrigieren.

## Acceptance Criteria
- [ ] **Push-to-Talk**-Aufnahme im Auftrag-Feld (PROJ-9) und in Card-Antworten (PROJ-4): aufnehmen → transkribieren → Text einfügen.
- [ ] **Standard-Transkription self-hosted** auf dem VPS (faster-whisper/whisper.cpp); kein API-Key nötig, keine laufenden Kosten.
- [ ] **Optionaler Groq-Fallback** ist konfigurierbar (API-Key in `.env`), standardmäßig **aus**; Umschalten ist eine bewusste Nutzerentscheidung.
- [ ] **Browser Web Speech API wird nicht verwendet** (kein Audio an Google); Audio geht nur an die konfigurierte (lokale/EU-)Transkription.
- [ ] Das **Transkript ist vor dem Absenden editierbar** (Korrektur), nicht auto-submit.
- [ ] Mikrofon-Zugriff scheitert/verweigert → klare Meldung, Tippen bleibt jederzeit möglich.
- [ ] Alle Texte deutsch; Aufnahme-/Transkriptions-/Fehler-Zustände sichtbar.

## Edge Cases
- **Kein Mikrofon / Permission verweigert** → verständlicher Hinweis, Feature degradiert auf Texteingabe.
- **Whisper-Dienst nicht erreichbar** → Fehlermeldung + (falls konfiguriert) Angebot Groq-Fallback; nie stiller Verlust der Aufnahme.
- **Lange Aufnahme** → Größen-/Längenlimit mit Hinweis; Transkription gestreamt/segmentiert.
- **Schlechte Audioqualität** → Transkript trotzdem anzeigen (editierbar), keine Auto-Aktion.
- **Groq aktiviert ohne Key** → Setup-Hinweis, bleibt auf self-hosted.
- **Mehrsprachigkeit** → Sprache konfigurierbar/Autodetect, Default Deutsch.

## Technical Requirements (optional)
- Muster analog `watch`-Skill: self-hosted Whisper als Standard, Groq als optionaler pay-per-use-Fallback.
- DSGVO: keine US-Browser-Speech-API; Audio-Upload nur an konfigurierten lokalen/EU-Endpunkt; Secrets via `.env`.
- Audio wird nach Transkription nicht dauerhaft gespeichert (sofern nicht bewusst aktiviert).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
