# PROJ-49: WebSocket-Flapping zum Browser — Stabilität + Event-Replay bei Reconnect

## Status: Planned
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
_To be added by /abc-architecture_
