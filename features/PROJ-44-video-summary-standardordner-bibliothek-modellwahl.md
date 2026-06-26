# PROJ-44: Video Summary — Standard-Ordner, Bibliotheks-Kachel & Modellwahl

## Status: Architected
**Created:** 2026-06-26
**Last Updated:** 2026-06-26

## Dependencies
- Requires: PROJ-41 (Video Summary Micro-App) — dieses Feature erweitert/fixt die bestehende native Micro-App; ohne sie kein Bezugspunkt.
- Requires: PROJ-2 (Vault-Anbindung als Dienst) — der Bibliotheks-Scan liest den Hal-Vault über den bestehenden Vault-/Files-Dienst.
- Requires: PROJ-7 (MD-Reader) — „per Klick aufs MD-File zugreifen" öffnet die Notiz im Jupiter MD-Reader.
- Bezug: `hal-video-summary`-Skill — der Skill bleibt grundsätzlich unverändert; nur der **aufrufende Prompt** der Verarbeitungs-Session schreibt künftig einen festen Zielordner statt Auto-Kategorie vor.

## Problem / Motivation
Drei konkrete Lücken im Live-Betrieb der Video-Summary-App:
1. **Ergebnisse unauffindbar:** Heute wählt die Verarbeitungs-Session die Hal-Kategorie **selbst** (PROJ-41-Entscheidung 4C) → erzeugte Notizen liegen verstreut über `04 Resources/AI & Claude`, `…/Programming`, … Der Nutzer findet seine erste Video-Analyse nicht wieder.
2. **Keine Übersicht:** Es gibt keine Stelle, an der **alle bereits umgewandelten Videos** gelistet sind; die Queue-Liste verliert Einträge (entfernt/Neustart) und zeigt nichts, was außerhalb der App (per Skill direkt) erzeugt wurde.
3. **Modell nicht wählbar:** Das Umwandlungs-Modell ist fest auf `sonnet` verdrahtet (`video_summary_model` in `config.py`) und in den App-Einstellungen nicht sichtbar/änderbar.

## User Stories
- Als Nutzer möchte ich, dass **alle** Video-Zusammenfassungen in **einen festen Standard-Ordner** im Hal-Vault geschrieben werden, damit ich sie immer am selben Ort wiederfinde.
- Als Nutzer möchte ich auf der Video-Summary-Seite eine **Kachel „Bibliothek"** sehen, die **alle bereits umgewandelten Videos** (Notizen im Standard-Ordner) auflistet, auch solche, die nicht mehr in der Warteschlange stehen.
- Als Nutzer möchte ich in dieser Liste **per einfachem Klick die `.md`-Notiz** des Videos **im MD-Reader öffnen**, ohne im Vault suchen zu müssen.
- Als Nutzer möchte ich in den **App-Einstellungen** das **Modell** wählen, das die Umwandlung durchführt (z. B. Haiku/Sonnet/Opus), um Kosten/Qualität zu steuern.
- Als Nutzer möchte ich, dass das **Default-Modell Sonnet** bleibt, wenn ich nichts ändere.

## Acceptance Criteria

### Block A — Standard-Video-Ordner (fester Zielort)
- [ ] Alle neuen Umwandlungen schreiben die `.md`-Notiz **und** das `.pdf` in **einen festen Standard-Ordner** `04 Resources/Video Summaries/` im Hal-Vault (statt einer automatisch gewählten Kategorie).
- [ ] Der aufrufende Prompt der headless-Session weist die Session an, **genau diesen Ordner** zu verwenden und **keine** Kategorie automatisch zu wählen (4C wird für diesen festen Ordner ersetzt); der `hal-video-summary`-Skill selbst wird nicht umgeschrieben.
- [ ] Der Standard-Ordner wird **angelegt, falls er nicht existiert** (kein Fehler beim ersten Lauf).
- [ ] Bild-/Anhang-Dateien dürfen weiterhin nach Skill-Konvention unter `07 Attachments/<slug>/` liegen; nur `.md`/`.pdf` müssen im Standard-Ordner landen.
- [ ] Der Zielordner ist **konfigurierbar** abgelegt (Default `04 Resources/Video Summaries/`), nicht im Code verstreut.

### Block B — Kachel „Bibliothek" (alle umgewandelten Videos)
- [ ] Auf der Video-Summary-Seite erscheint eine **Kachel/Bereich „Bibliothek"** (deutscher Titel), getrennt von der Warteschlange.
- [ ] Die Liste speist sich aus einem **Vault-Scan des Standard-Ordners** (alle `.md`-Notizen darin), **nicht** nur aus der DB-Queue — so erscheinen auch außerhalb der App erzeugte sowie nach Queue-Bereinigung verbleibende Notizen.
- [ ] Pro Eintrag werden mindestens **Titel** (Dateiname ohne `.md`) und **Erstell-/Änderungsdatum** angezeigt; sinnvoll sortiert (neueste zuerst).
- [ ] Ein **einfacher Klick** auf einen Eintrag **öffnet die `.md`-Notiz im Jupiter MD-Reader (PROJ-7)**.
- [ ] Falls zur Notiz ein gleichnamiges `.pdf` existiert, wird optional ein **PDF-Verweis** angeboten (nice-to-have, kein Blocker).
- [ ] **Leerer Standard-Ordner** → expliziter EmptyState („Noch keine umgewandelten Videos").
- [ ] Lade-/Fehlerzustand des Scans ist explizit behandelt (deutsch).

### Block C — Modellwahl in den Einstellungen
- [ ] Der **Einstellungs-Dialog** der Video-Summary-App enthält ein **Modell-Auswahlfeld** (Dropdown).
- [ ] Auswählbar sind mindestens **Haiku · Sonnet · Opus** (kurze, verständliche Labels; deutsche UI).
- [ ] **Default-Modell = Sonnet** (unverändert), wenn der Nutzer nichts auswählt.
- [ ] Die Auswahl wird **persistiert** (überlebt Reload/Neustart, analog Cooldown/Zeitplan in PROJ-41).
- [ ] **Neu gestartete** Umwandlungen verwenden das gewählte Modell (`--model` der headless-Session); bereits laufende Sessions bleiben unverändert.
- [ ] Ungültiger/unbekannter Modellwert wird serverseitig abgewiesen (deutsche Fehlermeldung), Default greift.

### Querschnitt
- [ ] Alle neuen Texte/Labels/Fehlermeldungen **deutsch** (App-Eigenname „Video Summary" bleibt).
- [ ] Keine Regression an der bestehenden Warteschlange/Drossel/Zeitplan-Logik (PROJ-41).

## Edge Cases
- **Bestehende, vor diesem Feature verstreut gespeicherte Notizen** → erscheinen **nicht** automatisch im Standard-Ordner (sie liegen woanders). Kein Auto-Move im MVP; Hinweis genügt. (Optionaler späterer „Aufräum"-Lauf außerhalb des Scopes.)
- **Standard-Ordner existiert noch nicht** beim ersten Bibliotheks-Aufruf → leere Liste/EmptyState statt Fehler.
- **Datei im Standard-Ordner ist keine valide Notiz** (z. B. eine MOC-Datei `Video Summaries.md`, Nicht-`.md`-Dateien) → robust filtern, nicht crashen.
- **Gleicher Video-Titel zweimal umgewandelt** → der Skill/Dateiname-Kollision wird wie bisher behandelt; die Bibliothek zeigt beide Dateien an, sofern unterschiedlich benannt.
- **Klick auf Notiz, die zwischenzeitlich gelöscht wurde** → MD-Reader zeigt seinen normalen Datei-nicht-gefunden-Zustand; kein App-Crash.
- **Modellwert in der Persistenz, der vom Engine-/CLI-Backend nicht (mehr) unterstützt wird** → serverseitige Validierung gegen erlaubte Werte; Fallback auf Sonnet + Hinweis.
- **Sehr viele Notizen im Standard-Ordner** → Scan bleibt performant (nur Verzeichnis-Listing + Metadaten, kein Volltext-Parse pro Datei).

## Technical Requirements (optional)
- **Standard-Ordner:** neuer Config-Wert (z. B. `video_summary_output_subdir` Default `04 Resources/Video Summaries`); der Prompt-Builder (`backend/app/engine/video_summary.py`, heute Zeile ~91 „Waehle die best passende Zielkategorie selbst") schreibt stattdessen den festen Ordner vor und fordert das Anlegen, falls fehlend.
- **Bibliotheks-Scan:** neue Read-only-Route (z. B. `GET /video-summary/library`), liest das Verzeichnis über den bestehenden Vault-/Files-Dienst; gibt `[{title, md_path, pdf_path?, created_at|mtime}]` zurück. Pfade müssen innerhalb `allowed_roots` liegen (wie PROJ-41-Security-Audit).
- **MD-Reader-Öffnen:** Klick verlinkt auf den bestehenden MD-Reader (PROJ-7) mit dem absoluten/vault-relativen Pfad — Mechanik wie bei anderen Vault-Notiz-Links in der App.
- **Modellwahl:** `video_summary_model` von fixem Config-Default zu **persistiertem Setting** (gleiche Settings-Ablage wie cooldown/schedule, PROJ-41 `video_summary_settings`); Schema-Erweiterung in `schemas/video_summary.py` + `PATCH /video-summary/settings`; serverseitige Whitelist der erlaubten Modell-Slugs.
- **Frontend:** Erweiterung der bestehenden Komponente `nextjs_app/components/microapps/video_summary/video-summary-app.tsx` (neue Bibliotheks-Sektion + Modell-Dropdown im Einstellungs-Dialog) + Client-Funktionen in `nextjs_app/lib/api.ts` + Typen in `nextjs_app/lib/types.ts`.
- **Tests:** Prompt schreibt festen Ordner (Helper-Test), Library-Route filtert/sortiert korrekt, Settings persistieren Modell + Whitelist-Validierung; keine Regression der PROJ-41-Suite.
- **Kein Auth/RLS** im MVP (Projekt-Entscheidung); `owner` wie gehabt nur gestempelt.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-26 · **Stack:** Next.js 16 (native Micro-App, Erweiterung PROJ-41) + FastAPI/asyncio-Worker + SQLite-Settings · **Branch:** dev

### Überblick / Grundhaltung
PROJ-44 ist ein **gezielter Fix-/Ausbau** der bestehenden, deployten Video-Summary-Micro-App (PROJ-41) — keine neue App, keine neue Infrastruktur. Alle drei Blöcke nutzen vorhandene Bausteine: den **Prompt-Builder** + **Settings-Tabelle** im Backend, die **`/files/list`**-Route für den Vault-Scan und den **MD-Reader-Deeplink** (`/doku?…`) im Frontend. Kein neues Paket, keine neue DB-Tabelle, kein Auth/RLS (Projekt-Entscheidung).

Codegestützte Verifikation (CodeGraph + direkter Code-Read): `build_prompt` und der `model`-Parameter sitzen in `engine/video_summary.py`; die Settings liegen in einer 1-Zeilen-SQLite-Tabelle; `/files/list` existiert und ist auf `allowed_roots` gehärtet; der MD-Reader lädt **jede** Datei über `readMdFile(<absoluter Pfad>)` (Backend erzwingt `allowed_roots ⊇ /home/dev/tools/Hal`) — unabhängig vom Sidebar-Baum.

### A) Komponenten-Struktur (UI-Baum)
```
/apps/video_summary  (bestehende native App, erweitert)
└── VideoSummaryApp
    ├── EingabeKarte            (unverändert)
    ├── SteuerLeiste            (unverändert) + Einstellungs-Dialog → NEU: Modell-Dropdown
    │     └── EinstellungsDialog
    │           ├── Zeitplan (HH:MM)        (vorhanden)
    │           ├── Cooldown-Minuten        (vorhanden)
    │           └── Modell  ▼ Haiku · Sonnet · Opus   ← NEU (Block C), Default Sonnet
    ├── WarteschlangenListe     (unverändert; Ergebnis-Link → künftig MD-Reader statt Download)
    └── BibliotheksKarte        ← NEU (Block B)
          ├── Liste „Bereits umgewandelte Videos" (Titel · Datum, neueste zuerst)
          │     └── Zeile: Klick → MD-Reader (/doku?source=vault&path=<abs .md>)
          │                 optional: kleiner „PDF"-Verweis, falls gleichnamiges .pdf existiert
          ├── EmptyState („Noch keine umgewandelten Videos")
          └── Lade-/Fehlerzustand (deutsch)
```

### B) Datenmodell (Klartext)
**Keine neue Tabelle.** Zwei Anpassungen am Bestehenden:

1. **Settings (Block C):** die bestehende 1-Zeilen-Tabelle `video_summary_settings` (heute `cooldown_minutes`, `batch_size`, `schedule`) erhält **ein zusätzliches Feld `model`** (Default `sonnet`). Idempotente `ALTER TABLE`-Migration nach dem Vorbild `session_index.py`; Zugriff via `get_settings`/`save_settings` (Spalten-Whitelist).
2. **Bibliothek (Block B):** **kein** persistenter Zustand — die Liste ist ein **Live-Scan** des Standard-Ordners im Dateisystem (Vault ist die Wahrheit, PRD-Prinzip). Quelle = Verzeichnis-Listing, nicht die DB-Queue.

**Standard-Ordner (Block A):** ein **Config-Wert** (z. B. `video_summary_output_subdir`, Default `04 Resources/Video Summaries`), relativ zum Vault-Root (`/home/dev/tools/Hal`). Kein DB-Eintrag.

### C) Verhalten je Block (Klartext, kein Code)

**Block A — fester Zielordner.** Im **Prompt-Builder** (`build_prompt`, heute „Waehle die best passende Zielkategorie … selbst") wird die Auto-Kategorie-Anweisung **ersetzt** durch eine feste Vorgabe: „Speichere Notiz **und** PDF **ausschließlich** unter `04 Resources/Video Summaries/`; lege den Ordner an, falls er fehlt; wähle **keine** Kategorie selbst." Der maschinenlesbare `JUPITER_VIDEO_RESULT`-Abschlussblock (note/pdf-Pfad) bleibt unverändert — der Worker liest die Ergebnis-Pfade weiter daraus. **Der `hal-video-summary`-Skill wird nicht umgeschrieben**; nur der steuernde Prompt ändert sich. Anhänge dürfen weiter unter `07 Attachments/<slug>/` liegen (Skill-Konvention, AC erfüllt).

**Block B — Bibliotheks-Kachel.** Neue **Read-only-Route** liefert den Inhalt des Standard-Ordners (`.md`-Dateien) als Liste `{title, md_path (absolut), pdf_path?, mtime}`. Implementierung lehnt sich an die bestehende `/files/list`-Mechanik an (gleicher `allowed_roots`-Guard); MOC-/Nicht-`.md`-Dateien werden gefiltert. Frontend rendert die Liste (neueste zuerst); **Klick** baut `/doku?source=vault&path=<absoluter md_path>` und öffnet die Notiz im MD-Reader (PROJ-7) — **keine** Änderung an der `/doku`-Seite nötig (sie lädt jeden absoluten Pfad innerhalb `allowed_roots`). Existiert ein gleichnamiges `.pdf`, wird ein optionaler PDF-Verweis via vorhandenem `fileDownloadUrl` angeboten. Leerer/fehlender Ordner → EmptyState statt Fehler.

**Block C — Modellwahl.** Der Worker liest das Modell künftig aus den **persistierten Settings** statt aus `settings.video_summary_model` (Config dient nur noch als Default beim ersten Start). Der `_start`-Aufruf übergibt das gewählte Modell als `model=` an `manager.create`. Der Einstellungs-Dialog bekommt ein Dropdown (Haiku/Sonnet/Opus); `PATCH /video-summary/settings` validiert gegen eine **Whitelist erlaubter Modell-Slugs** (ungültig → 400, deutsche Meldung). Laufende Sessions bleiben unberührt; nur neu gestartete nutzen die neue Wahl.

### D) API-Shape (Deltas zu PROJ-41, kein Code)
```
GET  /video-summary/library            → NEU: [{title, md_path, pdf_path?, mtime}] aus dem Standard-Ordner (Read-only, allowed_roots-gehärtet)
GET  /video-summary/settings           → erweitert: zusätzlich {model}
PATCH /video-summary/settings          → erweitert: akzeptiert {model?}; Whitelist-Validierung (400 bei ungültig)
```
Alle übrigen PROJ-41-Routen (queue, run-now, retry, delete) **unverändert**.

### E) Tech-Entscheidungen (WARUM)
- **Fester Ordner per Prompt statt Skill-Umbau:** der Skill bleibt wiederverwendbar/unverändert (gleiche Linie wie PROJ-41 4C); wir steuern nur das Verhalten über den Initial-Prompt. Kleinster Eingriff, kein Risiko für andere Skill-Nutzer.
- **Bibliothek als Live-Vault-Scan statt DB-Spiegel:** der Vault ist laut PRD die persistente Wahrheit; ein Scan zeigt **alle** Notizen (auch außerhalb der App erzeugte, auch nach Queue-Bereinigung) und kann nicht mit der Queue auseinanderlaufen. Nur Verzeichnis-Listing + Metadaten → performant, kein Volltext-Parse.
- **MD-Reader via `?path=`-Deeplink:** wiederverwendet die vorhandene, deep-linkbare `/doku`-Seite ohne jede Änderung; der Reader lädt jeden Pfad in `allowed_roots`. Die Bibliothek (nicht der Reader-Baum) ist die Navigations-Oberfläche.
- **Modell in den Settings statt fix in Config:** Persistenz wie cooldown/schedule (überlebt Neustart, AC); Config-Default `sonnet` bleibt als Fallback. Server-Whitelist verhindert ungültige `--model`-Slugs (PROJ-18-Slug-Falle vermeiden).
- **Keine neue Tabelle/kein neues Paket:** ein Settings-Feld + eine Read-only-Route + Frontend-Erweiterung — konsistent mit dem bestehenden Muster, minimaler Footprint.

### F) Abhängigkeiten (Pakete)
- **Keine neuen Pakete.** SQLite/asyncio (stdlib), `SessionManager`/`build_prompt` (vorhanden), `/files`-Service + `allowed_roots`-Guard (vorhanden), shadcn/ui Dialog/Select (vorhanden), `fileDownloadUrl` + MD-Reader-Deeplink (vorhanden).

### G) Bau-Reihenfolge / Hand-offs
1. **Backend** (`/abc-backend`): (A) Config `video_summary_output_subdir` + Prompt-Builder auf festen Ordner; (C) `model`-Feld in Tabelle/Schemas/Settings + Worker liest Modell aus Settings + Whitelist-Validierung in `PATCH /settings`; (B) Read-only-Route `GET /video-summary/library` (Vault-Scan, `allowed_roots`). Tests: Prompt schreibt festen Ordner, Library filtert/sortiert, Settings persistieren Modell + Whitelist; keine Regression der PROJ-41-Suite.
2. **Frontend** (`/abc-frontend`): Modell-Dropdown im Einstellungs-Dialog; Bibliotheks-Kachel (Liste, Klick → `/doku?source=vault&path=…`, optional PDF-Verweis, EmptyState, Lade-/Fehlerzustand); Ergebnis-Links der Queue künftig in den MD-Reader statt Download; Client-Funktion `getVideoSummaryLibrary` + Typen + `model` in den Settings-Typen.
3. **QA** (`/abc-qa`): ACs je Block + kein-Regression an Queue/Drossel/Zeitplan.
> Backend zuerst (Prompt/Settings/Route sind Fundament), dann Frontend gegen die fertige API.

### H) Referenz-Dateien (Ist-Stand, verifiziert)
- Prompt + Modell/Pfad: `backend/app/engine/video_summary.py` (`build_prompt` ~Z.82; `_start`/`manager.create` mit `model=`/`project_path=` ~Z.296)
- Settings-Persistenz: `backend/app/db/video_summary_queue.py` (`video_summary_settings`, `get/save_settings`, Whitelist); Schemas `backend/app/schemas/video_summary.py` (Settings Read/Patch); Routen `backend/app/routes/video_summary.py` (GET/PATCH /settings)
- Config: `backend/app/config.py` (`video_summary_model="sonnet"`, `video_summary_project_path="/home/dev/tools/Hal"`)
- Vault-Listing: `backend/app/routes/files.py` (`GET /list`, `allowed_roots`/`validate_project_path`-Guard)
- MD-Reader-Deeplink: `nextjs_app/app/(cockpit)/doku/page.tsx` (`?source=&path=` / `?source=vault&rel=`; lädt absolute Pfade via `readMdFile`)
- Frontend-App + Client: `nextjs_app/components/microapps/video_summary/video-summary-app.tsx`, `nextjs_app/lib/api.ts`, `nextjs_app/lib/types.ts`

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
