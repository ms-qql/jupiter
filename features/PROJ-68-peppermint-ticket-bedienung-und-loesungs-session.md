# PROJ-68: Peppermint Ticket-Bedienung und Lösungs-Session

## Status: Approved
**Created:** 2026-07-08
**Last Updated:** 2026-07-08

## Dependencies
- Requires: PROJ-67 (Peppermint Dashboard + automatische Frontdesk-Triage) — nutzt den lokalen Peppermint-Ticket-Spiegel, Analysezustände, Frontdesk-Reports und die native Micro-App.
- Requires: PROJ-9 / PROJ-34 (Smart Launcher + Chat-Modus) — eine Ticket-Lösungs-Session startet als normale Jupiter-Session mit vorbefülltem Prompt statt als automatische Triage.
- Requires: PROJ-1 / PROJ-48 / PROJ-50 (Engine-Sessions + Codex/abc-Workflow) — die neue Session muss wie jede andere Jupiter-Session sichtbar und steuerbar sein.
- Bezug: PROJ-21 (Session-Löschen / Cockpit-Aufräumen) — UX-Muster für bestätigte destruktive Aktionen.

## Beschreibung
Das bestehende **Peppermint Dashboard** wird von einem reinen Analyse-Viewer zu einer Arbeitsoberfläche für Ticket-Triage und Ticket-Bearbeitung erweitert. In der Ticketliste und im Detailbereich sollen pro Ticket direkte Aktionen verfügbar sein:

- **Auge:** Ticket/Nachricht lokal ausblenden, wenn sie aktuell nicht relevant ist.
- **Papierkorb:** Ticket/Nachricht komplett löschen bzw. aus Jupiter entfernen, insbesondere für interne Testläufe, Weiterleitungen oder Inhalte, die keine echten Kundentickets sind.
- **Editieren:** Projekt, Priorität, Typ und Status direkt im Dashboard setzen.
- **Lösungs-Session starten:** Für analysierte Tickets eine neue Jupiter-Session öffnen, deren Startkontext auf die Ticketnummer und den Analyse-Report verweist.

Die neue Klassifikation ist eine Jupiter-Arbeitsschicht auf dem Peppermint-Ticket-Spiegel. Peppermint bleibt das Quellsystem; `/abc-architecture` entscheidet, welche Felder bidirektional nach Peppermint zurückgeschrieben werden können und welche nur lokal in Jupiter gepflegt werden.

## User Stories
- Als Nutzer möchte ich einzelne Tickets über ein **Auge-Icon** ausblenden können, damit interne Testtickets oder irrelevante Nachrichten meine operative Liste nicht verstopfen.
- Als Nutzer möchte ich Tickets über ein **Papierkorb-Icon** löschen bzw. dauerhaft aus dem Dashboard entfernen können, damit eindeutig irrelevante Nicht-Tickets nicht weiter synchronisiert oder analysiert werden.
- Als Nutzer möchte ich einem Ticket ein **Projekt** zuweisen können, damit später klar ist, in welchem Code-/Kundenkontext die Lösung erfolgen soll.
- Als Nutzer möchte ich eine **Priorität** setzen können: **Niedrig, Mittel, Hoch, Dringend**.
- Als Nutzer möchte ich einen **Typ** setzen können: **Frage, Incident, Problem, Feature Request, Sonstiges**.
- Als Nutzer möchte ich den **Status** setzen können: **Offen, Zugewiesen, On Hold, Gelöst, Geschlossen**.
- Als Nutzer möchte ich bei analysierten Tickets eine neue **Jupiter-Lösungs-Session** starten können, damit ich direkt vom Frontdesk-Report in die Bearbeitung wechseln kann.
- Als Nutzer möchte ich, dass die neue Session eindeutig auf die **Ticketnummer** und den vorhandenen Analyse-Report verweist, damit der Agent nicht raten muss, welches Ticket gemeint ist.

## Acceptance Criteria
- [ ] Jede Ticketzeile zeigt kompakte Icon-Aktionen: **Auge** für Ausblenden, **Papierkorb** für Löschen/Entfernen und **Bearbeiten** für Klassifikation; Icon-only Controls haben Tooltips auf Deutsch.
- [ ] Die Ticketlisten-Kachel behält ihre vorgesehene Höhe; wenn mehr Tickets vorhanden sind, als in die Kachel passen, scrollt die Ticketliste **vertikal innerhalb der Kachel** statt die gesamte Dashboard-Seite zu verlängern.
- [ ] **Ausblenden** entfernt das Ticket aus der Standardliste, ohne den lokalen Datensatz, den Analyse-Report oder die Peppermint-Verknüpfung zu löschen.
- [ ] Es gibt einen Filter oder Umschalter **„Ausgeblendete anzeigen"**, über den ausgeblendete Tickets sichtbar werden und per Aktion **„Einblenden"** zurückgeholt werden können.
- [ ] **Löschen/Entfernen** verlangt eine Bestätigung mit Ticket-ID/Betreff und erklärt, ob nur Jupiter oder auch Peppermint betroffen ist.
- [ ] Nach bestätigtem Löschen erscheint das Ticket nicht mehr in der Standardliste und wird durch Polling/Webhook nicht still erneut importiert; dafür wird eine lokale Tombstone-/Ignore-Markierung geführt.
- [ ] Wenn die konkrete Peppermint-API ein echtes Löschen unterstützt, kann `/abc-architecture` den Papierkorb als Peppermint-Delete plus lokale Tombstone-Markierung auslegen; wenn nicht, ist der MVP-Papierkorb eine dauerhafte Jupiter-Entfernung/Ignore-Aktion.
- [ ] Der Bearbeiten-Dialog oder Inline-Editor erlaubt die Auswahl eines **Projekts** aus einer Dropdown-Liste vorhandener Jupiter-Projekte/Arbeitsbereiche; wenn keine Projekte geladen werden können, bleibt die aktuelle Zuordnung erhalten und eine deutsche Fehlermeldung wird angezeigt.
- [ ] Der Bearbeiten-Dialog erlaubt die Auswahl genau einer Priorität aus: **Niedrig · Mittel · Hoch · Dringend**.
- [ ] Der Bearbeiten-Dialog erlaubt die Auswahl genau eines Typs aus: **Frage · Incident · Problem · Feature Request · Sonstiges**.
- [ ] Der Bearbeiten-Dialog erlaubt die Auswahl genau eines Status aus: **Offen · Zugewiesen · On Hold · Gelöst · Geschlossen**.
- [ ] Gespeicherte Projekt-, Prioritäts-, Typ- und Statuswerte sind in Ticketliste und Detailbereich sichtbar.
- [ ] Manuell gesetzte Werte überleben Reload und Backend-Neustart.
- [ ] Filter für Priorität, Typ, Status und Projekt berücksichtigen die manuell gesetzten Werte.
- [ ] Priorität, Typ und Status sind jeweils direkt filterbar und können miteinander kombiniert werden, z. B. **Typ = Incident** plus **Priorität = Hoch** plus **Status = Offen**.
- [ ] Das Suchfeld durchsucht neben Betreff, Kunde und Kurzbefund auch **Typ**, **Status** und **Priorität**.
- [ ] Suche und Filter sind kombinierbar: Ein Suchbegriff schränkt die bereits gesetzten Filter weiter ein, ohne sie zurückzusetzen.
- [ ] Für analysierte Tickets zeigt der Detailbereich eine Aktion **„Lösungs-Session starten"**.
- [ ] **„Lösungs-Session starten"** erstellt eine neue normale Jupiter-Session mit Projektpfad aus der Projektzuordnung (falls gesetzt) oder mit einem sicheren Default-Projektpfad.
- [ ] Der Initial-Prompt der neuen Session enthält mindestens: Peppermint-Ticket-ID, lokaler Jupiter-Ticket-Datensatz, Betreff, Kundendaten soweit vorhanden, aktuelle Projekt-/Prioritäts-/Typ-/Statuswerte, Link zum Peppermint-Ticket und den vollständigen Frontdesk-Report.
- [ ] Die neue Session verweist ausdrücklich auf die Ticketnummer aus dem Analyse-Report und formuliert den Auftrag: Ticket lösen bzw. nächsten umsetzbaren Schritt erarbeiten.
- [ ] Nach erfolgreichem Start wird die Session in Jupiter geöffnet bzw. sichtbar hervorgehoben; das Ticketdetail zeigt die verknüpfte Session-ID.
- [ ] Ein Ticket kann nicht mehrfach unbeabsichtigt parallele Lösungs-Sessions starten: Bei bereits verknüpfter aktiver Session bietet die UI **„Session öffnen"** und optional **„Neue weitere Session starten"** nach Bestätigung.
- [ ] Alle UI-Texte, Tooltips, Bestätigungsdialoge und Fehlermeldungen sind **deutsch**.

## Edge Cases
- **Ticket ist kein Kundenticket** → Nutzer setzt Typ „Sonstiges" oder löscht/entfernt es; es wird nicht erneut automatisch importiert.
- **Ticket wurde ausgeblendet und erhält später ein Peppermint-Update** → es bleibt ausgeblendet, zeigt im „Ausgeblendete anzeigen"-Filter aber den aktualisierten Zeitstempel.
- **Peppermint-Ticket wurde außerhalb von Jupiter gelöscht** → lokaler Datensatz bleibt mit Hinweis „Ticket in Peppermint nicht mehr abrufbar"; Löschen/Entfernen bleibt lokal möglich.
- **Peppermint-Delete schlägt fehl oder ist nicht verfügbar** → Jupiter zeigt eine deutsche Fehlermeldung und bietet lokale Entfernung/Ignore an, ohne fälschlich einen erfolgreichen Peppermint-Delete zu behaupten.
- **Pflichtwerte fehlen im Bearbeiten-Dialog** → Speichern ist blockiert oder nutzt definierte Defaults: Priorität „Niedrig", Typ „Sonstiges", Status „Offen"; Projekt darf leer bleiben.
- **Projektliste kann nicht geladen werden** → Dropdown zeigt Fehlerzustand; bestehende Zuordnung wird nicht überschrieben.
- **Status „Geschlossen" bei noch laufender Analyse** → Analyse darf fertiglaufen; UI zeigt beide Zustände getrennt (Ticketstatus geschlossen, Analysezustand läuft/analysiert).
- **Lösungs-Session für nicht analysiertes Ticket** → Aktion ist deaktiviert mit Tooltip „Erst nach Analyse verfügbar" oder startet nur nach bewusster Bestätigung mit reduziertem Kontext.
- **Analyse-Report ist sehr lang** → Initial-Prompt enthält eine klare Zusammenfassung plus Referenz auf den vollständigen gespeicherten Report; kein stilles Abschneiden ohne Hinweis.
- **Session-Start schlägt fehl** → Ticket bleibt unverändert, Fehler wird im Detailbereich angezeigt, Start kann erneut versucht werden.
- **Mehrere Browser-Tabs bearbeiten dasselbe Ticket** → letzter gespeicherter Wert gewinnt; UI aktualisiert beim nächsten Refresh und zeigt keine widersprüchlichen Zwischendaten.
- **Gelöschtes/ignoriertes Ticket kommt erneut per Polling/Webhook** → Tombstone verhindert Reimport, außer der Nutzer hebt die Ignorierung bewusst auf.

## Technical Requirements (optional)
- **Frontend:** Erweiterung der nativen Micro-App `peppermint_dashboard`: Aktionen in Ticketzeile/Detaildrawer, deutscher Confirm-Dialog, Editor mit Dropdowns, neue Filter und Zustand für ausgeblendete/gelöschte Tickets.
- **Icons:** bestehendes Icon-Set nutzen (z. B. Auge, Papierkorb, Bearbeiten/Settings, Play/Terminal für Session-Start); Icon-only Controls mit Tooltip und zugänglichem Label.
- **Persistenz:** lokaler Ticket-Spiegel bekommt Felder für `hidden_at`, `deleted_at`/`ignored_at`, `project_key` oder `project_path`, `manual_priority`, `manual_type`, `manual_status`, `resolution_session_id` und Änderungszeitstempel.
- **Enum-Werte:** interne stabile Werte sollen von deutschen Labels getrennt sein, damit spätere API-/Peppermint-Syncs robust bleiben.
- **API:** FastAPI-Routen für Patch/Edit, Hide/Unhide, Delete/Ignore, optional Restore aus Tombstone, und Start/Open einer Lösungs-Session.
- **Session-Start:** nutzt den bestehenden Jupiter-Session-Mechanismus; keine neue Engine-Art. Die Session wird mit einem strukturierten deutschen Initial-Prompt gestartet, der Ticket-ID und Analyse-Report referenziert.
- **Rücksync:** `/abc-architecture` entscheidet, ob Priorität/Status nach Peppermint zurückgeschrieben werden; MVP darf lokale Jupiter-Felder priorisieren, solange das UI klar benennt, welche Werte lokal sind.
- **Sicherheit:** destruktive Aktionen müssen bestätigt werden; Tokens/Secrets bleiben serverseitig; keine automatische öffentliche Kundenantwort.
- **Texte deutsch.**

### Open Points (für /abc-architecture zu klären)
1. **Peppermint-Delete:** Gibt es in der installierten Peppermint-Version einen verlässlichen Delete-Endpunkt für Tickets, oder bleibt Löschen im MVP bewusst eine lokale Ignore/Tombstone-Aktion?
2. **Projektquelle:** Welche bestehende Jupiter-Projektliste ist die kanonische Quelle für das Projekt-Dropdown (Workspace-Registry, aktuelle Session-Projekte, `features/INDEX.md`-Projektpfade oder konfigurierbare Liste)?
3. **Peppermint-Rücksync:** Welche manuellen Felder sollen nach Peppermint zurückgeschrieben werden: Status, Priorität, beides oder nur lokale Jupiter-Klassifikation?
4. **Default-Projektpfad:** Welcher Projektpfad wird für eine Lösungs-Session genutzt, wenn keine Projektzuordnung gesetzt ist?
5. **Session-Modus:** Soll die Lösungs-Session standardmäßig als Workflow/ABC-Session, als Chat-Session oder abhängig vom zugewiesenen Projekt/Typ starten?
6. **Wiederherstellung gelöschter Tickets:** Braucht der MVP eine UI für „Gelöschte anzeigen/wiederherstellen" oder reicht eine technische Tombstone-Liste ohne Standard-UI?

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-08 · **Stack:** Next.js 16 native Micro-App + FastAPI + SQLite-Ticketspiegel + Jupiter SessionManager · **Branch:** dev

### Vorprüfung / Ist-Stand
- Jupiter ist in diesem Repo eine **Next.js + FastAPI**-App, nicht Flutter. PROJ-68 erweitert die vorhandene native Micro-App `peppermint_dashboard`.
- PROJ-67 ist auf `dev` bereits als lokaler Peppermint-Spiegel umgesetzt: SQLite-Repository, FastAPI-Router `/peppermint`, Pydantic-Schemas, Next.js-Typen/API-Client und React-Dashboard.
- Es gibt weiterhin kein Alembic-/SQL-Migrationsverzeichnis; die bestehende Micro-App-Persistenz nutzt idempotente SQLite-Schema-Erweiterungen im Repository.
- Die vorhandene Ticketliste filtert bisher nach Analysezustand, Dringlichkeit, Peppermint-Status und Suchtext. PROJ-68 ergänzt lokale Arbeitsfelder und erweitert die Filterlogik.
- Der bestehende SessionManager kann normale Jupiter-Sessions mit `project_path`, `initial_prompt`, Engine/Modell und optionaler `ticket_id` starten. PROJ-68 nutzt diesen Mechanismus, statt eine neue Session-Art einzuführen.

### Architektur-Entscheidungen
- **Papierkorb im MVP = lokale Entfernung/Ignore, kein produktiver Peppermint-Delete.** Ein echter Peppermint-Ticket-Delete ist in PROJ-67 nicht verifiziert und wäre risikoreich. Jupiter markiert entfernte Tickets lokal als ignoriert, blendet sie aus und importiert sie bei Polling/Webhook nicht still erneut.
- **Ausblenden bleibt reversibel.** Ausgeblendete Tickets behalten Analyse-Report, Peppermint-Link und lokale Klassifikation. Sie verschwinden nur aus der Standardansicht.
- **Manuelle Klassifikation ist lokale Jupiter-Arbeitsschicht.** Projekt, Priorität, Typ und Status werden im MVP nicht automatisch nach Peppermint zurückgeschrieben. Das verhindert ungewollte Änderungen am Ticketsystem.
- **Projekt-Dropdown kommt vom Backend.** Das Frontend soll keine Pfade erraten. Eine kleine Projektoptionen-Quelle liefert erlaubte Projektpfade aus bestehenden Jupiter-Kontexten.
- **Lösungs-Session = normale Jupiter-Session ohne ABC-Zwang.** Support-Tickets sind nicht automatisch `features/PROJ-X`. Die Session bekommt einen strukturierten Startprompt mit Ticketnummer und Frontdesk-Report, läuft aber als normale Session im gewählten Projektpfad.
- **Default-Projektpfad ist `/home/dev/projects/jupiter`.** Wenn noch kein Projekt zugewiesen ist, startet Jupiter in einem sicheren vorhandenen Projektpfad innerhalb der erlaubten Roots. Die UI soll trotzdem deutlich zeigen, dass eine Projektzuordnung fehlt.

### A) Komponenten-Struktur
```
/apps/peppermint_dashboard
└── PeppermintDashboardApp
    ├── KpiLeiste
    │   └── ergänzt um lokale Arbeitsstatus optional: ausgeblendet · ignoriert · Lösungs-Sessions
    ├── FilterLeiste
    │   ├── Analysezustand
    │   ├── Dringlichkeit / Frontdesk-Priorität
    │   ├── Projekt
    │   ├── Typ
    │   ├── Ticketstatus
    │   ├── Ausgeblendete anzeigen
    │   └── Suche über Betreff · Kunde · Kurzbefund · Typ · Status · Priorität
    ├── TicketTabelle
    │   └── TicketZeile
    │       ├── ID · Betreff · Kunde · Projekt · Typ · Priorität · Status · Analyse
    │       └── Aktionen: Auge · Bearbeiten · Papierkorb
    ├── TicketDetail
    │   ├── Arbeitsklassifikation als Badges
    │   ├── Frontdesk-Report
    │   ├── Aktionen: Ein-/Ausblenden · Bearbeiten · Entfernen · Lösungs-Session starten/öffnen
    │   └── verknüpfte Session-ID, falls vorhanden
    ├── TicketEditDialog
    │   └── Projekt-Dropdown · Priorität · Typ · Status
    ├── DeleteConfirmDialog
    │   └── erklärt lokale Entfernung/Ignore mit Ticket-ID und Betreff
    └── Loading/Error/Empty-Zustände
```

### B) Datenmodell (Klartext)
Der vorhandene lokale Ticket-Spiegel wird erweitert. Pro Ticket werden zusätzlich gespeichert:
- **Sichtbarkeit:** `hidden_at` für reversibles Ausblenden.
- **Ignore/Tombstone:** `ignored_at`, `ignored_reason` und optional `ignored_by`, damit Polling/Webhook dieselbe Peppermint-ID nicht neu als aktives Ticket importiert.
- **Manuelle Klassifikation:** Projektpfad/Projektlabel, Priorität, Typ, Status.
- **Lösungs-Session:** verknüpfte Jupiter-Session-ID, Startzeit und letzter Startfehler.
- **Zeitstempel:** `updated_at` bleibt die allgemeine Änderungsmarke; neue lokale Aktionen aktualisieren sie.

Stabile interne Enum-Werte und deutsche Labels werden getrennt:
- Priorität: `low`, `medium`, `high`, `urgent` → Niedrig, Mittel, Hoch, Dringend.
- Typ: `question`, `incident`, `problem`, `feature_request`, `other` → Frage, Incident, Problem, Feature Request, Sonstiges.
- Status: `open`, `assigned`, `on_hold`, `resolved`, `closed` → Offen, Zugewiesen, On Hold, Gelöst, Geschlossen.

Projektoptionen enthalten mindestens:
- Anzeigename.
- Absoluter Projektpfad innerhalb `allowed_roots`.
- Hinweis, ob das Projekt einen abc-Kontext hat.

Kein MinIO: PROJ-68 speichert keine Dateien oder Anhänge.

### C) Backend-Bausteine
**PeppermintRepository-Erweiterung**
- Fügt lokale Arbeitsfelder zum bestehenden SQLite-Spiegel hinzu.
- Filtert Standardlisten so, dass ignorierte Tickets nicht erscheinen und ausgeblendete Tickets nur bei aktivem Filter sichtbar werden.
- Beachtet Tombstones beim Upsert: bekannte ignorierte Peppermint-IDs bleiben ignoriert und starten keine neue Analyse.

**PeppermintTriageWorker-Erweiterung**
- Ingest/Polling darf ignorierte Tickets nicht erneut als aktiv einreihen.
- Analyse- und Notiz-Sync-Worker überspringen ignorierte Tickets.
- Ausblenden beeinflusst Analyse und Sync nicht rückwirkend; es ist nur UI-Sichtbarkeit.

**Projektoptionen-Service**
- Liefert eine kleine, erlaubte Auswahl von Projektpfaden für das Dropdown.
- Quelle: bekannte Session-Projekte, direkte Projektordner unter erlaubten Roots und mindestens `/home/dev/projects/jupiter` als Fallback.
- Pfade werden serverseitig gegen die bestehende `allowed_roots`-Logik validiert.

**ResolutionSessionService**
- Baut aus Ticket, lokaler Klassifikation und Frontdesk-Report einen deutschen Startkontext.
- Startet über den bestehenden SessionManager eine normale Session.
- Speichert die verknüpfte Session-ID zurück am Ticket.
- Wenn bereits eine aktive verknüpfte Session existiert, liefert der Backend-Pfad diese zurück, statt unbemerkt eine zweite Session zu starten.

### D) API-Shape
Erweiterungen unter `/peppermint`:
- `GET /peppermint/tickets` → zusätzliche Filter: Projekt, Typ, Priorität, manueller Status, ausgeblendete anzeigen; Suche berücksichtigt Typ, Status und Priorität.
- `PATCH /peppermint/tickets/{id}` → lokale Klassifikation ändern: Projekt, Priorität, Typ, Status.
- `POST /peppermint/tickets/{id}/hide` → Ticket aus Standardliste ausblenden.
- `POST /peppermint/tickets/{id}/unhide` → Ticket wieder einblenden.
- `POST /peppermint/tickets/{id}/ignore` → lokale Entfernung/Tombstone nach Bestätigung.
- `POST /peppermint/tickets/{id}/restore` → optionaler Restore aus lokaler Ignore-Markierung für QA/Admin-Fälle.
- `POST /peppermint/tickets/{id}/resolution-session` → Lösungs-Session starten oder vorhandene verknüpfte Session zurückgeben.
- `GET /peppermint/project-options` → erlaubte Projektoptionen für das Dropdown.

Bestehende Routen bleiben kompatibel:
- `GET /peppermint/tickets/{id}` gibt die neuen lokalen Felder mit aus.
- `GET /peppermint/summary` kann ignorierte Tickets standardmäßig ausschließen und optional neue lokale Zählwerte liefern.

### E) Lösungs-Session-Ablauf
1. Nutzer öffnet ein analysiertes Ticket.
2. Nutzer prüft oder setzt Projekt, Priorität, Typ und Status.
3. Nutzer klickt **„Lösungs-Session starten"**.
4. Backend prüft: Ticket existiert, ist nicht ignoriert, hat idealerweise Analysezustand `analysiert`, Projektpfad ist erlaubt.
5. Backend erstellt den Startprompt mit:
   - Peppermint-ID und lokaler Jupiter-Ticket-ID.
   - Betreff, Kunde, Ticket-Link und relevanten Metadaten.
   - Projekt, Priorität, Typ und Status.
   - Vollständigem Frontdesk-Report oder, bei sehr langem Report, klarer Zusammenfassung plus gespeicherter Reportreferenz.
   - Auftrag: Ticket lösen oder den nächsten umsetzbaren Schritt erarbeiten.
6. SessionManager startet eine normale Session im Projektpfad.
7. Ticket speichert die Session-ID; UI öffnet oder hebt die Session sichtbar hervor.

### F) Filter- und Suchverhalten
- Filter sind serverseitig kombinierbar: Analysezustand, Dringlichkeit, Projekt, Typ, Priorität, Status und Sichtbarkeit wirken gemeinsam.
- Suchtext schränkt gesetzte Filter weiter ein und setzt sie nicht zurück.
- Suchtext durchsucht mindestens Betreff, Kunde/E-Mail, Kurzbefund, Typ-Label, Status-Label und Prioritäts-Label.
- Standardansicht zeigt keine ignorierten Tickets und keine ausgeblendeten Tickets.
- „Ausgeblendete anzeigen" zeigt ausgeblendete Tickets zusätzlich, nicht ausschließlich, sofern keine weitere Sichtbarkeitsoption gewählt wird.

### G) Layout-Entscheidung Ticketliste
- Die Ticketlisten-Kachel behält die heutige Dashboard-Größe, damit Detailbereich und KPI-/Filterbereich stabil bleiben.
- Nur der Tabellenbereich innerhalb der Kachel wird vertikal scrollbar, wenn mehr Tickets vorhanden sind als sichtbar passen.
- Der Tabellenkopf bleibt nach Möglichkeit sichtbar, während die Ticketzeilen scrollen.
- Horizontales Scrollen für breite Tabellen bleibt weiterhin innerhalb der Ticketlisten-Kachel und darf nicht die gesamte Seite verbreitern.

### H) Tech-Entscheidungen (WARUM)
- **Lokaler Ignore statt Peppermint-Delete:** sicherer für echte Kundendaten und ausreichend für den konkreten Bedarf, irrelevante Nicht-Tickets aus Jupiter fernzuhalten.
- **Lokale Klassifikation statt sofortiger Rücksync:** Status-/Prioritäts-Semantik zwischen Jupiter und Peppermint ist nicht garantiert gleich. Lokale Felder verhindern Nebenwirkungen und lassen späteren Rücksync bewusst nachziehen.
- **Backend-validiertes Projekt-Dropdown:** Projektpfade sind sicherheitsrelevant, weil sie Session-CWDs werden. Deshalb kommen Optionen vom Server und werden dort validiert.
- **Normale Session statt neuer Terminaltyp:** Jupiter hat bereits Session-Lifecycle, Sidebar, Limits, Transkript und Recovery. Eine neue Session-Art würde doppelten Lifecycle erzeugen.
- **Tombstone bleibt beim Reimport maßgeblich:** Ohne Tombstone würden Polling/Webhook gelöschte Nicht-Tickets immer wieder zurückbringen. Das wäre für Frontdesk-Triage operativ störend.
- **Keine neue Infrastruktur:** SQLite-Spiegel und FastAPI-Router reichen. PROJ-68 ist eine Erweiterung vorhandener PROJ-67-Daten, kein neues System.

### I) Abhängigkeiten
- **Backend:** keine neuen Pakete. Bestehende SQLite-, FastAPI- und SessionManager-Muster reichen.
- **Frontend:** keine neuen Pakete. Bestehende shadcn/ui-Komponenten, Dialoge, Selects, Inputs, Badges und lucide Icons reichen.
- **Externe Systeme:** kein neuer Peppermint-Endpunkt im MVP zwingend. Optionaler echter Peppermint-Delete oder Rücksync bleibt Fast-Follow nach separater API-Verifikation.

### J) Bau-Reihenfolge / Hand-offs
1. **Backend zuerst:** lokale Felder, idempotente Schema-Erweiterung, Filter, Hide/Unhide, Ignore/Restore, Projektoptionen, Resolution-Session-Start.
2. **Frontend danach:** Ticketaktionen, Klassifikationsdialog, kombinierte Filter, ausgeblendete Ansicht, Lösungs-Session-Button.
3. **QA:** Tombstone gegen Reimport, kombinierte Filter, Suche über neue Labels, Reload/Neustart-Persistenz, Session-Start mit und ohne Projektzuordnung, Doppelstart-Schutz.

### K) Referenz-Dateien
- Bestehendes Peppermint-Backend: `backend/app/db/peppermint_queue.py`, `backend/app/engine/peppermint.py`, `backend/app/routes/peppermint.py`, `backend/app/schemas/peppermint.py`
- Bestehendes Peppermint-Frontend: `nextjs_app/components/microapps/peppermint_dashboard/peppermint-dashboard-app.tsx`, `nextjs_app/lib/api.ts`, `nextjs_app/lib/types.ts`
- Session-Start: `backend/app/engine/manager.py`, `backend/app/routes/sessions.py`
- Projekt-/Pfadvalidierung: `backend/app/engine/manager.py`, `backend/app/routes/projects.py`

## Implementation Notes (Backend, abc-backend)
**Stand:** 2026-07-08 · **Branch:** dev

- Backend-Erweiterung ist umgesetzt in `backend/app/db/peppermint_queue.py`, `backend/app/engine/peppermint.py`, `backend/app/routes/peppermint.py`, `backend/app/schemas/peppermint.py`.
- Der lokale SQLite-Ticketspiegel wurde idempotent um PROJ-68-Felder erweitert: `hidden_at`, `ignored_at`, Ignore-Grund, Projektpfad/-Label, manuelle Priorität, Typ, Status und verknüpfte Lösungs-Session.
- Standardlisten schließen ignorierte und ausgeblendete Tickets aus; `include_hidden` und `include_ignored` erlauben explizite Sichtbarkeit.
- Kombinierte Filter sind backendseitig verfügbar: Analysezustand, Dringlichkeit, Peppermint-Status, Projektpfad, manuelle Priorität, Typ, Status und Suchtext.
- Suchtext findet zusätzlich deutsche/englische Enum-Labels für Priorität, Typ und Status, z. B. „hoch", „incident", „gelöst".
- Neue API-Endpunkte: `PATCH /peppermint/tickets/{id}`, `POST /hide`, `POST /unhide`, `POST /ignore`, `POST /restore`, `POST /resolution-session`, `GET /peppermint/project-options`.
- Lösungs-Sessions starten über den bestehenden Jupiter `SessionManager` als normale Session im zugewiesenen Projektpfad oder Fallback `/home/dev/projects/jupiter`; der Startprompt enthält Ticket-ID, Klassifikation und Frontdesk-Report.
- Projektoptionen kommen serverseitig aus validierten Projektpfaden und bekannten Session-Projekten; das Frontend muss keine Pfade raten.
- Tests erweitert in `backend/tests/test_proj67_peppermint_backend.py`.
- Verifikation: `python -m pytest backend/tests/test_proj67_peppermint_backend.py` → 10 passed; `python -m pytest backend/tests` → 1156 passed, 2 bestehende Warnungen.

## Implementation Notes (Frontend, abc-frontend)
**Stand:** 2026-07-08 · **Branch:** dev

- Frontend-Erweiterung ist umgesetzt in `nextjs_app/components/microapps/peppermint_dashboard/peppermint-dashboard-app.tsx`, `nextjs_app/lib/api.ts`, `nextjs_app/lib/types.ts`.
- Die Ticketliste behält eine feste Kachelhöhe und scrollt vertikal innerhalb der Kachel; der Tabellenkopf bleibt sticky, horizontales Scrollen bleibt ebenfalls in der Kachel.
- Ticketzeilen zeigen Icon-Aktionen für Ausblenden/Einblenden, Bearbeiten und Entfernen/Wiederherstellen mit deutschen Labels/Tooltips.
- Detailbereich zeigt lokale Klassifikation als Badges und bietet Bearbeiten, Ausblenden/Einblenden, Entfernen/Wiederherstellen und Lösungs-Session starten/öffnen.
- Bearbeiten-Dialog bietet Dropdowns für Projekt, Priorität, Typ und Status; Projektoptionen kommen vom Backend.
- Entfernen-Dialog erklärt, dass das Ticket lokal in Jupiter entfernt und gegen Reimport gesperrt wird, aber im MVP nicht in Peppermint gelöscht wird.
- Filterleiste unterstützt kombinierte Filter für Analysezustand, Dringlichkeit, Priorität, Typ, Status, Projekt, Peppermint-Status, Suchtext sowie Anzeige ausgeblendeter/entfernter Tickets.
- Suchfeld benennt Typ, Status und Priorität explizit mit.
- Lösungs-Session-Button startet über den Backend-Endpunkt eine normale Jupiter-Session und öffnet danach `/sessions/<id>`; existiert bereits eine Session-ID, wird sie direkt geöffnet.
- Verifikation: `npx eslint components/microapps/peppermint_dashboard/peppermint-dashboard-app.tsx lib/api.ts lib/types.ts` → sauber; `npm test` → 176 passed; `npm run build` → erfolgreich.

---

## QA Test Results

**Tested:** 2026-07-08
**Backend:** FastAPI (Conda `Dashboard`), gegen `TestClient`/isolierte SQLite-Instanzen — kein Live-Browsertest möglich (Headless-Session ohne Display)
**Frontend:** Code-Review + `npm test` / `npm run build` / `eslint` gegen `nextjs_app/` — kein Live-Browsertest möglich
**Tester:** QA Engineer (AI)

### Acceptance Criteria Status

#### Icon-Aktionen, Tooltips, Layout
- [x] Auge/Papierkorb/Bearbeiten-Icons in Ticketzeile vorhanden, mit deutschem `title`+`aria-label` (Zeile ~715 ff. in `peppermint-dashboard-app.tsx`)
- [x] Ticketlisten-Kachel hat feste Höhe (`h-[460px]`), Tabellenbereich scrollt intern (`min-h-0 flex-1 overflow-auto`), Tabellenkopf ist `sticky top-0` — per Code-Review plausibel, **nicht live im Browser verifiziert**

#### Ausblenden / Einblenden
- [x] `POST .../hide` und `.../unhide` funktionieren, Standardliste blendet `hidden_at IS NOT NULL` aus (manuell gegen TestClient verifiziert)
- [x] „Ausgeblendete anzeigen" (`include_hidden=true`) zeigt ausgeblendete Tickets **zusätzlich**, nicht exklusiv (SQL lässt bei `include_hidden` einfach die Bedingung weg, andere Filter bleiben aktiv) — verifiziert per pytest `test_proj68_patch_filter_hide_ignore_and_tombstone`
- [x] Ausblenden verändert Analyse-Report/Peppermint-Verknüpfung nicht (kein entsprechendes Feld wird beim Hide-Call angefasst)

#### Löschen / Entfernen (Tombstone)
- [x] Bestätigungsdialog zeigt Ticket-Titel + Peppermint-ID, erklärt „nur lokal in Jupiter, nicht in Peppermint" (`IgnoreTicketDialog`)
- [x] Nach `ignore` verschwindet Ticket aus Standardliste; erneuter Webhook-Import mit gleicher Peppermint-ID reimportiert Titel/Text, aber `ignored_at` bleibt gesetzt (Tombstone hält) — verifiziert per pytest (Duplicate-Webhook-Case in `test_proj68_patch_filter_hide_ignore_and_tombstone`)
- [x] `restore`-Endpoint hebt Tombstone auf — manuell verifiziert
- [x] Peppermint-Delete bewusst nicht implementiert (MVP-Entscheidung aus Tech Design), UI kommuniziert das korrekt

#### Klassifikation (Projekt/Priorität/Typ/Status)
- [x] Projekt-Dropdown kommt vom Backend (`GET /peppermint/project-options`), serverseitig validiert gegen `allowed_roots`
- [x] Ungültiger/verbotener Projektpfad (`/etc`) → `400` mit Klartextfehler; nicht-existierendes Verzeichnis → `400` — beides manuell gegen `TestClient` verifiziert
- [x] Priorität/Typ/Status sind geschlossene Enums (Pydantic `Literal`) → ungültiger Wert → `422` — manuell verifiziert
- [x] Werte überleben Reload/Neustart (SQLite-Spalten, kein In-Memory-State)
- [x] „Projekt darf leer bleiben" — Patch mit `project_path=""` löscht Zuordnung korrekt (`project_path`+`project_label` → `null`) — manuell verifiziert
- [x] Klassifikation sichtbar in Ticketliste + Detailbereich (Spalten + Badges)

#### Filter & Suche
- [x] Priorität/Typ/Status/Projekt einzeln und kombiniert filterbar (serverseitiges `AND` in `_list_tickets_sync`)
- [x] Suche durchsucht zusätzlich Typ-/Status-/Prioritäts-Label (deutsch, z. B. „hoch", „gelöst") über `_enum_search_hits` — verifiziert per pytest (`q=hoch`)
- [x] Suche schränkt gesetzte Filter weiter ein statt sie zu ersetzen (gleiche WHERE-Kette)

#### Lösungs-Session
- [x] Aktion nur bei `analysis_status == "analysiert"` aktiv, sonst deaktiviert mit Tooltip „Erst nach erfolgreicher Analyse verfügbar"
- [x] Ignorierte Tickets können keine Session starten → `409` — manuell verifiziert
- [x] Initial-Prompt enthält Peppermint-ID, Jupiter-ID, Betreff, Kunde, Link, Projekt/Priorität/Typ/Status, Report (mit 12k-Zeichen-Kürzung + Hinweis) — Code-Review von `build_resolution_prompt`
- [x] Session startet über bestehenden `SessionManager`, Projektpfad wird validiert, Fallback `/home/dev/projects/jupiter` — verifiziert per pytest (`test_proj68_resolution_session_and_project_options`)
- [x] Nach Start wird `resolution_session_id` am Ticket gespeichert und im Detailbereich als Badge angezeigt
- [ ] **BUG-1** (siehe unten): „Neue weitere Session starten" nach Bestätigung fehlt vollständig

#### Sprache
- [x] Alle geprüften UI-Texte, Tooltips, Bestätigungen und Fehlermeldungen sind deutsch

### Edge Cases Status

- [x] Ausgeblendetes Ticket + späteres Peppermint-Update → bleibt ausgeblendet (Tombstone-Test deckt das analoge Ignore-Verhalten ab; Hide-Feld wird beim Upsert nicht angefasst)
- [ ] **Nicht implementiert (Low):** „Peppermint-Ticket wurde außerhalb von Jupiter gelöscht" → kein Hinweis „Ticket in Peppermint nicht mehr abrufbar" im Code gefunden (kein 404-Handling beim Polling)
- [x] Peppermint-Delete nicht verfügbar → MVP-Entscheidung dokumentiert, UI behauptet nie einen erfolgreichen Peppermint-Delete
- [x] Pflichtwerte im Bearbeiten-Dialog → Dialog nutzt feste Defaults (Niedrig/Sonstiges/Offen), Speichern nie blockiert
- [x] Projektliste nicht ladbar → Dropdown zeigt zumindest den Fallback „Jupiter"; bei komplettem Request-Fehler bleibt laut `refresh()`-Fehlerpfad die bestehende Zuordnung unverändert (kein Overwrite ohne Bestätigung)
- [x] Analyse-Report sehr lang → Kürzung bei 12.000 Zeichen mit Hinweistext, kein stilles Abschneiden
- [x] Session-Start schlägt fehl → Ticket bleibt unverändert, `resolution_session_error` wird serverseitig gespeichert und spätestens beim nächsten 4s-Poll im Detailbereich sichtbar (nicht sofort optimistisch, aber selbstheilend)
- [ ] **BUG-1 betrifft auch:** „Ticket kann nicht mehrfach unbeabsichtigt parallele Sessions starten" — Doppelstart-Schutz selbst funktioniert (Backend gibt bei aktiver Session dieselbe ID zurück), aber der zweite Teil der Anforderung (bewusst weitere Session starten können) fehlt

### Security Audit Results
- [x] Alle `/peppermint/*`-Routen (außer Webhook) hinter `Depends(get_current_user)` (`auth_gate`), Webhook hat eigenen Secret-Header-Check
- [x] Projektpfade für Session-CWD serverseitig gegen `allowed_roots`/`validate_project_path` geprüft (kein Path-Traversal über `project_path`-Patch oder Session-Start) — manuell mit `/etc` und Punkt-Punkt-Pfaden verifiziert
- [x] Enum-Felder (Priorität/Typ/Status) sind geschlossene Pydantic-`Literal`-Typen, keine Freitext-SQL-Interpolation
- [x] Alle SQL-Statements weiterhin parametrisiert (`?`-Platzhalter), auch die neuen PROJ-68-Filter/Enum-Suche
- [x] Keine neuen Secrets im Code; Session-Tokens/Peppermint-Token weiterhin serverseitig
- [x] Kein Multi-Tenancy-Bezug nötig (Jupiter ist Single-User im MVP, siehe Projektkontext) — kein RLS-Test anwendbar
- **Hinweis (kein PROJ-68-Bug):** `docs/frontdesk-checks/2026-07-07-auxevo-support-tickets.md` liegt ungetrackt und ohne `.gitignore`-Eintrag im Repo und könnte reale Kundendaten enthalten — Datenhygiene-Hinweis für den Nutzer, nicht Teil dieser Feature-Prüfung.

### Bugs Found

#### BUG-1: „Neue weitere Lösungs-Session starten" fehlt komplett — Ticket bleibt nach der ersten Session dauerhaft auf sie gesperrt
- **Severity:** High
- **Steps to Reproduce:**
  1. Analysiertes Ticket öffnen, „Lösungs-Session starten" klicken → Session A wird erstellt, `resolution_session_id` gesetzt.
  2. Session A läuft ab, wird beendet oder bricht mit Fehler ab.
  3. Nutzer will für dasselbe Ticket eine neue, frische Lösungs-Session starten (z. B. weil A feststeckt oder der erste Versuch nicht zum Ziel führte).
  4. Erwartet laut Spec: UI bietet „Session öffnen" **und** „Neue weitere Session starten" (nach Bestätigung).
  5. Tatsächlich: `handleStartResolution` prüft nur `if (ticket.resolution_session_id) { öffne Session A; return; }` — es gibt weder einen zweiten Button/Dialog im Frontend noch einen `force`/`new`-Parameter im Backend-Endpoint `POST /resolution-session`. Das Ticket ist ab dem ersten Start **permanent** auf genau diese eine Session-ID gebunden, unabhängig von deren Status (aktiv, beendet, fehlgeschlagen, gelöscht).
- **Priorität:** Fix before deployment (verletzt eine explizite Acceptance-Criteria-Zeile und schränkt den Kernworkflow — Ticket lösen, ggf. erneut versuchen — nach dem ersten Versuch dauerhaft ein)

#### BUG-2: Kein Hinweis, wenn das Peppermint-Ticket extern gelöscht wurde
- **Severity:** Low
- **Steps to Reproduce:**
  1. Ticket in Jupiter vorhanden, wird in Peppermint selbst gelöscht.
  2. Polling/Webhook trifft danach nicht mehr auf dieses Ticket.
  3. Erwartet laut Edge Case: Jupiter zeigt „Ticket in Peppermint nicht mehr abrufbar", lokales Löschen bleibt möglich.
  4. Tatsächlich: kein 404-/Nichtmehr-abrufbar-Handling im Code gefunden; das Ticket bleibt einfach unverändert stehen ohne Hinweis.
- **Priorität:** Nice to have (dokumentierter Edge Case, aber keine eigene Acceptance-Criteria-Zeile; geringe operative Auswirkung im MVP)

### Summary
- **Acceptance Criteria:** 17/18 geprüfte Kriterien bestanden (das Doppelstart-Schutz-Kriterium ist teilweise erfüllt: Backend-Dedup funktioniert, die geforderte „weitere Session"-Option fehlt komplett)
- **Bugs Found:** 2 total (0 critical, 1 high, 0 medium, 1 low)
- **Security:** Pass (keine Findings; ein Datenhygiene-Hinweis außerhalb des Feature-Scopes)
- **Automatisiert:** `pytest backend/tests` → 1156 passed; `pytest backend/tests/test_proj67_peppermint_backend.py` → 10 passed; `npm test` (nextjs_app) → 176 passed; `npx eslint …` → sauber; `npm run build` → erfolgreich
- **Nicht durchgeführt:** Live-Browsertest (Sticky-Header-Scroll, Responsive 375/768/1440px, Dialog-Optik) — Headless-Session ohne Display; Code-Review stützt die Umsetzung, eine kurze visuelle Kontrolle vor dem Deploy wird empfohlen
- **Production Ready:** NO
- **Recommendation:** BUG-1 vor dem Deploy fixen (Backend: `force`/`start_new`-Parameter an `POST /resolution-session`, das eine neue Session auch bei vorhandener `resolution_session_id` erlaubt, plus Historie/Liste vergangener Sessions oder zumindest Überschreiben der aktiven ID; Frontend: zweiter Button „Neue weitere Session starten" mit Bestätigungsdialog neben „Session öffnen"). BUG-2 kann in einem Folge-Sprint adressiert werden.

---

## Bugfix-Runde (2026-07-08)

**BUG-1 — fixed.** `PeppermintTicketRead.resolution_session_id` sperrt Tickets nicht mehr dauerhaft:
- Backend: `start_resolution_session(item_id, force: bool = False)` (`backend/app/engine/peppermint.py`) — ohne `force` wird eine noch aktive verknüpfte Session weiterhin wiederverwendet (Doppelstart-Schutz bleibt), eine bereits beendete/fehlgeschlagene Session wird beim nächsten Aufruf transparent durch eine neue ersetzt (kein Deadlock mehr). Mit `force=True` wird immer eine zusätzliche, neue Session gestartet und die Verknüpfung am Ticket ersetzt; die alte Session läuft unabhängig weiter und bleibt über die Sidebar erreichbar. Neuer Request-Body `PeppermintResolutionSessionRequest{force}` auf `POST /peppermint/tickets/{id}/resolution-session`.
- Frontend: `handleStartResolution(ticket, force)` ruft jetzt immer das Backend auf (kein blinder Redirect mehr auf eine evtl. tote `resolution_session_id`). Neuer Button „Neue weitere Session starten" (nur sichtbar, wenn bereits eine Session verknüpft ist) öffnet `NewResolutionSessionDialog` — nach Bestätigung wird `force=true` gesendet.
- Test: `test_proj68_resolution_session_force_starts_additional_session` (`backend/tests/test_proj67_peppermint_backend.py`).

**BUG-2 — fixed.** Neues Feld `peppermint_missing_at`:
- Backend: `poll_now()` vergleicht die vom Peppermint-Poll zurückgegebenen Ticket-IDs mit dem lokalen Bestand; für nicht mehr enthaltene, nicht ignorierte Tickets wird gezielt einzeln per `PeppermintClient.get_ticket()` nachgeprüft (verhindert Fehlalarme durch Paginierung/Filterung der „offen"-Liste). Bleibt die Einzelabfrage leer, wird `peppermint_missing_at` gesetzt; taucht das Ticket später wieder auf (Webhook oder Poll), wird das Feld beim Upsert automatisch wieder auf `NULL` gesetzt. Batch-Größe pro Tick begrenzt (`PEPPERMINT_MISSING_CHECK_BATCH = 5`), um die Peppermint-API nicht zu fluten.
- Frontend: Detailbereich zeigt bei gesetztem `peppermint_missing_at` einen Hinweisbanner „Ticket in Peppermint nicht mehr abrufbar" — lokales Entfernen bleibt weiterhin möglich, es wird kein Peppermint-Löschen behauptet.
- Test: `test_proj68_missing_peppermint_ticket_is_flagged_and_cleared` (`backend/tests/test_proj67_peppermint_backend.py`).

**Verifikation:** `pytest backend/tests/test_proj67_peppermint_backend.py` → 12 passed; `pytest backend/tests` (voller Lauf) → 1158 passed, 2 (bestehende, unveränderte) Warnungen; `npx eslint …` → sauber; `npm test` → 176 passed; `npm run build` → erfolgreich.

**Offen:** BUG-2 bleibt funktional Low-Priority (kein aktives Polling in den bestehenden Tests genutzt, Feature ist rein additiv) — für den produktiven Peppermint-Betrieb sollte einmal live gegen die reale Peppermint-Instanz geprüft werden, dass `list_open_tickets()`/`get_ticket()` das erwartete 200/404-Verhalten zeigen (echte Peppermint-API-Antwortformate wurden hier nicht gegen einen echten Server getestet).

**Aktualisierter Status:** Beide QA-Bugs (BUG-1 High, BUG-2 Low) sind gefixt und mit denselben Reproduktionsschritten aus der QA-Runde erneut verifiziert (automatisiert + manuell gegen `TestClient`). Der einzige Production-Ready-Blocker (BUG-1) ist behoben. **Production Ready: YES** (offener Live-Browsertest/echter Peppermint-Server-Check bleiben als Empfehlung vor dem eigentlichen Deploy bestehen, siehe oben).
