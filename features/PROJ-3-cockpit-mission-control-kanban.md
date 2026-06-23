# PROJ-3: Cockpit — Mission Control + Session-Kanban + Ampel-Kacheln

## Status: Approved
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — für Session-Status/Events
- Requires: PROJ-2 (Vault-Anbindung) — für Session-Liste/Persistenz

## Beschreibung
Das Gesicht von Jupiter: der erste Screen als kompaktes Lagebild der gesamten Flotte. Mission Control (#1) + Ampel-Kacheln (#2) + Session-Kanban nach Zustand (#3). Enthält die manuelle Modell-Wahl pro Session (UI-Seite von #22). Cockpit-first, nicht Chat-first.

## User Stories
- Als Nutzer möchte ich beim Öffnen von Jupiter ein kompaktes Lagebild aller Agenten und Sessions sehen.
- Als Nutzer möchte ich Sessions als Kacheln mit Ampel sehen (arbeitet / wartet auf dich / fertig / Fehler), um Handlungsbedarf sofort zu erkennen.
- Als Nutzer möchte ich Sessions in einem Kanban nach Zustand sehen (Arbeitet → Wartet auf dich → Review/Approval → Fertig).
- Als Nutzer möchte ich pro Session das Modell wählen (Haiku/Sonnet/Opus).
- Als Nutzer möchte ich auf eine Kachel klicken und in die Session-Detailansicht springen.

## Acceptance Criteria
- [ ] Startbildschirm zeigt einen kleinen globalen Status (Anzahl aktiv / wartend / Fehler) + Liste aller Sessions.
- [ ] Jede Session-Kachel zeigt ohne Klick: Ampel-Status, aktive Rolle/Skill, Projekt, Laufzeit.
- [ ] Kanban-Board mit Spalten **Arbeitet / Wartet auf dich / Review/Approval / Fertig**; Karten wandern bei Statuswechsel automatisch.
- [ ] „Wartet auf dich" ist visuell das stärkste Signal.
- [ ] Modell-Auswahl (Haiku/Sonnet/Opus) pro Session in der UI; Auswahl wird an den Treiber (#22, PROJ-1) durchgereicht.
- [ ] Live-Aktualisierung der Kachel-Zustände (WebSocket oder Polling) ohne manuelles Reload.
- [ ] Persistente, immer sichtbare Liste aktiver Sessions (Navigations-Rail, „Recents"-Stil): jede Zeile zeigt Ampel + Kurztitel + Laufzeit und ist anklickbar; Klick führt direkt in die Session-Detailansicht.
- [ ] Responsive (Desktop-first; nutzbar ab Tablet).

## Edge Cases
- 0 Sessions → klarer Empty-State mit „Neue Session"-CTA.
- Viele Sessions (> 20) → Board bleibt performant und scrollbar.
- Backend nicht erreichbar → Fehler-State statt leerem/irreführendem Board.
- Session im Fehlerstatus → rote Ampel + Kurzgrund direkt auf der Kachel.

## Technical Requirements (optional)
- Next.js 16 (App Router) + React + Tailwind + shadcn/ui; Komponenten zuerst aus shadcn/ui (kein Hand-Roll von Card/Tabs/Dialog).
- Live-Updates via WebSocket oder Polling gegen PROJ-1.
- Alle Texte deutsch; Loading/Error/Empty/Success-States explizit.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-22 · **Stack:** Next.js 16 (App Router) + React + Tailwind + shadcn/ui · FastAPI (bestehend) · In-Memory Session-Registry (noch kein Postgres) · **Branch:** dev

> Hinweis: Jupiter überschreibt die globalen Defaults (Next.js statt Flutter, kein JWT/RLS im MVP — `owner` serverseitig gestempelt). PROJ-3 ist das **erste Frontend** — es legt das `nextjs_app/`-Gerüst an.

### Entscheidungen (mit User abgestimmt)
1. **Live-Updates des Boards: Polling.** Das Cockpit pollt `GET /sessions` alle ~4 s für Ampel/Kanban. Der bestehende `WS /sessions/{id}/stream` wird nur in der späteren Detailansicht genutzt (Drill-down). Kein neuer Backend-Endpoint nötig; AC erlaubt Polling explizit.
2. **Modell-Wahl: nur bei Erstellung.** Dropdown (Haiku/Sonnet/Opus) im „Neue Session"-Dialog, durchgereicht an `POST /sessions`. Laufende Sessions behalten ihr Modell (Backend kennt heute keinen Runtime-Wechsel).
3. **Erstellung enthalten:** Empty-State-CTA + minimaler „Neue Session"-Dialog (Projekt-Pfad, Initial-Prompt, Modell).

### A) Komponenten-Struktur (Next.js / shadcn/ui)
```
app/(cockpit)/layout.tsx  — Shell mit persistenter Session-Rail (links) + Inhalt (rechts)
├── SessionsRail           (persistente „Recents"-Liste aktiver Sessions — siehe A.1)
│   ├── RailHeader         („Aktive Sessions" + Button „Neue Session")
│   ├── SessionRailItem    (klickbare Zeile: Ampel-Punkt + Icon + Kurztitel + Laufzeit) → Detailroute
│   └── RailFooter         (Link „Alle anzeigen →" → volles Board)
└── app/(cockpit)/page.tsx  — Mission-Control-Seite (Board)
    ├── GlobalStatusBar    (Mission Control: zählt aktiv / wartet / Fehler — client-seitig aus der Liste)
    ├── ViewToggle         (shadcn Tabs: „Kacheln" ⇄ „Kanban")
    ├── SessionGrid        (Ansicht A — Ampel-Kacheln)
    │   └── SessionTile     (shadcn Card + Badge)  →  Ampel, Rolle/Skill, Projekt, Laufzeit, Modell, context_fill %, Kosten
    ├── KanbanBoard        (Ansicht B — 4 Spalten)
    │   └── KanbanColumn    „Arbeitet" | „Wartet auf dich" | „Review/Approval" | „Fertig"
    │       └── SessionCard  (gleiche Kachel, kompakter; „Wartet" visuell am stärksten)
    ├── NewSessionDialog    (shadcn Dialog + Form: Projekt-Pfad, Initial-Prompt, Select Modell)
    ├── EmptyState          („Noch keine Sessions" + CTA „Neue Session")
    └── ErrorState          (Backend nicht erreichbar — statt leerem Board)

app/(cockpit)/sessions/[id]/page.tsx  — Session-Detailroute (Ziel von Rail-Klick + Kachel-Klick)
```
Geteilte Bausteine in `components/cockpit/`; shadcn-Primitives (Card, Badge, Tabs, Dialog, Select, Button) **nicht** hand-rollen. Ampel als kleiner Statuspunkt im Theme-Token-Stil.

#### A.1) SessionsRail — persistente „Recents"-Liste (Vorbild: Bild #2 „Recents")
Eine **immer sichtbare, anklickbare Liste** aktiver Sessions als linke Navigations-Rail — schneller Einstieg unabhängig von Kachel-/Kanban-Ansicht. Vorbild: der „Recents"-Bereich aus der Referenz (Sidebar-Zeilen mit Icon + Kurztitel + „Alle anzeigen →"), kombiniert mit dem „working · 4m ago / idle"-Statusmuster.

- **Pro Zeile (`SessionRailItem`):** Ampel-Statuspunkt (gleiches Mapping wie B) · kleines Rollen-/Skill-Icon · einzeilger Kurztitel (Projektname + Rolle, sonst Snippet des Initial-Prompts, mit `…` gekürzt) · rechts dezent die Laufzeit (relativ, z. B. „4m"). Hover-Highlight; aktive Session optisch markiert.
- **Klick → `sessions/[id]`** (Session-Detailroute). Dieselbe Route nutzt auch der Klick auf eine Board-Kachel (AC: „auf Kachel klicken → Detailansicht").
- **Sortierung:** „Wartet auf dich" zuoberst (Handlungsbedarf), dann nach `last_activity` absteigend (zuletzt aktiv oben — wie „Recents").
- **Footer „Alle anzeigen →":** scrollt/führt zum vollen Board (Pendant zu „View all 83 →"). Bei vielen Sessions zeigt die Rail nur die obersten ~10, das Board alle.
- **Datenquelle:** dieselbe gepollte `GET /sessions`-Liste wie das Board (kein Extra-Request) — Rail und Board bleiben konsistent.
- **States:** leer → „Keine aktiven Sessions" + CTA; Fehler → dezenter Hinweis in der Rail statt leerer Liste.

### B) Status → Ampel → Kanban (verbindliches Mapping)
Backend-Status-Enum (5 Werte, aus `backend/app/engine/manager.py`): `starting · running · waiting · done · error`.

| Backend-Status | Ampel | Kanban-Spalte |
|---|---|---|
| `starting`, `running` | 🟢 grün | **Arbeitet** |
| `waiting` | 🟡 gelb (stärkstes Signal) | **Wartet auf dich** |
| `error` | 🔴 rot (+ `error`-Kurzgrund auf Karte) | (separat hervorgehoben, in „Wartet"-Nähe) |
| `done` | ⚪ grau | **Fertig** |

> **Offene Lücke „Review/Approval":** Das Backend kennt heute keinen eigenen `review`-Status — Freigaben kommen erst mit **PROJ-4 (Decision Cards)**. Für PROJ-3 bleibt die Spalte „Review/Approval" im Board sichtbar, aber vorerst leer (Platzhalter), bis PROJ-4 einen Approval-Zustand liefert. Bewusst keine Backend-Änderung in PROJ-3.

### C) API-Nutzung (bestehende Endpoints, keine neuen außer CORS)
```
GET  /sessions            → Liste aller Sessions (Polling alle ~4s) — Primärquelle fürs Board
GET  /sessions/{id}       → Detail (für späteren Drill-down / Klick auf Kachel → Detail-Route)
POST /sessions            → neue Session anlegen (project_path, initial_prompt, model, permission_mode)
WS   /sessions/{id}/stream → nur Detailansicht (nicht fürs Board-Polling)
```
Genutzte Felder je Session-Kachel: `status`, `role`, `project_path`, `created_at`/`last_activity` (Laufzeit), `model`, `context_fill_pct`, `total_cost_usd`, `error`.

### D) Tech-Entscheidungen (Begründung)
- **Polling statt N WebSockets fürs Board:** Ein WS pro sichtbarer Session skaliert schlecht (Edge Case > 20 Sessions) und braucht Reconnect-Logik je Socket. Ein Poll auf `GET /sessions` alle 4 s ist robust, einfach und deckt das AC ab. WS bleibt der späteren 1:1-Detailansicht vorbehalten.
- **Mission-Control-Zähler client-seitig:** Kein `/sessions/stats`-Endpoint nötig — die Aggregation (aktiv/wartet/Fehler) rechnet das Frontend aus der ohnehin gepollten Liste. Spart Backend-Arbeit.
- **API-Client als dünne BFF-Schicht** (`lib/api-client.ts`): zentralisiert Basis-URL + Fehlerbehandlung; `owner`/Auth entfällt im MVP (single-user).
- **Erst-Frontend-Gerüst:** `nextjs_app/` wird in diesem Feature angelegt (Tailwind + shadcn/ui init).

### E) Voraussetzung im Backend (kleiner, notwendiger Eingriff)
- **CORS aktivieren** in `backend/app/main.py` (`CORSMiddleware`, `allow_origins` = `http://localhost:3000` für Dev). **Blocker** — ohne das kann der Browser das Backend nicht erreichen. Das ist die einzige Backend-Änderung für PROJ-3; sie geht an den Backend-Developer (`/abc-backend`), nicht ans Frontend.
- Betriebshinweis (unverändert): uvicorn mit **einem** Worker starten (`--workers 1`), da die Session-Registry Subprozess-Handles im Speicher hält.

### F) Abhängigkeiten (Pakete)
- **Frontend (neu):** `next`, `react`, `tailwindcss`, shadcn/ui-CLI (Card/Badge/Tabs/Dialog/Select/Button), `zod` + `react-hook-form` (Erstell-Dialog-Validierung), optional `swr` oder eigener Polling-Hook für `GET /sessions`.
- **Backend:** keine neuen Pakete — nur CORS-Middleware (FastAPI-Bordmittel).

### G) States (explizit, deutsch)
- **Loading:** Skeleton-Kacheln beim ersten Laden.
- **Empty:** „Noch keine Sessions" + CTA „Neue Session".
- **Error:** „Backend nicht erreichbar" (Poll fehlgeschlagen) — Board bleibt nicht leer/irreführend.
- **Success:** Live-aktualisierte Kacheln/Kanban; gelbe „Wartet auf dich"-Karten optisch priorisiert.

### Handoff
1. **Backend (`/abc-backend`):** CORS-Middleware in `main.py` (kleiner Vorab-Schritt, entblockt das Frontend).
2. **Frontend (`/abc-frontend`):** `nextjs_app/`-Gerüst + Cockpit gemäß obiger Struktur.

## Implementation Notes — Backend (abc-backend, 2026-06-22)
**Branch:** dev · **Umfang:** nur die im Tech-Design vorgesehene CORS-Freischaltung (kein DB-/RLS-Teil — Jupiter-MVP ist single-user, kein JWT).

- `backend/app/config.py`: neue Einstellung `cors_origins` (Default `["http://localhost:3000", "http://127.0.0.1:3000"]`, überschreibbar via `JUPITER_CORS_ORIGINS` als JSON-Liste).
- `backend/app/main.py`: `CORSMiddleware` in `create_app()` verdrahtet (`allow_origins=settings.cors_origins`, `allow_credentials=True`, alle Methoden/Header) — entblockt das Browser-Frontend (Next.js :3000).
- Tests (`backend/tests/test_sessions_api.py`): `test_cors_allows_frontend_origin` (Preflight + GET spiegeln den erlaubten Origin), `test_cors_blocks_unknown_origin` (fremde Origin erhält keinen Allow-Header).
- **Ergebnis:** volle Suite grün — **122 passed**.
- Betriebshinweis unverändert: uvicorn mit **einem** Worker starten (`--workers 1`), Session-Registry hält Subprozess-Handles im Speicher.

Keine neuen Endpoints/Tabellen. Damit ist der Backend-Blocker für PROJ-3 (CORS) erledigt; der Rest von PROJ-3 ist reine Frontend-Arbeit (`/abc-frontend`).

## Implementation Notes — Frontend (abc-frontend, 2026-06-22)
**Branch:** dev · **Stack:** Next.js 16.2.9 (App Router, Turbopack) · React 19 · Tailwind v4 · shadcn/ui (**Base UI**, nicht Radix).

**Gerüst neu angelegt:** `nextjs_app/` (erstes Frontend des Projekts). shadcn-Komponenten: Button, Card, Badge, Tabs, Dialog, Select, Input, Label, Textarea, ScrollArea, Separator, Skeleton, Sonner. Dark-Mode default, deutsche UI, DSGVO: `next/font/google` (Geist) self-hosted zur Build-Zeit (kein Runtime-CDN-Request).

**Struktur:**
- `lib/types.ts` — spiegelt `SessionRead`/`SessionCreate`. `lib/api.ts` — dünner Client (`NEXT_PUBLIC_API_BASE`, Default `:8000`, `streamUrl()` für WS). `lib/status.ts` — verbindliches Status→Ampel→Kanban-Mapping, Zähler, `modelLabel()` (fängt aufgelöste IDs wie `claude-haiku-4-5-…` → „Haiku" ab).
- `components/cockpit/sessions-provider.tsx` — **EIN** Polling (`GET /sessions`, 4 s) via Context für Rail + Board (kein Doppel-Request); `useNow()` für laufende Relativzeiten.
- `SessionRail` (persistente „Recents"-Liste, klickbar → Detail, „Wartet"/Fehler zuoberst, Footer „Alle anzeigen →"), `GlobalStatusBar`, `SessionTile` (Ampel, Modell, Laufzeit, Kontext-%, Kosten), `SessionGrid`, `KanbanBoard` (4 Spalten; Review/Approval = Platzhalter bis PROJ-4), `NewSessionDialog` (Projekt/Prompt/Modell/Modus → `POST /sessions`), `Ampel`, `states.tsx` (Loading/Empty/Error).
- Routen: `app/(cockpit)/layout.tsx` (Shell: Rail + Inhalt), `…/page.tsx` (Board, Tabs Kacheln/Kanban), `…/sessions/[id]/page.tsx` (Detail: Live-Transkript via **WebSocket** `/sessions/{id}/stream` mit Reconnect + initialer Historie via `GET /sessions/{id}`, Eingabe/Stop).

**Backend-Anpassung (Base UI):** `DialogTrigger` nutzt `render={…}` statt Radix-`asChild`.

**Verifikation (echter End-to-End-Smoke gegen laufendes Backend, 1 echte Haiku-Session):**
- `npm run build` grün (TypeScript + 3 Routen).
- Empty-State, Board (Kacheln), Kanban (4 Spalten, Karte in „Wartet auf dich"), Detailseite (WS „● live", Transkript „Hallo", Eingabe/Stop) per Screenshot bestätigt.
- Mission-Control-Zähler, Ampel-Pulsieren, amber Hervorhebung „Wartet auf dich", Modell-Label, Klick Rail/Kachel → Detail: alle ok.
- CORS gegen Browser-Origin verifiziert.

**Bekannte/abgestimmte Grenzen:** Review/Approval-Spalte leer bis PROJ-4. Modell-Wechsel nur bei Erstellung (Backend kennt keinen Runtime-Switch). Rail-Titel = Projekt + Rolle (Initial-Prompt-Snippet ist in `GET /sessions` nicht enthalten).

→ Bereit für `/abc-qa`.

## Nachträge / Enhancements (2026-06-23)
Zwei Nutzer-Anforderungen nach dem ersten Cockpit-Release umgesetzt:

### 1. Auxevo-Branding + Light/Dark-Toggle
- **Brand-Tokens** (aus HAL `00 Context/Branding.md`) in `app/globals.css` für **beide** Modi: Teal `#0D9488` als Primary/Ring, Ink `#0A0A0A` / Off-White `#FAFAFA`, Surfaces `#171717`/`#1F1F1F`, Radius 8px (sm/md/lg ≈ 4/6/8). Light-Mode aus dem Dark-first-Brand abgeleitet.
- **Fonts** DSGVO-konform via `next/font` self-hosted: **DM Sans** (Sans) + **JetBrains Mono** (Mono) — ersetzt Geist.
- **Theme-Toggle** (`components/cockpit/theme-toggle.tsx`, Sonne/Mond) oben rechts in Board-Header, Detail-Header und Mobile-Topbar; `next-themes` `ThemeProvider`, **Dark als Brand-Default**, expliziter Light/Dark-Switch (kein System-Mode). Verifiziert: Dark+Light per Screenshot, Toggle schaltet `html.dark`/`html.light`.

### 2. Beendete Session fortsetzen (Bug: „kann nicht weiterarbeiten")
Eine selbst beendete Session (`done`/`error`) ließ sich nicht fortsetzen — die Detailseite blendete die Eingabe aus, und `POST /input` warf 409.
- **Backend (PROJ-1-Engine):** `claude --resume <session-id>` lädt die bestehende Konversation. `LaunchSpec.resume`, `build_argv` (resume → `--resume` statt `--session-id`), `SessionManager.send_input` ist resume-fähig (toter Treiber → frischer Treiber via `_resume`, Modell-Alias-Normalisierung), neuer `_model_alias`-Helfer. Treiber-Swap am `SessionRuntime`, `_done_fired` zurückgesetzt.
- **Frontend:** Detailseite zeigt die Eingabe **immer**; bei beendeter Session Hinweis „Session beendet — eine Nachricht setzt sie fort." + Button **„Fortsetzen"** (Stop ausgeblendet). Die offene WS-Verbindung streamt die fortgesetzten Events live.
- **Tests:** Backend `test_send_input_resumes_done_session`, `test_build_argv_resume_vs_new`, `test_input_after_stop_resumes` (alter 409-Test auf neues Soll umgestellt) → **124 passed**.
- **Live verifiziert:** beendete Haiku-Session per `POST /input` fortgesetzt → sie **erinnerte den Kontext** (zuvor gemerkte Zahl „42") + UI-End-to-End („Fortsetzen" → „Arbeitet ● live").

## QA Test Results
**Getestet:** 2026-06-22 · **Branch:** dev · **Methode:** Vitest-Unit (lib/status.ts) + Playwright-E2E gegen laufendes Backend (uvicorn, 1 Worker) + visuelle Screenshots (Empty/Board/Kanban/Detail/Responsive/Error).

### Automatisierte Tests
- **Backend-Regression:** `pytest` → **122 passed** (keine Regression durch CORS).
- **Frontend-Unit (neu):** `nextjs_app/lib/status.test.ts` (Vitest) → **17 passed** — deckt das verbindliche Status→Ampel→Kanban-Mapping, `columnFor` (inkl. error→wartet, review-Platzhalter), `countStatuses`, `railRank`-Sortierung, `modelLabel` (aufgelöste IDs), `formatDuration`, `projectName`. `npm test` verankert.
- **Build:** `next build` grün (3 Routen, TypeScript ok).

### Akzeptanzkriterien (E2E, 12/12 Checks PASS)
| AC | Ergebnis |
|----|----------|
| Globaler Status + Session-Liste | ✅ Mission-Control-Zähler Aktiv/Wartet/Fehler/Fertig + Liste |
| Kachel zeigt Ampel/Rolle/Projekt/Laufzeit | ✅ (Rolle wird angezeigt, wenn gesetzt) |
| Kanban 4 Spalten, Auto-Wandern bei Statuswechsel | ✅ Spalten korrekt; Karte folgte `running→waiting` automatisch (Polling) |
| „Wartet auf dich" stärkstes Signal | ✅ amber Ring auf Kachel + amber Spalte + hervorgehobener Zähler |
| Modell-Wahl pro Session, an Treiber durchgereicht | ✅ Dialog Haiku/Sonnet/Opus; gewähltes „Haiku" am Backend bestätigt |
| Live-Aktualisierung ohne Reload | ✅ Board-Polling (4 s) + Detail-WebSocket (`● live`) |
| Persistente Rail (Recents), klickbar → Detail | ✅ Rail-Eintrag + Kachel führen zur Detailroute |
| Responsive (ab Tablet) | ✅ 768 px + 1440 px voll nutzbar (siehe Edge/Low-2 für <600 px) |

### Edge Cases
- **0 Sessions →** Empty-State + CTA ✅
- **Backend nicht erreichbar →** Fehler-State „Backend nicht erreichbar" statt leerem Board ✅
- **Fehlerstatus (rote Ampel + Kurzgrund) →** Mapping unit-getestet (statusMeta.error=rot, columnFor.error=wartet) + Kachel rendert `session.error`. ⚠️ Nicht live erzwungen (kein deterministischer Weg, eine Session in `error` zu bringen) — als getestet-per-Logik gewertet.
- **>20 Sessions (Performance/Scroll) →** ⚠️ Nicht last-getestet (kein praktikabler Weg, 20 echte Claude-Sessions zu spawnen). Rail kappt bei 10 + „Alle anzeigen (+N) →", ScrollArea + responsives Grid vorhanden (per Design abgedeckt, nicht stressverifiziert).

### Security (red-team)
- **Kontext:** Single-User-MVP, **kein JWT/RLS/mandant_id** (bewusst, #21) → Tenant-Isolation/JWT-Audit **N/A**.
- **CORS:** beschränkt auf konfigurierte Origins; fremde Origin erhält keinen Allow-Header (unit-getestet, backend).
- **Secrets:** Frontend-Bundle enthält nur `NEXT_PUBLIC_API_BASE` (öffentliche API-URL, by design) — keine Secrets geleakt.
- **Hinweis Phase 2:** WS-/REST-Endpoints sind unauthentifiziert (MVP-Entscheidung). Vor Multi-User/Exponierung echtes Auth nachrüsten (#21).

### Gefundene Bugs (alle **Low** — keine Critical/High/Medium) — **alle behoben 2026-06-22**
- **LOW-1 (Lint/CI-Hygiene) — ✅ FIXED:** `react-hooks/set-state-in-effect` in `sessions-provider.tsx`. Poll-Logik in eine lokale `tick()`-Funktion im Effect verlagert, manueller `refresh` über Ref. `npm run lint` jetzt grün.
- **LOW-2 (Responsive < Tablet) — ✅ FIXED:** Neue `CockpitShell` — Rail inline ab `md`, darunter einklappbarer Overlay-Drawer mit Menü-Button (opak, schließt bei Navigation/Backdrop). 375 px Board jetzt voll nutzbar; Desktop unverändert (Rail inline, kein Menü-Button) — per Screenshot bestätigt.
- **LOW-3 (Kosmetik) — ✅ FIXED:** `ErrorState` unterdrückt die generische Meldung, wenn sie dem Titel entspricht — „Backend nicht erreichbar" erscheint nur noch einmal; spezifische Detailmeldungen (z. B. „Fehler 500") werden weiterhin angezeigt.

**Verifikation nach Fixes:** `npm run lint` grün · Vitest **17 passed** · `next build` grün · Screenshots (Mobile Board/Drawer, Desktop, Error-State) bestätigt.

### Empfehlung
**Production-ready: JA** (innerhalb des MVP-Scopes). Keine Critical/High/Medium-Bugs; 3 Low-Findings als Nachzieharbeiten dokumentiert. Empfohlene Folgearbeit: dedizierte Playwright-E2E-Suite unter `nextjs_app/e2e/` (das QA-E2E lief als Verifikation, ist aber noch nicht als Repo-Regression eingecheckt).

## Deployment
_To be added by /deploy_
