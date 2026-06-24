# PROJ-17: Recovery über den Vault

## Status: Deployed
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #20 (kritischstes Failure-Szenario)

## Dependencies
- Requires: PROJ-2 (Vault) — der Vault ist die persistente Wahrheit/Recovery-Quelle.
- Requires: PROJ-5 (Handover) — der letzte Handover ist der Wiederanknüpfpunkt.
- Requires: PROJ-1 / PROJ-14 (Engine + Persistenz-Seam) — rekonstruierte Sessions werden wieder als Live-Sessions geführt.

## Beschreibung
Nach einem VPS-Reboot oder Backend-Crash **rekonstruiert Jupiter Sessions aus dem Vault** bis zum letzten Handover und bietet pro Strang einen „Hier ging's weiter"-Vorschlag an. Der Vault wirkt als **Crash-Recovery-Journal** — ein Konzept, das zusammen mit Gedächtnis (#9) und Doku (#8) dreifach zahlt.

## User Stories
- Als Nutzer möchte ich nach einem Reboot eine Liste wiederherstellbarer Sessions sehen, statt bei null anzufangen.
- Als Nutzer möchte ich pro Session den letzten bekannten Stand (Handover) und einen „Hier weitermachen"-Vorschlag sehen.
- Als Nutzer möchte ich entscheiden, welche Sessions ich wiederherstelle und welche ich verwerfe.
- Als Nutzer möchte ich, dass eine wiederhergestellte Session den verdichteten Handover als Kontext-Seed mitbekommt.

## Acceptance Criteria
- [ ] Beim Start erkennt Jupiter aus dem Vault **wiederherstellbare Stränge** (letzter Handover je Session/Projekt).
- [ ] Es gibt eine **Recovery-Ansicht**: Liste der Kandidaten mit Projekt, letzter Phase, Zeitpunkt des letzten Handovers.
- [ ] Pro Kandidat ein **„Hier ging's weiter"-Vorschlag** (Zusammenfassung offener Punkte aus dem Handover).
- [ ] **Wiederherstellen** startet eine neue Session mit dem Handover als System-Kontext (Seed), verknüpft als Nachfolger (`parent_session_id`, analog PROJ-5).
- [ ] **Verwerfen** entfernt den Kandidaten aus der Ansicht, ohne den Vault-Eintrag zu löschen (Audit bleibt).
- [ ] Recovery funktioniert auch, wenn der In-Memory-Zustand vollständig weg ist (reiner Vault-Wiederaufbau).
- [ ] Bereits laufende/erfolgreich re-attachte Sessions (PROJ-14) erscheinen **nicht** doppelt als Recovery-Kandidat.
- [ ] Alle Texte deutsch; Lade-/Fehler-/Leer-Zustände explizit.

## Edge Cases
- **Kein Handover vorhanden** (Session ohne sauberen Übergabepunkt) → letzter roher Stand als schwächerer Vorschlag, klar als „unvollständig" markiert.
- **Beschädigter/halber Handover** → robust parsen, fehlende Felder tolerieren, Warnung anzeigen.
- **Mehrere Handovers je Strang** → den jüngsten als Anknüpfpunkt wählen.
- **Projektpfad existiert nicht mehr** → Kandidat anzeigen, aber Wiederherstellen blockieren mit Hinweis.
- **Doppelte Wiederherstellung** desselben Strangs → idempotent, nur eine Nachfolge-Session pro Strang (1 Strang = 1 Nachfolger, wie PROJ-5).

## Technical Requirements (optional)
- Liest die Vault-Handover-Artefakte (PROJ-5/#8) und die Schicht-Struktur (PROJ-15).
- Wiederherstellung nutzt denselben Reset-Kind-Mechanismus wie PROJ-5 (Seed + Staffelstab-Verknüpfung).
- Setzt den Persistenz-Seam aus PROJ-14 voraus, um Doppelungen mit re-attachten Sessions zu vermeiden.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** Next.js 16 (Cockpit) + FastAPI + Vault (Datei-MD) + SQLite Live-Index · **Branch:** dev

### Kernerkenntnis (prägt das Design)
Heute wird **nur das Session-Log automatisch** in den Vault geschrieben — und erst beim sauberen `DONE` (`_write_session_log`, `backend/app/engine/manager.py:1268`). **Handovers werden nur manuell** per `POST /sessions/{id}/handover` geschrieben. Ein Crash/Reboot beendet aktive Sessions abrupt → `rehydrate()` markiert sie als `ERROR` „**Verwaist nach Backend-Neustart**" (`manager.py:857-861`); sie haben **oft weder Handover noch Session-Log**. Recovery muss daher **mehrstufig** aus der jeweils besten verfügbaren Quelle bauen — deckt den Edge-Case „Kein Handover → roher Stand als schwächerer Vorschlag".

### A) Recovery-Quellen (Stufen, stärkste zuerst)
```
Recovery-Kandidat je Strang
├── Stufe 1: Manueller Handover im Vault (Handovers/)   → starker Vorschlag
├── Stufe 2: Auto-Session-Log im Vault (Sessions/)      → mittlerer Vorschlag
└── Stufe 3: Persistierte Index-Metadaten (SQLite)      → schwacher Vorschlag ("unvollständig")
            (Projekt, letzte ABC-Phase, Zeitpunkt, Tokens)
```
- „Wiederherstellbar" = Strang, der beim letzten Lauf **aktiv** war (jetzt verwaist/ERROR) **und** noch **keinen Nachfolger** hat (`child_session_id is None`).
- **Reiner Vault-Wiederaufbau** (AC): fehlt der SQLite-Index ganz, wird die Kandidatenliste **direkt aus den Vault-Dateien** (Handovers/Sessions, `session_id` aus Frontmatter) rekonstruiert.

### B) Komponenten-Struktur (Frontend)
```
RecoveryBanner (im Cockpit-Shell, nur sichtbar wenn Kandidaten > 0)
└── RecoveryDialog
    ├── RecoveryList
    │   └── RecoveryCandidateCard  (je Strang)
    │       ├── Projekt + letzte ABC-Phase + Zeitpunkt letzter Handover
    │       ├── "Hier ging's weiter"-Vorschlag (offene Punkte)
    │       ├── Quellen-Badge: Handover | Log | unvollständig
    │       ├── [Wiederherstellen]   (blockiert, wenn Projektpfad fehlt)
    │       └── [Verwerfen]
    ├── EmptyState ("Keine wiederherstellbaren Sessions")
    └── Lade-/Fehler-Zustand
```

### C) Datenmodell (Klartext)
Kein neues Persistenz-Schema nötig — Recovery ist eine **read-only Sicht** über Vorhandenes:
- **Live-Index (SQLite, PROJ-14):** verwaiste Stränge + Verkettungs-Status (`parent/child_session_id`).
- **Vault (Dateien):** Handover-/Log-Inhalt für den „Hier ging's weiter"-Vorschlag.
- **Neu, nur leichtgewichtig:** ein **Verworfen-Marker** je Strang (`recovery_dismissed` im Live-Index), damit „Verwerfen" persistent ist, **ohne den Vault-Eintrag zu löschen** (Audit bleibt). Idempotent, kein Datenverlust.

### D) API-Shape (Endpunkte, kein Code)
```
GET    /recovery                       → Liste wiederherstellbarer Stränge
                                         (Projekt, letzte Phase, Zeitpunkt, Quelle, Vorschlag,
                                          restore_blocked + Grund)
POST   /recovery/{session_id}/restore  → neue Session, Handover/Log als Seed (System-Prompt-
                                          Append), verknüpft via parent_session_id (wie PROJ-5)
POST   /recovery/{session_id}/dismiss  → Kandidat verbergen (Vault-Eintrag bleibt)
```
- `restore` **wiederverwendet den Reset-Kind-Mechanismus** aus PROJ-5 (`manager.py:1209`: Seed + Staffelstab), damit **1 Strang = 1 Nachfolger** garantiert idempotent ist.
- Recovery-Sicht baut auf dem Stand nach `rehydrate()` (Lifespan) auf.

### E) Tech-Entscheidungen (WARUM)
- **Sicht statt neuem Speicher:** verwaiste Sessions sind bereits persistiert (PROJ-14) und im Vault gespiegelt — Recovery aggregiert nur, statt eine zweite Wahrheit zu schaffen.
- **Seed als System-Prompt-Append, nicht `--resume`:** identisch zu PROJ-5; bläht den Kontext der neuen Session nicht mit dem alten Volltranskript auf.
- **Keine Doppel-Kandidaten:** Filter `child_session_id is None` **und** Ausschluss aktiver/re-attachter Sessions → AC „erscheinen nicht doppelt".
- **Verwerfen ≠ Löschen:** Marker im Index, Vault-Datei unangetastet → Audit-Spur bleibt.
- **Robustes Parsen:** halber/beschädigter Handover → fehlende Felder tolerieren, Warnung zeigen (nutzt vorhandenes `_parse_frontmatter`).

### F) Abhängigkeiten
Keine neuen Pakete. Wiederverwendet: `VaultService` (list/read/parse), `SessionManager.reset()`-Flow, `SessionIndexRepository` (PROJ-14), Cockpit-/Dialog-UI (shadcn/ui).

### Entschiedene Designfragen
1. **Verworfen-Marker:** im SQLite-Live-Index (`recovery_dismissed`), nicht als Vault-Marker-Datei. Vault bleibt unangetastet (Audit).
2. **Auto-Handover bei Verwaisung:** **nicht im MVP**. Stufen 2/3 (Session-Log / Index-Metadaten) reichen als Fallback.

### Frontend-Umsetzung (abc-frontend, 2026-06-24)
Stack: Next.js Cockpit (kein Flutter — projektweite Abweichung). Branch `dev`.

**Neue Dateien**
- `nextjs_app/components/cockpit/recovery-banner.tsx` — lädt `GET /recovery` beim Mount (Loader im Effect + Ref-Refresh wie `SessionsProvider`); blendet sich selbst aus, wenn 0 Kandidaten oder Abruf fehlschlägt (Recovery ist additiv, kein Fehler-Toast im Hintergrund-Load). Öffnet den Dialog; nach Aktion lädt es Recovery-Liste **und** Sessions neu (Kind-Session erscheint sofort).
- `nextjs_app/components/cockpit/recovery-dialog.tsx` — Kandidatenliste in `ScrollArea`. Pro Karte: Projektname, ABC-Phasen-Badge, Quellen-Badge (Handover/Session-Log/unvollständig), Zeitpunkt (relativ via `formatDuration`), „Hier ging's weiter"-Vorschlag, Warnung (beschädigter Handover) und Blockade-Grund (Projektpfad fehlt). Aktionen **Wiederherstellen** (deaktiviert bei `restore_blocked`) / **Verwerfen**, je mit Busy-Zustand und Toasts.

**Geänderte Dateien**
- `lib/types.ts` — `RecoverySource`, `RecoveryCandidate`, `RecoveryListResult` (Frontend-Spiegel des geplanten `backend/app/schemas/recovery.py`).
- `lib/api.ts` — `listRecovery()`, `restoreRecovery(id, initialPrompt?)`, `dismissRecovery(id)`.
- `app/(cockpit)/page.tsx` — `<RecoveryBanner />` über der `GlobalStatusBar` eingehängt.

**Erwarteter Backend-Vertrag (für /abc-backend)**
- `GET /recovery` → `{ candidates: RecoveryCandidate[] }`. Kandidat = verwaister Strang (Status `error`/„Verwaist", aktiv beim letzten Lauf) **und** `child_session_id is None` **und** nicht `recovery_dismissed`. Felder: `session_id, project_path, project_name, abc_phase, last_handover_at, source, suggestion, restore_blocked, blocked_reason, warning`. `source`/`suggestion` aus Stufen-Quelle (Handover→Log→Index). `restore_blocked=true` + Grund, wenn `project_path` nicht mehr existiert.
- `POST /recovery/{id}/restore` Body `{ initial_prompt?: string|null }` → `Session` (Kind). Seed serverseitig aus Handover/Log verdichtet; reuse PROJ-5-Reset-Kind (Seed als `--append-system-prompt`, `parent_session_id`-Verknüpfung). Idempotent: Zweitversuch → **409**.
- `POST /recovery/{id}/dismiss` → **204**. Setzt `recovery_dismissed` im Live-Index; Vault-Datei bleibt.

**Status-/Lade-/Leer-/Fehler-Zustände:** Banner unsichtbar bis geladen; Dialog zeigt Leerzustand „Keine wiederherstellbaren Sessions"; pro Aktion Busy-Label + Erfolg/Fehler-Toast. Alle Texte deutsch. Responsive (`flex-wrap`, `ScrollArea max-h-[60vh]`).

### Backend-Umsetzung (abc-backend, 2026-06-24)
Branch `dev`. Read-only Sicht über Live-Index (PROJ-14) + Vault (PROJ-2/PROJ-5); kein neues DB-Schema außer einem Flag.

**Neue Dateien**
- `backend/app/engine/recovery.py` — `RecoveryService(manager, vault)`. `candidates()` aggregiert verwaiste In-Memory-Stränge (Status `error` + Fehler beginnt mit „Verwaist", `child_session_id is None`, nicht `recovery_dismissed`) **und** reine Vault-Kandidaten (Frontmatter-`session_id` aus `Handovers/`/`Sessions/`, nicht im Speicher). 3-stufige Quelle: Handover → Session-Log → `incomplete` (nur Metadaten). „Hier ging's weiter" = `## Offen`/`## Wo stehen wir?`-Extrakt bzw. letzter Log-Block. `restore()` baut den Seed (Handover-Body bzw. mechanisches Gerüst via `build_handover_md`) und ruft `manager.recover()`. `dismiss()` = In-Process-Set + persistiertes Flag. Idempotenz über „existiert bereits ein Strang mit diesem `parent_session_id`?".
- `backend/app/schemas/recovery.py` — `RecoveryCandidate`, `RecoveryList`, `RecoveryRestoreRequest`.
- `backend/app/routes/recovery.py` — `GET /recovery`, `POST /recovery/{id}/restore` (201/404/409/400/503), `POST /recovery/{id}/dismiss` (204, idempotent).
- `backend/tests/test_proj17_recovery.py` — 14 Tests (alle AC + Edge-Cases: jüngster Handover gewinnt, beschädigter Handover → Warnung, Projektpfad weg → blockiert, reiner Vault-Wiederaufbau, Idempotenz, Dismiss überdauert Rehydrate, API-Flow). Grün.

**Geänderte Dateien**
- `backend/app/engine/manager.py` — `SessionState.recovery_dismissed`; `recover()` (wie `reset()`, aber ohne `stop()`, Seed serverseitig, Idempotenz-Guard → `RuntimeError`/409); `mark_recovery_dismissed()`; `_row`/`_state_from_row` um das Flag erweitert.
- `backend/app/db/session_index.py` — Spalte `recovery_dismissed` + leichtgewichtige `ALTER TABLE`-Migration für bestehende DBs.
- `backend/app/main.py` — `RecoveryService` als `app.state.recovery`, Router registriert.

**Vertrag erfüllt** wie im Frontend-Abschnitt dokumentiert (Felder/Status-Codes identisch). Regression: 447 Tests grün (14 neu + 433 bestehend; volle Suite nur batch-weise wegen Speicher).

## QA Test Results
**Getestet:** 2026-06-24 · **Branch:** dev · **Tester:** QA Engineer (Red-Team)

### Automatisierte Tests
- Backend: `tests/test_proj17_recovery.py` — **14/14 grün**. Regression (Batch-weise wegen Speicher): **433/433** bestehende Tests grün.
- Frontend: `lib/api.recovery.test.ts` (5) — **62/62 grün** (volle vitest-Suite). ESLint sauber.

### Acceptance Criteria
| # | Kriterium | Status | Nachweis |
|---|-----------|--------|----------|
| 1 | Beim Start wiederherstellbare Stränge aus Vault erkennen | ✅ PASS | `candidates()` (Rehydrate-Orphans + Vault-Scan); `test_inmemory_orphan_with_handover`, `test_pure_vault_candidate_handover` |
| 2 | Recovery-Ansicht (Projekt, letzte Phase, Zeitpunkt) | ✅ PASS | Schema-Felder + `recovery-dialog.tsx` (Phasen-/Quellen-Badge, `formatDuration`) |
| 3 | „Hier ging's weiter"-Vorschlag (offene Punkte) | ✅ PASS | `## Offen`-Extrakt; `test_inmemory_orphan_with_handover` |
| 4 | Wiederherstellen = Kind-Session mit Seed + `parent_session_id` | ✅ PASS | `recover()`; `test_restore_links_child_idempotent` (Seed im `effective_constitution`, Parent-Link) |
| 5 | Verwerfen entfernt aus Ansicht, Vault bleibt | ✅ PASS | `dismiss()`; `test_dismiss_hides_but_keeps_vault` |
| 6 | Reiner Vault-Wiederaufbau (In-Memory weg) | ✅ PASS | `test_pure_vault_candidate_handover` |
| 7 | Keine Doppel-Kandidaten (aktiv/re-attacht) | ✅ PASS | `test_active_session_is_not_candidate` + `recovered`-Filter |
| 8 | Deutsch; Lade-/Fehler-/Leer-Zustände | ✅ PASS | Banner/Dialog deutsch, Leer-/Busy-/Toast-Zustände |

### Edge Cases
| Fall | Status | Nachweis |
|------|--------|----------|
| Kein Handover → roher Stand, „unvollständig" | ✅ PASS | `test_incomplete_without_handover_or_log` |
| Beschädigter/halber Handover → Warnung | ✅ PASS | `test_damaged_handover_warns` |
| Mehrere Handovers → jüngsten | ✅ PASS | `test_newest_handover_wins` |
| Projektpfad weg → anzeigen, Restore blockiert | ✅ PASS | `test_blocked_when_project_path_gone` |
| Doppelte Wiederherstellung → idempotent (409) | ✅ PASS | `test_restore_links_child_idempotent`, `test_api_recovery_flow` |

### Security / Red-Team
- **Path-Traversal über `session_id`:** kein Dateipfad wird aus `session_id` gebaut (Dict-Lookup + Frontmatter-Vergleich) → sicher.
- **XSS im Vorschlag:** `suggestion` als React-Textknoten (auto-escaped, `whitespace-pre-wrap`) → sicher.
- **Verwerfen ≠ Löschen:** Vault-Datei bleibt (verifiziert) → Audit-Spur erhalten.
- MVP ohne JWT/RLS (projektweite Entscheidung) — keine Tenant-Isolation zu prüfen.

### Bugs
**BUG-1 (Medium) — ✅ BEHOBEN (2026-06-24).**
Fix: `_is_orphan_strand(state)` (Status `error` + „Verwaist"-Marker) als Guard in `_candidate_for()` — eine nicht-verwaiste In-Memory-Session ist kein Kandidat → `restore` liefert **404**. Der Idempotenz-Fall (Orphan mit `child_session_id`) bleibt bewusst ausgenommen und läuft weiter über `recover()` → **409**. Regressionstests: `test_restore_active_session_rejected`, `test_api_restore_active_session_404`. 16/16 PROJ-17-Tests + 76 Regression grün.

_Ursprünglicher Befund:_
**`restore` validiert die Orphan-Eigenschaft nicht.**
`RecoveryService._candidate_for()` baut für **jede** im Speicher liegende Session einen Kandidaten — unabhängig vom Status. `POST /recovery/{id}/restore` mit der ID einer **aktiven** (z. B. `waiting`/`running`) Session läuft daher durch: es entsteht eine Duplikat-Kind-Session für einen lebenden Strang und `child_session_id` wird gesetzt (verifiziert: aus `waiting` → `active_count() == 2`).
- *Reproduktion:* aktive Session erstellen → `POST /recovery/{id}/restore` → 201 statt Ablehnung.
- *Impact:* über die UI nicht auslösbar (nur Kandidaten haben Buttons), aber im no-auth-MVP per direktem API-Call erreichbar; verletzt „1 Strang = 1 Nachfolger" und kann eine Claude-Session doppeln (Kosten).
- *Vorschlag (Backend):* in `_candidate_for` (und/oder `restore`) nur fortfahren, wenn der In-Memory-Strang ein echter Recovery-Kandidat ist (Status `error` **und** Fehler beginnt mit „Verwaist", `child_session_id is None`); sonst `KeyError` → 404. `recover()`-Guard bleibt als zweite Verteidigungslinie.

**BUG-2 (Low) — `dismiss` akzeptiert beliebige `session_id`.**
`dismiss` setzt das Flag auch auf eine aktive Session (idempotent, 204). Folgenlos im Lauf, aber eine später verwaiste Session wäre dann vorab „verworfen". Optional dieselbe Orphan-Validierung wie BUG-1.

**BUG-3 (Low) — Vault-Scan in `candidates()` ist O(n²) bei vielen Dateien.**
`_vault_candidates()` liest jede Datei und ruft `_candidate_for` → `_load_source`, das `Handovers/`+`Sessions/` erneut listet/liest. Für den Single-User-MVP unkritisch; bei großen Vaults vor Phase 2 cachen/zusammenführen.

**BUG-4 (Low) — theoretischer Race bei gleichzeitigem Doppel-Restore.**
Der Idempotenz-Guard in `recover()` (Parent-Scan) liegt außerhalb des `_create_lock`; zwei exakt gleichzeitige Restores desselben Strangs könnten beide passieren. Sehr unwahrscheinlich; ggf. Guard in den Lock ziehen.

**BUG-5 (High) — ✅ BEHOBEN (2026-06-24).** *Reiner Vault-Kandidat mit nur Session-Log war nicht wiederherstellbar.*
Symptom: Im Recovery-Dialog zeigten Log-only-Stränge „Projektpfad nicht rekonstruierbar — Wiederherstellung nicht möglich" und der „Wiederherstellen"-Button war blockiert (Toast-Fehler). Ursache: Der Projektpfad wurde nur aus dem Handover-Body (`Projektpfad: \`…\``) gelesen; ein Session-Log trug den Pfad **nirgends** (Frontmatter nur `owner/session_id/created/type/title`). Fehlte der Live-Index (genau der Reboot-Fall, für den Recovery existiert), war der Strang tot. Fix:
- `vault.write_session_log()` schreibt `project_path` + `project_name` ins Frontmatter (durable für reinen Vault-Wiederaufbau).
- `RecoveryService` rekonstruiert den Pfad nun mehrstufig: Handover-Body → Frontmatter-`project_path` → Projektname gegen existierende Verzeichnisse unter `settings.allowed_roots` (Backfill für Altbestand ohne Frontmatter-Pfad; gibt nur einen **tatsächlich existierenden** Ordner zurück, sonst bleibt es blockiert).
- Regressionstests: `test_pure_vault_log_with_frontmatter_path`, `test_pure_vault_log_path_resolved_by_name` (+ angepasster `test_pure_vault_log_only_blocked`).

### Produktionsreife
**READY → Approved (2026-06-24).** BUG-1 (Medium) behoben + durch Regressionstests abgesichert. Keine Critical/High/Medium offen. BUG-2–4 (Low) bleiben als optionale Phase-2-Härtung dokumentiert (kein Blocker).

## Deployment
_To be added by /abc-deploy_
