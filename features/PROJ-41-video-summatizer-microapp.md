# PROJ-41: Video Summary (native Micro-App)

## Status: Deployed
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
- [ ] Ein **Eingabefeld (Textarea)** akzeptiert **eine oder mehrere Video-URLs per Copy-and-Paste**; ein eingefügter Block wird beim „Hinzufügen" in einzelne Einträge zerlegt (Trenner: Zeilenumbruch, Leerzeichen, Komma, Semikolon), getrimmt und dedupliziert.
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
    │   ├── Textarea „Video-URLs (per Copy-and-Paste, ein Link pro Zeile)"
    │   │     → native Paste-Unterstützung; ein eingefügter Block wird beim
    │   │       Hinzufügen in mehrere Einträge zerlegt (Trenner: Zeilenumbruch,
    │   │       Leerzeichen, Komma, Semikolon), getrimmt + dedupliziert
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

## Implementation Notes (Backend — /abc-backend, 2026-06-25)

**Branch:** `dev` (laut Tech-Design). Backend vollständig; Frontend (native Komponente + `engines.yaml`/Registry-Eintrag) ist der nächste Hand-off.

### Neue/geänderte Dateien
- `backend/app/db/video_summary_queue.py` — SQLite-Repo (Vorbild `session_index.py`): Tabellen `video_summary_queue` (eine Zeile/Video) + `video_summary_settings` (1-Zeile: cooldown/batch/schedule). `init`/`list_queue`/`add`/`get`/`update`(Whitelist)/`delete`/`reset_running`/`get_settings`/`save_settings`. Off-thread via `asyncio.to_thread`, WAL.
- `backend/app/engine/video_summary.py` — `VideoSummaryWorker` (sequenziell, **eine** Session zur Zeit) + reine Helfer `parse_urls`, `parse_result_paths`, `build_prompt`, `_next_run_at`.
- `backend/app/schemas/video_summary.py` — Pydantic v2 (QueueItemRead, WorkerStateRead, QueueRead, QueueAddRequest/Result, Settings Read/Patch).
- `backend/app/routes/video_summary.py` — Router (siehe API unten).
- `backend/app/config.py` — neue Settings: `video_summary_db_path`, `video_summary_poll_interval_seconds` (5s), `video_summary_default_cooldown_minutes` (30), `video_summary_batch_size` (4), `video_summary_model` (`sonnet`), `video_summary_permission_mode` (`bypassPermissions`), `video_summary_project_path` (Default Hal-Vault).
- `backend/app/main.py` — `vs_repo` gebaut, `app.state.video_summary` (Worker), `_video_summary_loop` als Lifespan-Task, `startup()` (Schema + running→pending) im Lifespan, Router registriert, `vs_repo.close()` beim Shutdown.
- `backend/app/db/__init__.py` — Exporte; `backend/tests/conftest.py` — Test-Isolation (eigene DB in tmp, Poll-Intervall 3600s aus).
- `backend/tests/test_proj41_video_summary.py` — 17 Tests (Helper + Worker-Drossel + Persistenz + API). **651/651 grün, keine Regression.**

### Worker-Verhalten (umgesetzt)
- **Sequenziell + Drossel:** genau eine headless Session gleichzeitig; nach je `batch_size` (4) verarbeiteten Videos `paused_until = jetzt + cooldown_minutes`; danach automatisch weiter, bis Queue leer (→ idle, consecutive-Reset).
- **Turn-Ende-Erkennung:** der `claude -p`-Prozess bleibt nach dem One-Shot-Lauf **alive** (Status `waiting`, nicht `done`) → Worker wertet `waiting`/`done` als „fertig", liest Notiz-/PDF-Pfad aus dem `JUPITER_VIDEO_RESULT`-Block des Abschlussberichts (best-effort) und **stoppt** danach die Session (gibt Slot/Prozess frei, PROJ-14).
- **Skill unverändert:** `build_prompt` ruft `/hal-video-summary <URL>` + Anweisung „Kategorie selbst wählen, keine Rückfragen" + maschinenlesbarer Pfad-Block. `permission_mode=bypassPermissions` (headless kann kein Decision-Card-Gate bedienen).
- **Zeitplan:** dependency-freier Tagesplan `HH:MM` (kein cron-Paket); fällig → Drain anstoßen (idempotent, keine Überlappung).
- **Persistenz:** Queue + Einstellungen in SQLite (überleben Neustart); `running`→`pending` beim Start; Laufzeit-Zustand (consecutive/paused/draining) bewusst nur im Speicher.
- **Fehler/Retry:** Start-/Skill-Fehler → Eintrag `error` + Ursache, Queue läuft weiter; `retry` setzt `error`→`pending` + Drain. `SessionLimitError` → Eintrag bleibt `pending` (nächster Tick).

### API-Vertrag (für Frontend)
```
GET    /video-summary/queue            → {items:[QueueItem], state:{status:idle|running|paused, draining, paused_until, next_scheduled_run}}
POST   /video-summary/queue            → Body {urls: string|string[]}  → {added, rejected, duplicates, queue}; nur-ungültig → 400
DELETE /video-summary/queue/{id}       → 204 (404 unbekannt)
POST   /video-summary/queue/{id}/retry → QueueRead (404 unbekannt, 409 wenn nicht error)
POST   /video-summary/run-now          → QueueRead (Drain sofort, idempotent)
GET    /video-summary/settings         → {cooldown_minutes, batch_size, schedule}
PATCH  /video-summary/settings         → Teil-Update {cooldown_minutes?, batch_size?, schedule?}; ungültiger schedule → 400
```
QueueItem: `{id, url, owner, status, result_note_path, result_pdf_path, error_message, session_id, created_at, started_at, finished_at}`.

### Offener Hand-off (Frontend, /abc-frontend)
- `engines.yaml`-Eintrag `video_summary` (`kind: native`, `group: micro`, Label „Video Summary", Icon z. B. `film`/`play`).
- Eintrag in `nextjs_app/lib/microapps-registry.ts` (`video_summary → lazy(import …)`) + Komponente `components/microapps/video_summary/` (Eingabe-Textarea/Paste, Queue-Liste mit Polling auf `GET /queue`, Steuerleiste „Jetzt ausführen"/Status-Badge, Einstellungs-Dialog). Render über native-Zweig in `app/(cockpit)/apps/[key]/page.tsx`.

## Implementation Notes (Frontend — /abc-frontend, 2026-06-25)

**Branch:** `dev`. Stack: **Next.js** (native Micro-App, PROJ-40-Muster) — kein iFrame.

### Neue/geänderte Dateien
- `nextjs_app/components/microapps/video_summary/video-summary-app.tsx` — die native Komponente (Default-Export, Props `{appKey}`). Enthält: **EingabeKarte** (Textarea + „Zur Warteschlange hinzufügen", Paste-Hinweis), **SteuerLeiste** („Jetzt ausführen", Worker-Badge Leerlauf/Läuft/Pausiert-bis-HH:MM, nächster Plan-Lauf, „Einstellungen"-Dialog), **WarteschlangenListe** (URL · Status-Badge Wartend/Läuft/Fertig/Fehler · bei Fertig Download-Links „Notiz öffnen"/„PDF" · bei Fehler Ursache + „Erneut versuchen" · „Entfernen"), **EmptyState**, **Lade-/Fehlerzustand**. Polling alle 3 s auf `GET /video-summary/queue`.
- `nextjs_app/lib/microapps-registry.ts` — `video_summary: lazy(() => import(…))`.
- `nextjs_app/lib/api.ts` — Client-Funktionen `getVideoSummaryQueue`, `addVideoSummaryUrls`, `deleteVideoSummaryItem`, `retryVideoSummaryItem`, `runVideoSummaryNow`, `getVideoSummarySettings`, `patchVideoSummarySettings`.
- `nextjs_app/lib/types.ts` — Typen `VideoSummaryItem/WorkerState/Queue/AddResult/Settings`.
- `backend/config/engines.yaml` (prod, gitignored) **und** `backend/config/engines.example.yaml` (getrackt) — neuer Eintrag `video_summary` (`kind: native`, `group: micro`, `icon: film`).

### Entscheidungen
- **Ergebnis-Links** via `fileDownloadUrl(absoluter Vault-Pfad)` (Vault liegt unter `/home/dev/tools` = allowed root) — kein Vault-Root-Wissen im Client nötig, robust auch wenn nur einer der Pfade ermittelt wurde.
- **shadcn/ui** durchgängig (Dialog/Button/Badge/Input/Textarea/Label); deutsche Texte; Loading/Error/Empty/Success explizit.
- Verifiziert: `eslint` (0 Fehler), `tsc --noEmit` (keine Fehler in den neuen Dateien), Backend `test_proj40_microapps`/`test_proj18_engines` grün (geänderte example.yaml).

> Render läuft über den bestehenden native-Zweig in `app/(cockpit)/apps/[key]/page.tsx` (`NativeMicroAppHost` → `resolveMicroApp`) — keine Routen-Änderung nötig. Die Sidebar-Sektion „Micro-Apps" listet den Eintrag über `GET /engines` (group=micro); Direkt-URL `/apps/video_summary` bleibt auch bei ausgeblendeter Sektion erreichbar.

## QA Test Results (/abc-qa, 2026-06-25)

**Branch:** `dev` · **Ergebnis: PRODUCTION-READY** (keine Critical/High-Bugs).

### Automatisierte Tests
- **Backend:** `test_proj41_video_summary.py` (17) + `test_proj41_qa.py` (6) = **23 PROJ-41-Tests grün**. Volle Suite **657 passed**, keine Regression. Regressions-Spot-Check `test_proj40_microapps`/`test_proj18_engines` (34) grün.
- **Frontend:** `eslint` 0 Fehler · `tsc --noEmit` keine Fehler in den neuen Dateien · **`next build` erfolgreich** (`/apps/[key]` kompiliert inkl. lazy nativer Komponente).
- **Integrationsbeweis AC1/AC2:** `GET /engines` liefert `video_summary` mit `kind=native, group=micro, icon=film, available=true, url=null` (TestClient gegen die echte `engines.yaml`).

### Acceptance Criteria — Matrix
| # | Kriterium | Status | Beleg |
|---|-----------|--------|-------|
| 1 | Eintrag in Sidebar „Micro-Apps" (group:micro, kind:native), Label+Icon, Vollbild /apps/<key> | ✅ | engines.yaml + GET /engines + native-Route |
| 2 | Native Micro-App (React, registriert) — kein iFrame | ✅ | Komponente + microapps-registry.ts |
| 3 | Textarea akzeptiert mehrere URLs per Paste; Block-Zerlegung (Zeilenumbruch/Leerzeichen/Komma/Semikolon), getrimmt, dedup | ✅ | `parse_urls`-Tests, `add_urls` |
| 4 | URL-Validierung: ungültige abgewiesen (deutsch), gültige übernommen | ✅ | per-URL `rejected` + 400 bei nur-ungültig; `test_invalid_url_does_not_enter_queue` |
| 5 | Warteschlangen-Liste mit Status Wartend/Läuft/Fertig/Fehler | ✅ | `StatusBadge`, QueueRead |
| 6 | „Jetzt ausführen" startet sofort | ✅ | `run-now` + `test_drossel…` |
| 7 | Wiederkehrender Zeitplan einstellbar, automatisch abgearbeitet | ✅ | Tagesplan HH:MM, `test_schedule_due_sets_draining_and_advances` |
| 8 | Nie mehr als 4 in Folge → Cooldown (30), dann weiter bis leer | ✅ | `test_drossel_pauses_after_batch_size` |
| 9 | Cooldown-Dauer konfigurierbar (Default 30) | ✅ | Settings, `test_settings_survive_restart` |
| 10 | Jede Verarbeitung ruft `hal-video-summary` über headless Session, ohne Skill-Änderung | ✅ | `build_prompt` + `manager.create`; Skill unberührt |
| 11 | Session bestimmt Hal-Kategorie automatisch (kein Dialog); Notiz+PDF unter 04 Resources/ | ✅ | Prompt erzwingt Auto-Kategorie + bypassPermissions (kein AskUserQuestion) |
| 12 | Bei „Fertig": Link auf Notiz/PDF | ✅ | Download-Links via `fileDownloadUrl`; `test_done_item_records_result_paths` |
| 13 | Bei „Fehler": knappe Ursache + „Erneut versuchen" | ✅ | `error_message` + `retry`; 409 bei Nicht-Fehler |
| 14 | Einträge entfernen | ✅ | DELETE; `test_remove_running_stops_session` |
| 15 | Queue + Einstellungen überleben Reload/Neustart | ✅ | SQLite; `test_running_reset_to_pending_on_restart`, `test_settings_survive_restart` |
| 16 | Alle Texte deutsch | ✅ | UI + Fehlermeldungen deutsch (Eigenname „Video Summary") |

**Edge Cases** (Spec) — alle abgedeckt: >4 Videos→Pause (test), run-now während laufend→kein Doppelstart (test), Cron während Lauf→keine Überlappung (sequenziell + idempotenter Drain, test), ungültige/Doppel-URL (tests), Skill/Session-Fehler→error+retry, Tab zu→serverseitige Verarbeitung läuft weiter (Worker im Lifespan), Backend-Neustart→running→pending (test), Sektion ausgeblendet→Direkt-URL erreichbar (page.tsx lädt aus /engines unabhängig von der Sidebar-Sichtbarkeit).

### Security-Audit (Red-Team)
- **SQL-Injection:** keine — alle Queries parametrisiert; `update` zusätzlich mit Spalten-Whitelist. ✅
- **Pfad-Scope:** Session-cwd (`video_summary_project_path`) wird über `validate_project_path` auf `allowed_roots` geprüft; Ergebnis-Download über `/files/download` erzwingt ebenfalls `allowed_roots` → ein außerhalb liegender Pfad ist nicht abrufbar. ✅
- **Auth/RLS:** im MVP bewusst keins (Projekt-Entscheidung); `owner` gestempelt, nicht gefiltert — wie der Rest von Jupiter. Akzeptiert.
- **Beobachtung (Low, akzeptiert):** Verarbeitungs-Sessions laufen mit `bypassPermissions` → für DIESE Sessions greifen die PROJ-4-Decision-Cards/der Selbst-Restart-Guard nicht. Eingegrenzt dadurch, dass der Prompt fest auf `/hal-video-summary <URL>` lautet (wohldefinierter, vault-skopierter Skill) und der cwd in `allowed_roots` liegt. Headless erfordert bypass (kein interaktives Gate bedienbar) — dokumentierte Architektur-Entscheidung, kein Blocker.

### Bugs
Keine Critical/High/Medium gefunden. Eine Low-UX-Note: ungültige Zeilen einer gemischten Paste werden als Aggregat-Zähler („Y ungültig") gemeldet, nicht pro Zeile — AC4 ist über Zähler + 400-bei-nur-ungültig erfüllt; kein Fix nötig.

**Production-Ready: JA.**

## Deployment
- **Production URL:** https://jupiter.auxevo.tech (Route `/apps/video_summary`)
- **Deployed:** 2026-06-25 · **Version:** 0.15.0 · **Tag:** v0.15.0
- **Host:** Dev-VPS host-native (systemd `jupiter-backend`/`jupiter-frontend` + Caddy TLS), Auto-Deploy via GitHub-Webhook auf `main` ([[jupiter-deployment]]).
- **Geshippt:** native Micro-App Video Summary — Backend-Queue-Worker (URL-Queue → `hal-video-summary` → Hal-Vault, Drossel/Cooldown/Zeitplan) + Frontend (Paste-Queue, Settings, Polling).
- **Hinweis:** Prod-`engines.yaml` (gitignored) trägt den `video_summary`-Eintrag bereits.
- **Browser-Smoke (nach SW-Hard-Refresh):** Kachel „Video Summary" in Micro-Apps, URL einreihen → Verarbeitung, Ergebnis-Links (Notiz/PDF).
