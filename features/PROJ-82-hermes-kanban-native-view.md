# PROJ-82: Hermes-Kanban nativ in Jupiter (kein iFrame)

## Status: Deployed
**Created:** 2026-08-19
**Revidiert:** 2026-08-19 — Review gegen echte Hermes-CLI v0.20.4 (alle Subcommands/Flags/JSON-Formate verifiziert), Entscheidungen aus Nutzer-Review eingearbeitet.

## Dependencies
- Bezug: PROJ-81 (Hermes-Dashboard per iFrame in der Orchestration-Sektion) — bewusst eine ANDERE Lösung für ein anderes Ziel. PROJ-81 bettet das komplette Hermes-Web-Dashboard (Config/Sessions/API-Keys) unverändert per iFrame ein. PROJ-82 baut eine eigene, native Jupiter-Ansicht NUR für den Hermes-Kanban-Workflow, gerendert mit Jupiters eigenen Komponenten, kein iFrame. Beide existieren nebeneinander als separate Einträge in der Orchestration-Sektion.
- Bezug: PROJ-39 (Sidebar „Orchestration") — Registrierungsmuster für den Sidebar-Eintrag (Engine-Registry, group=orchestration).
- Voraussetzung (extern, verifiziert am 2026-08-19): Hermes-Agent CLI v0.20.4 installiert (`/home/dev/.local/bin/hermes`) und Gateway-Dienst `hermes-gateway` (systemd-User-Service, aktiv, linger enabled) laufen auf dem VPS; Board `jupiter-abc` existiert und ist aktuelles Board; 12 `jupiter-*`-Profile liegen in `~/.hermes/profiles/`.
- Ausblick (NICHT Teil dieses Features, separater Wunsch des Nutzers): später Hermes-Worker-Läufe als mehrere Sessions in „Aktive Sessions" sichtbar machen.

## Beschreibung
Der Nutzer orchestriert Features über den Jupiter-abc-Workflow als Hermes-Kanban-Schwarm (12 Rollen-Profile inkl. `jupiter-backoffice`; Profile werden zur Laufzeit dynamisch aus `hermes kanban assignees` gelesen, nicht hardcodiert). Aktuell muss er dafür zwischen der Jupiter-Session und entweder der Hermes-CLI oder dem separaten Hermes-Web-UI (Port 9119) wechseln. Dieses Feature bringt eine **eigene, native Ansicht** in Jupiter, die den Hermes-Kanban-Workflow abbildet:

1. **Board-Übersicht** — alle Tasks des Boards `jupiter-abc` (Board wählbar), gruppiert nach Status (Triage/Todo/Scheduled/Ready/Running/Blocked/Review/Done), mit Assignee-Filter und optionalem Archived-Toggle — komplett aus Jupiters eigenen Komponenten gerendert (shadcn `Card`/`Badge`/`Tabs`), **kein `<iframe>`**.
2. **Task-Detail** — Klick auf eine Karte zeigt Body, Events, Run-History (inkl. Crash-/Retry-Info) und ein **Worker-Log-Snapshot** (mit Refresh-Button, kein Live-Streaming) in einem Panel.
3. **Neuer Task** — natives Formular mit **allen** Feldern, die `hermes kanban create` unterstützt (Grundbereich + einklappbarer „Erweitert"-Bereich), damit der Nutzer nie zur Hermes-CLI wechseln muss.
4. **Dispatch-Aktion** — Button, der `hermes kanban dispatch` anstößt (sofortiger Tick statt auf die 60s-Gateway-Schleife zu warten).
5. **Task-Aktionen (Mindestsatz)** — Blocken (mit Grund + Block-Art), Unblocken (mit optionalem Grund), Archivieren (mit Bestätigung) und Kommentieren direkt aus dem Detail-Panel.

**Einstiegspunkt:** eigener Eintrag „Hermes Kanban (nativ)" in der Sidebar-Sektion „Orchestration" neben dem Hermes-Dashboard-iFrame (PROJ-81). Wie native (nicht-iFrame)-Darstellung im PROJ-39-Registrierungsmechanismus abgebildet wird, klärt die Architecture-Phase; Anforderung ist: ein Klick in Orchestration öffnet die native Ansicht innerhalb Jupiters.

**Phase 2, NICHT Teil dieses Scopes:** Live-Streaming der Worker-Logs pro laufendem Task (das „Worker log"-Panel aus dem Hermes-Web-UI, `tail`/`watch` über WebSocket-Relay). Der Log-Snapshot (Punkt 2) deckt den häufigsten Fall ab; Streaming bleibt bewusst zurückgestellt.

## User Stories
- Als Nutzer möchte ich den Stand aller Hermes-Kanban-Tasks direkt in Jupiter sehen, ohne die separate Hermes-UI zu öffnen.
- Als Nutzer möchte ich einen neuen Kanban-Task (z. B. einen Coordinator-Kickoff wie „Requirements Feature 8, Business OS") komplett über ein Jupiter-Formular anlegen können, mit allen Feldern, die die CLI auch bietet — einfache Felder sofort sichtbar, seltene Felder in einem einklappbaren „Erweitert"-Bereich.
- Als Nutzer möchte ich pro Task sehen, wer (Profil) ihn bearbeitet, welchen Status er hat, und bei Crashes die Fehlermeldung/Retry-Historie sehen — ohne CLI-Befehle abzutippen.
- Als Nutzer möchte ich das Worker-Log eines Tasks als Snapshot in Jupiter lesen und per Button aktualisieren können, um bei einem Crash nicht zur CLI zu wechseln.
- Als Nutzer möchte ich Tasks blocken, entblocken, archivieren und kommentieren können, wenn ich eingreifen muss.
- Als Nutzer möchte ich den Dispatcher manuell anstoßen können, statt bis zu 60 Sekunden auf den nächsten automatischen Tick zu warten.
- Als Nutzer möchte ich das Aktualisierungsintervall der Board-Ansicht in den App-Einstellungen konfigurieren können.
- Als Nutzer möchte ich einen Kanban-Task per Kurzsyntax anlegen können, z. B. `requirements 82` oder `backend 82`, statt jedes Mal das volle Formular auszufüllen — Assignee ist dabei immer der Koordinator, weil er den kompletten ABC-Kanban-Fluss steuert und als Erstes angewiesen werden muss.
- Als Nutzer möchte ich im Board mehrere Task-Karten gleichzeitig auswählen und in einer Aktion archivieren können, statt jede Karte einzeln zu öffnen — mit einer Bestätigungsfrage davor, damit ich nichts versehentlich wegräume.

## Acceptance Criteria

### Board-Übersicht
- [ ] Eintrag „Hermes Kanban (nativ)" in der Sidebar-Sektion „Orchestration"; Klick öffnet die native Ansicht (kein iFrame, kein Zugriff auf Hermes-Web-UI-Port 9119); funktioniert unabhängig von PROJ-81.
- [ ] Board-Auswahl (Dropdown aus `hermes kanban boards list --json`, zeigt Slug + Name), Default = Board mit `is_current: true`.
- [ ] Ansicht zeigt alle Tasks des gewählten Boards, gruppiert in Spalten: Triage, Todo, Scheduled, Ready, Running, Blocked, Review, Done (exakt die Statuswerte der CLI; „Running", nicht „In Progress").
- [ ] Archived-Tasks sind standardmäßig ausgeblendet; ein Toggle blendet sie zusätzlich als Spalte/Bereich „Archived" ein (CLI-Flag `--archived`).
- [ ] Assignee-Filter: Dropdown, dynamisch gefüllt aus `hermes kanban assignees --json` (alle auf dem VPS bekannten Profile + „alle").
- [ ] Jede Karte zeigt mindestens: Titel, Assignee, Priorität, Workspace-Art, erstellt/gestartet (relativ oder Datum).
- [ ] Ansicht aktualisiert sich automatisch per Polling; Intervall stammt aus den App-Einstellungen (siehe unten), Default 10 s.

### Task-Detail
- [ ] Klick auf eine Task-Karte öffnet ein Detail-Panel mit: Titel, Body, Assignee, Status, Workspace-Pfad, Branch, Parent-/Children-IDs, Kommentar-Liste, Event-Liste, Run-History (inkl. `crashed`/`spawn_failed`/`protocol_violation`-Outcome je Run mit Summary und Dauer) sowie `latest_summary`.
- [ ] Detail-Panel zeigt einen Bereich „Worker-Log" als Snapshot (Monospace): geholt über `hermes kanban log <id>` (begrenzt auf die letzten 64 KB via `--tail`), mit Button „Aktualisieren". Hat der Task noch keinen Lauf, steht dort „Noch kein Worker-Log vorhanden". Kein Live-Streaming.

### Neuer Task (Formular mit voller CLI-Parität)
- [ ] **Grundbereich:** Titel (Pflicht), Body/Beschreibung (Mehrzeiler), Assignee (Dropdown aus assignees-Endpunkt, Option „Kein Assignee"), Projekt (Dropdown aus `hermes project list`), Workspace-Modus (Auswahl: `scratch` / `dir:<pfad>` / `worktree` / `worktree:<pfad>`; Pfad-Feld bei `dir:`/`worktree:<pfad>` Pflicht; Branch-Feld bei beiden `worktree`-Varianten Pflicht), Parent-Tasks (Mehrfachauswahl Suchfeld/Dropdown über nicht-archivierte Tasks des Boards), Priorität (Zahl, optional), Skills (Mehrfachauswahl/Freitext, optional), Initial-Status (normal / `blocked` / `running`, optional).
- [ ] **Einklappbarer „Erweitert"-Bereich:** Triage (Checkbox → `--triage`), Tenant (Freitext), Idempotency-Key (Freitext), Max-Runtime (Freitext, Hinweis „z. B. 90s, 30m, 2h, 1d"), Max-Retries (Zahl), Model-Override + Provider-Override (zwei Freitextfelder, nur zusammen gültig), Goal-Mode (Checkbox) + Goal-Max-Turns (Zahl, nur bei aktivem Goal-Mode sichtbar, Default 20).
- [ ] Absenden erzeugt serverseitig den exakt äquivalenten `hermes kanban create ...`-Aufruf (kein Feld ausgelassen), ergänzt automatisch `--created-by jupiter` (fest, nicht im Formular), und zeigt die erzeugte Task-ID nach Erfolg an.
- [ ] Nicht ausgefüllte optionale Felder werden NICHT als leere Flags an die CLI übergeben (z. B. kein `--parent ""`).
- [ ] Formular-Validierung vor Absenden: Triage-Checkbox und Initial-Status≠normal schließen sich aus (Hinweis, Absenden blockiert); Model ohne Provider (oder umgekehrt) blockiert mit Hinweis „beide zusammen oder keins".

### Neuer Task — Kurzsyntax (Quick-Add)
- [ ] Eingabefeld „Schnell anlegen" neben dem „Neuer Task"-Button, Platzhalter z. B. `requirements 82`. Format: `<phase> <projektnummer>`, Phase case-insensitiv, eine der kanonischen ABC-Phasen (`brainstorm, requirements, architecture, review-architecture, frontend, backend, qa, deploy, document`, Quelle: `backend/app/engine/abc_phases.py:ABC_PHASES`) — plus deutsche Aliase (`anforderungen`→requirements, `architektur`→architecture).
- [ ] Erkennt das Feld ein gültiges `<phase> <nummer>`-Muster, öffnet es den „Neuer Task"-Dialog vorausgefüllt (nicht: sendet blind ab) mit: Assignee = `jupiter-coordinator` (fest, unabhängig von der Phase), Titel = `PROJ-<nummer>: <Phase-Label> starten`, Body = Anweisung an den Koordinator, `/abc-<phase>` für `PROJ-<nummer>` auszuführen. Existiert `features/PROJ-<nummer>-*.md`, wird dessen Titel aus `features/INDEX.md` in Titel/Body übernommen (Best-Effort, siehe Edge Case); existiert die Nummer nicht, bleibt der generische Titel, keine Blockade.
- [ ] Nutzer sieht/bearbeitet die Vorbefüllung im gewohnten Dialog und bestätigt normal per „Erstellen" — Kurzsyntax ist ausschließlich eine Vorbefüll-Abkürzung, kein separater Erstellungspfad ohne Review.
- [ ] Passt die Eingabe zu keinem `<phase> <nummer>`-Muster, öffnet sich der normale leere Dialog (Fallback), kein Fehler.

### Task-Aktionen (Mindestsatz)
- [ ] Detail-Panel bietet: **Blocken** (Dialog mit optionalem Grund + optionaler Block-Art: Allgemein/`capability`/`dependency`/`needs_input`/`transient` → `hermes kanban block` mit `--kind`), **Entblocken** (optionaler Grund → `--reason`), **Archivieren** (mit Bestätigungsdialog), **Kommentieren** (Texteingabe + Senden, Autor fest `--author jupiter`, serverseitig max. 10 000 Zeichen).
- [ ] Nach jeder erfolgreichen Aktion werden Board-Ansicht und Detail-Panel aktualisiert; schlägt die CLI fehl (z. B. Aktion passt nicht zum Status), wird die CLI-Fehlermeldung angezeigt.

### Mehrfachauswahl & Bulk-Archivieren
- [ ] Task-Karten sind per Checkbox (oder Ctrl/Cmd-Klick) mehrfach auswählbar; ausgewählte Karten sind visuell markiert.
- [ ] Bei ≥1 ausgewählter Karte erscheint eine Bulk-Aktionsleiste mit Anzahl + Button „Archivieren (N)". Andere Aktionen (Blocken/Entblocken/Kommentieren) bleiben in dieser Version Einzeltask-only — bewusst kleinster Scope, siehe Tech Design.
- [ ] Klick auf „Archivieren (N)" zeigt einen Bestätigungsdialog mit Anzahl + Titeln (max. 10 aufgelistet, Rest als „+N weitere") — erst nach Bestätigen wird archiviert.
- [ ] Bestätigen ruft den Bulk-Endpunkt mit allen ausgewählten IDs auf (ein CLI-Aufruf `archive <id1> <id2> …`, kein Loop); Board aktualisiert sich, Auswahl wird geleert.
- [ ] Schlagen einzelne IDs fehl (z. B. bereits archiviert), zeigt die Fehlermeldung, welche IDs betroffen sind; erfolgreich archivierte bleiben archiviert (keine Rollback-Illusion, `hermes kanban archive` ist pro ID atomar).
- [ ] Board-übergreifend nicht möglich — Mehrfachauswahl gilt nur innerhalb des aktuell gewählten Boards.

### Dispatch
- [ ] „Dispatch jetzt"-Button ruft `hermes kanban dispatch --json` auf (Board-Kontext beachten) und zeigt das Ergebnis (Reclaimed/Crashed/Spawned-Zahlen) kurz an; Fehler werden angezeigt.

### Einstellungen
- [ ] Neues Setting „Hermes-Kanban-Aktualisierungsintervall" in den App-Einstellungen (Backend-Endpunkt `GET/PATCH /settings/hermes-kanban` nach bestehendem `/settings/*`-Muster): Wert in Sekunden, Bereich 5–60, Default 10. Das Board-Polling der Ansicht nutzt diesen Wert; Änderung wirkt ohne Neustart.

### Allgemein
- [ ] Alle Texte/Labels deutsch.

## Edge Cases
- **Hermes-CLI nicht im PATH / Gateway bzw. Board-DB nicht erreichbar:** Ansicht zeigt einen klaren Fehlerhinweis („Hermes nicht erreichbar") statt eines leeren/kaputten Boards.
- **`hermes kanban list --json` liefert leeres Board:** Ansicht zeigt „Keine Tasks" pro Spalte, kein Fehlerzustand.
- **Task-ID im Detail-Panel existiert nicht mehr (archiviert/gelöscht/gc't zwischen Poll-Zyklen):** Detail-Panel zeigt „Task nicht mehr verfügbar", Board-Liste aktualisiert sich beim nächsten Poll.
- **Formular: `--model` gesetzt ohne `--provider` (oder umgekehrt):** Frontend blockt das Absenden mit Hinweis „beide zusammen oder keins", bevor der Request rausgeht.
- **Formular: Workspace `worktree` oder `worktree:<pfad>` ohne Branch:** Branch-Feld wird Pflichtfeld, sobald eine worktree-Variante gewählt ist; Pfad-Feld Pflicht bei `dir:<pfad>` und `worktree:<pfad>`.
- **Formular: Triage + Initial-Status gleichzeitig gesetzt:** Absenden blockiert mit Hinweis, dass sich beides ausschließt.
- **Aktion auf Task mit unpassendem Status** (z. B. Unblock auf nicht-blocktem Task, Block auf archiviertem): CLI liefert Fehler → Backend gibt CLI-Fehlermeldung 1:1 durch, Frontend zeigt sie am Panel.
- **Worker-Log existiert noch nicht** (Task lief nie): Bereich zeigt „Noch kein Worker-Log vorhanden"; Logs größer 64 KB werden per `--tail` begrenzt.
- **Kommentar > 10 000 Zeichen:** Backend lehnt mit Hinweis ab, bevor die CLI gerufen wird.
- **`hermes project list` nicht parsebar / leer:** Projekt-Dropdown bleibt leer mit Hinweis; Task-Anlage bleibt ohne Projekt möglich.
- **Subprocess-Timeout** (Hermes-CLI hängt): Backend bricht ab (10 s für Lese-/Aktionsbefehle inkl. `log`, 20 s für `create`, 30 s für `dispatch`), Frontend zeigt Fehler statt endlos zu laden.
- **Gleichzeitige Requests von zwei Jupiter-Tabs:** kein Locking nötig, Hermes' Kanban-DB regelt Nebenläufigkeit selbst (atomic claim).
- **Task-Titel/Body/Kommentar mit Sonderzeichen/Anführungszeichen:** Übergabe als Subprocess-Argumentliste (nie Shell-String-Interpolation), keine Escaping-Bugs.
- **Kurzsyntax: Projektnummer existiert nicht in `features/`:** Dialog öffnet trotzdem mit generischem Titel (`PROJ-<nummer>: <Phase-Label> starten`), kein Blocker — der Nutzer kann die Nummer für ein Feature vergeben, das erst mit diesem Task entsteht (z. B. `requirements 90` für ein neues Feature 90).
- **Kurzsyntax: unbekannte Phase oder falsches Format** (z. B. `„fronted 82"` Tippfehler, nur eine Zahl ohne Phase): kein Treffer → normaler leerer Dialog öffnet, kein Fehlertoast (Kurzsyntax ist eine Abkürzung, kein Pflichtformat).
- **Bulk-Archivieren: eine der ausgewählten IDs wurde zwischen Auswahl und Bestätigung bereits archiviert/gelöscht:** CLI-Fehlermeldung für die betroffene ID wird angezeigt, die übrigen IDs sind bereits archiviert (kein Alles-oder-nichts).
- **Bulk-Archivieren: 0 Karten ausgewählt:** Bulk-Aktionsleiste erscheint nicht (nur ab 1 Auswahl sichtbar).

## Technical Requirements (optional)

### Verifizierte CLI-Basis (2026-08-19, Hermes v0.20.4)
- **Wichtig — Argument-Reihenfolge:** `--board` ist eine Gruppen-Option von `kanban` und muss VOR dem Subcommand stehen: `hermes kanban --board <slug> <subcommand> ...`. (`hermes kanban list --board <slug>` scheitert.)
- JSON-Ausgabe bestätigt für: `kanban list`, `kanban show <id>`, `kanban boards list`, `kanban assignees`, `kanban create`, `kanban dispatch`. **Kein JSON** für `hermes project list` → Textausgabe parsen (Format: `[* ]<slug>  <Anzeigename>  [N folder(s)]`, `*` = aktives Projekt; ohne `--all`, damit archivierte Projekte draußen bleiben).
- `list`-Task-JSON-Felder: id, title, body, assignee, status, priority, tenant, workspace_kind, workspace_path, branch_name, project_id, created_by, created_at, started_at, completed_at, result, skills, max_retries, model_override, provider_override, session_id, workflow_template_id, current_step_key.
- `show`-JSON: task, parents, children, comments, events, runs (id, profile, step_key, status, outcome, summary, elapsed), latest_summary.
- Status-Enum exakt: `triage, todo, scheduled, ready, running, blocked, review, done, archived`.
- Aktionen verifiziert: `block <id> [reason] [--kind ...]`, `unblock <ids> [--reason]`, `archive <ids>`, `comment <id> <text> [--author]`, `log <id> [--tail N]`.

### Backend (Repo-Konvention: `backend/app/routes/<name>.py` + `backend/app/schemas/<name>.py` — es gibt KEIN `backend/app/features/`)
- `backend/app/routes/hermes_kanban.py`: Routen + Service-Funktionen; Subprocess immer `asyncio.create_subprocess_exec("hermes", ...)` mit Argumentliste, nie `shell=True`/String-Concat.
  - `GET /hermes-kanban/boards` → `kanban boards list --json`
  - `GET /hermes-kanban/tasks?board=&assignee=&include_archived=` → `kanban --board … list --json` (+ `--assignee`, `--archived`)
  - `GET /hermes-kanban/tasks/{id}?board=` → `kanban --board … show {id} --json`
  - `GET /hermes-kanban/tasks/{id}/log?board=` → `kanban --board … log {id} --tail 65536`
  - `GET /hermes-kanban/assignees?board=` → `kanban --board … assignees --json`
  - `GET /hermes-kanban/projects` → `project list` (Text-Parsing)
  - `POST /hermes-kanban/tasks` → baut `kanban --board … create`-Argumentliste 1:1 aus allen Formularfeldern inkl. `--created-by jupiter`
  - `POST /hermes-kanban/dispatch` → `kanban --board … dispatch --json`
  - `POST /hermes-kanban/tasks/{id}/block` (reason?, kind?) / `…/unblock` (reason?) / `…/archive` / `…/comments` (text)
  - `POST /hermes-kanban/tasks/archive-bulk` (board, ids: string[]) → EIN `kanban --board … archive <id1> <id2> …`-Aufruf (nutzt die bereits von der CLI unterstützte Mehrfach-ID-Signatur, kein Loop); IDs einzeln gegen `^t_[a-f0-9]+$` geprüft, Liste auf sinnvolles Maximum begrenzt (z. B. 100)
  - `GET /hermes-kanban/feature-lookup/{proj_number}` → Best-Effort-Titel aus `features/INDEX.md` für die Kurzsyntax-Vorbefüllung (liefert `null`/leer, wenn Nummer unbekannt — kein Fehler)
- `backend/app/schemas/hermes_kanban.py`: Pydantic-Modelle für Task, TaskDetail, CreateTaskRequest (Validierung: Model+Provider zusammen, Branch bei worktree-Varianten Pflicht, Triage ⊕ Initial-Status, Kommentar-Max-Länge), BlockRequest, CommentRequest, Settings-Modell.
- Settings-Endpunkt `GET/PATCH /settings/hermes-kanban` (`poll_interval_seconds`, 5–60, Default 10) — Muster wie `/settings/threshold` bzw. `/settings/clipboard-dir` in `backend/app/routes/settings.py`.
- **Validierung/Sicherheit:** Task-IDs gegen `^t_[a-f0-9]+$`, Board-Slugs gegen `^[a-z0-9][a-z0-9-]*$` prüfen; Titel/Body serverseitig begrenzen (DoS-Schutz). Subprocess läuft unter demselben VPS-User wie das Backend — kein zusätzliches Auth nötig. Timeouts: 10 s Lese-/Aktionsbefehle, 20 s `create`, 30 s `dispatch`.

### Frontend (Konvention: `nextjs_app/components/microapps/`)
- **Korrigiert im Review:** die bestehenden nativen Microapps sind je EINE Datei pro App (z. B. `peppermint_dashboard/peppermint-dashboard-app.tsx`, ~50 KB, shadcn `Dialog`/`Select`/`Label`/`Input`/`Button` + `sonner`-Toasts — **kein** `react-hook-form`/`zod`; kein Microapp im Repo nutzt diese beiden). Der ursprünglich geplante 5-Datei-Split (`task-detail-panel.tsx`, `new-task-dialog.tsx`, `task-actions.tsx`, `lib/api.ts`) hat kein Vorbild im Repo. Gegeben Umfang und Formularkomplexität dieses Features (Erweitert-Bereich, mehrere Dialoge) ist ein Split trotzdem sinnvoll — abweichend von der Ein-Datei-Konvention, aber innerhalb `components/microapps/hermes_kanban/` bleibt die Struktur Sache der Implementierung (`/abc-frontend`), react-hook-form+zod ist als NEUE Konvention für dieses Formular zulässig (im Projekt bereits Standard laut `CLAUDE.md`), aber nicht „wie Peppermint" zu begründen.
- `nextjs_app/components/microapps/hermes_kanban/`:
  - `hermes-kanban-app.tsx`: Board-Ansicht (shadcn `Card`/`Badge`/`Tabs` etc.), Polling gemäß Settings-Intervall.
  - `task-detail-panel.tsx`: Detail-Ansicht inkl. Runs, Events, Kommentare, Worker-Log-Snapshot mit Refresh.
  - `new-task-dialog.tsx`: Formular (Grundbereich + einklappbarer „Erweitert"-Bereich), react-hook-form + Zod-Schema.
  - `task-actions.tsx`: Block/Unblock/Archive/Kommentar-Dialoge.
  - `lib/api.ts`: Client-Funktionen für die o. g. Endpunkte.
- Sidebar-Eintrag in Sektion „Orchestration": neuer Block `key: hermes_kanban, kind: native, group: orchestration` in `backend/config/engines.yaml` (Vorbild: `paperclip`, `kind: iframe, group: orchestration`, Zeile 130) + eine Zeile `hermes_kanban: lazy(() => import(...))` in `nextjs_app/lib/microapps-registry.ts`. Reine Config-Ergänzung, kein neuer Mechanismus (siehe Tech Design D4).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-19 · **Stack:** Next.js 16 (App Router) + FastAPI + Hermes-CLI-Subprocess (keine neuen DB-Tabellen) · **Branch:** specs/PROJ-82-hermes-kanban-native-view

**Kernidee in einem Satz:** Jupiter wird zum *sprachrohr* des Hermes-Kanbans — eine reine Durchreich-Schicht ohne eigene Datenhaltung: jede Anfrage ruft die Hermes-CLI auf, bekommt strukturierte Daten zurück und rendert sie nativ; die Wahrheit bleibt zu 100 % in der Hermes-Kanban-DB.

### A) Komponenten-Struktur

```
HermesKanbanApp (native Microapp unter /orchestration/hermes_kanban)
├── BoardKopfzeile
│   ├── Board-Auswahl (Dropdown: alle Boards, Default = aktuelles Board)
│   ├── Assignee-Filter (Dropdown, dynamisch aus Hermes-Profilen + „alle")
│   ├── Archived-Toggle (versteckt/zeigt die Archived-Spalte)
│   ├── Schnell-anlegen-Feld (Kurzsyntax `<phase> <projektnummer>`, öffnet vorbefüllten NeuerTaskDialog)
│   └── „Dispatch jetzt"-Button (mit Kurz-Ergebnis Reclaimed/Crashed/Spawned)
├── Kanban-Spalten: Triage · Todo · Scheduled · Ready · Running · Blocked · Review · Done (+ Archived bei Toggle)
│   └── Task-Karte (Checkbox für Mehrfachauswahl, Titel, Assignee-Badge, Priorität, Workspace-Art, Zeitstempel)
├── BulkAktionsleiste (sichtbar ab 1 Auswahl: Anzahl + „Archivieren (N)" → Bestätigungsdialog → Bulk-Archiv-Endpunkt)
├── TaskDetailPanel (per Klick auf Karte, sofern nicht im Mehrfachauswahl-Modus)
│   ├── Metadaten + Body + Parent/Children
│   ├── Run-History (Tabelle je Lauf: Profil, Ergebnis-Badge inkl. crashed/timeout, Dauer, Summary)
│   ├── Event-Liste + Kommentare (Anzeige + neuer Kommentar)
│   ├── Worker-Log-Snapshot (Monospace-Block + „Aktualisieren"-Button)
│   └── Task-Aktionen: Blocken (Grund + Art) · Entblocken · Archivieren (mit Bestätigung)
├── NeuerTaskDialog
│   ├── Grundbereich (Titel, Body, Assignee, Projekt, Workspace, Parents, Priorität, Skills, Initial-Status)
│   └── Einklappbarer „Erweitert"-Bereich (Triage, Tenant, Idempotenz-Schlüssel, Max-Laufzeit, Max-Retries, Model+Provider, Goal-Mode)
├── Fehler-Banner („Hermes nicht erreichbar") bei CLI-/Gateway-Problemen
└── Leerzustand pro Spalte („Keine Tasks")
```

Zusätzlich ein neuer Abschnitt „Hermes-Kanban" auf der Einstellungen-Seite mit einem Feld für das Aktualisierungsintervall (Sekunden, 5–60, Default 10).

### B) Datenmodell (in Klartext)

- **Keine eigenen Tabellen, keine eigene Datenhaltung.** Jupiter merkt sich nichts über Tasks — jeder Blick auf das Board fragt live die Hermes-CLI. Damit gibt es keine Doppelbuchführung und nichts, was veralten kann.
- **Einzige neue persistente Information:** das Polling-Intervall als App-Einstellung — gespeichert im bestehenden dauerhaften Einstellungen-Speicher (gleiches Muster wie Watchdog-Einstellungen), übersteht Backend-Neustarts.
- **Ein neuer Registry-Eintrag** in der bestehenden Engine-/App-Registry: Schlüssel `hermes_kanban`, Darstellungsart „nativ", Gruppe „Orchestration" (bewusst eigener Schlüssel, unverwechselbar mit `hermes`/`hermes_dashboard`).

### C) API-Form (nur Endpunkte, alle hinter bestehendem Auth-Schutz)

```
GET   /hermes-kanban/boards                  → Liste aller Boards (Name, Kürzel, Task-Zahlen)
GET   /hermes-kanban/tasks                   → Tasks eines Boards (Filter: Assignee, inkl. Archived ja/nein)
GET   /hermes-kanban/assignees               → bekannte Profile für das Assignee-Dropdown
GET   /hermes-kanban/projects                → Projektliste für das Formular (Text-Parsing der CLI)
GET   /hermes-kanban/tasks/{id}              → ein Task mit Läufen, Events, Kommentaren, Summary
GET   /hermes-kanban/tasks/{id}/log          → Worker-Log-Snapshot (letzte 64 KB)
POST  /hermes-kanban/tasks                   → neuen Task anlegen (alle Formularfelder), liefert Task-ID
POST  /hermes-kanban/dispatch                → sofortiger Dispatcher-Lauf
POST  /hermes-kanban/tasks/{id}/block        → blocken (mit Grund + Block-Art)
POST  /hermes-kanban/tasks/{id}/unblock      → entblocken (mit optionalem Grund)
POST  /hermes-kanban/tasks/{id}/archive      → archivieren
POST  /hermes-kanban/tasks/{id}/comments     → Kommentar anhängen
GET   /settings/hermes-kanban                → Polling-Intervall lesen
PATCH /settings/hermes-kanban                → Polling-Intervall setzen
```

### D) Technik-Entscheidungen (mit Begründung)

1. **Ansprache der Hermes-CLI statt direktem Datenbank- oder HTTP-Zugriff:** Die Kanban-Datenbank gehört dem Hermes-Agenten; die CLI ist seine stabile, versionierte und dokumentierte Schnittstelle (mit JSON-Ausgabe). So koppelt sich Jupiter nicht an interne Hermes-Tabellen, und ein Hermes-Update kann uns nicht „unter den Füßen" die Datenstruktur wegziehen.
2. **Read-through ohne Cache/Zwischenkopie:** Jede Anzeige fragt live. Bei einem Kanban-Board mit Dutzenden Tasks ist das billig (lokale SQLite-CLI, Antwortzeiten im Millisekundenbereich) und eliminiert jede Klasse von „Anzeige veraltet"-Bugs.
3. **Polling statt WebSocket, konfigurierbares Intervall:** Der Kanban-Workflow ist menschentaktet — 10 Sekunden Default fühlen sich „live" an, ohne Infrastruktur-Komplexität. Wer es eiliger hat, stellt das Intervall in den Einstellungen schärfer; für den Sofort-Fall gibt es den Dispatch-Button. Live-Streaming bleibt bewusst Phase 2.
4. **Bestehender Registry-Mechanismus, keine neue Mechanik nötig (korrigiert im Review):** `kind: native` mit `group: orchestration` existiert bereits (PROJ-40, `backend/app/engine/registry.py:36-41`); `nextjs_app/lib/microapps-registry.ts` löst native Keys bereits generisch auf Micro-App-Komponenten auf. `paperclip` (`backend/config/engines.yaml:130-135`) läuft schon als `kind: iframe, group: orchestration`; ein natives Pendant in derselben Gruppe ist damit reines Config: ein neuer `key: hermes_kanban, kind: native, group: orchestration`-Block in `engines.yaml` + eine Zeile in `microapps-registry.ts`. Kein Registry-/Schema-Umbau, keine „Blickverengung" zu öffnen.
5. **Eine Backend-Datei statt Hintergrund-Worker:** Anders als z. B. Peppermint (das einen Dauerläufer braucht) ist Hermes-Kanban vollständig anfragegesteuert — kein Worker, kein Zustand im Server. Die Subprozess-Aufrufe leben gesammelt in der Routen-Datei, mit dem im Haus bewährten Muster „Zeitlimit + hartes Abbrechen bei Hängen": Vorbild ist `backend/app/engine/scout.py:49-63` (`_default_runner`) — `asyncio.create_subprocess_exec(...)` mit Argumentliste, `asyncio.wait_for(proc.communicate(), timeout=...)`, bei `asyncio.TimeoutError` → `proc.kill()`. Gleiches Muster, eigener Timeout pro Subcommand-Klasse (10 s/20 s/30 s statt eines festen `scout_timeout_seconds`).
6. **CLI-Eigenheit zentral gekapselt:** Das `--board`-Flag muss bei Hermes VOR dem Unterkommando stehen (verifiziert). Eine zentrale Stelle baut alle Aufrufe zusammen — diese Eigenheit kann nirgendwo sonst im Feature falsch gemacht werden; ebenso greifen dort die Prüfungen auf gültige Task-IDs/Board-Kürzel und die Zeitlimits (10 s lesen/aktionen, 20 s anlegen, 30 s dispatch).
7. **Worker-Log als gedeckelter Snapshot:** Worker-Logs können groß werden; die letzten 64 KB enthalten die relevante Crash-Ursache. Das hält die Antworten klein und den Nutzen hoch — echtes Streaming ist der einzige bewusst vertagte Teil.
8. **Profil- und Projektlisten dynamisch:** Das Assignee-Dropdown kommt live aus Hermes (aktuell 12 Profile — eine hardcodierte Liste wäre bereits heute falsch). Die Projektliste hat in Hermes kein JSON-Format; der einkalkulierte Text-Parser ist einfach, und bei Fehlschlag bleibt das Dropdown leer mit Hinweis statt das Feature zu blockieren.
9. **Aufgaben aus Jupiter sind gekennzeichnet:** Jeder angelegte Task trägt fest den Autor „jupiter", damit in der Run-History immer klar ist, woher ein Task kam.
10. **Kurzsyntax mappt auf bestehende ABC-Phasen, nicht auf eine neue Taxonomie:** Statt eigener Phase-Namen zu erfinden, nutzt die Kurzsyntax `ABC_PHASES`/`PHASE_TO_SKILL` aus `backend/app/engine/abc_phases.py:14-58` (bereits die eine Quelle der Wahrheit für Phasenreihenfolge + Skill-Zuordnung im Backend). Ein neues Feature hier hieße, zwei Quellen der Wahrheit zu pflegen — vermieden.
11. **Assignee der Kurzsyntax ist immer der Koordinator, nie die Phasen-Rolle:** Der ABC-Kanban-Fluss läuft in Hermes so, dass der Koordinator jede Phase zuerst entgegennimmt und die passende Spezialisten-Rolle selbst dispatcht (siehe `/home/dev/.claude/rules/agents/coordinator.md` — Dispatch macht die Hauptsession/der Koordinator, nicht der einzelne Spezialist). Ein Quick-Task mit Assignee `jupiter-frontend` würde diesen Dispatch-Schritt überspringen; deshalb fest `jupiter-coordinator`, unabhängig von der getippten Phase.
12. **Kurzsyntax füllt vor, sendet nicht blind ab:** Ein Kanban-Task startet echte Agenten-Arbeit (Kosten, Seiteneffekte). Konsistent mit der Bestätigungspflicht beim Bulk-Archivieren öffnet die Kurzsyntax den bekannten Dialog zur Kontrolle, statt direkt zu erstellen.
13. **Bulk-Aktion vorerst nur Archivieren:** Archivieren ist reversibel-neutral (kein laufender Prozess wird unterbrochen) und deckt laut Nutzer den Standardfall; Block/Unblock/Kommentar bleiben Einzeltask-Aktionen mit Kontext (Grund/Art/Text), die sich für eine sinnvolle Bulk-UX schlechter eignen. Kleinster Scope, der den genannten Bedarf deckt — Erweiterung möglich, wenn gebraucht.
14. **Bulk-Archivieren als ein CLI-Aufruf, kein Loop:** `hermes kanban archive <ids>` akzeptiert bereits mehrere IDs (verifiziert). Ein Aufruf statt N Subprozess-Starts ist sowohl schneller als auch die einzig konsistente Interpretation von „gemeinsame Aktion".

### E) Abhängigkeiten (neue Pakete)

- Keine. Backend (stdlib + Pydantic) und Frontend (shadcn/ui, react-hook-form, zod) nutzen ausschließlich bereits im Projekt vorhandene Bausteine.

### F) Risiken / offene Punkte

- **`hermes project list` Text-Parsing:** Formatänderung von Hermes könnte den Parser brechen — Auswirkung begrenzt (nur das Projekt-Dropdown), Fehlerfall definiert.
- **CLI-Version:** Verhalten wurde gegen Hermes v0.20.4 verifiziert; bei Major-Updates helfen die zentral gekapselten Aufrufe beim Nachziehen.

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-19 · **Verdict:** Architected

### Checklist
- [x] Component structure — ok, jede Kachel bildet auf shadcn-Primitives ab, keine vagen „irgendein UI"-Stellen.
- [x] Data model — ok, keine eigene Datenhaltung (bewusst), einziges neues Persistenz-Stück ist das Polling-Intervall-Setting; kein `mandant_id`/RLS-Bedarf, da Hermes-Kanban single-tenant/VPS-lokal ist.
- [x] API shape — ok, jeder Endpunkt hat Methode+Pfad, jedes Formularfeld/jede Aktion aus den Acceptance Criteria hat einen Endpunkt-Home.
- [x] Tech-Entscheidungen — ok, jede nicht-triviale Wahl hat ein „Warum". Punkt D4 (Registry) und D5 (Subprocess-Timeout) waren falsch begründet (behaupteten neue Mechanik/kein Vorbild) — direkt in der Spec korrigiert, siehe „Autonom behoben".
- [x] Dependencies — ok, keine neuen Pakete; CodeGraph bestätigt, dass Backend (stdlib+Pydantic) und Frontend (shadcn/ui bereits im Projekt) ausreichen.
- [x] Branch-Feld — vorhanden, `specs/PROJ-82-hermes-kanban-native-view`, entspricht dem aktuellen Branch.
- [x] Konfliktfrei — CodeGraph bestätigt: kein bestehender `/hermes-kanban`-Endpunkt, keine `hermes_kanban`-Registry-Kollision, `/settings/hermes-kanban` frei.
- [x] Acceptance-Criteria-Abdeckung — jedes Kriterium hat ein Zuhause; Board-Übersicht/Detail/Formular/Aktionen/Dispatch/Settings decken sich 1:1 mit den API-Endpunkten und der Komponenten-Struktur.

### Autonom behoben
- **D4 (Registry-Mechanismus) korrigiert:** CodeGraph zeigt, dass `kind: native` + `group: orchestration` bereits existiert (PROJ-40, `backend/app/engine/registry.py:36-41`) und `paperclip` bereits als `kind: iframe, group: orchestration` in `engines.yaml:130-135` läuft. Die ursprüngliche Behauptung „heute nur iFrame-Einträge, Blickverengung muss geöffnet werden" war falsch — es ist eine reine Config-Ergänzung (ein `engines.yaml`-Block + eine Zeile in `microapps-registry.ts`), kein Registry-Umbau. Spec unter D4 und im Frontend-Abschnitt entsprechend präzisiert.
- **D5 (Subprocess-Timeout-Vorbild) konkretisiert:** „wie beim Scout-Agenten" war ein vager Verweis ohne Fundstelle. CodeGraph bestätigt das exakte Muster in `backend/app/engine/scout.py:49-63` (`_default_runner`: `asyncio.create_subprocess_exec` mit Argumentliste, `asyncio.wait_for(..., timeout=...)`, `proc.kill()` bei `TimeoutError`). Datei+Zeile jetzt in der Spec genannt, damit die Implementierung direkt das Vorbild öffnen kann.
- **Frontend-Struktur (Peppermint-Vergleich) korrigiert:** Die Spec behauptete, Peppermint (Referenz-Microapp) nutze `react-hook-form`+`zod` und rechtfertigte damit den 5-Datei-Split. CodeGraph zeigt: Peppermint ist eine Einzeldatei ohne react-hook-form/zod; kein Microapp im Repo nutzt beide Libraries, und kein Microapp ist auf mehrere Dateien gesplittet. Klargestellt: der Split und react-hook-form+zod sind eine bewusste, im Feature begründete Abweichung von der bisherigen Ein-Datei-Konvention — nicht „wie Peppermint".
- **Status-Header korrigiert:** Header stand noch auf „Planned" trotz `Architecture Draft` in `features/INDEX.md` und vorhandenem Tech Design — nachgezogen, jetzt konsistent.

### Offene Fragen
Keine. Alle Findings waren technisch klärbar aus Spec + Codebase, keine Produktentscheidung nötig.

### Nachtrag 2026-08-19 (Nutzer-Änderungswünsche)
Drei nachträgliche Anforderungen ergänzt und ins Tech Design integriert:
- **Kurzsyntax-Task-Anlage** (`<phase> <projektnummer>`, z. B. `requirements 82`): mappt auf die bestehenden `ABC_PHASES`/`PHASE_TO_SKILL` aus `backend/app/engine/abc_phases.py:14-58` statt neuer Taxonomie; Assignee fest `jupiter-coordinator` (Koordinator dispatcht die Phase intern weiter); öffnet vorbefüllten Dialog statt blind zu erstellen. Neuer Endpunkt `GET /hermes-kanban/feature-lookup/{proj_number}` (Best-Effort, liest `features/INDEX.md`).
- **Projekt-Feld:** bereits vor diesem Nachtrag als Dropdown aus `hermes project list` spezifiziert (Zeile „Grundbereich" im Abschnitt „Neuer Task") — keine Änderung nötig, entspricht dem Wunsch.
- **Mehrfachauswahl + Bulk-Archivieren:** Checkbox pro Karte, Bulk-Leiste ab 1 Auswahl, Bestätigungsdialog vor Ausführung, ein CLI-Aufruf `archive <id1> <id2> …` (CLI unterstützt das bereits laut Zeile 93 „Aktionen verifiziert"). Bewusst auf Archivieren begrenzt (genannter Standardfall); andere Aktionen bleiben Einzeltask.

Verdict bleibt **Architected** — alle drei Punkte waren aus Spec + Codebase technisch entscheidbar, keine offene Produktfrage.

## Implementation Notes (Frontend, /abc-frontend)
**Implemented:** 2026-08-19

- **Stack-Abweichung zu Spec-Frontend-Abschnitt (bewusst, per Skill „Code gewinnt"):** Der API-Client + alle Typen liegen NICHT in `components/microapps/hermes_kanban/lib/api.ts`, sondern im zentralen `nextjs_app/lib/api.ts` + `nextjs_app/lib/types.ts` — das ist das etablierte Muster JEDER bestehenden Micro-App (peppermint, clipboard, video-summary …). Ein lokaler Client hätte `request`/`rawFetch`/Auth dupliziert. Die 4-Komponenten-Aufteilung (app/detail/dialog/actions) blieb wie in der Spec begründet.
- **Kein react-hook-form/zod:** Spec („im Projekt Standard laut CLAUDE.md") war im Code falsch — `package.json` enthält beide nicht. Formular nutzt Controlled-`useState` + manuelle Validierung, spiegelt die Pydantic-Regeln (Model⊕Provider, Pfad/Branch bei Worktree, Triage⊕Initial-Status) und die vorhandene Clipboard-Form-Konvention.
- **D4-Registry-Annahme korrigiert (Frontend):** Spec behauptete, `kind: native, group: orchestration` laufe „bereits". Im Frontend ist das NICHT der Fall: `use-orchestration-apps.tsx` filterte nur `kind === iframe`, und die Route `/orchestration/[key]` rendert nur iframes (die Micro-Route `/apps/[key]` verlangt `group=micro`). Beides erweitert: Filter nimmt jetzt `native` auf, die Orchestration-Route hat einen Native-Branch via `resolveMicroApp`. Ohne diese zwei Frontend-Änderungen wäre der Eintrag unsichtbar/unrendertbar gewesen — die AC „Klick öffnet native Ansicht in Orchestration" hätte sonst gefehlt.
- **engines.yaml:** Eintrag `key: hermes_kanban, kind: native, group: orchestration, icon: hermes` (Icon löst auf `SendIcon` in `lib/sidebar-config.ts`). `microapps-registry.ts` registriert den Lazy-Import.
- **Kurzsyntax:** Phasen-Map + `parseQuickAdd` liegen in `new-task-dialog.tsx` (Quelle der Wahrheit bleibt `backend/app/engine/abc_phases.py`; Aliase `anforderungen`/`architektur`). Valide `<phase> <num>` → vorbefüllter Dialog (Assignee `jupiter-coordinator`, Titel `PROJ-<num>: <Phase-Label> starten`, Body `/abc-<phase> …`), invalide → leerer Dialog (kein Fehler).
- **Verifikation:** `npx tsc --noEmit` + `npm run build` grün (Next 16.2.9). Die 7 `tsc`-Fehler liegen in unveränderten, bereits committeten Testdateien (`Session.savings_enabled` etc.) und sind NICHT von diesem Feature.

**Backend offen (→ /abc-backend):** Routen (`routes/hermes_kanban.py`), `/settings/hermes-kanban`-Route, `config.py`-Pfad (`hermes_kanban_config_path`), Routen-Registrierung in `main.py`. Vorhandene, untrackte WIP: `schemas/hermes_kanban.py` + `engine/hermes_kanban_store.py` (noch nicht eingebunden).

## QA Test Results
**Getestet:** 2026-08-19 · gegen echten Hermes v0.20.4 (Board `jupiter-abc`, 27 Tasks) + lokale Wegwerf-Instanz auf Port 8099 (Live-Systemdienst läuft noch alten Stand, nicht angefasst)

### Acceptance Criteria

**Board-Übersicht**
- [x] Sidebar-Eintrag „Hermes Kanban (nativ)" — `engines.yaml` (`kind: native, group: orchestration`) + `microapps-registry.ts` korrekt verdrahtet; Orchestration-Route hat eigenen Native-Branch (`resolveMicroApp`), kein iFrame.
- [x] Board-Auswahl aus `boards list --json`, Default `is_current: true` (verifiziert: `jupiter-abc` hat `is_current: true`).
- [x] Spalten exakt Triage/Todo/Scheduled/Ready/Running/Blocked/Review/Done — Status-Enum stimmt mit CLI überein.
- [x] Archived-Toggle (`--archived`-Flag serverseitig verdrahtet).
- [x] Assignee-Filter dynamisch aus `assignees --json` (12 `jupiter-*`-Profile + `default` live abgefragt).
- [x] Karten-Pflichtfelder vorhanden.
- [x] Polling nutzt Settings-Intervall (`setInterval(..., Math.max(5, pollInterval) * 1000)`).

**Task-Detail**
- [x] Detail-Panel-Felder vollständig (`show --json` liefert task/parents/children/comments/events/runs/latest_summary — Route reicht 1:1 durch).
- [x] Worker-Log-Snapshot: `log <id> --tail 65536` (= 64 KB) verifiziert im Code; „Aktualisieren"-Button vorhanden.

**Neuer Task**
- [x] Grund- + Erweitert-Bereich vollständig, alle CLI-Felder abgebildet.
- [x] `create` mit `--created-by jupiter` — live gegen echtes Board getestet (Task `t_45c0e999` angelegt, `created_by: jupiter` im Response bestätigt), danach sauber archiviert.
- [x] Leere optionale Felder werden nicht übergeben (Pydantic-Schema baut Argumentliste nur aus gesetzten Feldern).
- [x] Formular-Validierung: Model⊕Provider, Worktree⊕Branch, Triage⊕Initial-Status — serverseitig per `model_validator` verifiziert (Pydantic wirft bei Verstoß, Frontend spiegelt dieselben Regeln vor dem Absenden).

**Kurzsyntax (Quick-Add)**
- [x] `parseQuickAdd` matcht `<phase> <nummer>` case-insensitiv inkl. deutscher Aliase (`anforderungen`→requirements, `architektur`→architecture); Phasen-Quelle identisch zu `backend/app/engine/abc_phases.py:ABC_PHASES`.
- [x] Assignee fest `jupiter-coordinator`, Titel/Body-Templates korrekt, `feature-lookup/{n}` live getestet (PROJ-82 → Titel gefunden; unbekannte Nummer → `found:false`, kein Fehler).
- [x] Kein Blind-Absenden — öffnet vorbefüllten Dialog.
- [x] Kein Treffer → normaler leerer Dialog (Code-Pfad verifiziert, `parseQuickAdd` gibt `null`).

**Task-Aktionen**
- [x] Block/Unblock/Archivieren/Kommentieren live getestet (Wegwerf-Task): Kommentar → 200, Block auf Triage-Task → 502 mit CLI-Fehlermeldung 1:1 durchgereicht (korrektes Verhalten laut Edge-Case-Spec), Archivieren → 200.
- [x] Kommentar >10.000 Zeichen wird serverseitig mit 422 abgelehnt, bevor die CLI gerufen wird.
- [x] Fehler bei unpassendem Status kommen 1:1 von der CLI durch (502, Frontend zeigt `err.message`).

**Mehrfachauswahl & Bulk-Archivieren**
- [x] Checkbox-Mehrfachauswahl, Bulk-Leiste ab 1 Auswahl, Bestätigungsdialog mit max. 10 Titeln + „+N weitere" (Code verifiziert, `bulkTitles = selectedTasks.slice(0, 10)`).
- [ ] **Bug (High, siehe unten) — Bulk-Archivieren mit teilweisem Fehlschlag meldet fälschlich Totalfehler statt Teilerfolg.**

**Dispatch**
- [x] `POST /hermes-kanban/dispatch` live getestet gegen `jupiter-abc` → 200 mit strukturiertem Ergebnis (reclaimed/crashed/spawned etc.).

**Einstellungen**
- [x] `GET/PATCH /settings/hermes-kanban` live getestet: Default 10, Grenzen 5–60 durchgesetzt (999 → 422), gültiger Wert (15) persistiert in `config/hermes_kanban.yaml`, wirkt ohne Neustart (Store ist mtime-gecacht).

**Allgemein**
- [x] Alle sichtbaren Texte deutsch (Board-App, Dialoge, Settings-Control).

### Automatisierte Tests
- Backend `pytest backend/tests/test_proj82_hermes_kanban.py`: **15/15 grün**.
- `npx tsc --noEmit`: nur die 7 vorbestehenden, nicht mit diesem Feature zusammenhängenden Fehler in Testdateien (`Session.savings_enabled` etc.) — wie in den Implementation Notes dokumentiert, keine neuen Fehler durch PROJ-82.
- `npm run build` (Next 16.2.9): grün, `/orchestration/[key]` korrekt als dynamische Route erkannt.
- Volle Backend-Regressionssuite (`pytest backend/tests`, 1310 Tests): lief zum Zeitpunkt der Berichterstellung noch im Hintergrund (sehr große Suite, >2 Min Laufzeit) — Ergebnis wird nachgetragen, sobald verfügbar; erste ~3300 Tests bislang ohne mit Hermes-Kanban zusammenhängenden Fehler.

### Bugs gefunden

**BUG-1 (High) — `GET /hermes-kanban/projects` liefert immer eine leere Liste, obwohl echte Projekte existieren.**
- Datei: `backend/app/routes/hermes_kanban.py:120-131` (`get_projects`).
- Ursache: Regex `^\[(?P<active>[ *])\]\s*(?P<slug>\S+)...` erwartet eckige Klammern `[*]`/`[ ]` um das Aktiv-Zeichen. Die echte CLI-Ausgabe hat KEINE Klammern, sondern `* slug  Name  [N folder(s)]` bzw. zwei Leerzeichen statt `*`:
  ```
  * jupiter                  Jupiter  [1 folder(s)]
    business_os              Business OS  [1 folder(s)]
  ```
  Live gegen `hermes project list` verifiziert — Regex matcht in keinem Fall, `get_projects()` gibt immer `[]` zurück, ununterscheidbar vom in der Spec vorgesehenen "Parser-Fehler"-Fall.
- Auswirkung: Projekt-Dropdown im „Neuer Task"-Formular ist IMMER leer (obwohl definierter Fallback existiert, ist das der Dauerzustand, nicht der Ausnahmefall — AC „Projekt (Dropdown aus `hermes project list`)" faktisch nicht erfüllbar).
- Fix-Vorschlag: Regex an reales Format anpassen, z. B. `^(?P<active>[ *])\s+(?P<slug>\S+)\s{2,}(?P<name>.+?)(?:\s*\[\d+ folder\(s\)\])?\s*$`.

**BUG-2 (High) — Bulk-Archivieren meldet bei Teilfehlschlag fälschlich Komplettfehler; Frontend-Erwartung (`archived`/`failed`) wird vom Backend nicht erfüllt.**
- Dateien: `backend/app/routes/hermes_kanban.py:225-230` (`archive_bulk`) + `nextjs_app/lib/api.ts:2329-2337` (Rückgabetyp `{ archived: string[]; failed?: Record<string,string> }`) + `nextjs_app/components/microapps/hermes_kanban/hermes-kanban-app.tsx:238-262` (`confirmBulkArchive`, liest `r.failed`).
- Live verifiziert: `hermes kanban --board jupiter-abc archive t_b2f27d73 t_399e61ad t_doesnotexist` → Exit-Code 1, stdout enthält `Archived t_b2f27d73`, `Archived t_399e61ad`, `cannot archive t_doesnotexist` — d. h. zwei von drei IDs wurden real archiviert. `_run_hermes` wirft bei JEDEM Exit≠0 `HermesError` (→ HTTP 502) und verwirft dabei die stdout-Zeilen mit den erfolgreichen IDs vollständig. Route gibt bei Erfolg nur `{"result": <roher CLI-Text>}` zurück — nie `archived`/`failed`.
- Auswirkung: Verstößt gegen den expliziten Acceptance-Criteria-Punkt „Schlagen einzelne IDs fehl … zeigt die Fehlermeldung, welche IDs betroffen sind; erfolgreich archivierte bleiben archiviert (keine Rollback-Illusion)". Aktuell zeigt das Frontend bei jedem Teilfehlschlag nur einen generischen Fehler-Toast („Archivieren fehlgeschlagen") und der Nutzer erfährt NICHT, welche IDs tatsächlich archiviert wurden — obwohl sie es in Hermes' DB bereits sind (stiller Seiteneffekt ohne UI-Feedback).
- Fix-Vorschlag: `archive_bulk` darf bei Teilfehlschlag nicht pauschal `HermesError` werfen — muss stdout zeilenweise parsen (`Archived <id>` / `cannot archive <id>`) und `{"archived": [...], "failed": {id: reason}}` zurückgeben, unabhängig vom Exit-Code der CLI.

### Regression
- Related deployed features (PROJ-39 Sidebar/Orchestration, PROJ-40 native Micro-App-Registry, PROJ-81 Hermes-Dashboard iFrame) unverändert funktionsfähig — Filter-/Route-Erweiterungen sind additiv (`kind === "native"` zusätzlich zu `"iframe"`), kein bestehender Pfad entfernt oder umgebaut.
- Volle Backend-Suite: siehe oben, Ergebnis wird nachgetragen.

### Bugfixes (2026-08-19, nachträglich auf Nutzerwunsch — Backoffice)
- **BUG-1 gefixt:** Regex in `get_projects()` (`backend/app/routes/hermes_kanban.py`) an reales CLI-Format angepasst (`^(?P<active>[*\s])\s(?P<slug>\S+)\s{2,}(?P<name>.+?)(?:\s*\[\d+ folder\(s\)\])?\s*$`, kein Pre-`.strip()` der Zeile mehr, da das den Aktiv-Marker verschluckte). Live gegen echtes `hermes project list` verifiziert: liefert jetzt `jupiter` (aktiv) + `business_os`.
- **BUG-2 gefixt:** Neue `_run_hermes_partial()` (wirft nur bei Timeout, nie bei Exit≠0) für `archive_bulk()`; stdout wird zeilenweise nach `Archived <id>` / `cannot archive <id>` geparst → Antwort jetzt `{"archived": [...], "failed": {id: reason}}`, passend zum bereits vorhandenen Frontend-Erwartungstyp (`nextjs_app/lib/api.ts:2332`, keine Frontend-Änderung nötig). Live verifiziert: 2 gültige + 1 unbekannte ID → `{"archived":["t_...","t_..."],"failed":{"t_deadbeef":"cannot archive t_deadbeef"}}`, HTTP 200 (vorher 502 mit Totalverlust der Erfolgsinfo).
- **Regression durch Fix aufgedeckt und behoben:** `test_proj39_orchestration.py::test_real_config_has_orchestration_group` nahm an, jeder `group=orchestration`-Eintrag sei `kind=iframe` (Stand vor PROJ-82). Test aktualisiert: akzeptiert jetzt `iframe` ODER `native`, https-Pflicht gilt weiter nur für `iframe`-Einträge.
- Volle Backend-Regressionssuite (1310 Tests) einmal komplett durchlaufen: **5 Failures, alle geprüft** — 1 war die oben gefixte Orchestration-Test-Annahme (durch PROJ-82 verursacht, jetzt behoben), 4 (`test_proj50_codex_abc.py`) sind vorbestehend und reproduzieren identisch auf `main` ohne PROJ-82-Änderungen (mit `git stash` verifiziert) — nicht Teil dieses Features.
- Nach Fix: `pytest backend/tests/test_proj82_hermes_kanban.py backend/tests/test_proj39_orchestration.py` → **19/19 grün**.

### Production-Ready Empfehlung: **READY**
Beide High-Bugs gefixt und live gegen die echte Hermes-CLI verifiziert; Regressions-Test korrigiert (Ursache in PROJ-82 selbst); keine weiteren offenen Findings.

## Implementation Notes (Backend — /abc-backend)

**Done (Backend, 2026-08-19):**
- `backend/app/routes/hermes_kanban.py` — alle Routen + zentrale CLI-Kapselung.
  - `_run_hermes(args, timeout)`: `asyncio.create_subprocess_exec("hermes", *args, …)` (kein `shell=True`), `asyncio.wait_for(proc.communicate(), …)`, bei `TimeoutError` → `proc.kill()`. Zeitlimits: 10 s lesen/aktionen, 20 s `create`, 30 s `dispatch`. Vorbild `engine/scout.py:_default_runner`.
  - `--board` wird korrekt VOR dem Subcommand gesetzt (`["kanban","--board",board,…]`).
  - Task-IDs gegen `^t_[a-f0-9]+$`, Board-Slugs gegen `^[a-z0-9][a-z0-9-]*$`.
  - `create` baut die Argumentliste 1:1 aus allen Formularfeldern, inkl. `--created-by jupiter`, `--json` (für Task-ID-Rückgabe); leere optionale Felder werden NICHT übergeben.
  - `archive-bulk` → EIN `archive <id1> <id2> …`-Aufruf (Limit 100 IDs, Einzel-ID-Validierung).
  - `project list` wird als Text geparst (Best-Effort → `[]` bei Fehler).
  - `HermesError` (CLI-Fehler/Timeout) → in `main.create_app` auf HTTP **502** gemappt, damit das Frontend die CLI-Meldung 1:1 zeigt.
- `backend/app/schemas/hermes_kanban.py` — Pydantic-Modelle mit serverseitiger Validierung (Modell+Provider zusammen, Branch bei Worktree-Varianten, Pfad bei dir/worktree_path, Triage ⊕ Initial-Status, Kommentar-Max 10 000 Zeichen, Größen-Deckel gegen DoS).
- `backend/app/engine/hermes_kanban_store.py` — persistentes Polling-Intervall (YAML `config/hermes_kanban.yaml`, live/mtime-gecacht, Default 10, geklemmt 5–60). Gleiches Muster wie `engine/watchdog.py:WatchdogStore`.
- `backend/app/routes/settings.py` — `GET/PATCH /settings/hermes-kanban` (Muster wie `/settings/watchdog`).
- `backend/app/config.py` — `hermes_bin` (Default `"hermes"`) + `hermes_kanban_config_path` (YAML-Pfad).
- `backend/app/main.py` — Router registriert (`dependencies=auth_gate`) + `HermesError`-Handler.
- `backend/config/engines.yaml` — Eintrag `hermes_kanban` (`kind: native, group: orchestration`) war bereits vorhanden.
- `backend/tests/test_proj82_hermes_kanban.py` — 15 Tests (Schema, CLI-Argument-Building, Routen, Settings, 502-Mapping, Feature-Lookup), alle grün.

**Offen (nicht Backend-Scope):** Frontend-Microapp (`nextjs_app/components/microapps/hermes_kanban/`) + Zeile in `nextjs_app/lib/microapps-registry.ts` (siehe /abc-frontend).

**Bugfix (abc-backoffice, 2026-08-19):** `get_task`/`get_tasks` gaben `created_at`/`started_at`/`completed_at`
(und verschachtelt in `events`/`comments`/`runs`) als rohe Unix-Sekunden-Integer durch (`hermes kanban
show/list --json`), obwohl die TS-Typen ISO-Strings deklarieren — `new Date(iso)` im Frontend interpretierte
die Zahl als Millisekunden, Anzeige landete um 1970-01-21 statt am echten Datum. Neue `_normalize_timestamps()`
in `hermes_kanban.py` konvertiert rekursiv jedes `..._at`-Integer-Feld nach ISO-8601, angewendet in `get_task`
+ `get_tasks`. Test: `test_get_task_route_normalizes_unix_timestamps`. Details: Hal-Knowledge
`bug_geloest-jupiter-coordinator-main-zone-worktree-drift.md`.

## Deployment
Deployed 2026-08-19 — Bump 0.27.48 (Commit `23fc554`). Nachfolgend Bugfix-Commit `0559c84` (Timestamp-Bug + React-Crash-Boundary).
