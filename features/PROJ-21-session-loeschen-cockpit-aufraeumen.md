# PROJ-21: Session-Löschen / Cockpit-Aufräumen

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23

## Kontext / Motivation
Das Backend hat aktuell **keinen Lösch-Pfad** für Sessions. Das `SessionIndexRepository`
(SQLite, `backend/app/db/session_index.py`) kennt nur `upsert` / `list_all` — kein `delete`.
Folge: Terminale Sessions (`done` / `error` / verwaist) bleiben dauerhaft im Live-Index und
werden bei jedem Backend-Restart via `rehydrate()` neu geladen. In der UI lassen sie sich nicht
entfernen; sie mussten am 2026-06-23 manuell per `DELETE FROM session_index` bereinigt werden.
Dieses Feature schließt das Produkt-Gap: ein sauberer Lösch-/Aufräum-Pfad von der API bis ins Cockpit.

## Dependencies
- Requires: **PROJ-1** (Engine-Treiber) — `SessionManager` + In-Memory-Registry, die der Lösch-Pfad bereinigt
- Requires: **PROJ-14** (Härtung: Limit + Persistenz) — der SQLite-Live-Index + `rehydrate()`, an dem `delete` ansetzt
- Requires: **PROJ-3** (Cockpit) — Mission-Control-Kacheln + Sidebar, in denen Lösch-/Aufräum-UI sitzt

## User Stories
- Als Operator möchte ich eine einzelne fehlgeschlagene/erledigte Session-Kachel löschen, um die Lagebild-Übersicht sauber zu halten.
- Als Operator möchte ich mit einer Aktion „Erledigte aufräumen" **alle** terminalen Sessions auf einmal entfernen, statt jede einzeln wegzuklicken.
- Als Operator möchte ich, dass ein versehentlich noch laufender, nicht steuerbarer Claude-Prozess beim Löschen einer verwaisten Session mit beendet wird, damit keine Geister-Prozesse Tokens verbrennen.
- Als Operator möchte ich vor jedem Löschen eine Bestätigung sehen, um nicht versehentlich Sessions zu entfernen.
- Als Operator möchte ich, dass eine **aktive** Session sich nicht löschen lässt, damit laufende Arbeit nicht abgewürgt wird.

## Funktionsumfang / Entscheidungen
- **Löschbar = nur terminale Sessions:** `done`, `error` und verwaiste Sessions. Aktive Stati
  (`starting`, `running`, `waiting`, „Freigabe nötig") sind **nicht** löschbar.
- **Bulk „Erledigte aufräumen" = alle terminalen** (`done` + `error` + verwaist) auf einmal.
- **Orphan-Prozess:** Hat eine (verwaiste) Session noch eine lebende persistierte PID, wird der
  OS-Prozess beim Löschen **best-effort per SIGTERM beendet** (kein harter SIGKILL im ersten Schritt).
- **Lösch-Tiefe = nur Live-Index:** Entfernt den Eintrag aus SQLite **und** der In-Memory-Registry.
  Das Session-Log/Transkript im **Vault bleibt erhalten** (Design-Prinzip „Live-Index, nicht die Wahrheit").
- **Bestätigung immer:** Sowohl Einzel- als auch Bulk-Löschen zeigen einen Bestätigungsdialog
  (shadcn/ui `AlertDialog`). Deutsche UI.

## Acceptance Criteria

### Backend — Repository
- [ ] `SessionIndexRepository`-Protokoll erhält `async def delete(session_id: str) -> None`.
- [ ] `SqliteSessionIndexRepository.delete` führt `DELETE FROM session_index WHERE session_id = ?` aus (parametrisiert, via `asyncio.to_thread`).
- [ ] `NullSessionIndexRepository.delete` ist ein No-op (Persistenz aus → kein Fehler).
- [ ] Optionale Bulk-Hilfe `async def delete_terminal(statuses: list[str]) -> int` ODER der Manager iteriert über `delete` — Entscheidung dem Architekten überlassen; Verhalten = alle terminalen weg.

### Backend — Manager
- [ ] `SessionManager.delete(session_id)` entfernt die Session aus der In-Memory-Registry **und** ruft `repo.delete`.
- [ ] Ist die Session **aktiv** (Status in `ACTIVE_STATES` bzw. nicht terminal), wirft `delete` einen Fehler, der als **HTTP 409** an die UI geht.
- [ ] Hat die zu löschende Session eine **lebende** persistierte PID, wird best-effort `SIGTERM` an den Prozess gesendet (Fehler beim Kill blockieren das Löschen nicht — best-effort, geloggt).
- [ ] `SessionManager.cleanup_terminal() -> int` löscht alle terminalen Sessions (done/error/verwaist), gibt die Anzahl zurück und wendet dieselbe Orphan-Kill-Regel pro Session an.

### Backend — API (`backend/app/routes/sessions.py`)
- [ ] `DELETE /sessions/{session_id}` → `204 No Content` bei Erfolg.
- [ ] `DELETE /sessions/{session_id}` auf unbekannte ID → **404** (`"Session nicht gefunden."`).
- [ ] `DELETE /sessions/{session_id}` auf aktive Session → **409** (`"Aktive Session kann nicht gelöscht werden — zuerst stoppen."`).
- [ ] `POST /sessions/cleanup` (oder `DELETE /sessions?status=terminal`) → `{"deleted": <int>}`, löscht alle terminalen.
- [ ] Nach `delete` taucht die Session in `GET /sessions` **nicht** mehr auf — auch nicht nach einem Backend-Restart (rehydrate lädt sie nicht erneut).

### Frontend — Cockpit (Next.js, `nextjs_app`)
- [ ] Jede **terminale** Kachel (Mission Control) zeigt einen Lösch-Button (Icon/Trash). Aktive Kacheln zeigen ihn **nicht** (oder disabled).
- [ ] Die Sidebar-Einträge terminaler Sessions sind ebenfalls löschbar (Kontextmenü oder Hover-Button).
- [ ] Eine globale Aktion „Erledigte aufräumen" ist sichtbar, sobald ≥ 1 terminale Session existiert; sie zeigt die Anzahl betroffener Sessions an.
- [ ] Einzel- **und** Bulk-Löschen öffnen einen `AlertDialog` mit deutschem Text und „Abbrechen" / „Löschen".
- [ ] Nach erfolgreichem Löschen verschwindet die Kachel/der Eintrag (Liste wird neu geladen/gepollt); ein Erfolgs-Toast bestätigt (z. B. „Session gelöscht." / „3 Sessions aufgeräumt.").
- [ ] Fehlerfall (409/404/Netzwerk) zeigt eine deutsche Fehlermeldung (Toast/Inline), die Liste bleibt konsistent.
- [ ] Loading-/Disabled-Zustand während des Löschens (kein Doppel-Klick-Trigger).

## Edge Cases
- **Aktive Session:** Löschen wird mit 409 abgelehnt; UI erklärt „zuerst stoppen". Bulk überspringt aktive Sessions stillschweigend (löscht nur terminale).
- **Verwaiste Session mit toter PID:** Kill entfällt (PID nicht lebend), Eintrag wird normal entfernt.
- **Verwaiste Session mit lebender PID:** SIGTERM best-effort; schlägt der Kill fehl (Permission/race), wird trotzdem aus dem Index gelöscht und der Vorgang als Warnung geloggt.
- **Race — Session wechselt Status zwischen UI-Klick und Request:** Server entscheidet autoritativ; wird sie inzwischen aktiv, kommt 409 zurück und die UI aktualisiert.
- **Concurrent Bulk + Einzel-Delete:** `delete` ist idempotent — eine bereits entfernte ID liefert 404 bzw. wird im Bulk-Zähler nicht doppelt gezählt.
- **Persistenz aus (`NullSessionIndexRepository`):** Löschen wirkt nur In-Memory; kein Fehler.
- **Leerer Zustand:** Sind keine terminalen Sessions da, ist „Erledigte aufräumen" ausgeblendet/disabled.
- **Vault-Log:** Bleibt nach dem Löschen erhalten; ein späteres Recovery (PROJ-17) kann die Session bei Bedarf aus dem Vault rekonstruieren.

## Technical Requirements (optional)
- Performance: `DELETE` und `cleanup` < 200 ms bei realistischer Session-Zahl (≤ einige Dutzend).
- Security: MVP single-user, **kein JWT/RLS** (Jupiter-Override). `owner` serverseitig gestempelt; Pfade/IDs validiert.
- Parametrisierte SQL ausschließlich (kein String-Concat).
- Best-effort-Prinzip: DB- oder Kill-Fehler dürfen den In-Memory-Pfad / die UI nicht blockieren (degradiert zu Warnung).
- Browser Support: Chrome, Firefox, Safari (Next.js Web).
- Mobile: responsiv ab 375 px.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
