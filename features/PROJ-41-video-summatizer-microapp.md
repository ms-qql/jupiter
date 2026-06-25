# PROJ-41: Video Summary (native Micro-App)

## Status: Planned
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-40 (Sidebar-Sektion „Micro-Apps" + `kind: native`) — Video Summary ist die **erste echte native Micro-App** (`group: micro`, `kind: native`, Route `/apps/[key]`, Eintrag in `microapps-registry.ts`).
- Requires: PROJ-1 (Engine-Treiber: Claude-Max-Session headless) — jede Video-Umwandlung läuft als **headless Claude-Code-Session**, die den `hal-video-summary`-Skill ausführt.
- Requires: PROJ-2 (Vault-Anbindung) — die erzeugten Notizen/PDFs landen im Hal-Vault unter `04 Resources/<Kategorie>/`.
- Bezug: PROJ-14/PROJ-16 (Session-Limits/Watchdog) — die Verarbeitungs-Sessions unterliegen denselben Limits wie reguläre Sessions.

## Beschreibung
Eine native Micro-App **„Video Summary"** in der Sidebar-Sektion „Micro-Apps". Der Nutzer hinterlegt eine oder mehrere **Video-URLs**; die App reiht sie in eine **Warteschlange** und lässt sie — sofort („Jetzt ausführen") oder per **wiederkehrendem Zeitplan** — vom bestehenden **`hal-video-summary`-Skill** in je eine **Markdown-Notiz + integriertes PDF** umwandeln und im **Hal Second Brain** speichern.

**Am `hal-video-summary`-Skill wird nichts geändert** — die App ist eine GUI + Orchestrierungs-Schicht drum herum. Pro Video startet das Backend eine **headless Claude-Code-Session** (PROJ-1-Mechanik), die den Skill mit der Video-URL ausführt.

**Drossel gegen YouTube-Blocking:** Es werden **nie mehr als 4 Videos direkt hintereinander** verarbeitet; danach legt die Queue eine **Cooldown-Pause** ein (Default 30 min, konfigurierbar) und arbeitet anschließend automatisch weiter, bis sie leer ist.

### Geklärte Entscheidungen (2026-06-25)
- **Rate-Limit (2A):** Nach je **4 Videos** eine **konfigurierbare Cooldown-Pause** (Default **30 min**); Queue läuft danach automatisch weiter, bis leer.
- **Zeitplan (3A):** **Ein** wiederkehrender Zeitplan (z. B. „täglich 02:00") arbeitet die gesamte Queue ab — **plus** Button **„Jetzt ausführen"**.
- **Hal-Kategorie (4C):** Die Verarbeitungs-**Session bestimmt die Zielkategorie automatisch** (bestfittende `04 Resources/`-Kategorie). Da headless **kein** interaktives `AskUserQuestion` möglich ist, wählt die Session selbst — **kein** Kategorie-Dialog.
- **Eingabe (5A):** **Nur Video-URLs** (eine oder mehrere; ein Link pro Zeile). **Kein** lokaler Datei-Upload im MVP.
- **Status (6A):** Pro Video sichtbarer **Status** (Wartend · Läuft · Fertig · Fehler) **plus Link** zur erzeugten Notiz/PDF im Vault.

## User Stories
- Als Nutzer möchte ich in der Micro-App **eine oder mehrere Video-URLs** (ein Link pro Zeile) ablegen, um sie zur Zusammenfassung einzureihen.
- Als Nutzer möchte ich die eingereihten Videos **sofort verarbeiten** („Jetzt ausführen"), um nicht auf den Zeitplan warten zu müssen.
- Als Nutzer möchte ich einen **wiederkehrenden Zeitplan** festlegen (z. B. täglich 02:00), damit die Warteschlange automatisch abgearbeitet wird.
- Als Nutzer möchte ich, dass **nie mehr als 4 Videos hintereinander** verarbeitet werden und danach eine **Pause** eingelegt wird, damit YouTube die Abrufe nicht blockt.
- Als Nutzer möchte ich pro Video den **Status** (Wartend · Läuft · Fertig · Fehler) sehen und bei „Fertig" die **erzeugte Notiz/PDF** im Vault öffnen können.
- Als Nutzer möchte ich die **Cooldown-Länge** (Default 30 min) und den **Zeitplan** in den App-Einstellungen anpassen können.
- Als Nutzer möchte ich einzelne Einträge aus der Warteschlange **entfernen** oder einen **fehlgeschlagenen** Eintrag **erneut versuchen** können.

## Acceptance Criteria
- [ ] **Video Summary** erscheint als Eintrag in der Sidebar-Sektion „Micro-Apps" (`group: micro`, `kind: native`) mit Label + Icon und öffnet als Vollbild unter `/apps/<key>`.
- [ ] Die App ist als **native** Micro-App umgesetzt (React-Komponente im Repo, registriert in `microapps-registry.ts`) — **kein** iFrame.
- [ ] Ein **Eingabefeld** akzeptiert **eine oder mehrere Video-URLs** (ein Link pro Zeile); „Hinzufügen" reiht sie in die Warteschlange ein.
- [ ] **URL-Validierung:** offensichtlich ungültige Zeilen werden abgewiesen mit deutscher Fehlermeldung; gültige werden übernommen.
- [ ] Eine **Warteschlangen-Liste** zeigt alle Einträge mit Status **Wartend · Läuft · Fertig · Fehler**.
- [ ] Button **„Jetzt ausführen"** startet die Abarbeitung der Warteschlange sofort.
- [ ] Ein **Zeitplan** (wiederkehrend, z. B. Cron-artig) ist in der App einstellbar; zur geplanten Zeit wird die Warteschlange automatisch abgearbeitet.
- [ ] Es werden **nie mehr als 4 Videos direkt hintereinander** verarbeitet; danach folgt eine **Cooldown-Pause** (Default 30 min), dann läuft die Queue automatisch weiter, bis sie leer ist.
- [ ] Die **Cooldown-Dauer** ist in den App-Einstellungen konfigurierbar (Default 30 min).
- [ ] Jede Verarbeitung ruft den **`hal-video-summary`-Skill** über eine **headless Claude-Code-Session** auf — **ohne Änderung am Skill**.
- [ ] Die Verarbeitungs-Session **bestimmt die Hal-Kategorie automatisch** (kein interaktiver Kategorie-Dialog); Notiz **und** PDF landen unter `04 Resources/<Kategorie>/` im Vault.
- [ ] Bei Status **„Fertig"** zeigt der Eintrag einen **Link/Verweis** auf die erzeugte Notiz (und/oder PDF) im Vault.
- [ ] Bei Status **„Fehler"** wird eine knappe Fehlerursache angezeigt und ein **„Erneut versuchen"** angeboten.
- [ ] Einzelne Warteschlangen-Einträge lassen sich **entfernen**.
- [ ] Die Warteschlange + Einstellungen **überleben einen Reload/Neustart** (persistiert, nicht nur im Browser-State).
- [ ] Alle Texte/Labels/Fehlermeldungen **deutsch** (App-Eigenname „Video Summary" bleibt).

## Edge Cases
- **Mehr als 4 Videos in der Queue** → erste 4 verarbeiten, dann Cooldown-Pause, dann nächste 4 usw., bis leer. Während der Pause zeigt die UI den Pausen-Zustand + verbleibende Zeit (oder „pausiert bis HH:MM").
- **„Jetzt ausführen" während bereits eine Verarbeitung läuft** → kein Doppelstart; entweder no-op mit Hinweis oder reiht nur neue Einträge an die laufende Queue an.
- **Cron-Lauf während die Queue noch vom letzten Lauf arbeitet** → keine Überlappung/Doppelverarbeitung desselben Eintrags.
- **Ungültige / nicht erreichbare URL** → Eintrag geht auf „Fehler" mit Ursache; blockiert die übrigen Einträge nicht.
- **Skill/Session schlägt fehl** (yt-dlp-Fehler, Video privat/gelöscht, Whisper-/PDF-Fehler) → „Fehler" + „Erneut versuchen"; Queue läuft mit den restlichen Einträgen weiter.
- **Duplikat-URL** (schon in der Queue oder schon verarbeitet) → Hinweis; kein stiller Doppel-Eintrag.
- **App geschlossen / Tab gewechselt während Verarbeitung** → Verarbeitung läuft **serverseitig** weiter (headless Session); Status wird beim Wiederöffnen korrekt angezeigt.
- **Neustart des Backends mitten in der Queue** → laufender/wartender Zustand wird aus der Persistenz wiederhergestellt (kein Verlust der Warteschlange).
- **Sehr langes Video / sparse Frame-Scan** → der Skill behandelt das selbst; die App zeigt nur Erfolg/Fehler, mischt sich nicht in die Skill-Logik ein.
- **Sektion „Micro-Apps" im Konfig-Panel ausgeblendet** → App per Direkt-URL `/apps/<key>` weiter erreichbar (kein verwaister Zustand, wie PROJ-40).

## Technical Requirements (optional)
- **Native Micro-App-Muster (PROJ-40):** Metadaten-Eintrag in `backend/config/engines.yaml` (`kind: native`, `group: micro`, Label, Icon); Code unter `nextjs_app/components/microapps/<key>/`, registriert in `nextjs_app/lib/microapps-registry.ts`; Render über die kind-Verzweigung in `app/(cockpit)/apps/[key]/page.tsx`.
- **Persistenz:** Warteschlange (URL, Status, Ergebnis-Pfad, Zeitstempel, owner) + App-Einstellungen (Cooldown-Minuten, Zeitplan) in **Postgres** als Live-Index (raw SQL via `run_query_m`/`run_command_m`, Pydantic v2). `owner`-Feld (single-user-MVP).
- **Verarbeitungs-Mechanik:** Backend-Worker/Queue startet pro Video eine **headless Claude-Code-Session** (PROJ-1) mit dem `hal-video-summary`-Skill und der URL; **kein** API-Key, Subscription-Auth. Drossel (max. 4 in Folge, dann Cooldown) im Worker durchgesetzt — **nicht** clientseitig.
- **Zeitplan:** ein wiederkehrender Trigger (Backend-Scheduler/Cron-artig), der „Jetzt ausführen" auf die Queue anwendet. Genaues Scheduling-Backend (DB-getriebener Poller vs. System-Cron) entscheidet `/abc-architecture`.
- **Skill unverändert:** Aufruf des `hal-video-summary`-Skills exakt wie heute; die **automatische Kategorie-Wahl** muss ohne interaktives `AskUserQuestion` funktionieren (Session entscheidet selbst).
- **API:** neue FastAPI-Routen für Queue-CRUD + Trigger + Einstellungen (`backend/app/routes/`), Schemas in `backend/app/schemas/`.
- **Frontend:** React-Komponente (Tailwind + shadcn/ui), Zustände Loading/Error/Empty/Success explizit; Polling/Refresh des Queue-Status.
- **Texte deutsch.** Kein Auth/RLS im MVP (Projekt-Entscheidung), `owner`-Feld vorbereitet.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (native Micro-App) + FastAPI/asyncio-Worker + **SQLite** (kein Postgres/RLS im MVP) · **Branch:** dev

### Überblick / Grundhaltung
Video Summary ist eine **native Micro-App** (PROJ-40-Muster): React-Komponente im Repo, Metadaten in `engines.yaml` (`kind: native`, `group: micro`), gerendert über `/apps/video_summary`. Drei neue Backend-Bausteine: **(1)** eine **SQLite-Warteschlangen-Tabelle** + Repo (Vorbild `db/session_index.py`), **(2)** ein **asyncio-Worker im Lifespan** (Vorbild `_liveness_loop()` in `main.py`), der die Queue **sequenziell** abarbeitet und Drossel/Cooldown/Zeitplan durchsetzt, **(3)** CRUD-/Trigger-/Settings-Routen. Jede Umwandlung ist eine **headless Claude-Session** (`SessionManager.create(initial_prompt="/hal-video-summary <URL>")`) — der Skill bleibt unverändert.

**Grundsatz: alle Drossel-/Zeitplan-Logik liegt im Backend-Worker, nie im Client.** Tab zu = Verarbeitung läuft serverseitig weiter; UI ist nur Ansicht + Steuerung.

### A) Komponenten-Struktur (UI-Baum)
```
/apps/video_summary  (native, Vollbild)
└── VideoSummaryApp
    ├── EingabeKarte
    │   ├── Textarea „Video-URLs (ein Link pro Zeile)"
    │   └── Button „Zur Warteschlange hinzufügen"  + Inline-Validierungsfehler (deutsch)
    ├── SteuerLeiste
    │   ├── Button „Jetzt ausführen"         (startet Drain sofort)
    │   ├── Status-Badge: Leerlauf · Läuft · Pausiert bis HH:MM
    │   └── Button „Einstellungen"  → Dialog (Zeitplan, Cooldown-Minuten)
    ├── WarteschlangenListe
    │   └── VideoZeile  (URL · Status-Badge Wartend/Läuft/Fertig/Fehler ·
    │        bei Fertig: Link „Notiz öffnen" / „PDF" · bei Fehler: Ursache + „Erneut versuchen" ·
    │        Button „Entfernen")
    ├── EmptyState („Noch keine Videos in der Warteschlange")
    └── Lade-/Fehlerzustand (Polling des Queue-Status)
```
- Registry: `engines.yaml`-Eintrag + `microapps-registry.ts` (`video_summary → lazy(import …)`) + Komponente unter `components/microapps/video_summary/`.
- Die Liste **pollt** den Backend-Status (z. B. alle paar Sekunden), da die Verarbeitung serverseitig/asynchron läuft.

### B) Datenmodell (Klartext — SQLite, kein Postgres/RLS)
**Tabelle `video_summary_queue`** (eine Zeile pro eingereichtem Video):
- `id` (eindeutig), `url` (Video-Link), `owner` (single-user-MVP, immer „du" — für spätere Team-Migration)
- `status`: `pending` · `running` · `done` · `error`
- `result_note_path` / `result_pdf_path` (gefüllt bei `done`; Vault-Pfade für den Link)
- `error_message` (bei `error`, knappe Ursache)
- `created_at`, `started_at`, `finished_at`, `session_id` (verknüpfte Headless-Session)

**Worker-Konfiguration/-Zustand** (kleine Settings-Ablage, Vorbild `engine/policy.py`/`settings.py` — YAML/Config, **nicht** pro Video):
- `cooldown_minutes` (Default **30**), `batch_size` (**4**, fix per Anforderung, aber konfigurierbar abgelegt)
- `schedule` (ein wiederkehrender Zeitplan, z. B. Cron-Ausdruck oder „täglich HH:MM"; leer = nur manuell)
- Laufzeit-Zustand (im Speicher/abgeleitet): `consecutive_count`, `paused_until`, `next_scheduled_run`

Persistenz wie `session_index.py`: `CREATE TABLE IF NOT EXISTS` + idempotente `ALTER TABLE`-Migrationen, Zugriff via `asyncio.to_thread`. **Queue + Einstellungen überleben Neustart** (Akzeptanzkriterium); Laufzeit-Zustand wird beim Start aus der Tabelle rekonstruiert (`running` ohne lebende Session → zurück auf `pending`).

### C) Worker-Logik (Klartext, kein Code)
Ein asyncio-Task tickt alle paar Sekunden (Vorbild Liveness-Loop) und macht **sequenziell** (immer nur **eine** Session gleichzeitig):
1. **Läuft gerade eine Session?** → ihren Status prüfen. Fertig → Eintrag auf `done`, Notiz-/PDF-Pfad aus dem Abschlussbericht der Session übernehmen; `consecutive_count++`. Fehlgeschlagen → `error` + Ursache. Danach: wenn `consecutive_count` ein Vielfaches von `batch_size` (4) ist → `paused_until = jetzt + cooldown_minutes`.
2. **Keine Session aktiv, Drain gewünscht, `jetzt ≥ paused_until`, es gibt `pending`** → nächsten Eintrag starten (`SessionManager.create` mit Prompt `/hal-video-summary <URL>` + Anweisung „Kategorie automatisch wählen, keine Rückfragen").
3. **Drain-Auslöser:** „Jetzt ausführen" (manuell) **oder** der Zeitplan ist fällig. Drain endet, wenn keine `pending`-Einträge mehr da sind (Zustand → Leerlauf).
- **Sequenziell + Cooldown** setzt „nie mehr als 4 hintereinander" hart durch und ist am schonendsten für YouTube.
- **Ergebnis-Link (6A):** Der `hal-video-summary`-Skill nennt am Ende Notiz- und PDF-Pfad; der Worker liest diesen Abschlussbericht aus dem Session-Event-Stream und speichert die Pfade am Eintrag. Schlägt das Parsen fehl → Eintrag bleibt `done`, Link „best effort".

### D) API-Shape (neue Routen, kein Code)
Neuer Router `backend/app/routes/video_summary.py` (+ Schemas in `schemas/video_summary.py`):
```
GET    /video-summary/queue            → Warteschlange + Status (für Polling)
POST   /video-summary/queue            → eine/mehrere URLs einreihen (Body: Liste URLs)
DELETE /video-summary/queue/{id}       → Eintrag entfernen
POST   /video-summary/queue/{id}/retry → fehlgeschlagenen Eintrag erneut einreihen
POST   /video-summary/run-now          → Drain sofort starten
GET    /video-summary/settings         → Zeitplan + Cooldown lesen
PATCH  /video-summary/settings         → Zeitplan + Cooldown ändern
```
Kein Auth/RLS (MVP-Entscheidung); `owner` wird gesetzt, aber nicht gefiltert. URL-Validierung serverseitig (gültiges http(s)-Schema) zusätzlich zur Client-Vorprüfung.

### E) Tech-Entscheidungen (WARUM)
- **SQLite + asyncio-Worker statt Postgres/Celery:** Jupiter ist heute SQLite + In-Memory + Lifespan-Tasks (kein Postgres-`run_query_m`, kein Message-Broker). Wir spiegeln das bestehende Muster (`session_index.py` + `_liveness_loop`) statt neue Infrastruktur einzuführen — kleinster, konsistentester Eingriff.
- **Sequenzielle Verarbeitung, eine Session zur Zeit:** erfüllt „max. 4 in Folge" zwangsläufig, vermeidet parallele Session-Last (PROJ-14/16-Limits) und ist am robustesten gegen YouTube-Drosselung.
- **Drossel im Worker, nicht im Client:** Schließen des Tabs darf die Drossel nicht aushebeln; nur der Server kennt `consecutive_count`/`paused_until`.
- **Skill unverändert, Prompt steuert Nicht-Interaktivität:** headless kann kein `AskUserQuestion` → der Prompt weist die Session an, die Hal-Kategorie selbst zu wählen (4C). Keine Skill-Änderung nötig.
- **Ergebnis-Pfade aus dem Abschlussbericht der Session:** der Skill gibt Notiz-/PDF-Pfad am Ende aus; der Worker hört ohnehin den Event-Stream mit → kein zusätzlicher Mechanismus.
- **Kein MinIO:** Artefakte liegen im Hal-Vault (Dateisystem), nicht in Object Storage.

### F) Abhängigkeiten (Pakete)
- **Keine neuen Pakete.** SQLite (stdlib), asyncio (stdlib), `SessionManager`/`claude_driver` (vorhanden), `lucide-react`-Icon (z. B. `play`/`film`), shadcn/ui-Komponenten (vorhanden). Der `hal-video-summary`-Skill (+ `watch`/`pdf`) ist Host-seitig bereits eingerichtet (Engines-Setup).

### G) Bau-Reihenfolge / Hand-offs
1. **Backend** (`/abc-backend`): SQLite-Tabelle + Repo, Worker-Task im Lifespan, Routen + Schemas, Settings-Ablage, headless-Session-Aufruf mit auto-Kategorie-Prompt.
2. **Frontend** (`/abc-frontend`): `engines.yaml`-Eintrag (`video_summary`, native/micro/icon) + `microapps-registry.ts` + Komponente unter `components/microapps/video_summary/` (Eingabe, Liste mit Polling, Steuerleiste, Einstellungs-Dialog).
3. **QA** (`/abc-qa`): ACs + Drossel-Verhalten (5 Videos → Pause nach 4), Persistenz über Neustart, Fehler-/Retry-Pfad, Direkt-URL bei ausgeblendeter Sektion.
> Reihenfolge hier **Backend zuerst** (Worker+API sind das Risiko/Fundament), dann Frontend gegen die fertige API.

### H) Referenz-Dateien (Ist-Stand, CodeGraph-verifiziert)
- Headless-Session: `backend/app/engine/manager.py` (`SessionManager.create`), `backend/app/engine/claude_driver.py` (headless argv)
- Persistenz-Vorbild: `backend/app/db/session_index.py` (`CREATE TABLE IF NOT EXISTS` + Migrationen)
- Worker-Vorbild: `backend/app/main.py` (`_liveness_loop`, Lifespan-Task)
- Settings-Vorbild: `backend/app/routes/settings.py`, `backend/app/engine/policy.py`
- Native Micro-App: `nextjs_app/lib/microapps-registry.ts`, `nextjs_app/app/(cockpit)/apps/[key]/page.tsx` (native-Zweig, `MicroAppComponentProps`)
- Registry: `backend/config/engines.yaml` (neuer Eintrag `video_summary`)

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
