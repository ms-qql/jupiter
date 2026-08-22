# PROJ-86: Hermes-Chat direkt fortsetzen — schneller Start und stabiler Kontext

## Status: Architecture Draft
**Created:** 2026-08-22
**Last Updated:** 2026-08-22

## Dependencies
- Requires: PROJ-85 (Hermes-Chat-Sessions im Cockpit) — behebt ausschließlich dessen Start-, Turn- und Resume-Vertrag.
- Reuses: PROJ-3 (Cockpit: Mission Control + Kanban + Ampel-Kacheln) — Hermes-Sessions bleiben in derselben Session-Ansicht.
- Reuses: PROJ-56 (Kontext-Persistenz & Resume für Nicht-Claude-Engines) — die Hermes-Conversation-ID wird im bestehenden Session-Index gehalten.
- Does not change: PROJ-63/64/65 (tmux-Transport) — deren Verhalten für Standard-Engines bleibt unverändert.

## Beschreibung

Hermes-Chat-Sessions im Cockpit verwenden derzeit den Hermes-One-shot-Modus. Dieser legt pro Turn eine neue Hermes-Conversation an, obwohl Jupiter eine Resume-ID speichert. Außerdem startet eine neue Cockpit-Session mit einem künstlichen Agentenauftrag statt erst mit der ersten echten Nutzereingabe. Das verursacht unnötige Laufzeit, falsche Statusanzeigen und nach wenigen Turns verlorenen Gesprächskontext.

PROJ-86 ersetzt **nur für `engine="hermes"`** diesen Ablauf durch den dokumentierten, direkt fortsetzbaren Hermes-Chat-Aufruf. Eine neu angelegte Hermes-Session wartet zunächst auf die erste Eingabe. Jeder echte Turn verwendet dieselbe von Hermes ausgegebene Conversation-ID; bei einer fehlenden oder abgelehnten ID endet der Turn sichtbar mit einem deutschen Fehler und erzeugt nie still eine neue Unterhaltung.

Hermes bleibt im direkten Prozessmodus. tmux, tmux-spezifische Retry-/Liveness-Mechanismen und automatische Reanimation werden für Hermes nicht verwendet. Standard-Jupiter-Sessions (Claude, Codex, OpenCode und weitere Engines) behalten ihren bestehenden Start-, Transport-, Liveness- und Resume-Ablauf unverändert.

## User Stories

- Als Nutzer möchte ich eine neue Hermes-Session sofort im Cockpit sehen, ohne dass Hermes vorher einen künstlichen Auftrag bearbeitet.
- Als Nutzer möchte ich nach jeder Nachricht in derselben Hermes-Unterhaltung bleiben, damit der Gesprächskontext nach vielen Turns erhalten bleibt.
- Als Nutzer möchte ich eine Hermes-Session nach einem Backend-Neustart mit ihrer echten Hermes-Conversation-ID fortsetzen, damit kein neuer Chat im Namen der bestehenden Session entsteht.
- Als Nutzer möchte ich nach einem beendeten Hermes-Turn den Status „wartet auf Eingabe“ sehen, damit ich nicht fälschlich reaktivieren muss.
- Als Nutzer möchte ich bei einer nicht fortsetzbaren Hermes-Unterhaltung eine klare deutsche Fehlermeldung sehen, damit ich bewusst einen neuen Chat starten kann.
- Als Nutzer möchte ich, dass normale Jupiter-Sessions unverändert weiterlaufen, damit dieser Hermes-Fix keine Regressionen in anderen Engines auslöst.

## Acceptance Criteria

- [ ] `POST /sessions/hermes` erzeugt eine Hermes-Session ohne einen künstlichen Hermes-Prompt oder einen Hermes-Prozess zu starten.
- [ ] Eine neu erzeugte Hermes-Session steht vor der ersten Nutzereingabe sichtbar auf „wartet auf Eingabe“ und ist direkt in der bestehenden Session-Ansicht bedienbar.
- [ ] Die erste nichtleere Nutzereingabe startet genau einen direkten Hermes-Chat-Turn; leere oder nur aus Whitespace bestehende Eingaben starten keinen Prozess.
- [ ] Jeder Folge-Turn einer Hermes-Session verwendet den von Hermes ausgegebenen Conversation-Identifier und setzt exakt diese Conversation fort.
- [ ] Der verwendete Hermes-Aufruf unterstützt Resume tatsächlich; der frühere One-shot-Aufruf, der eine Resume-ID ignoriert, wird für Hermes-Chat-Sessions nicht mehr verwendet.
- [ ] Nach einem erfolgreichen Hermes-Turn speichert Jupiter die von Hermes ausgegebene Conversation-ID atomar zur zugehörigen Jupiter-Session und zeigt den Zustand „wartet auf Eingabe“.
- [ ] Ein erfolgreicher Hermes-Turn zeigt weder „Session beendet/nicht steuerbar“ noch einen Reaktivieren-Knopf.
- [ ] Hermes-Sessions verwenden stets den direkten Prozessmodus und starten oder prüfen keine tmux-Session.
- [ ] Für Hermes-Sessions führt die Liveness-Auswertung keine automatische Reanimation aus.
- [ ] Wenn Hermes eine gespeicherte Conversation-ID nicht findet oder Resume ablehnt, zeigt die Session einen deutschen Fehler mit der Hermes-Ursache; Jupiter startet nicht automatisch eine neue Hermes-Conversation.
- [ ] Nach einem Backend-Neustart bleibt eine ruhende Hermes-Session sichtbar. Die nächste Eingabe setzt sie mit der gespeicherten Hermes-Conversation-ID fort, sofern Hermes diese akzeptiert.
- [ ] Laufende Standard-Sessions behalten unverändert ihren bisherigen Transport, ihren Liveness-Status, ihre Reanimation und ihr Resume-Verhalten.
- [ ] Hermes-Kanban und eingebettetes Hermes-Dashboard bleiben unverändert.
- [ ] Die automatisierten Tests decken mindestens Erststart, drei aufeinanderfolgende Folge-Turns, abgelehntes Resume, Backend-Neustart einer ruhenden Hermes-Session sowie die Unverändertheit einer Nicht-Hermes-Session ab.

## Edge Cases

- **Erste Eingabe ist leer:** Die Session bleibt wartend; Hermes wird nicht gestartet.
- **Hermes liefert nach einem Turn keine Conversation-ID:** Jupiter markiert die Session mit einem deutschen Fehler; die nächste Eingabe darf keinen frischen Chat vortäuschen.
- **Gespeicherte Conversation-ID existiert bei Hermes nicht mehr:** Jupiter zeigt die Originalmeldung von Hermes in deutscher Fehlerhülle und bietet keinen stillen Fallback an.
- **Backend-Neustart während eines laufenden direkten Hermes-Turns:** Der Turn gilt als unterbrochen. Jupiter darf ihn nicht als erfolgreich oder fortsetzbar markieren; der Nutzer erhält eine klare Fehlermeldung und kann danach bewusst erneut senden.
- **Backend-Neustart zwischen Turns:** Die persistierte Hermes-ID wird beim nächsten echten Text verwendet; es entsteht keine zusätzliche Conversation.
- **Doppelklick oder parallele Eingaben:** Solange ein Hermes-Turn läuft, wird die zweite Eingabe mit der bestehenden deutschen Busy-Meldung abgelehnt; es startet kein zweiter Prozess.
- **Provider-/Netzwerkfehler:** Der Fehler wird sichtbar an die Hermes-Session gebunden; andere Sessions und ihre Liveness bleiben unbeeinflusst.
- **Hermes liefert zusätzliche Diagnosezeilen:** Nur der von Hermes eindeutig ausgegebene Conversation-Identifier wird persistiert; Diagnoseausgabe darf nicht als Chat-Nachricht oder ID fehlinterpretiert werden.

## Non-Goals

- Keine Änderung am gemeinsamen tmux-Transport und keine Entfernung der bestehenden tmux-Härtungen für andere Engines.
- Keine Änderung der Standard-Session-API oder des Liveness-/Reanimationsverhaltens für Nicht-Hermes-Engines.
- Keine eigene Hermes-Chat-Oberfläche, kein Hermes-TUI und keine Browser-Terminal-Emulation.
- Keine Änderung an Hermes-Kanban, Hermes-Dashboard, Hermes-Profilen, Modellwahl oder Provider-Konfiguration.
- Keine automatische Wiederholung eines fehlgeschlagenen Hermes-Turns und kein stiller Wechsel auf eine neue Conversation.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-22 · **Stack:** Next.js/shadcn + FastAPI + bestehender raw-SQL/SQLite-Session-Index mit JWT-Owner-Scope; Hermes CLI; Dokploy · **Branch:** main

### Ziel und Abgrenzung

PROJ-86 korrigiert nur den `engine="hermes"`-Pfad aus PROJ-85. Eine neue
Hermes-Session ist zunächst ein ruhender Chat-Eintrag, kein Auftrag. Der erste
nichtleere Text startet genau einen direkten Hermes-Chat-Turn. Jeder weitere
Turn setzt ausschließlich die von Hermes zurückgegebene Conversation-ID fort.

`hermes -z/--oneshot` und `--usage-file` sind für Cockpit-Hermes-Chats kein
zulässiger Transport: `hermes chat --help` bietet kein `--usage-file`.
Stattdessen startet der Driver je Turn einen direkten, nichtinteraktiven
`hermes chat -q <text> --cli -Q`-Prozess; der Folgeturn ergänzt ausschließlich
`--resume <hermes_conversation_id>` und behält Provider, Modell,
Arbeitsverzeichnis und Safety-Flags bei. Beide Läufe bleiben direkte
Subprozesse; `tmux`, Pane-Checks, tmux-Respawn und Auto-Reanimation sind für
Hermes ausgeschlossen.

Standard-Engines und Hermes-Kanban/-Dashboard liegen außerhalb des Features.

### Komponenten und Zustandsfluss

```
Bestehender HermesStartDialog
└── POST /sessions/hermes
    └── SessionManager.create_hermes()
        ├── SessionIndex: Status waiting, ohne Prozess
        └── HermesChatDriver: nur vorbereitet, noch kein CLI-Aufruf

Bestehende SessionView
└── POST /sessions/{id}/input
    ├── leer/Whitespace: deutsche 422-Antwort, kein Zustands- oder Prozesswechsel
    ├── erster Text: direkter Hermes-Chat-Turn
    └── Folgetext: direkter Hermes-Chat-Resume-Turn mit persistierter ID

HermesChatDriver
└── stdout-Kontrollzeile `session_id: <opaque-id>` + Ergebnis
    ├── genau eine Zeile, nur stdout; nie `stderr` oder Usage-Datei
    ├── Zeile wird vor Plaintext-Adapter abgefangen und nie als Assistant-Text angezeigt
    ├── Erfolg: atomar persistieren, Status waiting
    ├── fehlende ID: Status error, deutsche Ursache
    └── Resume abgelehnt: Status error, deutsche Fehlerhülle + Hermes-Ursache
```

Die vorhandene `SessionView` bleibt Oberfläche für Text, Transkript und Fehler.
Für Hermes zeigt sie beim Status `waiting` den Text **„Wartet auf Eingabe“**.
Sie zeigt weder das Liveness-Banner „Session beendet/nicht steuerbar“ noch den
Reaktivieren-Knopf. Bei `error` bleibt das vorhandene deutsche Fehlerfeld und
die Eingabe sichtbar; eine neue Eingabe darf jedoch keinen neuen Chat unter
dieser Session erzeugen.

### Datenmodell, Schreiber und Lesepfade

Kein MinIO und keine neue Domänentabelle. Der bestehende SQLite-Live-Index
bleibt führend für diese flüchtigen Session-Metadaten. Jupiter ist im echten
PROJ-25-Vertrag single-tenant: `owner` kommt aus JWT-`sub`; es gibt weder
`mandant_id` noch Postgres-RLS. Alle unten genannten Lese- und Schreibpfade
prüfen den bestehenden Owner-Scope serverseitig. Der Browser kann keinen Owner
setzen.

1. **Session** (bestehend)
   - Felder: `session_id`, `owner`, `engine="hermes"`, Modell-/Provider-Snapshot,
     Projektpfad/-name, Status, Fehler, Zeitstempel und `transport="direct"`.
   - **Schreiber/Owner:** `POST /sessions/hermes` erzeugt die Zeile mit
     `waiting`; `SessionManager` schreibt Turn-Status, Fehler und Zeitstempel.
     `owner` wird ausschließlich aus dem JWT abgeleitet.
   - **Lesepfade:** `GET /sessions` für Rail/Kacheln; `GET /sessions/{id}` und
     `WS /sessions/{id}/stream` für Ansicht und Live-Snapshot; jeweils nach
     Owner-Prüfung. `POST /sessions/{id}/input` ist einziger Nutzer-Schreibpfad
     für einen Turn.

2. **Hermes-Conversation-Referenz** (bestehendes nullable
   `hermes_resume_ref`, 1:1 zur Session)
   - Opaque, nicht geratene Hermes-Conversation-ID. Quelle ist ausschließlich
     die einzelne, nach Prozessende vorliegende stdout-Zeile
     `session_id: <nichtleerer-Wert>` von `hermes chat` und `hermes chat --resume`.
     Der Driver akzeptiert nur eine vollständig passende Zeile (optionale
     umgebende Leerzeichen, ein nichtleerer Wert ohne Leerzeichen); null, keine
     oder mehrere passende Zeilen sind ungültig. `null` ist vor dem ersten
     erfolgreichen Turn erlaubt, danach nur bis zum sichtbaren Fehlerzustand.
   - **Schreiber/Owner:** ausschließlich `HermesChatDriver` liefert die exakt
     von Hermes gemeldete ID; `SessionManager` schreibt sie zusammen mit dem
     erfolgreichen Turn-Übergang nach `waiting`. Kein Client-Endpoint schreibt
     dieses Feld.
   - **Lesepfade:** nur über die berechtigte Session in internem Resume,
     `GET /sessions/{id}` und WS-Snapshot; nie als separate Liste oder
     Browser-Eingabe. Nach Backend-Neustart liest nur der Manager sie aus dem
     Session-Index, bevor die nächste Eingabe einen Resume-Turn auslöst.

3. **UI-Transkript** (bestehendes `session_transcript`, 1:1 zur Session)
   - Einträge: Rolle, Text, Zeit. Es bleibt Anzeigehistorie, nicht Quelle für
     Hermes-Kontext und wird nicht zum Prompt-Replay verwendet.
   - **Schreiber/Owner:** `SessionManager` übernimmt Benutzertext und
     Hermes-Assistant-Ausgabe über die vorhandenen Stream-Ereignisse und
     persistiert nur vollständige/zulässige Zustandswechsel.
   - **Lesepfade:** `GET /sessions/{id}`, `GET /sessions/{id}/transcript` und
     WS-Snapshot nach Owner-Prüfung. Die SessionView liest zuerst Detail bzw.
     Snapshot, bevor sie weitere Eingaben zeigt.

4. **Hermes-Modelloptionen** (kein persistiertes Objekt)
   - Die bestehende Registry/Resolver-Leseseite bleibt unverändert.
   - **Schreiber/Owner:** Engine-Settings-Verwaltung schreibt Registry/Profile;
     PROJ-86 schreibt nichts daran.
   - **Lesepfad:** `GET /sessions/hermes/options` vor der Modellauswahl im
     Startdialog; `POST /sessions/hermes` validiert dieselbe Auswahl erneut.

### API- und Fehlervertrag

Alle bestehenden Session-Endpunkte verlangen JWT und nutzen Owner-Scope. Es
kommen keine öffentlichen neuen Endpunkte hinzu.

- `POST /sessions/hermes` bleibt 201-Startvertrag mit Titel, Projektpfad,
  Registry-Engine und Modell. Es legt eine Hermes-Session ohne künstlichen
  Prompt, ohne Prozess und mit `status="waiting"`, `transport="direct"` an.
  Rückgabe ist der normale `SessionRead`-Snapshot.
- `POST /sessions/{id}/input` bleibt 202 bei angenommener nichtleerer Eingabe.
  Whitespace-only wird serverseitig mit 422 und deutscher Meldung abgewiesen;
  es entsteht weder Prozess noch Transkriptzeile. Eine parallele Eingabe während
  `running` bleibt 409 mit bestehender Busy-Meldung.
- Für eine Hermes-Session mit `hermes_resume_ref` startet derselbe Endpoint den
  Resume-Turn. Fehlt die Referenz nach einem Turn oder lehnt Hermes Resume ab,
  setzt der Manager `status="error"`, persistiert eine deutsche Fehlerhülle mit
  unverfälschter Hermes-Ursache und liefert den Fehler sichtbar zurück. Kein
  Fallback auf einen Erstturn, keine automatische Wiederholung.
- `GET /sessions`, `GET /sessions/{id}` und `WS /sessions/{id}/stream` bleiben
  additive Read-Verträge. Nach jedem erfolgreichen Turn zeigen sie
  `status="waiting"`; bei Fehler `status="error"` samt Meldung.
- `POST /sessions/{id}/reanimate` bleibt für Nicht-Hermes unverändert. Für
  Hermes wird er serverseitig nicht als Resume-Mechanismus verwendet und liefert
  409 mit deutscher Erklärung statt einen Prozess zu erzeugen.

### Neustart, Liveness und Atomizität

- **Zwischen Turns:** Rehydrate baut für eine ruhende Hermes-Session nur einen
  direkten, vorbereiteten Driver mit gespeicherter Conversation-ID (oder einen
  noch referenzlosen Erststart) und behält `waiting`. Kein Drain-Auto-Resume,
  kein Prozess und kein tmux-Check.
- **Während eines Turns:** Ein Backend-Neustart markiert die Session als
  unterbrochen/`error` mit deutscher Meldung. Der unvollständige Turn wird nicht
  als Erfolg, neue Conversation oder fortsetzbare Wartestellung ausgegeben.
- **Liveness:** `SessionManager.evaluate_liveness_once()` erhält als erste
  Anweisung der Runtime-Schleife bei `manager.py:2218` das konkrete
  Engine-Gate `if runtime.state.engine == "hermes": continue`, vor
  `derive_liveness()` und vor jedem Auto-Resume. `auto_resume_drained()`
  erhält beim Durchlauf seiner Drain-Kandidaten dasselbe Gate, vor
  `_resume()`. Damit sind sowohl Poller- als auch Drain-Auto-Reanimation für
  Hermes ausgeschlossen; Nicht-Hermes durchläuft unverändert den bestehenden
  Pfad. `SessionManager.reanimate()` weist Hermes vor seiner bisherigen
  Liveness-/Slot-Prüfung mit 409 ab. Für ruhendes `waiting` ist der direkte,
  vorbereitete Resume-Driver gesund, nicht „tot“.
- **Atomizität:** Erst wenn Hermes Turn-Erfolg und eine gültige Conversation-ID
  geliefert hat, schreibt der Manager Referenz, Status `waiting`, Fehler-Löschung
  und Zeitstempel in einem Session-Index-Commit. Der Driver bewertet die
  Kontrollzeile erst nach stdout-EOF/Prozessende, aber vor der bestehenden
  Turn-Ende-Entscheidung. Das UI-Transkript bleibt der bestehende getrennte
  Best-effort-Snapshot und ist nie Resume-Quelle. Fehlt die ID oder ist die
  stdout-Kontrollzeile nicht eindeutig lesbar, bleibt keine scheinbar
  erfolgreiche Wartestellung zurück: Status wird `error`.

### Entscheidungen und ADRs

- **ADR-86-1 — `hermes chat`, nicht `-z`: angenommen.** `-z` ist laut CLI ein
  One-shot-Modus; `hermes chat --resume <ID>` ist der dokumentierte echte
  Conversation-Resume-Vertrag. Das verhindert pro Turn neue Unterhaltungen.
- **ADR-86-2 — `waiting` ist erfolgreicher Hermes-Turnabschluss: angenommen.**
  Ein direkter Chat-Prozess endet nach einem Turn absichtlich. Der UX-Zustand
  muss daher fortsetzbare Eingabe statt „beendet“ sein.
- **ADR-86-3 — Hermes immer `direct`: angenommen.** Nur ein Prozessmodell
  vermeidet tmux-Reanimation, Pane-Liveness und deren widersprüchliche Status.
  Das eng begrenzte Engine-Gate schützt alle anderen Engines vor Regressionen.
- **ADR-86-4 — Kein Kontext-Fallback: angenommen.** Fehlende oder abgelehnte
  Hermes-ID ist ein sichtbarer Fehler. Ein verdeckt frischer Chat wäre ein
  Daten-/Kontextverlust unter derselben Jupiter-Session.
- **ADR-86-5 — Bestehender Owner-Scope: angenommen.** Diese Änderung erweitert
  keine Persistenzplattform. Sie folgt PROJ-25: SQLite + JWT-`sub` +
  Service-Scoping, nicht einem nicht vorhandenen Mandanten-/Postgres-RLS-Modell.
- **ADR-86-6 — stdout-Kontrollzeile ist einziger ID-Kanal: angenommen.**
  `hermes chat` gibt die ID als `session_id: <ID>` auf stdout aus; `--usage-file`
  ist dort nicht verfügbar. Der Driver akzeptiert pro Turn exakt eine vollständige
  Kontrollzeile, entfernt sie vor der Anzeige und verwirft fehlende/mehrdeutige
  Ausgabe sichtbar. Das verhindert, dass Diagnose- oder Assistant-Text als
  Resume-ID persistiert wird.

### Lieferreihenfolge und Tests

1. Backend: `HermesChatDriver`, `SessionManager`, Rehydrate/Liveness und
   Session-Schema auf den direkten Hermes-Chat-Vertrag begrenzen.
2. Frontend: SessionView/Kachel für Hermes-`waiting`, Fehler und ausgeblendete
   Reanimation verfeinern; Startdialog/Session-Rail wiederverwenden.
3. Tests: leerer Erststart ohne Prozess; Whitespace; Erstturn; drei Folge-Turns
   mit exakt derselben Conversation-ID; je ein `session_id:`-Kontrollzeilen-Test
   für Erst- und Resume-Turn; fehlende, doppelte oder nur auf `stderr` liegende
   ID; Ausschluss der Kontrollzeile aus Assistant-Text; abgelehntes Resume;
   Neustart zwischen Turns; unterbrochener Turn; parallele Eingabe; Hermes-Skip
   im Liveness-Poller; manuelles Hermes-Reanimate-409; und ein
   Nicht-Hermes-Tmux-/Reanimations-Regressionstest.

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-22 · **Verdict:** Nacharbeit eingearbeitet — erneute Review erforderlich

### Checklist
- [x] Komponenten/Zustandsfluss — plausibel, deckt Erststart/Resume/Fehler ab.
- [x] Datenmodell/Schreiber/Lesepfade — alle 4 Entitäten mit Owner + Lesepfad belegt (Session, `hermes_resume_ref`, Transkript, Modelloptionen). Owner-Check + Lesepfad-Check bestanden.
- [x] Endpunkte — alle 7 existieren bereits (routes/sessions.py:88,115,125,152,162,219,391), kein Neubau nötig.
- [x] **Liveness-Gate präzisiert.** Die Nacharbeit legt das Gate als erste Anweisung in der Runtime-Schleife von `evaluate_liveness_once()` fest: `if runtime.state.engine == "hermes": continue`, vor `derive_liveness()` und vor `_auto_reanimate`; `auto_resume_drained()` erhält dasselbe Gate vor `_resume()`. Damit bleibt der generische Pfad für Nicht-Hermes unverändert.
- [x] **Conversation-ID-Extraktion präzisiert.** Der direkte `hermes chat`-Vertrag nutzt ausschließlich eine vollständige stdout-Kontrollzeile `session_id: <opaque-id>`; `stderr` und `--usage-file` sind ausgeschlossen. Pro Turn ist genau eine solche Zeile zulässig, sie wird vor dem Plaintext-Adapter entfernt und zusammen mit dem Übergang nach `waiting` atomar persistiert.
- [x] ADRs — technisch konsistent mit obigen zwei Punkten als offene Ergänzung.
- [x] Non-Hermes unverändert — Design berührt nur `engine=="hermes"`-Zweige, keine Änderung an generischem Pfad behauptet außer Punkt 1 oben.

### Nicht autonom behoben
Beide offene Punkte sind Technik-Detailentscheidungen für die Umsetzung (welche Codezeile gated, welcher Extraktionskanal), keine reinen Lückenfüller ohne Entscheidung — zurück an `jupiter-architecture` zur Präzisierung:
1. Konkrete Gate-Stelle in `evaluate_liveness_once()`/`_auto_reanimate` für `engine=="hermes"` benennen.
2. Extraktionsmechanismus der Hermes-Conversation-ID aus `hermes chat`/`--resume`-Ausgabe festlegen (Kanal + Parsing-Vertrag), da `--usage-file` beim `chat`-Subcommand laut `hermes chat --help` nicht existiert.

## Implementation Notes (Backend)

**Implementiert:** 2026-08-22 — Backend-Teil (Schritt 1 der Lieferreihenfolge). Frontend (Schritt 2) und QA (Schritt 3) ausstehend.

### Geänderte Stellen
- `backend/app/engine/hermes_chat_driver.py` — vollständig auf den `hermes chat -q <text> --cli -Q`-Vertrag umgestellt. Erster Turn ohne `--resume`, Folge-Turn mit `--resume <hermes_resume_ref>`. Conversation-ID wird aus genau EINER stdout-Kontrollzeile `session_id: <id>` gezogen (`_intercept_line`, bevor der plaintext-Adapter läuft) — nie als Assistant-Text gezeigt. Fehlt die Zeile/ist sie mehrdeutig/lehnt Hermes Resume ab → `system/error` (deutsch + Hermes-Ursache aus stderr), KEIN stiller neuer Chat. Hermes ist immer `transport="direct"` (`supports_self_resume=True` → Manager löst keinen generischen Resume aus).
- `backend/app/engine/generic_cli_driver.py` — zwei Hooks ergänzt: `_intercept_line(line)` (Control-Zeile abfangen) und `_suppress_terminal_error(rc)` (eigenes Fehler-Event des Treibers respektieren).
- `backend/app/engine/manager.py`:
  - `create_hermes()` startet mit **leerem** Initial-Prompt und `transport="direct"` → Session entsteht als `waiting` OHNE Prozess/Platzhalter-Prompt.
  - `send_input()` schaltet nur noch auf `running`, wenn der Treiber tatsächlich noch lebt (Hermes-One-Shot kehrt bereits als `waiting` zurück).
  - `_persist()` übernimmt die Treiber-Resume-ID IMMER an `state.hermes_resume_ref` (auch bei Null-Repo in Tests).
  - `evaluate_liveness_once()` / `auto_resume_drained()` / `reanimate()`: Hermes-Gate `engine == "hermes"` → keine Auto-Reanimation, kein tmux-Drain-Resume, `reanimate()` liefert 409.
  - `rehydrate()`: eine ruhende Hermes-Session wird nach Restart NICHT als verwaist/ERROR geführt, sondern mit vorbereitetem Driver + gespeicherter Ref fortsetzbar gehalten.
- `backend/app/routes/sessions.py` — `POST /sessions/{id}/input` lehnt leere/Whitespace-Eingabe bei Hermes-Sessions mit **422** ab (kein Prozess, kein Transkripteintrag).

### Tests
- `backend/tests/test_proj85_hermes.py` + `test_proj85_hermes_chat_driver.py` — Start ohne Prozess, Whitespace→422, Erst-/Folge-Turn mit stablem Ref, fehlende/doppelte/stderr-ID→Fehler, abgelehntes Resume, Liveness-Skip, Reanimate-409. Alle 24 grün; Manager/Liveness/Rehydrate-Regressionen (77 Tests) unverändert grün.

## QA Test Results

**Tested:** 2026-08-22  
**Backend:** gezielte pytest-Integrationstests (Fake-Hermes; keine produktiven Hermes-Credentials)  
**Frontend:** Quellprüfung; Browser-E2E nicht ausführbar, da kein lokaler App-Start mit Hermes-Credentials vorlag  
**Tester:** QA Engineer (AI)

### Acceptance Criteria Status

- [x] AC 1–10, 12–13: durch `test_proj85_hermes.py`, `test_proj85_hermes_chat_driver.py` und Quellprüfung abgedeckt (Start ohne Prompt/Prozess, Whitespace-422, direkter `hermes chat`, Kontrollzeile, Resume-Fehler, Liveness-/tmux-Ausschluss, UI-Hinweis/Reanimate-Ausblendung, Nicht-Hermes-Regression).
- [ ] AC 11: Backend-Neustart setzt die gewählte Hermes-Provider-Invocation nicht fort; siehe BUG-2.
- [ ] AC 14: die geforderten Neustarttests fehlen; zusätzlich verletzt ein Neustart während eines laufenden Hermes-Turns den Edge-Case, siehe BUG-1.

### Edge Cases Status

- [x] Leere Eingabe, fehlende/doppelte/stderr-only Conversation-ID, abgelehntes Resume und paralleler Turn sind gezielt getestet.
- [ ] Laufender Hermes-Turn beim Backend-Neustart wird als fortsetzbares `waiting` rehydriert statt sichtbar als unterbrochenes `error` markiert (BUG-1).
- [ ] Ruhe zwischen Turns mit nicht-Anthropic Provider verliert beim Rehydrate den Provider (BUG-2).

### Security Audit Results

- [x] Owner-Scope: alle Session-Lese-/Schreibendpunkte nutzen `_owned_or_404`; `owner` stammt aus dem JWT-Sub.
- [x] Eingabevalidierung: leere Hermes-Eingaben werden serverseitig mit 422 abgewiesen; Conversation-ID ist kein Client-Feld.
- [x] XSS/Secrets: SessionView rendert Text als React-Text, ohne HTML-Injection; die CLI-ID wird nicht angezeigt.
- [x] Auth-Ratelimits: Login 5/min, Refresh 30/min konfiguriert.
- [ ] Produktiver JWT-/Cross-Owner- und realer Hermes-CLI-Test nicht ausgeführt (keine Testidentitäten bzw. Hermes-Credentials).

### Automated Tests

- [x] Backend gezielt: **40 passed** — `test_proj85_hermes.py`, `test_proj85_hermes_chat_driver.py`, `test_proj63_manager_transport.py`, `test_proj74_tmux_liveness_rehydrate.py`.
- [ ] Vollständige Backend-Suite: bei ca. 16 % abgebrochen, da ein bereits laufender Alt-Test CPU-intensiv nicht abschloss; kein PROJ-86-Testfehler beobachtet.
- [ ] Frontend: **198 passed, 7 failed** — bestehende Gantt-/Koordinator-Erwartungen (`status.test.ts`, `gantt-chart.test.tsx`, `feature-run-view.test.tsx`), nicht durch PROJ-86 ausgelöst, aber vor Release zu bereinigen.

### Bugs Found

#### BUG-1: Laufender Hermes-Turn wird nach Backend-Neustart fälschlich fortsetzbar
- **Severity:** High
- **Steps to Reproduce:** Hermes-Session starten, während eines direkten Turns das Backend neu starten, anschließend die Session lesen.
- **Expected:** Status `error` mit deutscher Unterbrechungsnachricht; kein erfolgreicher/fortsetzbarer Turn.
- **Actual:** `rehydrate()` behandelt für Hermes alle `ACTIVE_STATES` gleich und erhält auch `running` als fortsetzbaren Runtime-Eintrag.
- **Priority:** Fix before deployment.

#### BUG-2: Rehydrate verliert den ursprünglich gewählten Hermes-Provider
- **Severity:** High
- **Steps to Reproduce:** Hermes-Session über ein nicht-Claude Registry-Modell (z. B. Codex/OpenAI) starten, erfolgreichen Turn abwarten, Backend neu starten und nächste Eingabe senden.
- **Expected:** Resume mit derselben Provider-/Modell-Invocation wie beim Erstturn.
- **Actual:** `hermes_invocation` ist nur flüchtig; Rehydrate baut den Driver ohne persistierten Provider und fällt auf `profile.auth_env or "anthropic"` zurück.
- **Priority:** Fix before deployment.

#### BUG-3: Frontend-Testsuite ist nicht grün
- **Severity:** High
- **Steps to Reproduce:** In `nextjs_app` `npm test` ausführen.
- **Expected:** Vollständige Suite grün.
- **Actual:** 7 Fehler in Gantt-/Koordinator-Tests.
- **Priority:** Fix before deployment.

### Summary

- **Acceptance Criteria:** 11/14 verifiziert; 2 fehlgeschlagen, 1 wegen fehlender Neustartabdeckung nicht verifiziert.
- **Bugs Found:** 3 total (0 Critical, 3 High, 0 Medium, 0 Low).
- **Security:** Kein bestätigter Sicherheitsfehler; produktiver Auth-/CLI-Test ausstehend.
- **Production Ready:** **NO**.
- **Recommendation:** High-Bugs zuerst beheben, dann `/abc-qa` erneut ausführen.

## QA Re-verification

**Re-tested:** 2026-08-22

- [x] BUG-1 fixed: nur Hermes-`waiting` wird nach Restart fortsetzbar rehydriert; ein laufender Turn wird sichtbar als unterbrochenes `error` gespeichert.
- [x] BUG-2 fixed: der Hermes-Provider wird zusammen mit Resume-Referenz persistiert und beim Rehydrate wieder an den direkten Driver gegeben.
- [x] BUG-3 fixed: Frontend-Erwartungen spiegeln die kanonische neunphasige ABC-Reihenfolge und die Schwarm-Begriffe.
- [x] Backend: **42 passed** (PROJ-86 + Transport-/Rehydrate-Regressionen).
- [x] Frontend: **205 passed**.

## QA Re-verification 2

**Re-tested:** 2026-08-22

- [x] AC 1–14: gezielte Backend-, Rehydrate-, Nicht-Hermes-Transport- sowie Auth-/Owner-Regressionstests bestätigen den Vertrag; insbesondere Provider-Persistenz und der unterbrochene laufende Turn nach Backend-Neustart.
- [x] BUG-1 bis BUG-3: verifiziert behoben.
- [x] Security: Auth-/Owner-Regressionen **33 passed**; kein bestätigter Auth-, Owner- oder Injection-Befund.
- [x] Backend gezielt: **75 passed** (1 externe TestClient-Deprecation-Warnung).
- [x] Frontend: **205 passed**.
- [ ] Vollständige Backend-Suite: reproduzierbar nach ca. 10 % CPU-intensiv ohne Abschluss; für ein Release muss dieser Suite-Blocker separat geklärt werden.

### Re-QA Summary

- **Feature-Bugs:** 0 offen.
- **Production Ready:** **NO** — vollständige Backend-Regression noch nicht abschließbar.
- **Recommendation:** Suite-Blocker untersuchen, dann `/abc-qa 86` einmal abschließend wiederholen.

## Deployment
_To be added by /abc-deploy_
