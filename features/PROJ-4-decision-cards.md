# PROJ-4: Decision Cards — Freigabe-Flow

## Status: Planned
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — Session signalisiert genehmigungspflichtige Aktion
- Requires: PROJ-3 (Cockpit) — Cards werden im Cockpit/Kanban angezeigt

## Beschreibung
Der Entscheidungsmoment, optimiert: Wenn eine Session deine Freigabe braucht, entsteht eine **Decision Card** mit allem für eine 5-Sekunden-Entscheidung (#4). Im MVP **fixer konservativer Trigger** (Schreib-/Shell-Operationen → Card, reine Lesezugriffe → auto); die konfigurierbare Trust-Policy (#5) ist P1.

## User Stories
- Als Nutzer möchte ich benachrichtigt werden, wenn ein Agent meine Freigabe braucht.
- Als Nutzer möchte ich in einer Karte sofort sehen, was der Agent will, warum, und den relevanten Ausschnitt (Diff/Befehl), um in Sekunden zu entscheiden.
- Als Nutzer möchte ich Freigeben / Ablehnen / Mit Kommentar zurück / In Session springen.

## Acceptance Criteria
- [ ] Erreicht eine Session eine genehmigungspflichtige Aktion (fixer konservativer Trigger: Schreib-/Shell-Operationen → Card; reine Lesezugriffe → auto), entsteht eine Decision Card.
- [ ] Karte zeigt: **Was** (Aktion), **relevanter Ausschnitt** (Diff/Befehl — NICHT das ganze Log), **Warum**, **Kontext** (Projekt / abc-Phase).
- [ ] Aktionen: **Freigeben**, **Ablehnen**, **Mit Kommentar zurück**, **In Session springen**.
- [ ] Freigabe/Ablehnung wird an die wartende Session zurückgespielt; Session läuft entsprechend weiter oder bricht ab.
- [ ] Eine wartende Session erscheint im Kanban (PROJ-3) in der Spalte „Wartet auf dich".
- [ ] Der Trigger ist im MVP fix/konservativ und an **einer** zentralen Stelle im Code definiert (vorbereitet auf konfigurierbare Policy #5).

## Edge Cases
- Mehrere offene Cards gleichzeitig → klar gelistet, einzeln entscheidbar.
- Session stirbt, während eine Card offen ist → Card wird als „obsolet" markiert.
- Nutzer ignoriert Card lange → Session bleibt sauber pausiert (kein Timeout-Autoproceed).
- „Mit Kommentar zurück" → Kommentartext wird als nächste Eingabe an die Session gesendet.

## Technical Requirements (optional)
- Trigger-Logik an einer zentralen Stelle kapseln, damit #5 (konfigurierbare Trust-Policy, P1) sie ersetzen kann.
- Ausschnitt-Erzeugung (Diff/Befehl statt Volltext) zahlt auf Token-Disziplin ein.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-23 · **Stack:** Next.js 16 (App Router) + shadcn/ui (Cockpit, bestehend) · FastAPI + In-Memory Session-Registry (bestehend) · **neuer MCP-Permission-Endpoint im selben FastAPI-Prozess** · **Branch:** dev

> Jupiter-Overrides gelten weiter: Next.js statt Flutter, kein JWT/RLS im MVP (single-user, `owner` serverseitig gestempelt). PROJ-4 ist rein **additiv** zum bestehenden Engine-Layer — die Seams (`LaunchSpec`, `build_argv`, `SessionRuntime`, WS-Broadcast, `routes/sessions.py`) existieren bereits; PROJ-1 hat `--permission-mode` schon verdrahtet und `--permission-prompt-tool` als TODO für genau dieses Feature offengelassen (`claude_driver.py:11`).

> ⚠️ **Umsetzungs-Update (siehe Implementation Notes):** Der Mechanismus wurde von einem MCP-Permission-Tool auf einen **Claude-Code `PreToolUse`-Hook** umgestellt (das `mcp`-SDK ist mit dem gepinnten FastAPI inkompatibel). Funktional identisch — blockierender Tool-Abfang, `session_id`-Korrelation, Deny-mit-Begründung —, aber **ohne neue Abhängigkeit**. Der Abschnitt unten beschreibt die ursprüngliche MCP-Idee; gebaut wurde die Hook-Variante.

### Kernmechanismus (das „Wie" in einem Satz)
Claude Code headless kennt das Flag **`--permission-prompt-tool`**: vor jeder genehmigungspflichtigen Aktion ruft die Session ein von uns benanntes **MCP-Tool** auf und **blockiert**, bis dieses Tool `allow`/`deny` zurückgibt. Jupiter hostet dieses Tool selbst — der Tool-Aufruf erzeugt eine **Decision Card** und wartet auf deine Entscheidung; deine Antwort wird zum Rückgabewert des Tools, und die Session läuft im selben Zug weiter oder bricht die Aktion ab. Kein zusätzlicher Daemon, kein Polling im Backend: das wartende Tool und der `SessionManager` leben im **selben uvicorn-Prozess** (Single-Worker-Betrieb ist ohnehin schon Pflicht) und teilen sich den Speicher.

### Entscheidungen (mit User abgestimmt, 2026-06-23)
1. **Eigene Kanban-Spalte „Review/Approval".** Eine Session mit offener Card bekommt den **neuen Status `awaiting_approval`** und füllt die von PROJ-3 reservierte (bisher leere) 4. Spalte. Bewusste **Verfeinerung des ursprünglichen AC** („… in der Spalte ‚Wartet auf dich'"): wir trennen *idle-nach-Turn* (`waiting`) klar von *blockiert-auf-Freigabe* (`awaiting_approval`). „Review/Approval" wird visuell als Handlungsbedarf hervorgehoben (wie „Wartet auf dich").
2. **„Mit Kommentar zurück" = natives Deny mit Begründung.** Der Kommentar reist als `message` im Deny-Resultat des Permission-Tools zurück; Claude sieht den Grund **inline** und passt die nächste Aktion im selben Turn an. Ein Roundtrip, kein Reihenfolge-Race mit einem separaten `/input`.

### A) Komponenten-Struktur

**Backend (additiv im bestehenden Engine-Layer):**
```
Permission-Layer (NEU, im selben FastAPI-Prozess)
├── Permission-MCP-Endpoint   HTTP-MCP unter /mcp/{session_id} — exponiert EIN Tool „approval_prompt"
│   └── approval_prompt(tool, input)  → erzeugt Card, awaitet Future, liefert allow/deny zurück
├── policy.requires_card(tool_name, input) -> bool   ← die EINE zentrale Trigger-Stelle (preps #5)
└── PendingDecisionRegistry   im SessionRuntime: offene Cards je Session (key = decision_id)

Bestehende Seams (nur erweitert):
├── LaunchSpec            + Felder: permission_prompt_tool, mcp_config_path
├── build_argv()          + --permission-prompt-tool + --mcp-config
├── SessionRuntime        + pending_decisions{} + Status awaiting_approval; löst Futures bei Tod auf
└── routes/sessions.py    + POST /sessions/{id}/decisions/{decision_id}  (entscheiden)
```

**Frontend (Erweiterung des bestehenden Cockpits):**
```
KanbanBoard (PROJ-3)
└── KanbanColumn „Review/Approval"   ← jetzt befüllt (Status awaiting_approval)
    └── DecisionCard                  (shadcn Card)
        ├── CardHeader     Was: Aktion (z. B. „Bash" / „Edit datei.py") + Projekt + abc-Phase
        ├── ExcerptBlock   relevanter Ausschnitt: Diff (Edit/Write) ODER Befehl (Bash) — NICHT das Log
        ├── RationaleText  Warum: letzte Assistenten-Begründung vor dem Tool-Aufruf
        └── ActionRow      [Freigeben] [Ablehnen] [Mit Kommentar zurück] [In Session springen]
            └── CommentPopover  (shadcn Popover/Textarea) für „Mit Kommentar zurück"
SessionDetail (PROJ-3)
└── inline dieselbe DecisionCard, wenn die offene Session eine Freigabe braucht
```
shadcn-Primitives (Card, Badge, Button, Popover, Textarea) **nicht** hand-rollen. „In Session springen" nutzt die bestehende Detail-Route `sessions/[id]`.

### B) Datenmodell (Klartext)
Eine **Decision** (nur im Speicher, lebt nur solange die Session blockiert — keine Postgres-/Vault-Persistenz im MVP):
- `decision_id` (= `tool_use_id` des blockierenden Aufrufs → erlaubt mehrere parallele Cards je Session)
- `session_id` · `tool_name` (z. B. `Bash`, `Edit`, `Write`)
- `excerpt` (vorbereiteter Ausschnitt: Diff bei Datei-Edits, Befehlszeile bei Shell — vom Backend aus dem Tool-Input destilliert, nicht der Volltext)
- `rationale` (letzter Assistenten-Text vor dem Aufruf)
- `context` (Projekt-Pfad, abc-Phase/Rolle — aus der Session)
- `created_at` · `state` (`open` / `resolved` / `obsolete`)

Neuer Session-Status `awaiting_approval`; `SessionRead` bekommt ein optionales Feld `pending_decisions` (Liste offener Cards), damit das gepollte Board die Cards ohne Extra-Request rendert.

### C) API-Form (nur Endpunkte, kein Code)
```
# Vom Cockpit genutzt (REST, wie PROJ-3 gepollt + WS-Live):
GET   /sessions                                   → enthält jetzt pending_decisions je Session
POST  /sessions/{id}/decisions/{decision_id}      → entscheiden:
        body = { decision: "approve" | "deny", comment?: string }
        approve            → Tool gibt { behavior:"allow", updatedInput } zurück, Session läuft weiter
        deny               → { behavior:"deny", message:"Vom Nutzer abgelehnt." }
        deny + comment     → { behavior:"deny", message: <comment> }   (= „Mit Kommentar zurück")
WS    /sessions/{id}/stream                        → broadcastet awaiting_approval + neue/aufgelöste Cards

# NUR von Claude Code selbst aufgerufen (nicht vom Browser), pro Session konfiguriert:
MCP   /mcp/{session_id}   → Tool „approval_prompt(tool_name, input)“ (blockiert bis Entscheidung)
```
MVP single-user → **kein JWT**; der `/mcp/{session_id}`-Endpoint bindet nur an localhost (Claude-Subprozess läuft lokal).

### D) Status → Ampel → Kanban (Ergänzung zum PROJ-3-Mapping)
| Backend-Status | Ampel | Kanban-Spalte |
|---|---|---|
| `awaiting_approval` (**neu**) | 🟠 orange (Handlungsbedarf, wie „Wartet") | **Review/Approval** (jetzt befüllt) |
| `waiting` (unverändert) | 🟡 gelb | Wartet auf dich |

→ Frontend-`lib/status.ts` (PROJ-3) bekommt `awaiting_approval` → `columnFor` = „review", plus orange Ampel-Token.

### E) Tech-Entscheidungen (warum)
- **HTTP-MCP-Tool im selben Prozess statt stdio-Sidecar.** Der `SessionManager` ist bereits eine In-Memory-Registry in **einem** uvicorn-Worker. Hostet das Backend das Permission-Tool selbst, kann der blockierende Tool-Handler direkt eine `asyncio.Future` in der Registry awaiten, die der REST-Entscheidungs-Endpoint auflöst — kein IPC, kein zweiter Prozess, keine Race-Conditions über Prozessgrenzen.
- **Session-Identität über die URL `/mcp/{session_id}`.** Claude Codes Permission-Tool kennt die Jupiter-Session-ID nicht von sich aus. Jede Session wird mit einer **eigenen** `--mcp-config` gestartet, deren URL die `session_id` trägt → der Tool-Aufruf ist eindeutig einer Session zugeordnet.
- **EINE zentrale Trigger-Stelle `policy.requires_card()`.** `--permission-mode default` lässt Claude Code Lesezugriffe ohnehin meist selbst durchwinken; trotzdem läuft **jeder** Permission-Aufruf durch unsere Policy-Funktion (read-only → auto-`allow` ohne Card, Schreib-/Shell-Op → Card). Damit ist der konservative Trigger an **einer** Stelle definiert und #5 (konfigurierbare Trust-Policy, P1) kann sie 1:1 ersetzen — erfüllt das AC explizit.
- **Ausschnitt statt Volltext.** Das Backend destilliert aus dem Tool-Input gezielt Diff bzw. Befehl (Token-Disziplin, zahlt auf die Knappheits-Konstitution PROJ-6 ein) — nicht das ganze Transkript in die Card.
- **`decision_id = tool_use_id`.** Ruft Claude in einem Turn mehrere Tools parallel auf, entstehen mehrere Cards gleichzeitig, jede einzeln auflösbar (deckt Edge Case „mehrere offene Cards" ab).
- **Kein Timeout / kein Auto-Proceed.** Eine offene Card hält den Tool-Aufruf einfach im `await`; ignoriert der Nutzer sie, bleibt die Session sauber pausiert (Edge Case erfüllt). Stirbt der Treiber, löst die Registry alle offenen Futures als `deny` auf und markiert die Cards `obsolet` (Edge Case erfüllt).
- **Benachrichtigung = In-Cockpit-Surfacing (MVP).** Card erscheint via bestehendes Board-Polling (4 s) + Detail-WS sofort; keine OS-/Push-Notification im MVP (separater Roadmap-Punkt).

### F) Abhängigkeiten (Pakete)
- **Backend:** ein leichtgewichtiger MCP-Server-Baustein für den HTTP-MCP-Endpoint (z. B. das offizielle `mcp`-Python-SDK, in den bestehenden FastAPI-Prozess gemountet) — **das einzige potenziell neue Paket**. Sonst FastAPI-Bordmittel (`asyncio.Future`, vorhandene WS-Fan-out-Logik). Kein `anthropic`-SDK (weiter CLI-getrieben).
- **Frontend:** keine neuen Pakete — `DecisionCard` aus bestehenden shadcn-Primitives (Card, Badge, Button, Popover, Textarea).
- **Extern:** `claude` CLI (vorhanden) — unterstützt `--permission-prompt-tool` + `--mcp-config` (im PROJ-1-Spike bereits als verfügbar gelistet).

### G) States (explizit, deutsch)
- **Card offen:** Session orange im „Review/Approval"-Board; Card zeigt Was/Ausschnitt/Warum/Kontext + 4 Aktionen.
- **Entschieden:** Card verschwindet, Session kehrt zu `running` zurück (oder beendet den Turn) — Live über WS.
- **Mehrere Cards:** klar untereinander gelistet, je einzeln entscheidbar.
- **Obsolet (Session gestorben):** Card grau „obsolet", nicht mehr entscheidbar.
- **Fehler beim Zurückspielen:** dezenter Hinweis an der Card statt stiller Verlust.

### Handoff
1. **Backend (`/abc-backend`):** Permission-MCP-Endpoint `/mcp/{session_id}` + `policy.requires_card()` + `PendingDecisionRegistry` (Futures) im `SessionRuntime`; `LaunchSpec`/`build_argv` um `--permission-prompt-tool` + `--mcp-config` erweitern; neuer Status `awaiting_approval`; `POST /sessions/{id}/decisions/{decision_id}`; `pending_decisions` in `SessionRead`. Ausschnitt-Destillation (Diff/Befehl).
2. **Frontend (`/abc-frontend`):** `DecisionCard` + „Review/Approval"-Spalte befüllen; `lib/status.ts` um `awaiting_approval` erweitern; Card auch inline in der Session-Detailansicht; „In Session springen" → bestehende Detail-Route.
3. **QA (`/abc-qa`):** AC + Edge Cases (mehrere Cards, Session-Tod → obsolet, ignorieren → pausiert, Deny-mit-Kommentar fließt zurück); Red-Team: kann der Browser den `/mcp`-Endpoint direkt missbrauchen? (sollte localhost-only sein).

## Implementation Notes — Backend (abc-backend, 2026-06-23)
**Branch:** dev · **Env:** conda `Dashboard` · **Stand:** Backend fertig (Frontend offen). **156→157 Tests grün** (124 Bestand + 33 neu), plus echter End-to-End-Smoke gegen eine reale Haiku-Session.

### Wichtige Abweichung vom Tech-Design: PreToolUse-Hook statt MCP-Tool
Das Tech-Design sah ein selbst-gehostetes **MCP-Permission-Tool** (`--permission-prompt-tool`) vor. Beim Bau zeigte sich: das offizielle `mcp`-Python-SDK (1.28) zieht **Starlette 1.3.1** nach und ist damit **inkompatibel mit dem gepinnten FastAPI 0.115** — es zerschießt das bestehende Backend. Statt FastAPI projektweit zu bumpen, wurde auf den **leichteren, dependency-freien Mechanismus** gewechselt, den Claude Code ebenfalls bietet:

- **`--settings` mit einem `PreToolUse`-Hook** (Matcher `*`). Per Spike (reale `claude` v2.1.186) verifiziert: der Hook-stdin-Payload enthält bereits `session_id` (= unsere `--session-id`), `tool_name`, vollständiges `tool_input` und `tool_use_id` → **direkte Session-Korrelation ohne MCP-Server, ohne Header-/URL-Tricks**. Der Hook **blockiert** Claude synchron bis zur Antwort.
- Rückgabe `{"hookSpecificOutput":{"permissionDecision":"allow"|"deny","permissionDecisionReason":…}}`. **Deny mit `permissionDecisionReason` reist inline zu Claude zurück** (= die abgestimmte „Mit Kommentar zurück"-Variante) — im Smoke bestätigt: Claude las den Kommentar und passte sein Verhalten an.
- **Vorteil ggü. MCP:** keine neue pip-Abhängigkeit (Hook-Skript = nur Stdlib), kein zweiter Prozess, kein Protokoll-Risiko. Der „shared-memory, kein IPC"-Vorteil bleibt: der interne Endpoint und der `SessionManager` leben im selben uvicorn-Prozess.

### Gebaute Module (`backend/app/`)
- `engine/policy.py` — **die EINE zentrale Trigger-Stelle** (`requires_card`): bekannte Lese-Tools (`AUTO_ALLOW_TOOLS`) → auto-allow ohne Card, alles andere (Bash/Edit/Write/NotebookEdit/Task/unbekannt) → Card. Plus `summarize_action` (Was), `extract_excerpt` (Befehl bzw. Mini-Diff statt Volltext, gekappt) und `clip_rationale`. Genau hier ersetzt #5 später die fixe Regel.
- `engine/decisions.py` — `PendingDecision` (Card-Datenmodell, `decision_id = tool_use_id`) + `DecisionOutcome` (→ `to_hook_response()` = exakter Hook-Vertrag).
- `engine/permission_hook.py` — **eigenständiges Stdlib-Hook-Skript** (json/urllib), das Claude pro Tool-Call ausführt; postet an `/internal/permission` und **fail-safe deny** bei jedem Fehler (Backend nicht erreichbar → blockiert, nie Auto-Approve).
- `engine/hooks.py` — `build_hook_settings()` baut die session-skopierte `--settings`-JSON (Hook-Befehl mit `sys.executable`, großzügiger `timeout`).
- `engine/manager.py` — neuer Status **`awaiting_approval`**; `SessionRuntime.request_decision()` (legt Card an, Status→`awaiting_approval`, **awaitet eine `asyncio.Future`**), `resolve_decision()` (Freigeben/Ablehnen/Kommentar → entsperrt; Status→`running`, wenn keine Card mehr offen), `abandon_decisions()` (Session-Tod/Stop → Cards `obsolet`, Futures als deny aufgelöst). „Warum" = jüngster Assistenten-Text **oder** Denk-Block. `to_read()` liefert `pending_decisions` mit.
- `engine/base.py` + `claude_driver.py` — `LaunchSpec.settings_json` + `build_argv` hängt `--settings` an (nur wenn gesetzt).
- `routes/permission.py` — interner `POST /internal/permission` (Token-Header, localhost-only): ruft `request_decision`, blockiert, gibt den Hook-Output zurück.
- `routes/sessions.py` — `POST /sessions/{id}/decisions/{decision_id}` (Body `{decision: approve|deny, comment?}`; 404/409-Fehlerpfade); `GET /sessions` + Detail liefern jetzt `pending_decisions`.
- `schemas/sessions.py` — `PendingDecisionRead`, `DecisionResolve`, `PermissionHookRequest`; `pending_decisions` an `SessionRead`.
- `config.py` — `enable_decision_cards` (Default an), `hook_self_url`, `hook_token`, `hook_timeout_seconds` (24 h → **kein** Timeout-Autoproceed; läuft er ab, greift Claudes sicherer Default = deny).

### Status → Kanban (für das Frontend, PROJ-3 `lib/status.ts`)
Neuer Wert **`awaiting_approval`** → Spalte **„Review/Approval"** (orange). `pending_decisions[]` je Session trägt die Card-Daten fürs Rendering.

### Edge Cases (verifiziert per Test)
- Mehrere offene Cards je Session (`decision_id = tool_use_id`) → einzeln auflösbar; Status bleibt `awaiting_approval`, bis die letzte entschieden ist.
- Session stirbt/gestoppt mit offener Card → Card `obsolet`, wartender Hook wird mit deny entsperrt (kein hängender Prozess).
- Nutzer ignoriert Card → kein Timeout-Autoproceed (Hook wartet; Future bleibt offen).
- Deny mit Kommentar → Kommentar als Begründung inline zu Claude (Smoke-bestätigt).
- Doppeltes Auflösen → 409/KeyError.

### Verifikation
- `pytest` → **157 grün** (`test_proj4_decision_cards.py`: Policy, Ausschnitt, Hook-Settings, blockierender Flow, Abandon, REST-Vertrag, voller Hook→Resolve-Roundtrip via `httpx.ASGITransport`). Keine Regression in den 124 Bestands-Tests.
- **Echter End-to-End-Smoke** (uvicorn, 1 Worker, reale Haiku-Session): Session bat um `echo hallo` via Bash → Status `awaiting_approval`, Card mit korrektem Was/Ausschnitt/Kontext → „Mit Kommentar zurück" → Claude erhielt die Begründung und passte sich an → Status zurück auf `waiting`, Card weg.

### Offene Punkte / Grenzen
- **Betrieb mit EINEM uvicorn-Worker** (unverändert; Registry + offene Futures liegen im Prozessspeicher). Mehrere Worker würden den blockierenden Hook-Endpoint und den `resolve`-Endpoint trennen.
- Hook-Timeout (24 h) ist die theoretische Obergrenze der Wartezeit; danach sicherer Default deny.
- `/internal/permission` ist nur per Token + localhost geschützt (MVP single-user; vor Multi-User/Exponierung härten, #21).

→ Bereit für `/abc-frontend` (DecisionCard + „Review/Approval"-Spalte) und danach `/abc-qa`.

## Implementation Notes — Frontend (abc-frontend, 2026-06-23)
**Branch:** dev · **Stack:** Next.js 16 (App Router) + shadcn/ui (Cockpit aus PROJ-3) — rein additiv, kein neues Paket.

### Gebaut
- **`components/cockpit/decision-card.tsx`** (NEU) — die Card: **Bash/Tool-Badge + Aktion** („Was"), **Kontext-Zeile** (Projekt · Phase/Rolle), **Ausschnitt** als `<pre>` (Befehl/Diff, scrollbar — nicht das Log), **„Warum"** (Rationale), Aktionen **Freigeben** / **Ablehnen** / **Mit Kommentar zurück** (klappt eine Textarea aus → Deny mit Begründung) / **In Session springen →** (`showJump`, auf der Detailseite ausgeblendet). Obsolet-Zustand grau + Aktionen deaktiviert. Toast bei Erfolg/Fehler; danach blendet das Polling/WS die Card aus.
- **`lib/types.ts`** — `SessionStatus` um `awaiting_approval`; neues `PendingDecision`-Interface; `pending_decisions: PendingDecision[]` an `Session`.
- **`lib/status.ts`** — neue Ampel-Farbe **`orange`**; `statusMeta.awaiting_approval` („Freigabe nötig"); `columnFor` → `awaiting_approval` = **„review"** (füllt PROJ-3s reservierte Spalte); `countStatuses.freigabe`; `railRank` priorisiert `awaiting_approval` ganz oben (braucht dich JETZT).
- **`components/cockpit/ampel.tsx`** — orange Punkt (pulsiert).
- **`kanban-board.tsx`** — die **„Review/Approval"-Spalte** rendert jetzt die offenen `DecisionCard`s (statt Platzhalter); orange Hervorhebung + Karten-Zähler.
- **`session-tile.tsx`** — `awaiting_approval` = orange Ring + „⚠ N Freigabe(n) nötig".
- **`global-status-bar.tsx`** — Mission-Control-Zähler **„Freigabe nötig"** (orange).
- **`lib/api.ts`** — `resolveDecision(sessionId, decisionId, "approve"|"deny", comment?)` → `POST /sessions/{id}/decisions/{decision_id}`.
- **Detailseite** (`sessions/[id]/page.tsx`) — offene Cards inline über der Eingabe (mit `showJump={false}`).

### Im Test gefundener & behobener Backend-Bug (per Screenshot)
Die Detailseite zeigte eine bereits offene Card **nicht** an: Der **initiale WebSocket-Snapshot** nutzte `runtime.state.to_read()` (ohne `pending_decisions`) und überschrieb damit den vollständigen REST-Load. Fix in `routes/sessions.py`: Snapshot nutzt jetzt `runtime.to_read()` (inkl. Cards). Mit Test `test_ws_initial_snapshot_carries_pending_decisions` abgesichert (Backend jetzt **158 grün**). Zusätzlich kleine Backend-Politur: „Warum" fällt auf den Denk-Block zurück, wenn kein Assistenten-Text vorausging (sonst leer) — im Live-Smoke bestätigt.

### Verifikation
- **Vitest** `lib/status.test.ts` → **18 grün** (neue Fälle: orange/awaiting_approval-Mapping, review-Spalte, `freigabe`-Zähler, railRank-Priorität). `npm run lint` grün, `next build` grün (TypeScript ok).
- **Echter visueller End-to-End-Smoke** (Prod-Build + reales Backend + reale Haiku-Session, Playwright-Screenshots): Session löst Bash-Card aus →
  - **Detailseite:** Card inline mit Bash-Badge, „Shell-Befehl: echo hallo", Kontext, Ausschnitt (`$ echo hallo`), gefülltem „Warum", Freigeben/Ablehnen/Mit Kommentar zurück.
  - **Board:** orange Kachel „⚠ 1 Freigabe nötig" + Mission-Control „1 Freigabe nötig"; **Kanban „Review/Approval"-Spalte (Zähler 1)** zeigt die Card inkl. „In Session springen →".
- Hinweis: Betrieb weiterhin **ein** uvicorn-Worker; `JUPITER_HOOK_SELF_URL` muss auf die Backend-Adresse zeigen (Default `:8000`).

→ Bereit für `/abc-qa`.

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
