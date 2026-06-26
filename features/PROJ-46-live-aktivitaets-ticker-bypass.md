# PROJ-46: Live-Aktivitäts-Ticker — sehen, was der Agent gerade tut (v. a. Bypass-Mode)

## Status: Planned
**Created:** 2026-06-26
**Last Updated:** 2026-06-26

## Dependencies
- Requires: PROJ-4 (Decision Cards) — der PreToolUse-Hook `request_decision` ([manager.py:513](backend/app/engine/manager.py#L513)) feuert bei **jedem** Tool, auch im Bypass; er ist die natürliche „ein Tool startet jetzt"-Quelle. Im Bypass-Zweig ([manager.py:613](backend/app/engine/manager.py#L613)) läuft die operative Freigabe **ohne Card** durch → genau hier fehlt heute jede Sichtbarkeit.
- Requires: PROJ-1 (Engine-Treiber) — liefert den Event-Strom (`assistant`-/`result`-Events) und die WS-Fan-out-Infrastruktur (`_broadcast`).
- Requires: PROJ-3 (Cockpit) — die Session-Ansicht + WebSocket-Anbindung, in der der Ticker angezeigt wird.
- Verwandt: PROJ-27 (Liveness-Icon/Heartbeat) — dieses Feature **ergänzt** den Heartbeat um *inhaltliche* Hinweise (das „dass es lebt" wird zum „was es gerade tut").
- Verwandt: PROJ-10 (Trust-Policy) / PROJ-1 — Ursprung des `bypassPermissions`-Modus.

## Problem
Läuft eine Session im **Bypass-Mode** (`bypassPermissions`), bekommt der Nutzer **keine inhaltliche Rückmeldung**, was der Agent gerade tut. Grund (im Code verankert):
- Im normalen Modus surfacen **Decision Cards** jeden operativen Tool-Call (welches Tool, welches Ziel) — das ist die faktische „der Agent arbeitet gerade an X"-Anzeige. Im **Bypass** werden operative Tools **ohne Card** auto-freigegeben ([manager.py:611-613](backend/app/engine/manager.py#L611)) → diese Sichtbarkeit entfällt komplett.
- Es gibt **kein** `tool_use`/`tool_result`-Event im Stream (vgl. PROJ-32-Design); `handle_event` sieht nur `assistant`- und `result`-Events. Zwischen zwei Assistenten-Sätzen — also während langer Tool-Ketten — kommt im UI minutenlang **gar nichts** an.

Folge: Das vorhandene **Liveness-Icon + Heartbeat** (PROJ-27) zeigt zwar „lebt/hängt", aber **nicht**, *woran* gearbeitet wird. Der Nutzer kann nicht unterscheiden, ob die Session noch sinnvoll arbeitet oder feststeckt — im normalen Claude-Terminal sieht man dagegen laufend Tool-Aufrufe und Zwischen-Output.

## Lösungsidee (bewusst aufwandsarm)
Ein **transienter Aktivitäts-Ticker** pro Session: eine kurze, flüchtige Zeile/Chip in der Session-Ansicht, die die **jüngste Agenten-Aktion** zeigt — primär **Tool-Start** (Tool-Name + knappes Ziel, z. B. `Edit · main.py`, `Bash · npm run build`, `Read · liveness.py`) und der **jüngste Assistenten-Zwischen-Text**. Quelle ist der bereits feuernde `request_decision`-Hook (auch im Bypass) plus die bereits gebroadcasteten `assistant`-Events — **kein** neuer Event-Parser nötig.

**Transient by design:** Diese Hinweise werden **nicht** persistiert (kein Vault-Session-Log, kein dauerhafter Transcript-Eintrag) — sie werden nur **kurzzeitig live** angezeigt (z. B. letzte 1–N Aktionen im Speicher, läuft nach kurzer Zeit/State-Wechsel aus). Das hält den Aufwand klein und die Logs schlank.

## User Stories
- Als Nutzer einer Bypass-Session möchte ich **live sehen, welches Tool gerade läuft** (Name + grobes Ziel), damit ich erkenne, dass — und woran — der Agent arbeitet.
- Als Nutzer möchte ich den **jüngsten Zwischen-Text/Gedanken** des Agenten kurz sehen, damit ich den inhaltlichen Fortschritt einordnen kann (wie im normalen Terminal).
- Als Nutzer möchte ich, dass diese Hinweise **flüchtig** sind (kurz angezeigt, nicht gespeichert), damit weder Vault-Logs noch UI zugemüllt werden.
- Als Nutzer möchte ich, dass der Ticker den vorhandenen **Heartbeat/Icon ergänzt**, nicht ersetzt — „lebt" + „tut gerade X" zusammen.
- Als Nutzer möchte ich, dass das auch **im Nicht-Bypass-Modus** funktioniert (dort ist es ein Bonus zusätzlich zu den Cards), ohne die Decision Cards zu verändern.

## Acceptance Criteria
- [ ] **Tool-Start sichtbar im Bypass:** Startet im `bypassPermissions`-Modus ein operatives Tool, erscheint im UI **innerhalb ~1 s** eine transiente Aktivitäts-Anzeige mit **Tool-Name** und einem **kurzen Ziel-Hinweis** (z. B. Datei/Befehl, serverseitig auf eine sichere, kurze Länge gekürzt). Kein Decision-Card-Verhalten wird dabei ausgelöst.
- [ ] **Zwischen-Text sichtbar:** Der jüngste `assistant`-Text-/Thinking-Schnipsel wird im Ticker kurz angezeigt (gekürzt), zusätzlich zum bestehenden Nachrichten-Broadcast.
- [ ] **Transient / nicht persistiert:** Die Ticker-Inhalte landen **weder** im Vault-Session-Log (`_write_session_log`) **noch** als dauerhafter Transcript-Eintrag; nach einem definierten Fenster/State-Wechsel verschwinden sie. Nachweis: ein Lauf erzeugt keine zusätzlichen persistierten Einträge durch den Ticker.
- [ ] **Über die vorhandene WS-Leitung:** Die Hinweise reisen über den bestehenden `_broadcast`/WebSocket-Kanal (eigener leichter `kind`, z. B. `"activity"`) — **kein** neuer Endpunkt, **kein** Polling.
- [ ] **Ergänzt den Heartbeat:** Das Liveness-Icon/Heartbeat (PROJ-27) bleibt unverändert; der Ticker steht sichtbar daneben/darunter in der Session-Ansicht.
- [ ] **Kein Decision-Card-Eingriff:** Cards (normaler Modus) und die Bypass-Auto-Freigabe (PROJ-4) verhalten sich funktional unverändert; der Ticker ist rein additiv/lesend.
- [ ] **Robust bei Stille:** Läuft ein langes Tool ohne neue Events, friert der Ticker auf der letzten Aktion ein (kein Flackern, keine falsche „fertig"-Anzeige) — die Hänger-Bewertung bleibt Sache von PROJ-27/32/45.
- [ ] Alle UI-Texte deutsch; Frontend-Lint/Typecheck/Tests grün; keine Backend-Regression (PROJ-4/27/32).

## Edge Cases
- **Sehr lange/sensible Tool-Eingaben:** Ziel-Hinweis wird **serverseitig** gekürzt/auf ein sicheres Feld reduziert (z. B. nur Tool-Name + Datei/Kommando-Kopf) — keine ungefilterte Ausgabe großer Payloads ins UI.
- **Schnelle Tool-Ketten:** Ticker zeigt die jeweils jüngste Aktion; kein Stau/Rückstand (nur letzter Stand bzw. kurze Ring-Historie der letzten N).
- **Parallele Tool-Calls:** Anzeige der zuletzt gestarteten Aktion genügt (analog PROJ-32-„in-flight").
- **Session terminal/`tot`:** Ticker leert sich / zeigt nichts mehr; keine veraltete Aktion „hängen lassen".
- **Mehrere UI-Clients an derselben Session:** Alle Subscriber bekommen denselben Broadcast (vorhandener Fan-out).
- **Reconnect/Spät-Verbinder:** Der Ticker ist transient — ein neu verbundener Client sieht ab dann die Live-Aktionen, ohne Nachladen von Historie (bewusst, da nicht persistiert).
- **Nicht-Bypass:** Ticker läuft zusätzlich zu den Cards; keine Doppel-Anzeige-Pflicht, kein Konflikt.

## Technical Requirements (optional)
- **Quelle Tool-Start:** der bereits bei jedem Tool feuernde `request_decision`-Hook (Matcher `"*"`), auch im Bypass-Zweig — **keine** neue Stream-Parsing-Logik.
- **Quelle Zwischen-Text:** vorhandener `assistant`-Broadcast (`handle_event`, manager.py:406).
- **Transienter Speicher:** kleiner In-Memory-Ring/letzter-Stand am `SessionRuntime`; **nicht** in `transcript`/Vault-Log schreiben. O(1) pro Event, kein Hot-Path-Regress.
- **Sicherheit:** Ziel-Hinweis serverseitig sanitisieren/kürzen; keine Secrets/vollständigen Payloads ins UI.
- **Frontend:** leichte Komponente im bestehenden Cockpit/Session-View, hört auf den neuen `activity`-WS-`kind`; Auto-Ausblenden nach Zeitfenster.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung dieses Features |
|---|---|
| **PROJ-4 (Decision Cards)** | Nutzt denselben PreToolUse-Hook als Signalquelle; Cards/Bypass-Freigabe selbst **unverändert** (rein lesend/additiv). |
| **PROJ-27 (Liveness/Heartbeat)** | Wird inhaltlich ergänzt: „lebt" → „lebt + tut gerade X". Icon/Heartbeat unverändert. |
| **PROJ-3 (Cockpit)** | Neue, kleine Anzeige in der Session-Ansicht über den vorhandenen WS-Kanal. |
| **PROJ-5 / Vault-Logging** | **Kein** zusätzliches Persistieren — Ticker ist bewusst flüchtig. |

## Offene Design-Fragen (für /abc-architecture — mit Default-Vorschlag)
1. **Anzeige-Umfang:** *Default-Vorschlag:* einzeiliger Ticker „letzte Aktion" (Tool-Chip + jüngster Text-Schnipsel), optional aufklappbare Kurz-Historie der letzten ~5 Aktionen. Alternative: nur einzeiliger letzter Stand.
2. **Lebensdauer der Anzeige:** *Default-Vorschlag:* letzte Aktion bleibt sichtbar, bis eine neue kommt oder die Session terminal wird (kein hartes Timeout) — „transient" = nicht persistiert, nicht zwingend selbst-verschwindend. Architektur bestätigt/justiert.
3. **Ziel-Hinweis-Granularität:** *Default-Vorschlag:* Tool-Name + erstes sinnvolles Argument (Datei-/Kommando-Kopf), serverseitig auf z. B. ≤ 80 Zeichen gekürzt.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_
