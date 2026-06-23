# PROJ-11: Fileexplorer + Drag-and-Drop-Transport

## Status: Approved
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #15 (+ Clipboard-Paste-Erweiterung)
**Backend:** ✅ implementiert (2026-06-23) · **Frontend:** ✅ implementiert (2026-06-23) · **QA:** ✅ READY (2026-06-23, 5 Low-Follow-ups)

## Dependencies
- Requires: PROJ-1 (Pfad-Scope) — Wiederverwendung der erlaubten Roots / `validate_project_path`-Logik für sicheren Datei-Zugriff.
- Requires: PROJ-3 (Cockpit / Session-Fenster) — der **In-Session Dokument-Clipboard** (Surface B, s. u.) sitzt im Session-Detail neben dem Eingabefeld und fügt den Pfad dort ein.
- Der **Fileexplorer** (Surface A) ist bewusst **von Sessions entkoppelt** (neutrale Arbeitsraum-Ebene); der **In-Session-Clipboard** (Surface B) ist bewusst **an die Session gekoppelt**. Beide teilen sich dasselbe Datei-/Upload-Backend.

## Beschreibung
Ein vollständiger **Fileexplorer** (Vorbild 1Panel) als neutrale Datei-Ebene auf dem VPS: Verzeichnisse browsen, Dateien anlegen/umbenennen/verschieben/löschen, und Dateien per **Drag-and-Drop** zwischen lokalem PC und VPS transportieren (Up-/Download). Bewusst getrennt vom Session-Mentalmodell — „gleiche Shell, getrennte Mentalmodelle".

**Clipboard-Paste (Erweiterung):** Inhalte können zusätzlich direkt **aus der Zwischenablage eingefügt** werden (Strg/Cmd+V) — vor allem Screenshots/Bilder, aber auch kopierte Dateien. Solche Pastes landen in einem **dedizierten Clipboard-Ordner** mit einem **kurzen, stabilen Pfad**, den man bequem aus einer Session/dem Terminalfenster referenzieren kann (z. B. um Claude ein gerade kopiertes Bild zu zeigen). Der Pfad der pasteten Datei (und des Ordners) ist per Klick kopierbar.

**In-Session Dokument-Clipboard (Schwerpunkt, Surface B):** Zusätzlich zum Explorer gibt es **direkt im Session-Fenster** einen **Ein-Klick-Weg**, eine Datei einzufügen — **ohne in den Fileexplorer zu wechseln**. Per Button/Drop-Zone neben dem Eingabefeld lässt sich eine Datei **per Drag-and-Drop oder per Paste aus der Zwischenablage** ablegen; sie wird in den Clipboard-Ordner hochgeladen und ihr **Pfad sofort in das Session-Eingabefeld eingefügt** (referenziert), sodass die Session/Claude die Datei direkt sehen/verwenden kann. Das ist der eigentliche Komfort-Kern: kopiertes Bild/Dokument → ein Klick → in der Session referenziert.

## User Stories
- Als Nutzer möchte ich die Projektverzeichnisse auf dem VPS im Browser durchsuchen, ohne SSH/Terminal.
- Als Nutzer möchte ich Dateien per Drag-and-Drop vom PC in ein VPS-Verzeichnis hochladen.
- Als Nutzer möchte ich Dateien vom VPS herunterladen.
- Als Nutzer möchte ich grundlegende Datei-Operationen (anlegen, umbenennen, verschieben, löschen) im UI ausführen.
- Als Nutzer möchte ich nur innerhalb erlaubter Roots arbeiten, damit ich nichts Systemkritisches berühre.
- Als Nutzer möchte ich Inhalte (v. a. Screenshots/Bilder) per **Strg/Cmd+V aus der Zwischenablage** hochladen, ohne sie erst als Datei zwischenspeichern zu müssen.
- Als Nutzer möchte ich, dass solche Pastes in einem **festen Clipboard-Ordner** landen, damit ich nicht jedes Mal ein Ziel wählen muss.
- Als Nutzer möchte ich den **Pfad** der gepasteten Datei (und des Clipboard-Ordners) mit einem Klick kopieren, um ihn direkt in einer Session/im Terminal zu referenzieren.
- Als Nutzer möchte ich **direkt im Session-Fenster** (ohne den Fileexplorer zu öffnen) per Knopfdruck eine Datei einfügen — per Drag-and-Drop **oder** Paste aus der Zwischenablage.
- Als Nutzer möchte ich, dass eine so eingefügte Datei automatisch in den Clipboard-Ordner hochgeladen und ihr **Pfad sofort in mein Session-Eingabefeld** eingefügt wird, damit ich sie ohne Tippen referenzieren kann.

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
- [ ] **In-Session Dokument-Clipboard (Surface B):** Im Session-Fenster gibt es neben dem Eingabefeld einen **sichtbaren Button/Drop-Bereich**, ohne Navigation in den Fileexplorer erreichbar.
- [ ] Über diesen Bereich kann eine Datei **per Drag-and-Drop** und **per Paste (Strg/Cmd+V)** eingefügt werden.
- [ ] Die eingefügte Datei wird in den **Clipboard-Ordner** hochgeladen (gleiche Backend-Logik wie der Explorer-Upload) und ihr **absoluter Pfad wird automatisch in das Session-Eingabefeld eingefügt** (an Cursor-Position/angehängt), nicht nur kopiert.
- [ ] Der Upload-/Einfüge-Vorgang zeigt Fortschritt/Erfolg und blockiert das Eingabefeld nicht dauerhaft; bei Fehler bleibt der getippte Text erhalten.
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
- **In-Session-Drop bei nicht-laufender/fehlerhafter Session** → Upload trotzdem möglich (Datei landet im Clipboard-Ordner), Pfad-Einfügen nur, wenn ein Eingabefeld aktiv ist; sonst Pfad zum Kopieren anbieten.
- **Pfad-Einfügen während die Session gerade tippt/sendet** → Pfad an aktueller Cursor-Position einfügen, vorhandenen Text nicht überschreiben.
- **Mehrere Dateien gleichzeitig in die Session droppen** → alle hochladen, alle Pfade (zeilenweise) einfügen.

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
**Erstellt:** 2026-06-23 · **Stack:** Next.js 16 (App Router) + Tailwind + shadcn/ui (Frontend) · FastAPI + **Dateisystem** (Backend; kein MinIO/DB — Jupiter host-native) · **Branch:** dev

### Kurzfassung
**Zwei Oberflächen, ein Backend.** Ein gemeinsamer Datei-/Upload-Dienst speist (A) den vollen **Fileexplorer** und (B) den **In-Session Dokument-Clipboard** — den Komfort-Schwerpunkt. Dateien leben direkt im VPS-Dateisystem innerhalb der erlaubten Roots (`allowed_roots = /home/dev/projects`, `/home/dev/tools`, [config.py:44](../backend/app/config.py#L44)) — **kein MinIO, keine DB, kein JWT** (Jupiter-Override). Pfad-Sicherheit kommt aus dem bestehenden `realpath`+Root-Muster (`validate_project_path`, `md_reader`). Clipboard-Inhalte landen in einem **globalen, kurzen, konfigurierbaren** Ordner. Viele Bausteine sind aus PROJ-7 (MD-Reader) und Rubric Pics wiederverwendbar (siehe Referenz-Sektion oben).

- **Surface A — Fileexplorer:** neue, von Sessions **entkoppelte** Cockpit-Ansicht (`/dateien`).
- **Surface B — In-Session Dokument-Clipboard:** an die Session **gekoppelt**; sitzt im Session-Detail neben dem Eingabefeld und fügt den hochgeladenen Pfad direkt dort ein.

### A) Komponenten-Struktur (Frontend)

**Geteilter Baustein:** ein `useFileUpload`-Hook + eine kleine `DropPasteZone`-Komponente (Drag-and-Drop + `onPaste`), die beide Oberflächen nutzen (DRY). Reuse-Konzept des Paste-Handlers aus Rubric (`index.html:630-648`).

**Surface A — Fileexplorer (entkoppelt):**
```
app/(cockpit)/dateien/page.tsx        ← NEUE Route „Dateien" (neben /doku); eigener useFileExplorer-Hook (nicht an SessionsProvider gebunden)
└── FileExplorer
    ├── RootSelector            → Umschalten Projekte / Tools (analog MD-Reader-Quellen)
    ├── Breadcrumb              → Pfad-Navigation
    ├── DirListing              → Ordner + Dateien (Name, Größe, mtime); Reuse des FileTree-Musters (file-tree.tsx)
    │   └── FileRow             → Aktionen: Download · Umbenennen · Verschieben · Löschen · „Pfad kopieren"
    ├── DropPasteZone (Overlay) → geteilt: Drag-and-Drop + Paste-Upload
    ├── ClipboardPin            → Schnellzugriff auf den Clipboard-Ordner + „Pfad kopieren"
    ├── UploadProgress
    └── Empty/Error/Loading     → Reuse states.tsx
```

**Surface B — In-Session Dokument-Clipboard (gekoppelt, Schwerpunkt):**
```
app/(cockpit)/sessions/[id]/page.tsx  ← BESTEHEND; Eingabe-Textarea (page.tsx:260) + input-State (:48) + sendInput (:78)
└── SessionInputBar (bestehend, erweitert)
    └── SessionClipboardButton (NEU)   → Ein-Klick-Button + DropPasteZone direkt am Eingabefeld
         · Drag-and-Drop ODER Strg/Cmd+V einer Datei
         · → useFileUpload → POST /files/upload (Ziel = Clipboard-Ordner)
         · → fügt den zurückgegebenen ABSOLUTEN Pfad in den input-State ein (an Cursor-Position),
           sodass er mit der nächsten Nachricht via sendInput an die Session geht
```
- **shadcn-first:** Tabelle/Buttons/Dialoge aus shadcn/ui; Clipboard & DnD über native Browser-APIs (kein Fremd-Paket).
- **„Pfad kopieren"** (Ordner **und** Einzeldatei) sowie das **automatische Pfad-Einfügen ins Session-Eingabefeld** sind die **neu zu bauenden** Kernfunktionen — in Rubric Pics nicht vorhanden.

### B) Datenmodell (kein DB-State)
Reine Dateisystem-Ebene. Persistenter Zustand = die Dateien selbst + **ein** Konfigurationswert:
```
clipboard_dir : absoluter Pfad des Clipboard-Ordners
                Default-Vorschlag: /home/dev/projects/clipboard  (innerhalb allowed_roots → im Explorer browsbar
                UND aus jedem Terminal/jeder Session kurz referenzierbar; Geschwister-Konvention zu Rubrics …/pics)
                konfigurierbar via JUPITER_CLIPBOARD_DIR (pydantic-settings) + PATCH-Endpoint (wie /settings/threshold)
Listing-Eintrag (read-only, je Datei/Ordner): name · kind (file|dir) · size · mtime · abs_path
Paste-Dateiname: clip-YYYYMMDD-HHMMSS.<ext>, kollisionsfrei via Suffix -1/-2 (uniqueName-Algorithmus aus Rubric portiert)
Limits: max. Dateigröße (Default 50 MB) · erlaubte Extensions (Whitelist) — Konzepte aus Rubric (server.js:37-44)
```

### C) API-Form (neuer `/files`-Router, alles scoped auf allowed_roots)
```
GET   /files/list?root=&path=     → Verzeichnis-Inhalt (Ordner+Dateien, name/size/mtime/kind)
GET   /files/download?path=       → Datei-Download (FileResponse, gestreamt für große Dateien)   ← neu
POST  /files/upload  (multipart)  → 1..n Dateien in Zielordner; Default-Ziel = clipboard_dir;
                                     Antwort: gespeicherte Namen + ABSOLUTE Pfade (für „Pfad kopieren")  ← neu
POST  /files/mkdir                → neuen Ordner anlegen
POST  /files/rename               → umbenennen
POST  /files/move                 → verschieben
POST  /files/delete               → löschen (Bestätigung im UI; safeName-Schutz)
GET   /settings/clipboard-dir     → aktuellen Clipboard-Pfad lesen
PATCH /settings/clipboard-dir     → Clipboard-Pfad setzen (Scope-geprüft)
```
- **Clipboard-Paste** nutzt denselben `POST /files/upload` mit Zielordner = `clipboard_dir` (kein Extra-Endpoint nötig); fehlt der Originalname (Screenshot), vergibt der Server den `clip-…`-Zeitstempelnamen.
- Jeder Pfad wird serverseitig per `realpath` normalisiert und gegen die Roots geprüft (Traversal/Symlink-Schutz); außerhalb → 403.

### D) Tech-Entscheidungen (warum)
- **Dateisystem statt MinIO/DB:** Jupiter läuft host-native auf dem Dev-VPS; die Dateien sollen genau dort liegen, wo Sessions/Terminals sie sehen — Object-Storage würde die „im Terminal referenzieren"-Anforderung gerade brechen.
- **Clipboard-Ordner INNERHALB der Roots:** nur so ist er zugleich im Explorer browsbar **und** kurz referenzierbar. (Bewusst anders als der erste Explore-Vorschlag eines isolierten Roots — Isolation würde Browsbarkeit + Referenzierbarkeit verhindern.)
- **Reuse vor Neubau:** Pfad-Scoping (`realpath`), atomares Schreiben (tempfile+`os.replace` aus `vault.py`), FileTree-UI, `lib/api.ts`/`ApiError`, `states.tsx`, Polling-Muster (eigener Hook statt SessionsProvider) — alles vorhanden. Aus Rubric Pics portiert: Paste-Handler, `uniqueName`, Whitelist/Limits.
- **Zwei Oberflächen, ein Endpoint:** Surface B (In-Session) nutzt **denselben** `POST /files/upload` mit Ziel = Clipboard-Ordner — kein zweiter Backend-Pfad. Der Unterschied liegt nur im Frontend: Surface A zeigt die Datei im Explorer, Surface B fügt den zurückgegebenen absoluten Pfad in die Session-`Textarea` ein (vorhandenes `input`-State/`sendInput`, [sessions/[id]/page.tsx:48](../nextjs_app/app/(cockpit)/sessions/[id]/page.tsx#L48)).
- **„Pfad kopieren" / „Pfad einfügen" als Mehrwert:** die wirklich neuen Kernfunktionen; Backend liefert dafür den absoluten Pfad in jeder Upload-/List-Antwort mit.
- **Sicherheit:** Streaming-Up-/Download (kein Voll-RAM), Größenlimit, Extension-Whitelist, harte Traversal-Prüfung; gefährliche Ops (Löschen) nur mit Bestätigung.

### E) Abhängigkeiten
- **Backend (neu):** `python-multipart` — von FastAPI für `UploadFile`/Multipart benötigt. (Dateisystem, Streaming, `realpath`, `tempfile` = Standardbibliothek.)
- **Frontend (neu):** keine — native Clipboard- & Drag-and-Drop-APIs + vorhandene shadcn/ui-Komponenten.

### F) Offene Punkte für die Umsetzung
- **Konkreter Clipboard-Pfad** (Default-Vorschlag `/home/dev/projects/clipboard`) — in der Review bestätigen.
- **Browse-Scope:** beide Roots (Projekte + Tools) oder nur Projekte? Default-Vorschlag: beide, wie heute bei Sessions.
- **Aufräumen** des Clipboard-Ordners: im MVP keine Auto-Löschung (siehe Open Design Question 2).

## Backend-Implementierung (2026-06-23)
Geliefert auf Branch `dev`. Dateisystem-Ebene, kein DB/JWT (Jupiter-Override); `realpath`-Scope auf `allowed_roots`.

**Neue Dateien:**
- `backend/app/engine/files.py` — `FileService` (Pfad-Härtung, gestreamter Upload mit Größen-Abbruch, atomares Schreiben via `os.replace`, `uniqueName`, Clipboard-Ordner).
- `backend/app/schemas/files.py` — Pydantic-Schemas (FileEntry, DirListing, UploadResult, …).
- `backend/app/routes/files.py` — `/files`-Router (synchrone Handler → Threadpool-Streaming).
- `backend/tests/test_proj11_files.py` — 21 Tests (Upload/Paste, Listing, Download, Ops, Security, Clipboard-Dir).

**Geändert:** `config.py` (`clipboard_dir` Default `/home/dev/projects/clipboard`, `upload_max_file_bytes` 50 MB, `upload_allowed_extensions`), `routes/settings.py` + `schemas/settings.py` (Clipboard-Dir-Endpoints), `main.py` (`app.state.files` + Router).

**Route-Kontrakt (fürs Frontend, `/abc-frontend`):**
| Methode + Pfad | Eingabe | Antwort |
|---|---|---|
| `GET /files/roots` | — | `[{label, path}]` (RootSelector) |
| `GET /files/list?path=` | optional `path` (Default = erste Wurzel) | `{path, entries:[{name,kind,size,mtime,path}]}` (Ordner zuerst) |
| `GET /files/download?path=` | `path` | Datei-Stream (FileResponse) |
| `POST /files/upload` | multipart `files[]` + optional Form `target_dir` (Default = Clipboard) | `{files:[FileEntry]}` — **`path` ist absolut** (für „Pfad kopieren" / Einfügen in Session-Textarea) |
| `POST /files/mkdir` | `{parent, name}` | `FileEntry` |
| `POST /files/rename` | `{path, new_name}` | `FileEntry` |
| `POST /files/move` | `{path, dest_dir}` | `FileEntry` |
| `POST /files/delete` | `{paths:[…]}` | `{deleted:[…], failed:[…]}` |
| `GET/PATCH /settings/clipboard-dir` | PATCH `{path}` | `{path}` |

Fehler: 400 (außerhalb Roots / zu groß / Typ nicht erlaubt / ungültiger Name), 404 (nicht gefunden), 409 (Namenskollision bei rename/move/mkdir).

**Hinweise / kleine Abweichungen:**
- **Surface B (In-Session):** Frontend ruft `POST /files/upload` (Default-Ziel Clipboard) und fügt den zurückgegebenen `files[0].path` in die Session-`Textarea` ein.
- **Clipboard-Paste ohne Endung** (Browser-„blob") → Endung wird aus `content_type` ergänzt; **gänzlich namenlos** → `clip-YYYYMMDD-HHMMSS.<ext>`.
- **Upload-Whitelist** (`upload_allowed_extensions`) deckt Bilder + gängige Dokumente ab; **leere Menge = alles erlauben**. Extensionslose Dateien (z. B. `LICENSE`) werden bei aktiver Whitelist abgelehnt — bei Bedarf Whitelist via `JUPITER_UPLOAD_ALLOWED_EXTENSIONS` leeren/erweitern.
- Echtes **Streaming** (kein Voll-RAM) via synchrone Handler + Chunk-Copy in temp-Datei; harter Abbruch bei Größenüberschreitung.

## Frontend-Implementierung (2026-06-23)
Next.js 16 + shadcn/ui, Branch `dev`. Beide Oberflächen über den geteilten Hook `useFileUpload`.

**Neue Dateien:**
- `components/cockpit/use-file-upload.ts` — geteilter Upload-Hook (Default-Ziel = Clipboard).
- `components/cockpit/session-clipboard-button.tsx` — Surface-B-Button („Anhängen").
- `components/cockpit/file-explorer.tsx` — Surface-A-Explorer (Roots, Navigation, Drop/Paste/Upload, Neuer Ordner, Download, Pfad kopieren, Umbenennen, Löschen, Clipboard-Pin).
- `app/(cockpit)/dateien/page.tsx` — Route „Dateien".
- `lib/clipboard.ts` — `copyText`-Helfer.

**Geändert:**
- `lib/types.ts` + `lib/api.ts` — File-Typen + API-Funktionen (`listFileRoots`, `listDir`, `uploadFiles` (multipart), `makeDir`, `renameFile`, `moveFile`, `deleteFiles`, `fileDownloadUrl`, `get/setClipboardDir`).
- `app/(cockpit)/sessions/[id]/page.tsx` — **Surface B**: „Anhängen"-Button + `onPaste`/`onDrop` an der Textarea → Upload in Clipboard-Ordner → absoluter Pfad ins Eingabefeld eingefügt.
- `components/cockpit/session-rail.tsx` — Sidebar-Link „Dateien".

**Verifikation:** ESLint sauber; `tsc` für alle PROJ-11-Dateien fehlerfrei (einziger Projekt-tsc-Fehler liegt in der fremden PROJ-7-Datei `lib/md-tree.test.ts`).

**Bewusste MVP-Abweichungen (für QA):**
- **Verschieben (move):** Backend-Endpoint vorhanden; im Explorer-UI noch **kein** Ziel-Picker (Umbenennen/Löschen/Upload sind drin). Nachgelagert.
- **Pfad-Einfügen** in die Session-Textarea hängt den Pfad **am Ende** an (nicht an Cursor-Position) — pragmatischer MVP.
- Umbenennen/Neuer-Ordner nutzen native `window.prompt`/`confirm` (kein eigener Dialog) — bewusst schlank.

## QA Test Results
**Getestet:** 2026-06-23 · **Branch:** dev · **Stack-Hinweis:** Jupiter ohne JWT/RLS → Security-Fokus = Pfad-Härtung, nicht Tenant-Isolation.

### Automatisierte Tests
- **Backend:** `tests/test_proj11_files.py` — **29 Tests grün** (21 Funktion + 7 Red-Team + 1 Permission-Fix).
- **Regression:** gesamte Backend-Suite **292 grün, 0 Regressionen**.
- **Frontend:** ESLint sauber · `next build` **erfolgreich** (Routen `/dateien` + `/sessions/[id]` kompiliert, TS-Check grün).
- **Hinweis:** Interaktive Browser-Flows (Drag-and-Drop/Paste-Gesten) sind statisch + per Build verifiziert; ein **manueller Browser-Smoke** vor Deploy wird empfohlen.

### Acceptance Criteria
| AC | Ergebnis | Beleg |
|---|---|---|
| Baum/Liste innerhalb Roots, Navigation | ✅ | `list_dir` + Explorer (Build) |
| Upload DnD + Dialog, mehrere Dateien | ✅ | Multiple-Upload, DropZone |
| Download einzelner Dateien | ✅ | `download` Roundtrip-Test (Ordner-Zip = optional, nicht gebaut) |
| mkdir / Umbenennen / Löschen (Bestätigung) | ✅ | Tests + Explorer (`confirm` beim Löschen) |
| **Verschieben (move)** | ⚠️ Teilweise | Backend ✅ getestet; **Explorer-UI fehlt** (Low-5) |
| Pfad serverseitig geprüft, außerhalb → Fehler | ✅ | Out-of-Roots/Traversal/Symlink-Tests |
| Große Dateien gestreamt + Größenlimit | ✅ | Streaming-Abbruch-Test |
| Clipboard-Paste (Strg/Cmd+V), Zeitstempelname | ✅ | `clip-…`/`blob.png`-Tests |
| Dedizierter Clipboard-Ordner, kurzer Pfad, auto-create | ✅ | Clipboard-Dir-Tests |
| Pastes default in Clipboard-Ordner | ✅ | Default-Target-Test |
| Clipboard-Pin + „Pfad kopieren" (Ordner & Datei) | ✅ | Explorer (`copyPath`, Pin) |
| **Surface B:** Button/Drop am Eingabefeld | ✅ | `SessionClipboardButton` + Textarea-Handler |
| **Surface B:** DnD + Paste → Upload → Pfad ins Eingabefeld | ✅ | `attachFiles` (Build) |
| Fortschritt/Erfolg, Text bei Fehler erhalten | ✅ | `uploading`-State; Append lässt getippten Text stehen |
| Loading/Error/Empty, deutsch | ✅ | Explorer-States |

### Edge Cases
✅ Traversal/Symlink-Ausbruch geblockt · zu große Datei · Typ nicht erlaubt · namenloser/blob-Paste · mehrere Dateien · Plaintext-Paste (fällt auf normales Einfügen zurück) · Clipboard-Ordner gelöscht (auto-create) · Kollision (auto-unique).
⚠️ **Kollision beim Explorer-Upload** wird **automatisch umbenannt** (`-1/-2`) statt „Überschreiben/Umbenennen/Abbrechen" abzufragen — sicher (kein Overwrite), aber Abweichung vom Edge-Case (Low-1).

### Befunde (alle Low — kein Critical/High)
- **Low-1:** Explorer-Upload-Kollision → Auto-Rename statt Nachfrage-Dialog (Abweichung; sicher).
- **Low-2:** ✅ **GEFIXT (2026-06-23):** OS-/Permission-Fehler bei upload/mkdir/rename/move werden jetzt sauber gemappt (`PermissionError`→403, sonstige `OSError`→400) statt 500. Regressionstest `test_upload_no_write_permission_returns_403`.
- **Low-3:** Löschbestätigung nennt keine Datei-Anzahl bei nicht-leerem Ordner.
- **Low-4:** Pfad-Einfügen in die Session-Textarea hängt **am Ende** an (nicht an Cursor-Position).
- **Low-5:** **Move** ohne Explorer-UI (Backend vorhanden).
- **Security-Note (Low, by trust model):** Explorer/Download exponieren **alle** Dateien unter `allowed_roots` (inkl. `.env`/Secrets/Quellcode). Akzeptabel im Single-User-/Tailscale-MVP; bei echtem Auth (#21) muss ein Owner-Scope/RLS davor. **Kein** MVP-Blocker.
- **Info:** Upload-Whitelist lehnt extensionslose Dateien ab (`LICENSE`); via `JUPITER_UPLOAD_ALLOWED_EXTENSIONS` leerbar.

### Produktionsreife: ✅ READY
Keine Critical/High-Bugs. Backend adversarial abgesichert, Build grün. Die 5 Low-Punkte sind sichere Abweichungen/Nice-to-haves und können als Follow-up adressiert werden. Empfehlung: kurzer manueller Browser-Smoke der beiden interaktiven Flows vor `/abc-deploy`.

## Deployment
_To be added by /abc-deploy_
