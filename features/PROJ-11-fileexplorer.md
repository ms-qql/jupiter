# PROJ-11: Fileexplorer + Drag-and-Drop-Transport

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #15 (+ Clipboard-Paste-Erweiterung)

## Dependencies
- Requires: PROJ-1 (Pfad-Scope) — Wiederverwendung der erlaubten Roots / `validate_project_path`-Logik für sicheren Datei-Zugriff.
- Bewusst **von Sessions entkoppelt** (neutrale Arbeitsraum-Ebene), nutzt aber dieselbe Shell/Backend.

## Beschreibung
Ein vollständiger **Fileexplorer** (Vorbild 1Panel) als neutrale Datei-Ebene auf dem VPS: Verzeichnisse browsen, Dateien anlegen/umbenennen/verschieben/löschen, und Dateien per **Drag-and-Drop** zwischen lokalem PC und VPS transportieren (Up-/Download). Bewusst getrennt vom Session-Mentalmodell — „gleiche Shell, getrennte Mentalmodelle".

**Clipboard-Paste (Erweiterung):** Inhalte können zusätzlich direkt **aus der Zwischenablage eingefügt** werden (Strg/Cmd+V) — vor allem Screenshots/Bilder, aber auch kopierte Dateien. Solche Pastes landen in einem **dedizierten Clipboard-Ordner** mit einem **kurzen, stabilen Pfad**, den man bequem aus einer Session/dem Terminalfenster referenzieren kann (z. B. um Claude ein gerade kopiertes Bild zu zeigen). Der Pfad der pasteten Datei (und des Ordners) ist per Klick kopierbar.

## User Stories
- Als Nutzer möchte ich die Projektverzeichnisse auf dem VPS im Browser durchsuchen, ohne SSH/Terminal.
- Als Nutzer möchte ich Dateien per Drag-and-Drop vom PC in ein VPS-Verzeichnis hochladen.
- Als Nutzer möchte ich Dateien vom VPS herunterladen.
- Als Nutzer möchte ich grundlegende Datei-Operationen (anlegen, umbenennen, verschieben, löschen) im UI ausführen.
- Als Nutzer möchte ich nur innerhalb erlaubter Roots arbeiten, damit ich nichts Systemkritisches berühre.
- Als Nutzer möchte ich Inhalte (v. a. Screenshots/Bilder) per **Strg/Cmd+V aus der Zwischenablage** hochladen, ohne sie erst als Datei zwischenspeichern zu müssen.
- Als Nutzer möchte ich, dass solche Pastes in einem **festen Clipboard-Ordner** landen, damit ich nicht jedes Mal ein Ziel wählen muss.
- Als Nutzer möchte ich den **Pfad** der gepasteten Datei (und des Clipboard-Ordners) mit einem Klick kopieren, um ihn direkt in einer Session/im Terminal zu referenzieren.

## Acceptance Criteria
- [ ] Baumansicht + Listenansicht der Verzeichnisse innerhalb der **erlaubten Roots**; Navigation per Klick/Breadcrumb.
- [ ] **Upload** per Drag-and-Drop und per Datei-Dialog; Fortschrittsanzeige; mehrere Dateien gleichzeitig.
- [ ] **Download** einzelner Dateien (und Ordner als Zip optional).
- [ ] Operationen **Neuer Ordner / Umbenennen / Verschieben / Löschen** mit Bestätigung bei Löschen.
- [ ] Jeder Pfad wird serverseitig gegen die erlaubten Roots geprüft; Zugriff außerhalb → 403 mit klarer Meldung.
- [ ] Große Dateien werden gestreamt (kein vollständiges Laden in den RAM); konfigurierbares Größenlimit.
- [ ] **Clipboard-Paste:** Strg/Cmd+V im Fileexplorer fügt Bild-/Datei-Inhalte aus der Zwischenablage als Upload ein; Bild-Pastes (ohne Originalnamen) erhalten einen **kollisionsfreien, sprechenden Namen** (z. B. Zeitstempel: `clip-2026-06-23-141207.png`).
- [ ] Es gibt einen **dedizierten Clipboard-Ordner** mit **kurzem, stabilem, konfigurierbarem Pfad** (Default-Vorschlag: ein fester Ordner innerhalb der erlaubten Roots, z. B. `…/clipboard/`); er wird bei Bedarf automatisch angelegt.
- [ ] Pastes landen **standardmäßig im Clipboard-Ordner** — unabhängig vom gerade geöffneten Verzeichnis (optional: „in aktuellen Ordner pasten").
- [ ] Der Clipboard-Ordner ist im UI **schnell erreichbar** (Shortcut/Pin) und sein **Pfad ist per Klick kopierbar**; ebenso der Pfad jeder einzelnen gepasteten Datei.
- [ ] Lade-/Fehler-/Leer-Zustände explizit; alle Texte deutsch.

## Edge Cases
- **Pfad-Traversal** (`../` / Symlink aus dem Root heraus) → serverseitig auf `realpath` normalisieren und ablehnen.
- **Namenskollision beim Upload** → Nachfragen: Überschreiben / Umbenennen / Abbrechen.
- **Datei zu groß** → klare Meldung statt Timeout; Limit konfigurierbar.
- **Keine Schreibrechte im Zielordner** → verständliche Fehlermeldung.
- **Löschen eines nicht-leeren Ordners** → explizite Bestätigung mit Anzahl betroffener Dateien.
- **Binär-/unbekannte Dateitypen** → kein Preview-Versuch, nur Download.
- **Leere/nicht unterstützte Zwischenablage** beim Paste (z. B. nur Plaintext, kein Datei-/Bildinhalt) → klarer Hinweis statt stiller No-Op; Plaintext-Paste optional als `.txt` ablegen.
- **Mehrere Bilder/Dateien gleichzeitig in der Zwischenablage** → alle als separate Dateien ablegen, kollisionsfrei nummeriert.
- **Browser verweigert Clipboard-Zugriff** (fehlende Permission/HTTP statt HTTPS) → verständliche Meldung + Fallback auf Drag-and-Drop/Datei-Dialog.
- **Namenskollision im Clipboard-Ordner** → automatisch eindeutiger Name (Zeitstempel/Suffix), kein Überschreiben ohne Rückfrage.
- **Clipboard-Ordner gelöscht/umkonfiguriert** → beim nächsten Paste automatisch neu anlegen.

## Technical Requirements (optional)
- Backend: Streaming-Up-/Download über FastAPI; serverseitige Pfad-Normalisierung (`os.path.realpath`).
- Kein DB-State nötig (reine Dateisystem-Ebene); Operationen idempotent wo möglich.
- Antwortzeit Verzeichnis-Listing < 300 ms für typische Ordner.
- Clipboard-Paste über die Browser **Clipboard API** (`paste`-Event / `navigator.clipboard`); benötigt sicheren Kontext (HTTPS/Tailscale ist vorhanden).
- Clipboard-Ordner-Pfad **zentral konfigurierbar** (Settings) mit sinnvollem, kurzem Default; gleiche Root-/`realpath`-Scope-Prüfung wie alle anderen Pfade.

## Open Design Questions (in /abc-architecture zu klären)
1. **Clipboard-Ordner global oder pro Projekt?** ✅ **Entschieden (2026-06-23): global, kurzer Pfad** — ein fester globaler Ordner (z. B. `~/clipboard/` bzw. `/home/dev/projects/.clipboard/`), aus jeder Session/jedem Terminal mit kurzem Pfad referenzierbar. Konkreten Pfad in `/abc-architecture` festzurren (innerhalb der erlaubten Roots).
2. **Aufbewahrung/Aufräumen?** _Default-Vorschlag:_ keine Auto-Löschung im MVP; optional späteres „älter als N Tage aufräumen", um den Ordner nicht volllaufen zu lassen.

## Wiederverwendung aus „Rubric Pics" (Referenz)
Rubric hat bereits ein funktionierendes Paste-→-Ordner-Pendant (Pics-Tab). Quelle: `/home/dev/projects/tools/rubric/templates/pics/` (`index.html` = Frontend, `server.js` = Backend). Stack ist anders (Rubric: Vanilla JS + Node-HTTP; Jupiter: React/Next.js + FastAPI), daher **Konzepte/Algorithmen portieren**, nicht Code 1:1 kopieren.

**Direkt übernehmbar (Muster/Algorithmus):**
- **Paste-Handler:** `document.addEventListener('paste', …)` → `e.clipboardData.items` iterieren, `kind === 'file'` via `getAsFile()` (`index.html:630-648`). Konzept 1:1 in einen React-`onPaste`-Handler übertragbar.
- **Dateiname für namenlose Pastes:** `paste-YYYYMMDD-HHMMSS.{ext}` (`index.html:543-550`) — deckt unsere AC „kollisionsfreier Zeitstempel-Name" ab (`clip-…` statt `paste-…`).
- **Kollisionsfreiheit:** `uniqueName(dir, name)` mit Suffix `-1/-2/…` (`server.js:91-102`) → in Python nachbauen.
- **Validierung:** Extension-Whitelist `ALLOWED_EXT`, `MAX_FILE_BYTES` (50 MB), `MAX_REQUEST_BYTES` (250 MB) (`server.js:37-44`) → als FastAPI-Limits/MIME-Check übernehmen.
- **Path-Traversal-Schutz:** `safeName()` (`server.js:85-89`) → in Python via `realpath`-Scope-Prüfung (haben wir schon als AC).
- **Storage-Ordner als Konvention:** Rubric nutzt einen **globalen, kurzen Pfad** `~/projects/pics/`, via `$STORAGE_DIR` konfigurierbar (`server.js:35`) — **bestätigt unsere Entscheidung „global, kurzer Pfad"**. Jupiters Clipboard-Ordner kann analog (`~/projects/.clipboard/` o. ä.) liegen oder bewusst neben dem Pics-Ordner.
- **List/Delete/Thumb-Endpoints** als REST-Muster (`server.js:267-359`) → Architektur-Vorlage für den Fileexplorer-Teil.

**Lücke — neu zu bauen (genau unser Mehrwert):**
- **„Pfad kopieren" fehlt in Rubric** (zeigt nur Dateiname, keinen absoluten Pfad). Genau die für PROJ-11 zentrale Funktion (Pfad einer gepasteten Datei/des Ordners per Klick kopieren, um ihn im Terminal/in einer Session zu referenzieren) ist **komplett neu** zu implementieren.
- Markitdown-Companion-`.md` aus Rubric (`server.js:327-336`) ist für Jupiter **nicht** nötig (weglassen).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
