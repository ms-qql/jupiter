# PROJ-84: Hermes-Kanban – Arbeitsfluss verfeinern

## Status: In Review

**Created:** 2026-08-20
**Last Updated:** 2026-08-20

## Dependencies

- Requires: PROJ-82 (Hermes-Kanban nativ in Jupiter) — erweitert ausschließlich dessen native Board-, Detail- und Task-Anlage-Ansicht.
- Requires: PROJ-20 (Spracheingabe / Push-to-Talk) — verwendet die bereits in Jupiter vorhandene Mikrofon-Eingabe für die Task-Beschreibung.

## Scope

Die native Hermes-Kanban-Ansicht wird auf den täglichen Jupiter-Workflow reduziert: sichtbare Phasen lassen sich direkt am Board wählen, der verfügbare Platz wird besser genutzt, das Detail bleibt neben dem Board lesbar und die neue Task-Anlage enthält nur die tatsächlich benötigten Felder.

Nicht Teil dieses Features sind neue Hermes-Statuswerte, Live-Streaming des Worker-Logs, Änderungen an bestehenden Hermes-Tasks oder eine neue Spracheingabe-Engine.

## User Stories

- Als Nutzer möchte ich oben rechts am Board per Checkbox wählen, welche Kanban-Phasen ich sehe, damit ich mich auf die gerade relevanten Tasks konzentriere.
- Als Nutzer möchte ich bei abgewählten Phasen keine Spalte sehen, damit das Board nicht ungenutzten Platz belegt.
- Als Nutzer möchte ich jede sichtbare Phase zunächst auf etwa ein Drittel der Bildschirmhöhe sehen und bei vielen Tickets mehr Platz erhalten, damit Karten weder unnötig klein noch abgeschnitten sind.
- Als Nutzer möchte ich nach Klick auf eine Karte weiterhin das Kanban neben dem Detail sehen und den Worker-Log breiter lesen können, damit ich Kontext und Log zugleich vergleichen kann.
- Als Nutzer möchte ich eine längere Beschreibung diktieren oder schreiben können, damit sich neue Kanban-Tasks schnell und vollständig anlegen lassen.
- Als Nutzer möchte ich neue Tasks standardmäßig dem `jupiter-coordinator` zuweisen, die Zuweisung bei Bedarf aber ändern können.
- Als Nutzer möchte ich beim Anlegen nur einen Projektordner unter `/home/dev/projects` ergänzen und keine unnötigen Projekt- oder Workspace-Modus-Felder bedienen müssen.
- Als Nutzer möchte ich Parent-Tasks nur bei Bedarf unter „Erweitert“ sehen, damit das Grundformular kompakt bleibt.

## Acceptance Criteria

### A — Phasenfilter und Board-Fläche

- [ ] Oben rechts in der Phasen- bzw. Board-Kopfzeile gibt es eine gut erkennbare Auswahl der Kanban-Phasen als Checkboxen; sie ersetzt den bisherigen Archived-Toggle.
- [ ] Beim Öffnen sind alle regulären Phasen ausgewählt: Triage, Todo, Scheduled, Ready, Running, Blocked, Review und Done.
- [ ] Das An- oder Abwählen einer Phase aktualisiert die sichtbaren Spalten sofort, ohne einen Hermes-Request auszulösen.
- [ ] Abgewählte Phasen belegen keinen Platz im Board.
- [ ] Sind alle Phasen abgewählt, zeigt das Board keine Phase und einen klaren deutschen Leerhinweis statt automatisch Häkchen zurückzusetzen.
- [ ] Archivierte Tasks werden in dieser Ansicht nicht mehr über einen Toggle eingeblendet.
- [ ] Jede sichtbare Phasenfläche nimmt mindestens ungefähr ein Drittel der verfügbaren Viewport-Höhe ein und wächst mit der Zahl ihrer enthaltenen Karten; Karten dürfen nicht durch eine feste, zu kleine Höhe abgeschnitten werden.
- [ ] Bei wenig Inhalt bleibt die Darstellung kompakt; bei viel Inhalt ist die Phase innerhalb der Seite bedienbar, ohne andere sichtbare Phasen zu überdecken.

### B — Angedocktes Task-Detail

- [ ] Ein Klick auf eine Task-Karte öffnet ihr Detail rechts neben dem weiterhin sichtbaren Kanban statt es als überlagerndes Vollbild zu verdecken.
- [ ] Das Detail ist auf Desktop-Breite deutlich breiter als bisher und bietet dem Worker-Log ausreichend horizontale Lesefläche; lange Log-Zeilen bleiben als Monospace-Inhalt lesbar und horizontal zugänglich.
- [ ] Schließen des Details stellt die vollständige Board-Fläche wieder her.
- [ ] Auf schmalen Ansichten bleibt die Detailansicht bedienbar und verdeckt nicht unzugänglich den Schließen-Mechanismus oder die Task-Aktionen.
- [ ] Das ausgewählte Task-Detail aktualisiert sich nach den bereits vorhandenen Aktionen und nach dem Board-Refresh weiterhin korrekt.

### C — Neues Task-Formular

- [ ] Das Beschreibungsfeld ist deutlich größer als das bisherige Vier-Zeilen-Feld und für längere Texte geeignet.
- [ ] Direkt am Beschreibungsfeld steht die in Jupiter bereits vorhandene Mikrofon-Eingabe zur Verfügung; ihr erkannter Text wird in die Beschreibung eingefügt, ohne bestehenden Text zu löschen.
- [ ] Die Mikrofon-Eingabe nutzt dieselben Verfügbarkeits-, Lade- und deutschen Fehlermeldungen wie die übrigen Jupiter-Eingabefelder; es wird kein separater Transkriptionsdienst eingeführt.
- [ ] Beim Öffnen eines normalen oder vorbefüllten neuen Tasks ist `jupiter-coordinator` als Assignee vorausgewählt, sofern dieses Profil verfügbar ist.
- [ ] Der Assignee bleibt über die vorhandene Auswahlliste änderbar; „Kein Assignee“ bleibt auswählbar.
- [ ] Das Projektfeld wird nicht mehr angezeigt und die Task-Anlage übermittelt keinen vom Nutzer gewählten Projektwert.
- [ ] Der Workspace-Modus ist fest `dir:<pfad>`; es gibt keine Auswahl für Scratch- oder Worktree-Modi und kein Branch-Feld.
- [ ] Das sichtbare Workspace-Pfadfeld startet mit `/home/dev/projects/`, sodass der Nutzer nur den Projektordner ergänzen kann; der vollständige resultierende Pfad bleibt vor dem Absenden sichtbar.
- [ ] Ein leerer Workspace-Pfad oder ein Pfad ohne Verzeichnis unter `/home/dev/projects` blockiert das Absenden mit einer verständlichen deutschen Meldung.
- [ ] Parent-Tasks sind nicht im Grundformular sichtbar, sondern liegen vollständig unter dem aufklappbaren Bereich „Erweitert“; Auswahl, Suche und Mehrfachauswahl bleiben dort unverändert möglich.
- [ ] Die bestehende Validierung für Titel, Triage, Model-/Provider-Override und weitere weiterhin sichtbare Felder bleibt wirksam.

## Edge Cases

- Alle Phasen sind abgewählt: Es erscheinen keine Spalten; der Leerhinweis erklärt, dass oben rechts mindestens eine Phase gewählt werden kann.
- Ein zuvor sichtbarer, ausgewählter Task gehört nach einer Filteränderung zu einer ausgeblendeten Phase: Das Detail bleibt nur solange sichtbar, wie es noch sinnvoll geladen werden kann; beim Schließen oder nächsten Board-Refresh entsteht kein fehlerhafter Auswahlzustand.
- Die Assignee-Liste enthält `jupiter-coordinator` nicht: Das Formular bleibt bedienbar, zeigt keinen erfundenen Wert und lässt den Nutzer einen verfügbaren Assignee wählen.
- Die Mikrofon-Eingabe ist nicht verfügbar, wird abgebrochen oder die Transkription schlägt fehl: Der bereits geschriebene Beschreibungstext bleibt erhalten und Jupiter zeigt die vorhandene deutsche Fehlermeldung.
- Der Nutzer ersetzt den vorausgefüllten Workspace-Pfad vollständig oder gibt nur `/home/dev/projects/` ein: Das Formular fordert einen konkreten Projektordner an, bevor es absendet.
- Ein Pfad außerhalb von `/home/dev/projects` wird eingegeben: Das Formular lehnt ihn vor dem Anlegen mit einer deutschen Meldung ab.
- Die Ansicht ist zu schmal für Board und angedocktes Detail nebeneinander: Das Detail bleibt nutzbar über die für kleine Ansichten passende vorhandene Darstellung, ohne Inhalt oder Aktionen zu verlieren.
- Ein Worker-Log enthält sehr lange Zeilen: Es wird nicht abgeschnitten oder umformatiert, sodass Kopieren und horizontales Lesen möglich bleiben.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-20 · **Stack:** Next.js 16 + shadcn/ui + FastAPI + Hermes-CLI-Subprocess · **Branch:** main (gemeinsamer Live-Arbeitsordner)

**Kernidee:** PROJ-84 bleibt eine reine Bedienungs-Verfeinerung der bestehenden native Hermes-Kanban-Microapp. Hermes bleibt die einzige Task-Wahrheit; es entstehen keine Jupiter-Tabellen, keine Migrationen, kein MinIO-Objekt und kein Hintergrunddienst.

### A) Komponenten und Verhalten

```
HermesKanbanApp
├── Board-Kopfzeile
│   ├── Board- und Assignee-Auswahl (unverändert)
│   ├── Phasenfilter (Checkboxen: Triage, Todo, Scheduled, Ready,
│   │   Running, Blocked, Review, Done)
│   ├── Schnell-Anlage, Aktualisieren, Dispatch, Neuer Task
│   └── kein Archived-Toggle
├── Board-Detail-Split
│   ├── sichtbare Kanban-Spalten
│   │   └── Task-Karte mit Mehrfachauswahl (unverändert)
│   └── TaskDetailPanel (Desktop angedockt; schmale Ansicht als vorhandenes
│       erreichbares Detail-Overlay/-Pane mit sichtbarem Schließen und Aktionen)
└── NewTaskDialog
    ├── Grundbereich: Titel, große Beschreibung + Push-to-Talk, Assignee,
    │   Workspace-Pfad, Priorität, Skills, Initial-Status
    └── Erweitert: Parent-Suche/-Mehrfachauswahl sowie bestehende seltene
        Optionen (Triage, Laufzeit, Retries, Modell+Provider, Goal-Mode usw.)
```

- **Phasenfilter:** acht reguläre Status sind beim Öffnen lokal ausgewählt. Änderung filtert ausschließlich den bereits geladenen Task-Bestand; weder Polling noch Hermes-Request werden ausgelöst. Archivierte Tasks werden stets nicht geladen und erhalten keine Spalte. Bei leerer Auswahl zeigt das Board den Hinweis „Keine Phase ausgewählt. Oben rechts mindestens eine Phase wählen.“
- **Spaltenhöhe:** jede sichtbare Spalte erhält mindestens rund `33dvh` Kartenfläche. Sie wächst mit dem Inhalt bis zur verfügbaren Board-Höhe; danach scrollt nur ihre Kartenliste. Karten werden nie durch eine kleine fixe Maximalhöhe versteckt.
- **Split:** ab Desktop-Breite liegen Board und Detail in einem gemeinsamen horizontalen Container. Das Detail erhält ungefähr 36–42 % Breite, mindestens etwa 36 rem; das Board nutzt den Rest. Schließen entfernt das Pane und gibt die gesamte Breite zurück. Unterhalb dieses Breakpoints nutzt das Detail die bereits mobile-fähige Pane-/Overlay-Darstellung statt eines unzugänglichen Seitensplits.
- **Auswahl bei Filter/Refresh:** wird die Phase eines geöffneten Tasks lokal ausgeblendet, bleibt sein bereits geladenes Detail bis zum Schließen nutzbar. Ergibt ein späteres Board-Refresh, dass der Task fehlt oder weiter ausgeblendet ist, wird die Auswahl sauber geschlossen. Kein verwaister Detailzustand.
- **Worker-Log:** bleibt unverändert ein Snapshot. Der Monospace-Block behält horizontales Scrollen und bricht lange Zeilen nicht künstlich um.
- **Diktat:** `PushToTalkButton` aus PROJ-20 wird direkt an der Beschreibung wiederverwendet. Sein Callback hängt erkannten Text mit einem Leerzeichen an vorhandenen Text an; Fehler, Aufnahme-/Ladezustände und Abbruch bleiben die bestehenden deutschen PROJ-20-Meldungen. Kein neuer Transkriptionsdienst.

### B) Datenmodell, Eigentümer und Lesepfade

| Entität/Zustand | Persistenz | Schreiber (Owner) | Lesepfade vor/nach Schreiben |
|---|---|---|---|
| Hermes-Task | Hermes-Kanban-DB, keine Jupiter-Kopie | `POST /hermes-kanban/tasks`; ausgelöst nur durch `NewTaskDialog` eines angemeldeten Jupiter-Nutzers | `GET /hermes-kanban/tasks` für Board/Parent-Auswahl; `GET /hermes-kanban/assignees` vor Assignee-Vorauswahl; `GET /hermes-kanban/tasks/{id}` und `/log` für Detail/Log |
| Task-Status/Archivierung/Kommentar | Hermes-Kanban-DB | bestehende Task-Aktionsendpunkte, ausgelöst aus `TaskActions` | bestehende Detail- und Board-Lesepfade; PROJ-84 fügt keinen Schreiber hinzu |
| Phasenauswahl und geöffnete Task | nur React-Ansichtszustand, nicht persistiert | `HermesKanbanApp` | vorhandene, bereits geladene Task-Liste; keine API und kein späterer Lesepfad nötig |
| Neues Task-Formular inklusive Beschreibung | nur React-Formularzustand bis Submit | `NewTaskDialog`; Diktat schreibt ausschließlich in `body` | Assignee-Liste, offene Tasks als Parent-Kandidaten; keine Projektliste mehr |

Es gibt keine neue relationale Entität und deshalb keine neue RLS-Policy oder Migration. Alle Hermes-Kanban-Endpunkte bleiben hinter dem bestehenden globalen FastAPI-Auth-Gate (`get_current_user`, aktuell in `backend/app/main.py` registriert). Der Client liefert weder Owner noch Mandant. Sobald Jupiter Mandanten im JWT führt, ist die Board-Zugriffsprüfung serverseitig aus diesem Claim abzuleiten; sie darf nie aus einem Formularfeld kommen. Die bestehende Hermes-Instanz ist lokal/single-tenant und erhält durch dieses UI keinen zusätzlichen Mandantenwert.

### C) API-Contract

Bestehende Lese- und Aktionsendpunkte bleiben unverändert. Das Feature verengt nur die Task-Anlage:

| Endpoint | Contract und Owner |
|---|---|
| `GET /hermes-kanban/tasks?board=&assignee=` | Liefert nur nicht archivierte Hermes-Tasks für Board, Filter und Parent-Auswahl. `HermesKanbanApp` ist Leser. Kein Request beim lokalen Phasenfilter. |
| `GET /hermes-kanban/assignees?board=` | Liefert verfügbare Profile. `NewTaskDialog` liest vor Öffnen/bei Board-Wechsel; `jupiter-coordinator` wird nur vorausgewählt, wenn exakt dieser Wert enthalten ist. „Kein Assignee“ bleibt möglich. |
| `POST /hermes-kanban/tasks?board=` | `NewTaskDialog` schreibt. Request akzeptiert Titel, Body, Assignee, Parents, `workspace_path` und die noch sichtbaren bestehenden Optionen. `workspace_mode`, `project` und `branch` werden aus `CreateTaskRequest` entfernt; Pydantic konfiguriert den Request mit `extra="forbid"`, damit direkte API-Calls mit einem dieser Alt-Felder 422 erhalten statt still einen anderen Workspace anzulegen. Der Route-Handler setzt den einzigen CLI-Workspace unabhängig vom Payload immer als `dir:<kanonischer_workspace_path>` und ergänzt weiterhin `created-by=jupiter`. |
| `GET /hermes-kanban/tasks/{id}` und `GET /hermes-kanban/tasks/{id}/log` | `TaskDetailPanel` liest Detail bzw. Snapshot. Bestehende Aktionen und Board-Refresh aktualisieren danach weiterhin diese Ansicht. |

`workspace_path` ist ein absoluter, sichtbarer Pfad. Das Formular startet mit `/home/dev/projects/`; die maßgebliche Server-Prüfung liegt als Pydantic-`field_validator` direkt auf `CreateTaskRequest.workspace_path` in `backend/app/schemas/hermes_kanban.py`, nicht im Route-Handler. Sie löst Root und Eingabepfad kanonisch und mit Existenzprüfung auf, akzeptiert nur ein existierendes Verzeichnis strikt unter `/home/dev/projects` und weist Root selbst sowie Pfade zurück, die durch `..` oder Symlink daraus ausbrechen. Ungültige Werte liefern den normalen Pydantic-422 mit verständlicher deutscher Meldung. Der validierte kanonische Pfad ist der einzige Wert, den `create_task()` in `backend/app/routes/hermes_kanban.py` an `dir:` übergibt. Client-Prüfung dient nur schnellem Feedback.

### D) Technische Entscheidungen

1. **Lokaler Phasenfilter statt Setting:** Filter ist eine situative Board-Ansicht. Keine Persistenz und kein Request vermeiden Stale-State und erfüllen die Sofort-Aktualisierung.
2. **Keine neue API für Layout:** Spalten, Split und leere Auswahl sind reine Darstellung. Backend/CLI bleiben klein und unverändert.
3. **Workspace fest auf `dir:`:** `workspace_mode` wird nicht mehr angenommen; der Handler erzeugt immer `dir:`. `project` und `branch` werden ebenfalls aus dem Request-Schema entfernt und durch `extra="forbid"` mit 422 abgewiesen, nicht deprecated oder ignoriert. Das ist ein klarer Contract statt stiller Fallbacks. Der Schema-Validator liefert ausschließlich einen kanonischen bestehenden Projektordner; damit können manipulierte Calls weder Scratch/Worktree noch fremde oder per Symlink erreichbare Pfade erzeugen.
4. **Kein Projekt-Dropdown/-Request:** Das bisherige `GET /hermes-kanban/projects` wird von dieser Microapp nicht mehr aufgerufen; der bestehende Endpunkt wird nicht in diesem Komfort-Feature entfernt, um keinen unnötigen API-Bruch zu erzeugen.
5. **Bestehendes Diktat wiederverwenden:** PROJ-20 kapselt Berechtigung, Aufnahme, Selbsthosting und deutsche Fehler bereits. Wiederverwendung hält Datenschutz- und Bedienungsverhalten konsistent.
6. **Desktop-Split, mobile Fallback-Ansicht:** Board-Kontext und breites Log sind auf Desktop gleichzeitig sichtbar; ein enger Split auf kleinen Screens würde Aktionen und Schließen verschlechtern.

### E) Abhängigkeiten und Nicht-Ziele

- Neue Pakete: keine. Vorhanden sind Next.js/shadcn/ui, `PushToTalkButton`/Whisper-Transkription, FastAPI/Pydantic und die Hermes-CLI-Bridge.
- Nicht ändern: Hermes-Statuswerte, Hermes-DB-Schema, Worker-Log-Streaming, Polling-Setting, Bulk-Aktionen und Projekt-/Workspace-Logik außerhalb der Neuanlage dieser Microapp.

### F) Nachweis gegen Bestand

- `HermesKanbanApp` enthält die acht regulären Status und den bisherigen Archived-Toggle (`nextjs_app/components/microapps/hermes_kanban/hermes-kanban-app.tsx:53-62, 306-313`); das Detail wird heute unter dem Board gerendert (`:375-415`).
- `TaskDetailPanel` ist bereits einzeln gekapselt, lädt Detail und Snapshot und nutzt horizontal scrollbares `<pre>` (`task-detail-panel.tsx:79-128, 328-340`).
- `NewTaskDialog` hält aktuell Projekt, Workspace-Modus, Branch und Parents im Grundbereich (`new-task-dialog.tsx:123-164, 336-478`); der Request wird in `CreateTaskRequest` in CLI-Argumente übersetzt (`backend/app/schemas/hermes_kanban.py:23-61`, `backend/app/routes/hermes_kanban.py:198-242`).
- CodeGraph war aktuell: 394 Dateien, 8.256 Knoten. Es zeigt `HermesKanbanApp → NewTaskDialog/TaskDetailPanel` und keine bestehenden Tests für diese drei UI-Komponenten; Implementierung braucht gezielte UI-/API-Regressionen.

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-20 (Runde 2) · **Verdict:** Architected

### Re-Review Runde 2
Nachbesserungs-Task t_f9b016bf abgeschlossen. Abschnitt C/D jetzt technisch eindeutig:
- `workspace_mode`, `project`, `branch` werden aus `CreateTaskRequest` entfernt; `extra="forbid"` liefert 422 bei Alt-Feldern (Breaking Change, explizit entschieden).
- Kanonische Root-/Symlink-Prüfung für `workspace_path` benannt: Pydantic `field_validator` direkt auf `CreateTaskRequest.workspace_path` in `backend/app/schemas/hermes_kanban.py`, nicht im Route-Handler.
- `create_task()` setzt `dir:<kanonischer_pfad>` unabhängig vom Payload.
Aktueller Code (`hermes_kanban.py:23-49`) zeigt erwartungsgemäß noch den alten Zustand (`workspace_mode` Pattern `scratch|dir|worktree|worktree_path`, `project`/`branch` vorhanden) — das ist normal für Architecture Draft, die Implementierung ist Aufgabe von `/abc-backend`. Die Ambiguität, die zum ursprünglichen Block führte (Design behauptete Prüfung ohne Ort/Mechanismus zu nennen), ist aufgelöst.

Alle 3 offenen Fragen aus Runde 1 beantwortet. Übrige Checklist-Punkte aus Runde 1 unverändert bestätigt (Component structure, Owner-/Lesepfad-Matrix, Auth-Gate, DB/RLS, Naming-Konflikte).

### Checklist (final)
- [x] Component structure
- [x] Owner-/Lesepfad-Matrix (Abschnitt B)
- [x] Auth-Gate
- [x] DB/RLS
- [x] Naming-/Routen-Konflikte
- [x] API shape / Server-Durchsetzung — jetzt eindeutig spezifiziert (Ort, Mechanismus, Feldentscheidung)

### Vorherige Runde (Runde 1, archiviert)
**Reviewed:** 2026-08-20 · **Verdict:** Blocked — Nachbesserung nötig

### Checklist
- [x] Component structure — COLUMNS-Array (8 Status, `hermes-kanban-app.tsx:53-62`) und TaskDetailPanel-Split (`task-detail-panel.tsx:132,142,159`, zwei aside-Renderpfade mobil/desktop) bestätigen Bestand wie im Nachweis behauptet.
- [x] Owner-/Lesepfad-Matrix (Abschnitt B) — vollständig; jede Entität hat Schreiber + Lesepfad, keine Lücke.
- [x] Auth-Gate — bestätigt: `hermes_kanban.router` läuft unter globalem `auth_gate = [Depends(get_current_user)]` (`backend/app/main.py:417,448`).
- [x] DB/RLS — korrekt: keine neue Tabelle, reine CLI-Durchreiche (`_run_hermes`), kein Mandant/Tenant-JWT-Konzept in `deps.py` vorhanden — Aussage "sobald Jupiter Mandanten im JWT führt" ist zutreffend als Zukunftsaussage, keine Fake-Referenz.
- [x] Naming-/Routen-Konflikte — keine gefunden.
- [ ] **API shape / Server-Durchsetzung — FAIL:** `CreateTaskRequest` (`backend/app/schemas/hermes_kanban.py:23-49`) erlaubt weiterhin `workspace_mode` als `scratch|dir|worktree|worktree_path` und akzeptiert `project`/`branch` als volle Felder; `create_task()` (`backend/app/routes/hermes_kanban.py:198-211`) reicht `workspace_path` unverändert an die CLI durch — **keine** kanonische Pfad-Validierung (kein `realpath`, kein Root-Containment-Check, kein Symlink-Check) existiert im Code. Das Design behauptet diese Prüfung in Abschnitt C als gegeben/geplant, benennt aber nicht wo sie greift. Damit ist der "verengte Contract" nur UI-Kosmetik: ein direkter API-Call mit `workspace_mode=worktree` würde weiterhin einen Worktree/Branch anlegen — widerspricht der Acceptance Criteria C ("keine Auswahl für Scratch-/Worktree-Modi").

### Offene Fragen (Rückgabe an jupiter-architecture)
1. Design muss explizit festlegen: wird `CreateTaskRequest.workspace_mode`-Pattern serverseitig auf `^dir$` verengt (Schema-Änderung) oder ignoriert der Handler abweichende Client-Werte und erzwingt `dir` unabhängig vom Payload? Ohne diese Festlegung bleibt die Sicherheitsgarantie aus AC C ("kein Branch-Feld, keine Scratch-/Worktree-Wahl") technisch nicht durchgesetzt.
2. Wo genau (Pydantic `field_validator` in `CreateTaskRequest` vs. Route-Handler `create_task`) soll die kanonische Root-/Symlink-Prüfung für `workspace_path` implementiert werden? Muss im API-Contract-Abschnitt konkret benannt sein, sonst rätselt Backend über den Implementierungsort.
3. Sollen `project`/`branch`-Felder aus dem Schema entfernt (Breaking Change) oder als deprecated/ignoriert beibehalten werden? Bitte explizit entscheiden und dokumentieren.

Nach Nachbesserung erneutes Review anfordern.

## QA Test Results
**Getestet:** 2026-08-20 · **Verdict: NOT READY — 1 Critical Bug (Prozess/Deployment, kein Logikfehler)**

### Kritischer Fund (BUG-1, Critical)

**Backend-Fix liegt im falschen Verzeichnis, nicht im gemeinsamen Feature-Worktree.**

`jupiter-backend` hat den verengten Create-Contract (extra="forbid", kanonische
`workspace_path`-Prüfung, Entfernung von `workspace_mode`/`project`/`branch`)
korrekt implementiert und getestet — aber im **Haupt-Checkout**
`/home/dev/projects/jupiter` (Branch `main`, uncommitted), NICHT im
zugewiesenen gemeinsamen Worktree `.worktrees/PROJ-84`
(Branch `specs/PROJ-84-hermes-kanban-arbeitsfluss-verfeinerung`), in dem
Frontend gearbeitet hat und der laut Skill-Vorgabe (`--workspace dir:<pfad>`)
der verbindliche Arbeitsort für dieses Feature ist.

`backend/app/schemas/hermes_kanban.py` im Worktree zeigt noch exakt den alten,
in der Architecture-Review (Runde 1) als unsicher befundenen Zustand
(`workspace_mode` akzeptiert `scratch|dir|worktree|worktree_path`, `project`/
`branch` volle Felder, keine kanonische Pfadprüfung).

**Eigener unabhängiger Nachweis (nicht nur Code-Diff, sondern Live-HTTP gegen
den auf dem Worktree-Code gestarteten Server, Port 8090):**
- `POST /hermes-kanban/tasks` mit `workspace_mode=worktree`, `branch=evil-branch` → **HTTP 200, ACCEPTED** (erwartet: 422)
- `POST .../tasks` mit `project=other-proj` → **HTTP 200, ACCEPTED** (erwartet: 422)
- `POST .../tasks` mit `workspace_path=/home/dev/projects/jupiter/../../etc` (Traversal) → **HTTP 200, ACCEPTED, workspace_kind="scratch"** (erwartet: 422, Pfad nie durchgereicht)
- `POST .../tasks` mit `workspace_path=/etc` (Root-Escape) → **HTTP 200, ACCEPTED** (erwartet: 422)
- Test-Tasks danach selbst archiviert (Cleanup).

Damit ist **AC C** ("Workspace-Modus fest `dir:`, kein Branch-Feld, Server
erzwingt kanonischen Pfad") im tatsächlich deploybaren Arbeitsstand
**FAIL** — trotz korrektem, isoliert getesteten Code im falschen Ordner.

Backend-`pytest`-Suite lief nur gegen den Haupt-Checkout grün (21/21 in
`test_proj82_hermes_kanban.py`, volle Suite 1328 passed/1 xfailed, 4
pre-existing unrelated Failures in `test_proj50_codex_abc.py` bestätigt via
Vergleichslauf ohne PROJ-84-Diff). Im zugewiesenen Worktree wurden diese
Tests nie ausgeführt/committed.

**Root Cause vermutlich:** Backend-Worker hat versehentlich im
Standard-Checkout statt im per `--workspace dir:<worktree-pfad>` vorgegebenen
Ordner gearbeitet.

**Fix:** Diff aus `/home/dev/projects/jupiter/backend/{app/schemas,app/routes}/hermes_kanban.py`
und `backend/tests/test_proj82_hermes_kanban.py` in den Worktree
`.worktrees/PROJ-84` übertragen (cherry-pick/manuell portieren), dort committen,
Tests im Worktree grün verifizieren. Änderungen im Haupt-Checkout danach
verwerfen (`git checkout -- ...`), damit `main` sauber bleibt.

### Acceptance Criteria — Ergebnis

**A — Phasenfilter und Board-Fläche: PASS** (Code-Review, `next build` grün)
- [x] Phasen-Popover ersetzt Archived-Toggle, 8 Checkboxen (`hermes-kanban-app.tsx:326-353`)
- [x] Alle 8 regulären Phasen initial ausgewählt (`:101-103`)
- [x] Lokaler Filter, kein Request (`useMemo` auf bereits geladenen `tasks`, `:193-196`)
- [x] Abgewählte Phasen erzeugen keine Spalte (`visibleCols.filter`, `:433-447`)
- [x] Leerer Filter zeigt deutschen Hinweis statt Auto-Reset (`:424-430`)
- [x] Kein Archived-Toggle mehr im Code
- [x] Spaltenhöhe `min-h-[33dvh]`, wächst mit Inhalt (`:538`, `flex-1 min-h-0 overflow-y-auto`)
- [x] Kompakt bei wenig Inhalt, scrollbar bei viel Inhalt ohne andere Spalten zu verdecken

**B — Angedocktes Task-Detail: PASS** (Code-Review, `next build` grün)
- [x] Detail rechts angedockt via `lg:flex-row` Split (`hermes-kanban-app.tsx:416-462`), kein Vollbild-Overlay
- [x] `lg:w-[40rem]` deutlich breiter als vorherige Implementierung; `<pre>` mit `overflow-auto` für Worker-Log (`task-detail-panel.tsx:132,159,338`)
- [x] Schließen entfernt Pane vollständig (`onClose` setzt `selectedTaskId=null`)
- [x] Schmale Ansicht: `max-h-[70vh] w-full` gestapelt, Schließen-Button immer erreichbar (`:132,142,159`)
- [x] Detail aktualisiert sich nach Aktionen/Refresh (`onChanged`-Callback, `refresh()`-Aufrufe)

**C — Neues Task-Formular: teils FAIL (siehe BUG-1)**
- [x] Beschreibungsfeld `rows=10`, deutlich größer (`new-task-dialog.tsx:307-319`)
- [x] `PushToTalkButton` aus PROJ-20 direkt am Feld, hängt Text an (`:315-318`, `appendTranscript` `:198-200`)
- [x] Wiederverwendung der PROJ-20-Komponente 1:1 (kein neuer Transkriptionsdienst)
- [x] `jupiter-coordinator` vorausgewählt nur wenn verfügbar (`:141`)
- [x] Assignee änderbar, "Kein Assignee" auswählbar (`:331`)
- [x] Kein Projektfeld mehr im Formular, kein `project` im Payload (`:217-236`)
- [x] Kein Workspace-Modus-/Branch-Feld im Formular
- [x] Workspace-Pfad startet mit `/home/dev/projects/`, vollständiger Pfad sichtbar (`:356-373`)
- [x] Client-seitige Blockade bei leerem/ungültigem Pfad (`pathError`, `:174-182`)
- [ ] **Serverseitige Durchsetzung FAIL** — im gemeinsamen Worktree fehlt die kanonische Prüfung/`extra=forbid` komplett (BUG-1); ein direkter API-Call umgeht die Frontend-Beschränkung vollständig.
- [x] Parents unter „Erweitert" (`:409-443`)
- [x] Bestehende Validierung (Titel, Triage, Model/Provider-XOR) unverändert wirksam

### Regression
- Kein Regressionstest gegen `features/INDEX.md` nötig über das oben Geprüfte hinaus — PROJ-84 ändert nur die 3 UI-Komponenten + den Create-Contract; Lese-Endpunkte, Board/Assignee-Aktionen, TaskActions unverändert (Diff-Scope bestätigt: nur `hermes-kanban-app.tsx`, `new-task-dialog.tsx`, `task-detail-panel.tsx`, `lib/types.ts` im Worktree).
- Backend-Unrelated-Failures (4x `test_proj50_codex_abc.py`, stale-tmp-path) unabhängig via Vergleichslauf ohne PROJ-84-Diff auf `main` bestätigt vorbestehend.

### Security-Redteam
- Auth-Gate bestätigt: `no-auth` Request auf `POST /hermes-kanban/tasks` → 401 (korrekt, Contract-Bug ist unabhängig davon).
- SQL-Injection-artiger Titel (`'; DROP TABLE tasks; --`) wurde als literaler String angenommen, kein Crash — Route ist reine CLI-Durchreiche ohne SQL, kein Injection-Vektor.
- Path-Traversal/Root-Escape/Legacy-Field-Injection: siehe BUG-1 oben — im aktuell deploybaren Arbeitsstand nicht abgewehrt.

### Browser-E2E (abc-qa-e2e, Einschränkung)
- Login-Seite rendert korrekt (Screenshot via Chrome-CLI-Fallback bestätigt: Benutzername/Passwort-Formular, `Jupiter · Anmelden`).
- Playwright-MCP-Browser-Toolset in dieser Session dauerhaft blockiert (Chrome-Subprozesse laufen defunct/hängen, Environment-Problem, kein Feature-Bug). Ausgewichen auf Chrome-CLI-Headless-Screenshot + reine HTTP/API-Verifikation (curl-äquivalent via Python/urllib mit selbst gemintetem JWT gegen den auf Worktree-Code laufenden Server, Port 8090). Kein Login mit echten Zugangsdaten durchgeführt (keine bekannten/dokumentierten Testcredentials gefunden) — daher keine eingeloggte Klick-Sequenz durchs Board/Formular verifiziert; das entspricht der bekannten Grenze aus dem `abc-qa-e2e`-Skill (CanvasKit/Auth-State nicht klickbar) und wurde stattdessen über Code-Review + `next build` + Live-API-Redteam kompensiert.
- Responsive 375/768/1440px nicht separat gegen echten Browser verifiziert (Blocker s.o.); Tailwind-Breakpoints (`lg:` = 1024px) im Code plausibel und konsistent mit AC B / Edge-Case „zu schmal für Split".

### Verdict
**NOT READY.** 1 Critical Bug (Prozess/Deployment — Fix existiert, liegt aber im falschen Ordner und ist im gemeinsamen Feature-Worktree nicht wirksam). Kein Logik- oder Codefehler im eigentlichen Fix. Alle Frontend-ACs (A, B, weitgehend C) PASS. Nach Portierung des Backend-Fixes in den Worktree + Commit ist Re-Verifikation gegen denselben Live-Redteam-Test erforderlich.

## Deployment

_To be added by /abc-deploy_
