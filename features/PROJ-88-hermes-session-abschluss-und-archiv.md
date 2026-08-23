# PROJ-88: Hermes-Sessions eindeutig beenden, archivieren und löschen

## Status: Approved
**Created:** 2026-08-23
**Last Updated:** 2026-08-23

## Kontext / Motivation

Ein erfolgreicher Hermes-Turn beendet seinen direkten Prozess absichtlich und
bleibt danach als `waiting` fortsetzbar. Das ist korrekt, wirkt im Cockpit aber
wie eine beendete Session unter „Aktive Sessions“. Nicht mehr nutzbare
Hermes-Sessions lassen sich aus der Detailansicht weder eindeutig abschließen
noch direkt löschen. Dadurch bleiben sie im aktiven Lagebild hängen.

PROJ-88 macht den Abschluss einer Hermes-Session explizit: Der Nutzer kann sie
aus der Detailansicht beenden und ins Archiv verschieben oder eine bereits
terminale Hermes-Session dort löschen. Der normale Folge-Turn bleibt
unverändert fortsetzbar.

## Dependencies

- Requires: PROJ-3 (Cockpit: Mission Control + Kanban + Ampel-Kacheln) — bestehende Session-Ansicht und Archiv.
- Requires: PROJ-21 (Session-Löschen / Cockpit-Aufräumen) — bestehender autorisierter Löschpfad.
- Requires: PROJ-85 (Hermes-Chat-Sessions im Cockpit) — Hermes-Sessiontyp.
- Requires: PROJ-86 (Hermes-Chat direkt fortsetzen) — `waiting` ist ein regulärer, fortsetzbarer Hermes-Zustand.

## User Stories

- Als Nutzer möchte ich eine ruhende Hermes-Session bewusst **beenden & archivieren**, damit sie nicht länger unter aktiven Sessions erscheint.
- Als Nutzer möchte ich eine laufende Hermes-Session nach Bestätigung abbrechen und archivieren, damit kein weiterer Turn weiterläuft.
- Als Nutzer möchte ich eine nicht fortsetzbare Hermes-Session mit Fehler ins Archiv verschieben, ohne sie reanimieren oder eine neue Unterhaltung vortäuschen zu müssen.
- Als Nutzer möchte ich eine terminale Hermes-Session direkt aus ihrer Detailansicht löschen, damit ich nicht erst Kachel oder Sidebar suchen muss.
- Als Nutzer möchte ich eine regulär wartende Hermes-Session weiterhin einfach fortsetzen können, damit der Abschluss nicht versehentlich erfolgt.

## Acceptance Criteria

- [ ] Die Detailansicht einer Hermes-Session mit Status `waiting` zeigt eine eindeutig benannte Aktion **„Beenden & archivieren“**.
- [ ] Die Aktion verlangt vor dem Abschluss eine deutsche Bestätigung; Abbrechen ändert weder Status noch laufenden Hermes-Turn.
- [ ] Nach bestätigtem Abschluss hat die Hermes-Session den Status `done`, verschwindet aus „Aktive Sessions“ und erscheint im bestehenden Archiv in Kacheln und Sidebar.
- [ ] Bei einer Hermes-Session mit aktivem Turn beendet dieselbe Aktion den Turn sauber, bevor sie archiviert wird.
- [ ] Bei einer Hermes-Session mit Status `error` ist **„Ins Archiv verschieben“** verfügbar; die Aktion startet Hermes nicht erneut und überführt die Session in `done`.
- [ ] Der Fehlertext einer archivierten Hermes-Fehlersession bleibt beim Öffnen der Session einsehbar.
- [ ] Eine Hermes-Session mit Status `done` oder `error` zeigt in ihrer Detailansicht die bestehende Aktion **„Session löschen“** mit Bestätigungsdialog.
- [ ] „Session löschen“ entfernt nur die eigene Session aus dem Cockpit; das Session-Log im Vault bleibt erhalten und fremde Sessions bleiben nicht zugreifbar.
- [ ] Für Nicht-Hermes-Sessions ändern sich weder Detailaktionen noch Statusübergänge.
- [ ] Die automatisierten Tests decken mindestens ruhendes Archivieren, laufendes Archivieren, Fehler → Archiv, Löschen aus der Detailansicht sowie die Unverändertheit einer Nicht-Hermes-Session ab.

## Edge Cases

- **Doppelklick / parallele Aktion:** Während Abschluss oder Löschen läuft, ist die jeweilige Aktion gesperrt; es entsteht kein zweiter Stop- oder Löschaufruf.
- **Hermes beendet den Turn während der Bestätigung:** Der Abschluss behandelt den inzwischen ruhenden Zustand als Erfolg und archiviert genau einmal.
- **Backend oder Netzwerk nicht erreichbar:** Der Nutzer erhält eine deutsche Fehlermeldung; die Session bleibt sichtbar und ihr lokaler UI-Zustand wird danach aktualisiert.
- **Session wurde in einem anderen Tab bereits gelöscht:** Die Detailansicht meldet „Session war bereits gelöscht“ und kehrt in eine konsistente Cockpit-Ansicht zurück.
- **Fremde oder unbekannte Session-ID:** Die bestehenden 404-/Owner-Schutzregeln bleiben wirksam; weder Archivieren noch Löschen leakt Sessiondaten.
- **Archivierte Fehlersession:** Das Archiv zeigt sie als beendet, nicht als fortsetzbar; ihre Diagnose bleibt ausschließlich zur Einsicht erhalten.

## Non-Goals

- Keine Änderung am Hermes-Resume-Vertrag oder automatische Archivierung nach jedem erfolgreichen Turn.
- Keine Änderung an Liveness, tmux oder Reanimation für Hermes oder andere Engines.
- Keine neue Archivdatenbank, kein neuer Sessionstatus und kein neues Berechtigungsmodell.
- Keine Änderung am globalen Löschen oder an Detailaktionen anderer Engines.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-23 · **Stack:** Next.js/shadcn + FastAPI + raw-SQL/SQLite-Session-Index mit JWT-Owner-Scope; Hermes CLI; Dokploy · **Branch:** main

### Ziel und bestehender Rahmen

PROJ-88 ergänzt keinen neuen Status, keine Archiv-Datenbank und keinen neuen
Hermes-Resume-Pfad. Das bestehende `done` ist das Archiv-Signal: Kacheln und
Sidebar zeigen nur `done` im bestehenden Archiv. Für Hermes wird der bewusste
Abschluss deshalb als schmaler Servervorgang ergänzt: laufenden Turn beenden,
danach einmalig `done` persistieren. Eine normale Hermes-Session auf `waiting`
bleibt ohne Nutzeraktion unverändert fortsetzbar.

Jupiter verwendet tatsächlich SQLite, raw SQL und einen serverseitig erzwungenen
Owner-Scope aus JWT-`sub` (PROJ-25), nicht Postgres/`mandant_id`/DB-RLS. Dieser
Feature-Scope führt keine widersprüchliche Persistenzplattform ein: Jeder neue
Lese- und Schreibpfad authentifiziert per JWT und prüft den Owner vor Zugriff.

### Komponenten und Nutzerfluss

```
Bestehende SessionView (nur engine = hermes)
├── waiting
│   └── AbschlussDialog „Beenden & archivieren"
├── running / starting
│   └── AbschlussDialog „Beenden & archivieren"
│       └── POST /sessions/{id}/archive
├── error
│   ├── AbschlussDialog „Ins Archiv verschieben"
│   └── bestehender DeleteSessionButton „Session löschen"
└── done
    └── bestehender DeleteSessionButton „Session löschen"

SessionManager.archive_hermes()
├── Owner-geprüfte Session aus Route
├── bei aktivem Turn: bestehende stop()-Semantik wiederverwenden
│   (driver.stop() + abandon_decisions(), wie in manager.py:2380-2385) —
│   kein zweiter, abweichender Stop-Pfad
├── Status done + Zeitstempel persistieren und State senden
└── Fehlertext einer Fehler-Session unverändert erhalten

Mission Control / SessionRail
└── bestehendes done-Archiv zeigt die abgeschlossene Hermes-Session
```

Der Dialog ist deutsch und erklärt die Wirkung. „Abbrechen" löst keinen Request
aus. Während Request oder Löschung läuft, ist die jeweilige Aktion gesperrt.
Nach Erfolg aktualisiert der vorhandene `SessionsProvider` sofort. Das Detail
bleibt nach Archivieren geöffnet, zeigt `Fertig` und bei zuvor `error` weiterhin
die gespeicherte Diagnose; nach Löschen schließt es die gelöschte Ansicht und
kehrt zur konsistenten Cockpit-Ansicht zurück.

Nicht-Hermes-Sessions erhalten weder neue Detailaktionen noch geänderte
Übergänge. Bestehende Kachel-, Rail- und Bulk-Löschregeln aus PROJ-21 bleiben
unverändert.

### Datenmodell, Schreiber und Lesepfade

Keine neue Tabelle, keine MinIO-Objekte und keine neue Abhängigkeit. Es werden
nur bestehende Session-Felder verwendet.

1. **Session** (bestehender SQLite-Live-Index)
   - Relevante Felder: `session_id`, `owner`, `engine`, `status`, `error`,
     `last_activity`, Prozess-/Transport-Metadaten und Transkriptverweis.
   - Zulässiger neuer Ablauf nur bei `engine="hermes"`: `waiting` oder aktiv
     (`starting`/`running`) nach `done`; `error` nach `done`. Ein `error`-Text
     wird beim letzten Übergang nicht geleert.
   - **Schreiber/Owner:** `POST /sessions/hermes` erzeugt die Session; der
     bestehende SessionManager schreibt Turn-Zustände. Ausschließlich der neue,
     owner-geprüfte Pfad `POST /sessions/{id}/archive` darf diesen expliziten
     Hermes-Abschluss schreiben. Der Owner wird stets aus JWT-`sub` gestempelt,
     nie aus Browserdaten.
   - **Lesepfade:** `GET /sessions` versorgt aktive Liste und Archiv; `GET
     /sessions/{id}` sowie `WS /sessions/{id}/stream` versorgen Detail,
     Bestätigungszustand und erhaltene Diagnose. Jeder Pfad prüft JWT und Owner
     vor dem Lesen. Der bereits vorhandene `GET /sessions/{id}`-Lesepfad läuft
     vor der Detailaktion; er liefert Engine und Status, damit nur passende
     Aktionen erscheinen.

2. **UI-Transkript und Fehlerdiagnose** (bestehend, 1:1 zur Session)
   - Inhalte: Rollen-/Text-/Zeit-Einträge sowie nullable `error` auf der
     Session. Es ist Anzeigehistorie, kein neuer Hermes-Kontext oder Archiv.
   - **Schreiber/Owner:** HermesChatDriver und SessionManager schreiben sie aus
     bestehenden Stream-/Fehlerereignissen; der Archivpfad schreibt keine neue
     Nachricht und verändert eine vorhandene Fehlerdiagnose nicht.
   - **Lesepfade:** `GET /sessions/{id}`, `GET /sessions/{id}/transcript` und
     der owner-geprüfte WS-Snapshot. Die Detailansicht lädt diese vor dem
     Archivieren/Löschen; nach Fehler-Archivierung rendert sie den erhaltenen
     Fehler auch bei Status `done`.

3. **Löschauftrag** (kein persistiertes Domänenobjekt)
   - Ein bestätigter, einmaliger Aufruf des bestehenden `DELETE /sessions/{id}`.
     Er entfernt ausschließlich Registry und SQLite-Live-Index; das Vault-Log
     bleibt gemäß PROJ-21 erhalten.
   - **Schreiber/Owner:** `DeleteSessionButton` der Hermes-Detailansicht löst
     ihn aus; Route und Manager prüfen Owner und terminalen Status. Der Browser
     schreibt keinen Owner, kein Log und keine Archivdaten.
   - **Lesepfade:** `GET /sessions/{id}` vor Anzeige des Buttons; `GET
     /sessions` nach Erfolg für die Refetch-Ansicht. 404 für fremde/unbekannte
     IDs bleibt absichtlich einheitlich und leakt keine Session.

### API- und Fehlervertrag

Alle Endpunkte verlangen JWT. `owner` kommt ausschließlich aus dem Token; die
Route verwendet vor jeder Manageraktion den vorhandenen Owner-Guard.

| Methode | Pfad | Erfolg | Fehler / Regeln |
|---|---|---|---|
| POST | `/sessions/{id}/archive` | 200, normaler `SessionRead`-Snapshot mit `status="done"` | 404 fremd/unbekannt; 409 Nicht-Hermes oder unzulässiger Status; 503 wenn ein laufender Hermes-Turn nicht sauber gestoppt werden kann. |
| DELETE | `/sessions/{id}` (bestehend) | 204 ohne Body | 404 fremd/unbekannt/bereits gelöscht; 409 nicht terminal. Nur bei Hermes `done` oder `error` zeigt PROJ-88 die Detailaktion. |
| GET | `/sessions`, `/sessions/{id}` (bestehend) | bestehende Snapshots | unverändert; liefert den Status für aktive Liste/Archiv und Fehleranzeige. |

`POST /sessions/{id}/archive` ist statisch nicht erforderlich, liegt aber wie
alle Unterpfade vor `/{session_id}`-Catchalls, falls solche später ergänzt
werden. Der Manager ist autoritativ:

- `waiting`: kein Prozessstart/-resume; direkt `done` persistieren.
- `starting`/`running`: erst Driver stoppen. Erst nach bestätigtem Stop wird
  `done` persistiert; ein Stop-Fehler lässt die Session sichtbar und liefert
  503.
- `error`: nie Hermes starten oder reanimieren; direkt `done` persistieren,
  vorhandenen `error` beibehalten.
- `done`: idempotent als bereits archivierter Erfolg behandeln. Das entschärft
  Doppelclick/Tab-Rennen ohne einen zweiten Stop.

Der Manager sendet nach Persistenz einen State-Snapshot. So aktualisieren WS,
Detailansicht und Polling ohne lokale Statusannahme. Beim parallel erfolgten
Turn-Ende wird `waiting` ebenfalls direkt zu `done`; genau ein Abschluss bleibt
sichtbar.

### Frontend-Abgrenzung

- Neue kleine Komposition `ArchiveHermesSessionButton` auf Basis des vorhandenen
  `ConfirmDialog`, `sonner`, `useSessions().refresh()` und API-Fehlerformats.
  Keine neue UI-Primitive und kein zweites Archiv.
- Einbau ausschließlich in `SessionView`: sichtbarer Abschluss bei Hermes
  `waiting`/aktiv, „Ins Archiv verschieben" bei Hermes-`error`; bestehender
  `DeleteSessionButton` zusätzlich in derselben Detailansicht bei Hermes
  `done`/`error`.
- `SessionView` zeigt nach Fehler-Archivierung die gespeicherte Diagnose weiter,
  obwohl der Archivstatus `done` ist. Composer/Stop sind dann nicht mehr als
  Fortsetzen-Aktion für diese Hermes-Session anzubieten.
- Bestehende Filter in `page.tsx`, `archived-section.tsx` und `session-rail.tsx`
  benötigen keinen neuen Status: `done` wandert bereits aus aktiven Listen in
  Kachel- und Sidebar-Archiv.

### Entscheidungen / ADRs

- **ADR-88-1 — `done` statt neuer Archivstatus: angenommen.** Archiv ist bereits
  UI-Sicht auf `done`; ein neuer Status würde Listen, Schema und PROJ-21 ohne
  Produktnutzen aufspalten.
- **ADR-88-2 — eigener Hermes-Archivpfad statt generischem Stop: angenommen.**
  Der bestehende Stop bleibt für alle Engines unverändert. Der neue Pfad kann
  Hermes-spezifisch aktiven Turn stoppen, Fehler ohne Reanimation abschließen
  und Nicht-Hermes zuverlässig ausschließen.
- **ADR-88-3 — Fehlertext bleibt nach `error` nach `done`: angenommen.** Die
  Archivierung ist ein Lagebildwechsel, keine Diagnose-Löschung; dies erfüllt
  die spätere Einsicht ohne zweites Fehlerarchiv.
- **ADR-88-4 — vorhandenes Delete wiederverwenden: angenommen.** PROJ-21
  garantiert terminales, owner-geschütztes Live-Index-Löschen bei erhaltenem
  Vault-Log. Der Featurewert ist dessen fehlende Detailplatzierung, nicht eine
  parallele Löschsemantik.
- **ADR-88-5 — bestehender JWT-Owner-Scope: angenommen.** Der echte Stack ist
  SQLite/single-tenant mit Service-Scoping, nicht Postgres-RLS. Neue Routen
  folgen dem vorhandenen `_owned_or_404`-Vertrag; ein `mandant_id`-Feld wird
  weder erfunden noch aus dem Client übernommen.

### Lieferreihenfolge und Tests

1. Backend: Manager-Archivübergang, owner-geschützte Route und gezielte Tests.
   Testmatrix: waiting, aktiver Turn, error ohne Spawn, `done`-Idempotenz,
   Stop-Fehler, fremde/unbekannte ID und Nicht-Hermes-409.
2. Frontend: Bestätigungsdialog, Busy-Sperre, Detail-Löschen, Fehlerdiagnose
   nach Archivierung und Close/Refresh nach 404-Löschen.
3. Regression: gezielt prüfen, dass eine wartende Hermes-Session ohne Aktion
   weiter `POST /input` annimmt und eine Nicht-Hermes-Session weder neue Aktion
   noch neuen Zustandsübergang erhält.

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-23 · **Verdict:** Architected

### Checklist
- [x] Component structure — ok. Nur bestehende `SessionView`/`ConfirmDialog`/`sonner`/`useSessions()` verwendet, keine neue Primitive.
- [x] Data model — ok, kein neues Feld. `session_id`/`owner`/`engine`/`status`/`error`/`last_activity` bestätigt in `backend/app/db/session_index.py:30-45`. Owner-Scope via JWT-`sub`, kein `mandant_id`/RLS (korrekt, Stack ist SQLite/single-tenant).
- [x] API shape — ok. `POST /sessions/{id}/archive` existiert nicht im Code (verifiziert: `sessions.py`, 503 Zeilen, kein `/archive`), muss neu gebaut werden — Design korrekt. `DELETE /sessions/{id}` existiert bereits (`sessions.py:306-322`, Owner-Guard `_owned_or_404:316`, 409 via `SessionActiveError` bei `ACTIVE_STATES` `manager.py:2403-2406`). `GET /sessions`, `GET /sessions/{id}` bestätigt vorhanden.
- [x] Tech decisions — 5 ADRs mit Begründung, keine Blankobehauptung.
- [x] Dependencies — keine neuen Pakete; `sonner` bereits in `package.json:24`.
- [x] Branch — `main` genannt.
- [x] Conflict-free — kein Routing-Konflikt; `/sessions/{id}/archive` liegt vor keinem Catchall, analog zu `/stop`, `/pause`, `/reanimate` (`sessions.py:260-303`).
- [x] Acceptance-criteria coverage — alle 10 ACs decken sich mit Tech-Design-Abschnitten (waiting→done, aktiv→stop+done, error→done ohne Reanimation, Fehlertext erhalten, delete-Detailaktion, Nicht-Hermes unverändert, Testmatrix).

### Owner-Check
`POST /sessions/{id}/archive` als einziger Schreibpfad für den expliziten Hermes-Abschluss benannt (Route + Manager). `DELETE /sessions/{id}` bestehender Schreibpfad fürs Löschen. Beide mit Owner-Guard. ✓ erfüllt.

### Lesepfad-Check
Für `archive`: `GET /sessions/{id}` liefert Engine/Status vor Anzeige der Aktion (dokumentiert). Für `delete`: `GET /sessions/{id}` vor Button-Anzeige, `GET /sessions` nach Erfolg für Refetch (dokumentiert). ✓ erfüllt.

### CodeGraph-Cross-Check (Explore-Agent + eigene Verifikation)
- `backend/app/routes/sessions.py:47-53` `_owned_or_404` bestätigt.
- `backend/app/routes/sessions.py:306-322` bestehendes `DELETE /{session_id}` bestätigt (404/409-Semantik wie im Design behauptet).
- `backend/app/engine/manager.py:2377-2409` `stop()`/`delete()` bestätigt; `ACTIVE_STATES` (`manager.py:61`) bestätigt für 409-Grenze.
- `nextjs_app/components/cockpit/delete-session-button.tsx` (existierender `DeleteSessionButton` inkl. `ConfirmDialog`, `sonner`, `useSessions().refresh()`) bestätigt — Design kann ihn wiederverwenden.
- `nextjs_app/components/cockpit/confirm-dialog.tsx` bestätigt, wiederverwendbar für Archiv-Dialog.
- `nextjs_app/components/cockpit/archived-section.tsx` sowie `session-rail.tsx:104-107,275-301` und `app/(cockpit)/page.tsx:40-41` bestätigen bestehenden `done`-Archiv-Filter — kein neuer Status nötig.
- `SessionManager.archive_hermes()` existiert nicht — neu zu bauende Methode korrekt als solche gekennzeichnet.

### Autonom behoben
- Tech Design nutzte `HermesChatDriver.stop()` direkt statt die bestehende `SessionManager.stop()`-Semantik (inkl. `abandon_decisions()`, `manager.py:2380-2385`) wiederzuverwenden — korrigiert, damit `archive_hermes()` keinen zweiten, abweichenden Stop-Pfad einführt.

### Offene Fragen
Keine.

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
