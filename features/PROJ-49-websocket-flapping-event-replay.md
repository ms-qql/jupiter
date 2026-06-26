# PROJ-49: WebSocket-Flapping zum Browser — Stabilität + Event-Replay bei Reconnect

## Status: In Progress
**Created:** 2026-06-26
**Last Updated:** 2026-06-26

## Dependencies
- Requires: PROJ-3 (Cockpit) — besitzt die WebSocket-Anbindung Frontend↔Backend (`/api/sessions/{id}/stream`) und den Subscriber-Fan-out (`manager.subscribe`/`_broadcast`).
- Requires: PROJ-1 (Engine-Treiber) — Quelle der Live-Events (`message`/`state`/`decision`).
- Verwandt: PROJ-25 (Auth/JWT) — der WS-Zugang läuft über `access_token`; Token-Refresh ist ein Reconnect-Verdächtiger.
- Verwandt: PROJ-46 (Aktivitäts-Ticker) — dessen `activity`-Events gehen bei Flapping ebenfalls verloren.
- Verwandt: PROJ-47 (Reader-Stall) — **anderer** Defekt (Backend↔Subprozess), gleicher Oberflächen-Effekt „eingefrorenes UI". PROJ-49 ist der Delivery-Layer (Backend↔Browser). Nicht vermischen.

## Problem / Beweislage (Live-Betrieb 2026-06-26)
Der Browser hält pro offener Session eine **WebSocket** zum Backend (`/api/sessions/{id}/stream`) für Live-Events (Assistenten-Nachrichten, Status, Decision Cards, Aktivitäts-Ticker). „**Flapping**" = diese Verbindung **bricht ab und verbindet sich wieder, immer wieder**, statt für die Session-Lebensdauer offen zu bleiben.

**Beleg (Vorfall, Session `3e16cb4a`):** in ~2 min **7×** `WebSocket … [accepted]` im Backend-Log (13:03:27, :55, 13:04:28, :42, :56, 13:05:11, :16), zusätzlich GET-Re-Polling der Session im ~15-s-Takt. **Beide** zu dem Zeitpunkt laufenden Sessions (`3e16cb4a`, `5a2969fc`) betroffen → kein Einzelfall.

**Intermittierend:** Im Normalbetrieb (späterer Check) nur **1 WS pro Session** = korrekt. Das Flapping tritt also **zeitweise** auf (Trigger noch unklar) — daher diese Spec mit der frischen Vorfall-Evidenz, bevor sie verblasst.

### Warum das schadet (Kernmechanik)
Bei jedem Reconnect legt das Backend eine **frische Subscriber-Queue** an (`manager.subscribe`), die **nur Events ab Verbindungszeitpunkt** erhält. **Es gibt kein Replay/Resync** verpasster Broadcasts. Folge: jedes `message`/`state`/`decision`/`activity`-Event, das **während einer Verbindungslücke** gesendet wurde, fehlt im UI **dauerhaft** → veraltetes/„eingefrorenes" Transkript, obwohl das Backend die Daten hat. (Im PROJ-47-Vorfall hat das die Diagnose zusätzlich verschleiert.)

### Ursache (Hypothesen — von /abc-architecture einzugrenzen)
Zwei Teilprobleme, getrennt behandelbar:
- **(A) Instabilität (warum bricht die WS ab?):** Kandidaten — Frontend re-mountet/re-initialisiert die WS auf einem Timer/Effekt; Caddy-Reverse-Proxy-Idle-Timeout für WS; JWT-`access_token`-Ablauf/Refresh (15 min, passt aber NICHT zum ~15-30-s-Takt → eher sekundär); Backend schließt idle WS; fehlende Heartbeat/Ping-Pong-Keepalive.
- **(B) Verlust bei Reconnect (warum gehen Events verloren?):** kein Replay/Resync — eine frische Subscription beginnt „leer".

## User Stories
- Als Nutzer möchte ich, dass die Live-Verbindung einer offenen Session **stabil offen bleibt** (kein ständiges Neu-Verbinden), damit das Cockpit nicht einfriert.
- Als Nutzer möchte ich, dass nach einem **unvermeidbaren** Reconnect (Netz, Tab-Wechsel, Token-Refresh) das UI den **aktuellen Stand nachlädt** — keine verlorenen Nachrichten/Status.
- Als Nutzer möchte ich erkennen, wenn die Live-Verbindung gerade getrennt ist (statt stiller, veralteter Anzeige).

## Acceptance Criteria
- [ ] **Stabile WS:** Eine offene Session hält **eine** WebSocket über ihre Lebensdauer (kein ~15-30-s-Reconnect-Takt). Nachweis: über ≥ 10 min aktiver Session **keine** wiederholten `[accepted]` für dieselbe Session im Backend-Log (außer bei echtem Netz-/Token-Ereignis).
- [ ] **Keepalive:** WS-Ping/Pong (oder gleichwertig) verhindert Idle-Timeouts (Backend/Caddy); die Verbindung übersteht stille Phasen (langer Tool-Lauf ohne Events).
- [ ] **Replay/Resync bei Reconnect:** Nach einem Reconnect erhält der Client den **aktuellen Vollzustand** (Status + jüngstes Transkript/Decision-Cards) — verpasste Events während der Lücke führen **nicht** zu dauerhaft fehlendem UI-Inhalt. (Z. B. Snapshot-on-subscribe und/oder Cursor/`since`-Resync.)
- [ ] **Token-Refresh ohne Daten-Lücke:** Läuft das `access_token` ab, wird die WS so erneuert, dass kein UI-Inhalt verloren geht (Resync greift).
- [ ] **Verbindungs-Status sichtbar:** Bei getrennter WS zeigt das UI einen klaren „getrennt/verbinde neu"-Hinweis statt stiller, veralteter Anzeige.
- [ ] **Ursache (A) behoben/erklärt:** der konkrete Flapping-Auslöser ist identifiziert und adressiert (nicht nur per Resync kaschiert).
- [ ] Deutsche UI-Texte; Frontend-Lint/Typecheck/Tests + Backend-Suite grün; keine Regression in PROJ-3/4/46.

## Edge Cases
- **Mehrere Tabs/Geräte (Tailnet) an derselben Session:** alle bekommen denselben Fan-out + jeweils sauberes Resync; kein gegenseitiges Trennen.
- **Echter Netzabriss (Laptop zu/Tunnel weg):** Reconnect + Resync stellt den aktuellen Stand her.
- **Sehr lange stille Phase (langer Tool-Lauf):** Keepalive hält die WS; danach kommen Events normal weiter.
- **Reconnect exakt während eines Broadcasts:** keine Doppelung und kein Verlust (Resync idempotent / Cursor-basiert).
- **Terminale Session während Trennung:** nach Reconnect korrekt als done/error dargestellt (kein „läuft noch"-Geist).

## Technical Requirements (optional)
- **Snapshot-on-subscribe:** beim WS-Connect sofort den aktuellen `to_read()`-Vollzustand (Status + Transkript-Tail + offene Cards) senden, bevor der Live-Strom anläuft — schließt die Replay-Lücke ohne Server-seitigen Event-Puffer.
- **Optional Cursor/`since`:** falls feingranulares Nachliefern nötig, ein monoton wachsender Event-Index, den der Client beim Reconnect mitschickt (vgl. das Byte-Offset-Muster des Sessions-Tabs in Rubric).
- **Keepalive:** WS-Ping-Intervall < Caddy/Proxy-Idle-Timeout; Caddy-WS-Pfad ggf. explizit konfigurieren.
- **Frontend-Reconnect:** Backoff statt Tight-Loop; WS nicht auf jedem Render/Poll-Tick neu aufbauen (Effekt-Abhängigkeiten prüfen — heißer Verdacht für (A)).
- **Diagnose:** der Trigger ist reproduzierbar einzugrenzen (Frontend-Effekt vs. Proxy-Timeout vs. Token) — nicht blind beide Layer „härten".

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung dieses Fixes |
|---|---|
| **PROJ-3 (Cockpit)** | Kern: WS-Stabilität + Snapshot/Resync beim Subscribe; Fan-out unberührt in der Semantik. |
| **PROJ-4 (Decision Cards)** | Karten dürfen bei Reconnect nicht „verschwinden" — Resync liefert offene Cards mit. |
| **PROJ-46 (Aktivitäts-Ticker)** | Profitiert direkt (transiente `activity`-Events gehen nicht mehr in Lücken verloren). |
| **PROJ-25 (Auth)** | Token-Refresh-Pfad für die WS sauber (kein Daten-Loch). |
| **PROJ-47 (Reader-Stall)** | Getrennt: Backend↔Subprozess. Beide zusammen ergeben „UI spiegelt Realität". |

## Offene Design-Fragen (für /abc-architecture — mit Default-Vorschlag)
1. **Replay-Mechanismus:** *Default-Vorschlag:* **Snapshot-on-subscribe** (aktueller Vollzustand beim Connect) — einfachster verlustfreier Weg, kein Server-Event-Puffer nötig. Cursor/`since` nur, falls feingranulares Nachliefern gebraucht wird.
2. **Reihenfolge der Arbeit:** *Default-Vorschlag:* zuerst **(B) Resync** (macht das UI sofort robust gegen JEDEN Reconnect), dann **(A) Stabilität** (eigentlicher Flapping-Trigger) — so ist der Nutzer auch bei unvermeidbaren Reconnects geschützt.
3. **Keepalive-Ort:** *Default-Vorschlag:* App-seitiges WS-Ping/Pong (Treiber-unabhängig) + Caddy-WS-Timeout prüfen.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-26 · **Stack:** Next.js (Cockpit) + FastAPI (WS) + In-Memory-Runtime · **Branch:** dev

### Befund (im Code verifiziert — kein Rätselraten)
- **Backend `stream_session`** (`backend/app/routes/sessions.py:332`) sendet beim Connect bereits einen Snapshot — aber **nur** `{"kind":"state", **runtime.to_read()}`. `to_read()` (`manager.py:378`) liefert Status + offene Decision Cards + Liveness, **NICHT das Transkript**. Das Transkript kommt heute ausschließlich aus dem einmaligen REST-`GET /{id}` beim Seiten-Mount.
- **Fan-out** (`subscribe`/`unsubscribe`/`_broadcast`, `manager.py:401`) legt pro Connect eine **frische, leere Queue** an → Events während einer Lücke sind weg.
- **Frontend `useSessionStream`** (`hooks/use-session-stream.ts`): äußerer Effekt hängt nur an `[id]`, Reconnect läuft *innerhalb* via `setTimeout(connect, 2000)`. `liveText` (seit-Connect-Strom) **überlebt** den Reconnect im React-State — aber während der Lücke gesendete `message`-Chunks fehlen für immer. **Kein Ping/Pong, kein Resync.**
- **Render-Modell der Detailseite** (`app/(cockpit)/sessions/[id]/page.tsx`): Transkript = `detail.transcript` (REST, einmalig) **+** `liveText` (WS, append-only). Genau hier reißt die Lücke ein.

**Konsequenz:** (B) Verlust ist strukturell — Snapshot trägt das Transkript nicht. (A) Flapping-Auslöser ist noch nicht im Code festnagelbar (Effekt-Deps sind sauber `[id]`); der ~15–30-s-Takt passt **nicht** zu Token-Ablauf (15 min) → Diagnose zuerst, nicht blind beide Layer „härten".

### Reihenfolge (folgt dem Default der Spec: erst B, dann A)
**B-Resync macht das UI sofort robust gegen JEDEN Reconnect** — auch gegen unvermeidbare (Netz, Tab, Token). Danach A-Stabilität gegen den eigentlichen Auslöser.

---

### Teil B — Verlustfreier Resync (Snapshot-on-subscribe, erweitert)
**Entscheidung (Design-Frage 1): Snapshot-on-subscribe statt Server-Event-Puffer.** Kein monoton wachsender Cursor/`since` im MVP — der vorhandene Voll-Snapshot beim Connect schließt die Lücke verlustfrei und ist idempotent. (Cursor bleibt eine spätere Option, falls je feingranulares Nachliefern statt Voll-Snapshot gebraucht wird — vgl. Byte-Offset-Muster des Rubric-Sessions-Tabs.)

**Was sich ändert (WAS, nicht WIE):**
- Der Connect-Snapshot trägt **zusätzlich das aktuelle Transkript** (Tail genügt; Vollzustand des Live-Index). Damit ist *ein* WS-Frame nach jedem (Re-)Connect die alleinige Wahrheit für Status + offene Cards + Transkript.
- Das **Frontend behandelt diesen Snapshot als Baseline**: beim Empfang ersetzt es die gerenderte Transkript-Basis und **setzt `liveText` zurück** (alles bis „jetzt" steckt schon im Snapshot). Folge-`message`-Chunks hängen wieder an. → Kein Doppeln, kein Verlust, egal wann der Reconnect fällt (Edge Case „mitten im Broadcast" ist abgedeckt, weil der Snapshot den Stand *zum Accept-Zeitpunkt* einfriert und der Live-Strom erst danach anläuft).
- **Decision Cards** reisen schon heute im `state`-Snapshot mit → bei Reconnect nicht „verschwunden" (PROJ-4 ✓). **Terminaler Status** kommt ebenfalls im Snapshot → kein „läuft-noch"-Geist (Edge Case ✓).
- **Mehrere Tabs/Geräte:** jeder Connect bekommt seinen eigenen Snapshot + eigene Queue; Fan-out-Semantik unberührt → kein gegenseitiges Trennen (Edge Case ✓).

### Teil A — Stabilität (Flapping abstellen)
**A1 — Keepalive (Design-Frage 3: app-seitig, treiber-unabhängig).** Server sendet im WS-Loop in festem Intervall einen leichten Ping (z. B. `{"kind":"ping"}`), das Frontend ignoriert ihn. Intervall **deutlich unter** dem Proxy-Idle-Timeout. Hält die WS durch stille Phasen (langer Tool-Lauf ohne Events) → deckt den „sehr lange stille Phase"-Edge-Case ab. Umgesetzt als dritter Zweig/Timeout im bestehenden `asyncio.wait`-Loop (kein zweiter Task-Apparat nötig).
**A2 — Caddy-WS-Pfad prüfen:** Idle-/Read-Timeout für `/api/sessions/*/stream` verifizieren und ggf. explizit setzen, sodass A1-Ping garantiert darunter liegt. (Infra-Schritt, human-gated über Deploy.)
**A3 — Diagnose des Auslösers (Pflicht-AC „Ursache A behoben/erklärt").** Bevor irgendetwas „gehärtet" wird, den Auslöser **reproduzierbar eingrenzen**, in dieser Reihenfolge:
1. **Frontend instrumentieren:** jedes WS `open`/`close` mit `code`/`reason` loggen und gegen die Backend-`[accepted]`-Zeilen korrelieren → klärt **wer schließt** (Client `onerror→close` vs. Server vs. Proxy).
2. **Remount-Hypothese (Leitverdacht):** Effekt-Deps sind sauber `[id]` — also ist nicht der Effekt, sondern ein **Remount der Detailseite/des Subtrees** der Hauptverdacht (z. B. ein 15-s-Poll im sessions-provider, das einen Key/State oben ändert und unten neu mountet). Per React-DevTools/Mount-Log bestätigen.
3. **Erst nach Befund** gezielt fixen (Remount stoppen / Backoff statt Tight-Loop / Proxy-Timeout) — **nicht** beide Layer blind härten.

### API-/Vertrags-Form (Endpunkte, keine Implementierung)
- **WS** `GET /api/sessions/{id}/stream?access_token=…` — unverändert im Pfad. Neu im **Frame-Vertrag**:
  - Connect-Snapshot: `{"kind":"state", …, transcript:[…]}` (Transkript **neu** im Snapshot).
  - Keepalive: `{"kind":"ping"}` periodisch (Client ignoriert).
  - Live wie bisher: `message` / `activity` / `notice` / `state`.
- Kein neuer REST-Endpunkt nötig (Resync läuft über den WS-Snapshot, nicht über Re-Polling).

### Verbindungs-Status sichtbar (AC „getrennt/verbinde neu")
`connected` liefert der Hook bereits. Das Cockpit zeigt bei `connected === false` einen klaren deutschen Hinweis („Verbindung getrennt — verbinde neu …") statt stiller, veralteter Anzeige. Reiner Frontend-Indikator, an `connected` gebunden.

### Warum so (für PM)
- **Snapshot statt Event-Puffer:** Der Server muss keine Event-Historie im RAM mitschleppen — er kennt seinen aktuellen Stand ohnehin und schickt ihn beim Connect komplett. Einfachster verlustfreier Weg, robust gegen *jeden* Reconnect-Grund.
- **Keepalive vor Proxy-Timeout:** Eine WS, die nichts sendet, sieht für Zwischenschichten „tot" aus und wird gekappt. Ein billiger Ping hält sie am Leben — ohne dass echte Daten fließen müssen.
- **Diagnose vor Härtung:** Der ~15–30-s-Takt verrät, dass etwas *aktiv* neu verbindet (kein zufälliger Netzabriss). Diesen Auslöser zu finden ist billiger und ehrlicher, als beide Layer „auf Verdacht" zu härten und das eigentliche Leck zu kaschieren.

### Betroffene Module (Mapping)
| Bereich | Datei | Änderung |
|---|---|---|
| Backend WS | `backend/app/routes/sessions.py:332` (`stream_session`) | Transkript in Connect-Snapshot; Keepalive-Ping im `asyncio.wait`-Loop |
| Frontend Hook | `nextjs_app/hooks/use-session-stream.ts` | Snapshot-Transkript als Baseline + `liveText`-Reset; `ping` ignorieren; Reconnect-Backoff prüfen |
| Frontend Seite | `app/(cockpit)/sessions/[id]/page.tsx` | Transkript-Render aus Snapshot-Baseline statt nur REST; „getrennt"-Hinweis an `connected` |
| Diagnose A | sessions-provider / Detailseite | Remount-Auslöser eingrenzen + abstellen |
| Infra | `Caddyfile` (Deploy, human-gated) | WS-Idle-Timeout für `/api/sessions/*/stream` prüfen |

### Dependencies
Keine neuen Pakete. Reine Verträge-/Verhaltensänderung auf vorhandenem WS-Stack (FastAPI/Starlette WebSocket + Browser-`WebSocket`).

### Abgrenzung
- **PROJ-47** (Reader-Stall, Backend↔Subprozess) ist ein **anderer** Defekt — hier ausschließlich Delivery-Layer Backend↔Browser. Nicht vermischen.
- **PROJ-46**-`activity`-Events profitieren automatisch (Snapshot/Keepalive), brauchen keine eigene Logik.

## Implementierung — Backend (2026-06-26, Branch `dev`)
**Datei:** `backend/app/routes/sessions.py` (`stream_session`), Tests in `backend/tests/test_sessions_api.py`.

- **B — Snapshot trägt jetzt das Transkript:** Der Connect-Frame ist `{"kind":"state", …, "transcript":[…]}` — `to_read()` (Status + offene Decision Cards + Liveness) **plus** `[vars(e) for e in runtime.transcript]` (identische Form wie `GET /{id}`). Damit ist ein einzelner Frame nach jedem (Re-)Connect die alleinige Wahrheit; während einer Lücke verpasste `message`-Chunks fehlen nicht mehr dauerhaft. Kein Server-Event-Puffer, kein neuer Endpunkt.
- **A1 — Keepalive-Ping:** Neue Konstante `_WS_PING_INTERVAL_S = 20.0`. Der `asyncio.wait`-Loop läuft jetzt mit `timeout=_WS_PING_INTERVAL_S`; bleibt `done` leer (stille Phase), wird `{"kind":"ping"}` gesendet (Client ignoriert). Hält die WS durch lange Tool-Läufe und unter dem Caddy/Browser-Idle-Timeout (~60 s).
- **Loop-Umbau:** `queue_get`/`sock_recv` werden **einmal** angelegt und über Iterationen gehalten (statt pro Runde neu) — so zerschneidet ein Ping-Timeout kein laufendes `receive()`. Der jeweils fertige Task wird gezielt neu erstellt; Disconnect bricht weiterhin sauber ab. Cleanup im `finally` unverändert (unsubscribe + Task-Cancel).

**Tests:** `test_websocket_sends_state_snapshot` prüft zusätzlich `transcript` im Snapshot; neuer `test_websocket_keepalive_ping` (Intervall via `monkeypatch` auf 0.1 s) erwartet Snapshot → `ping`. Suite grün: `test_sessions_api` 13 passed; Regression PROJ-4/25/47/1 (83) grün.

**Frame-Vertrag für Frontend (`/abc-frontend`):**
- Connect-Snapshot: `{"kind":"state", …, transcript:[{role,kind,text,ts}, …]}` → als **Baseline** verwenden, `liveText` zurücksetzen.
- `{"kind":"ping"}` → ignorieren (kein UI-Effekt).
- Offen für Frontend: Snapshot-Transkript ins Render übernehmen + `liveText`-Reset; sichtbarer „getrennt"-Hinweis an `connected`; A3-Diagnose des Remount-Auslösers.
