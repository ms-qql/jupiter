# PROJ-17: Recovery über den Vault

## Status: In Progress
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

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
