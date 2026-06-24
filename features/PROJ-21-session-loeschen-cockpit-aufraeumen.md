# PROJ-21: Session-Löschen / Cockpit-Aufräumen

## Status: In Progress
**Created:** 2026-06-23
**Last Updated:** 2026-06-24

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
**Erstellt:** 2026-06-24 · **Stack:** Next.js 16 (Cockpit) + FastAPI + SQLite-Live-Index · **Branch:** dev

### Kurzfassung
Es fehlt ein Lösch-Pfad über alle Schichten. Das Design ergänzt ihn additiv — keine bestehende
Methode wird umgebaut. Reihenfolge der Schichten: Repository → Manager → API → Cockpit.
Leitprinzip „Live-Index, nicht die Wahrheit": gelöscht wird nur der **Live-Eintrag**
(SQLite + In-Memory), das **Vault-Log/Transkript bleibt** unangetastet (ermöglicht Recovery via PROJ-17).

### A) Bestehender Stand (aus CodeGraph-Exploration)
- `SessionManager._sessions: dict[str, SessionRuntime]` — In-Memory-Registry je `session_id`.
  Status-Modell: `ACTIVE_STATES = {starting, running, waiting, awaiting_approval}`; terminal = `done`, `error`.
  Es gibt `stop(session_id)` (pausiert/beendet die Engine, markiert `done`) — aber **kein** Entfernen
  aus der Registry. PID liegt unter `runtime.driver.pid` und wird in `_row()` persistiert.
- `SessionIndexRepository` (Protokoll) kennt nur `init / upsert / list_all / close`; SQL läuft sync
  in `asyncio.to_thread`. Zwei Impls: `Sqlite…` (WAL, frische Connection je Op) und `Null…` (No-op).
  `rehydrate()` lädt beim Start alle Zeilen zurück → genau hier „überleben" gelöschte Sessions heute.
- `routes/sessions.py`: Manager via `_manager(request)`; etablierte Fehlermuster 404/409/429.
- Cockpit pollt `GET /sessions` alle 4 s über `SessionsProvider`/`useSessions()`. Toast = `sonner`
  (bereits vorhanden). `reset-session-button.tsx` ist die Vorlage für Button + Dialog + Toast.
  **`AlertDialog` existiert noch nicht** — neu anzulegen (auf Basis des vorhandenen `dialog.tsx`).

### B) Backend-Schichten

**1. Repository** (`backend/app/db/session_index.py`)
- Protokoll erhält `async def delete(session_id: str) -> None`.
- `Sqlite…`: `DELETE FROM session_index WHERE session_id = ?` (parametrisiert, in `asyncio.to_thread`).
  Idempotent — unbekannte ID ist kein Fehler auf Repo-Ebene.
- `Null…`: No-op.
- **Bulk-Entscheidung:** _Kein_ `delete_terminal` im Repo. Der Manager iteriert, weil nur er das
  autoritative Status-Wissen (aktiv vs. terminal) + die Orphan-Kill-Regel hat. Hält das Repo dumm.

**2. Manager** (`SessionManager`)
- `async def delete(session_id) -> None`:
  - Unbekannte ID → `KeyError`-Äquivalent → API mappt auf **404**.
  - Status in `ACTIVE_STATES` → Fehler → API mappt auf **409**.
  - Terminal/verwaist: lebt eine persistierte PID noch → **best-effort `SIGTERM`** (Fehler nur geloggt,
    blockiert nie). Danach Eintrag aus `_sessions` entfernen **und** `repo.delete(session_id)`.
- `async def cleanup_terminal() -> int`: iteriert über alle Sessions, ruft `delete` nur für terminale,
  überspringt aktive **stillschweigend**, gibt Anzahl gelöschter zurück. Wendet dieselbe Kill-Regel an.

**3. API** (`routes/sessions.py`)
- `DELETE /sessions/{session_id}` → **204** | 404 (`"Session nicht gefunden."`) | 409
  (`"Aktive Session kann nicht gelöscht werden — zuerst stoppen."`).
- `POST /sessions/cleanup` → **200** `{"deleted": <int>}`.
  (Gewählt statt `DELETE /sessions?status=terminal`: eigener Pfad, kein Query-Parsing, klare Semantik.)

### C) Frontend-Komponenten (`nextjs_app`)
```
SessionTile / SessionRail-Eintrag (terminal)
└── DeleteSessionButton (Trash-Icon; nur bei done/error/verwaist sichtbar)
    └── ConfirmDeleteDialog (neuer AlertDialog: "Session löschen?" · Abbrechen | Löschen[destructive])
        → api.deleteSession(id) → Toast "Session gelöscht." → Provider-Refetch

GlobalStatusBar / Mission-Control-Kopf
└── CleanupButton "Erledigte aufräumen (N)"  (nur sichtbar wenn N≥1 terminale)
    └── ConfirmDeleteDialog (Bulk-Text: "N Sessions aufräumen?")
        → api.cleanupSessions() → Toast "N Sessions aufgeräumt." → Refetch
```
- Neuer `api.ts`: `deleteSession(id)` (DELETE, 204→void), `cleanupSessions()` (POST → `{deleted}`).
- Neue UI-Primitive `components/ui/alert-dialog.tsx` (shadcn-Pattern, auf vorhandenem Dialog aufbauend).
- Lösch-Button trägt Loading-/Disabled-State (kein Doppel-Klick). Fehler (404/409/Netz) → deutscher
  Toast, Liste wird neu gepollt und bleibt konsistent.
- Aktive Kacheln zeigen den Button nicht (bzw. disabled). Server bleibt autoritativ (Race → 409 → Refetch).

### D) Tech-Entscheidungen (Begründung)
- **Bulk-Logik im Manager, nicht im Repo:** „aktiv vs. terminal" und der Orphan-Kill sind Laufzeit-Wissen
  des Managers; das Repo kennt nur Zeilen. So bleibt SQL trivial und testbar.
- **SIGTERM statt SIGKILL:** Engine darf sauber herunterfahren; Geister-Prozesse werden gestoppt, ohne
  hart abzuschießen. Schlägt der Kill fehl, wird trotzdem gelöscht (Best-effort, Warn-Log).
- **Nur Live-Index löschen:** Vault bleibt Wahrheit → versehentliches Löschen ist über Recovery heilbar.
- **`DELETE` + `POST /cleanup` statt einem Endpoint:** RESTful für Einzel-Delete (204), expliziter
  Bulk-Pfad mit Zähler-Antwort; konsistent mit den vorhandenen `POST /{id}/…`-Steuerpfaden.
- **Eigener `AlertDialog`:** Bestätigung ist Pflicht (AC); `sonner`-Toasts existieren bereits → wiederverwenden.

### E) Dependencies
Keine neuen Pakete. Backend: stdlib `signal`/`os` (SIGTERM). Frontend: vorhandenes `sonner` +
Base-UI-Dialog (Grundlage für den neuen `alert-dialog`). Kein JWT/RLS (Jupiter-MVP-Override).

### Schnittstellen-Kontrakt (für frontend/backend)
| Methode | Pfad | Erfolg | Fehler |
|---|---|---|---|
| DELETE | `/sessions/{id}` | 204 (kein Body) | 404 unbekannt · 409 aktiv |
| POST | `/sessions/cleanup` | 200 `{"deleted": int}` | — (überspringt aktive still) |

### Implementierungs-Notizen — Frontend (2026-06-24)
**Branch:** dev · Stack: Next.js 16 (kein Flutter — Jupiter-Override).

Neu:
- `lib/api.ts`: `deleteSession(id)` (DELETE → void via 204-Pfad), `cleanupSessions()` (POST → `{deleted}`).
- `lib/status.ts`: `isTerminalStatus(status)` (done|error) + `countTerminal(sessions)` — eine Quelle für UI-Sichtbarkeit (Server bleibt autoritativ).
- `components/cockpit/confirm-dialog.tsx`: wiederverwendbarer Bestätigungs-Dialog (kontrolliert, deutsch, destruktiver Confirm) auf Basis des vorhandenen base-ui-`Dialog`. **Bewusst kein separater `ui/alert-dialog.tsx`** — der vorhandene Dialog deckt die AC voll ab, weniger neue Primitive.
- `components/cockpit/delete-session-button.tsx`: Einzel-Löschen. Sitzt als Button in Kachel/Rail (beides `<Link>`), `preventDefault`+`stopPropagation` verhindern Navigation. Loading/Disabled gegen Doppelklick. 404 wird als „bereits gelöscht" (Erfolg) behandelt, 409/Netz als deutscher Fehler-Toast; danach immer `refresh()`.
- `components/cockpit/cleanup-button.tsx`: Bulk „Erledigte aufräumen (N)", rendert `null` bei N=0.

Verdrahtet:
- `session-tile.tsx`: Lösch-Button nur bei terminalen Kacheln (in der Kopfzeile neben Modell-Badge).
- `session-rail.tsx`: terminale Rail-Einträge (Archiv `done` + `error`) zeigen den Button on-hover statt der Laufzeit.
- `app/(cockpit)/page.tsx`: `CleanupButton` im Header (nur nach Initial-Load, sichtbar ab ≥1 terminaler Session).

Erfolgs-/Fehler-Feedback via vorhandenes `sonner`. Refetch über `useSessions().refresh()` → Eintrag verschwindet sofort statt erst beim nächsten 4s-Poll. `npx tsc`/`eslint` auf alle geänderten Dateien grün (einziger tsc-Fehler liegt vorbestehend in `lib/md-tree.test.ts`).

**Offen für `/abc-backend`:** `DELETE /sessions/{id}` + `POST /sessions/cleanup`, Repo-`delete`, `SessionManager.delete`/`cleanup_terminal` inkl. SIGTERM-Orphan-Kill (Backend-Sektion der AC).

### Implementierungs-Notizen — Backend (2026-06-24)
**Branch:** dev.

- `db/session_index.py`: `delete(session_id)` im `SessionIndexRepository`-Protokoll, `Sqlite…` (`DELETE FROM session_index WHERE session_id = ?` parametrisiert, via `asyncio.to_thread`, idempotent), `Null…` als No-op.
- `engine/manager.py`:
  - `SessionActiveError(RuntimeError)` (→ 409).
  - `delete(session_id)`: `_require` → `KeyError` bei unbekannt (→ 404); `ACTIVE_STATES` → `SessionActiveError`; sonst Orphan-Kill, aus `_sessions` entfernen, `_safe_delete` (best-effort Repo).
  - `cleanup_terminal() -> int`: iteriert, löscht nur Nicht-aktive, überspringt aktive still, zählt gelöschte.
  - `_terminate_orphan(runtime)`: best-effort `SIGTERM` an lebende `driver.pid` (Fehler nur geloggt), `_safe_delete` analog `_safe_upsert`.
- `engine/base.py`: `DeadDriver(pid=…)` trägt die rehydrierte PID — sonst ginge sie beim Restart verloren und der Orphan-Kill liefe ins Leere. `rehydrate()` reicht `row["pid"]` durch.
- `routes/sessions.py`: `POST /sessions/cleanup` (statisch, VOR `/{session_id}` deklariert) → `{"deleted": n}`; `DELETE /sessions/{id}` (`status_code=204, response_model=None`) → 204/404/409.

**Tests:** `tests/test_proj21_session_delete.py` — 13 Tests (Repo idempotent, delete 404/409/terminal, „überlebt keinen Restart", best-effort bei DB-Fehler, realer SIGTERM-Orphan-Kill via Subprozess, cleanup nur-terminal + leer, API 204/404/409 + cleanup). Volle Suite: **388 passed**.

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
