# PROJ-2: Vault-Anbindung als Dienst

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- None — kann parallel zu PROJ-1 gebaut werden (eigenständiger Backend-Dienst).

## Beschreibung
Ein Backend-Dienst, der den **Hal-Vault** (`/home/dev/tools/Hal`, Obsidian, PARA-Struktur) als Daten-/Wissensschicht anbindet: MD lesen, schreiben, auflisten, durchsuchen. Schreibt Session-Logs und Handover-Dokumente als offenes MD zurück. Grundlage für Gedächtnis (#9), Doku (#8) und spätere Recovery (#20) sowie für den geteilten Dienst (#14). Jedes Artefakt trägt ein `owner`-Feld (#21).

## User Stories
- Als Nutzer möchte ich, dass Session-Transkripte automatisch als MD in meinem Hal-Vault landen, um sie in Obsidian wiederzufinden.
- Als Nutzer möchte ich Handover-Dokumente im Vault speichern und lesen, damit Kontext über Resets hinweg erhalten bleibt.
- Als Nutzer möchte ich, dass jedes Artefakt ein `owner`-Feld trägt, um später ohne Migration teamfähig zu werden.
- Als System möchte ich Vault-MD durchsuchen können, um später Pointer statt Volltext zu liefern (Grundlage RAG #23).

## Acceptance Criteria
- [ ] Dienst kann MD-Dateien im Hal-Vault lesen, schreiben und auflisten.
- [ ] Jupiter-Artefakte landen unter einem dedizierten Vault-Unterordner (z. B. `02 Projects/Jupiter/…` bzw. `Agentic OS/…`; exakte Konvention = Architektur-Entscheidung), **ohne** die bestehende PARA-Struktur zu verändern.
- [ ] Geschriebene Dateien sind valides Obsidian-MD mit YAML-Frontmatter (mind. `owner`, `session_id`, `created`, `type`).
- [ ] Rohe Session-Logs und Handover-/kuratierte Dokumente liegen in getrennten Bereichen (Vorbereitung Stufe 3 / #10).
- [ ] Textsuche über Vault-MD liefert Treffer mit Dateipfad + Ausschnitt.
- [ ] Schreibzugriffe sind atomar (kein halb geschriebenes MD bei Absturz).

## Edge Cases
- Datei existiert bereits → konfigurierbar: anhängen vs. neue versionierte Datei (**kein** stilles Überschreiben).
- Vault-Pfad nicht erreichbar / Permission denied → klarer Fehler, keine Datenkorruption.
- Sehr großes Log → Streaming-Write statt alles im RAM.
- Umlaute/Sonderzeichen in Titeln → saubere Slug-Bildung für Dateinamen.
- Gleichzeitige Schreibzugriffe zweier Sessions → kein Datenverlust (getrennte Dateien / Locking).

## Technical Requirements (optional)
- **Vault-Struktur-Konvention** (Brainstorm offener Punkt #3) in der Architektur-Phase festlegen, passend zum bestehenden PARA-Layout (`00 Context` … `08 To-Dos`, `Agentic OS/`).
- Live-Zustand bleibt in Postgres; der Vault ist die persistente **Wahrheit** (Datenmodell-Grenze in Architektur klären).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
