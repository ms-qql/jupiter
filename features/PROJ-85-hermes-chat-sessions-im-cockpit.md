# PROJ-85: Hermes-Chat-Sessions im Cockpit

## Status: In Progress
**Created:** 2026-08-22
**Last Updated:** 2026-08-22

## Dependencies
- Requires: PROJ-3 (Cockpit: Mission Control + Kanban + Ampel-Kacheln) — Hermes-Sessions nutzen dieselbe Sidebar, Aktive Sessions und Session-Ansicht.
- Requires: PROJ-18 (Weitere Engines + iFrame/Launch) — Hermes wird als steuerbare Session-Engine integriert, nicht als weitere eingebettete App.
- Requires: PROJ-51 (Engine- und Modellverwaltung) — die im Startdialog auswählbaren Modelle stammen aus der bestehenden Engine-Registry.
- Requires: PROJ-56 (Kontext-Persistenz & Resume für Nicht-Claude-Engines) — Hermes-Sessions müssen nach Restart fortsetzbar bleiben.
- Reuses: PROJ-83 (Modellwahl pro Hermes-Profil) — dessen zentrale Registry-zu-Hermes-Modellübersetzung wird wiederverwendet, aber die Wahl gilt hier **pro Session**, nicht profilweit.
- Reuses: PROJ-73 (Token Savings) — für Hermes-Starts immer aktiviert und nicht im Dialog angezeigt.

## Beschreibung

Neben dem bestehenden Knopf **„Neu“** gibt es in der Jupiter-Sidebar den Knopf **„Neu Hermes“**. Er öffnet einen auf Hermes zugeschnittenen Startdialog. Der Nutzer kann einen Titel, Projektpfad und ein Modell wählen und startet damit eine Hermes-Chat-Session.

Eine Hermes-Session erscheint und verhält sich im Cockpit wie eine bisherige Session: Sie ist unter **„Aktive Sessions“** sichtbar, lässt sich neben anderen Standard- und Hermes-Sessions öffnen und fortführen und nutzt dieselbe Chat-Ansicht sowie dieselben Statuszustände. Die Hermes-spezifische Ausführung verwaltet Hermes selbst.

Der Dialog startet Hermes immer im **Bypass-Modus** und mit aktiviertem **Token Savings**; beide Festwerte werden nicht angezeigt und sind dort nicht veränderbar. Die Modellwahl wird für genau diese neue Hermes-Session in das Hermes-Modellformat übersetzt. Sie verändert weder andere laufende Hermes-Sessions noch die bestehenden `jupiter-*`-Hermes-Profile.

In der Session-Ansicht zeigt Jupiter zusätzlich den Hermes-Kontextverbrauch als absolute Werte und als Fortschrittsbalken, z. B. `18.600 / 256.000 Token · 7 %`, sobald Hermes diese Werte liefert.

## User Stories

- Als Nutzer möchte ich neben **„Neu“** den Knopf **„Neu Hermes“** sehen, damit ich gezielt einen Hermes-Chat starten kann.
- Als Nutzer möchte ich beim Start Titel, Projektpfad und Modell wählen, damit die Hermes-Session zum jeweiligen Vorhaben passt.
- Als Nutzer möchte ich mehrere Hermes-Sessions parallel zu Standard-Sessions unter **„Aktive Sessions“** sehen und öffnen, damit ich ohne Toolwechsel arbeiten kann.
- Als Nutzer möchte ich den Kontextverbrauch meiner Hermes-Session in Token und als Balken sehen, damit ich vor dem Kontextlimit reagieren kann.
- Als Nutzer möchte ich eine Hermes-Session nach einer Unterbrechung fortführen, damit ihr Gesprächskontext erhalten bleibt.

## Acceptance Criteria

- [ ] In der Sidebar steht direkt neben dem bestehenden Knopf **„Neu“** ein gleichwertig erreichbarer Knopf **„Neu Hermes“**.
- [ ] **„Neu Hermes“** öffnet einen Dialog mit den Feldern **Titel** (optional), **Projekt-Pfad** (erforderlich) und **Modell** (erforderlich); alle sichtbaren Texte und Fehlermeldungen sind deutsch.
- [ ] Die Modellliste enthält nur für Hermes unterstützte, aktuell verfügbare Modelle aus der bestehenden Engine-Registry. Eine ungültige oder nicht verfügbare Kombination kann nicht gestartet werden.
- [ ] Beim Start wird die gewählte Modellbezeichnung über die vorhandene Hermes-Übersetzung in eine Hermes-kompatible Modellkonfiguration für **diese Session** aufgelöst.
- [ ] Der Start einer Hermes-Session verändert kein bestehendes `jupiter-*`-Hermes-Profil und keine bereits gestartete Hermes-Session.
- [ ] Jede Hermes-Session startet fest im **Bypass-Modus** und mit **Token Savings aktiviert**. Beide Werte sind nicht Teil des Hermes-Startdialogs und können dort nicht geändert werden.
- [ ] Nach erfolgreichem Start erscheint die Session ohne manuelles Neuladen unter **„Aktive Sessions“**, trägt den eingegebenen Titel (sonst den abgeleiteten Projektnamen) und öffnet sich im bekannten Session-Hauptbereich.
- [ ] Mehrere Hermes-Sessions können gleichzeitig mit Standard-Sessions existieren, einzeln geöffnet werden und ihre Nachrichten bleiben jeweils ihrer eigenen Session zugeordnet.
- [ ] Die Hermes-Chat-Ansicht nutzt das bestehende Jupiter-Look-and-Feel für Nachrichten, Eingabe, Status und Session-Navigation; Hermes erhält keine separate Cockpit-Ansicht.
- [ ] Wenn Hermes Kontextverbrauch und Kontextfenster meldet, zeigt die Session-Ansicht die absoluten Werte `verbraucht / Fenster` sowie einen proportionalen, zugänglichen Fortschrittsbalken mit Prozentwert.
- [ ] Der Kontextbalken aktualisiert sich mit neuen Hermes-Usage-Daten und überschreitet visuell nie 100 %.
- [ ] Liefert Hermes keine Kontextwerte, zeigt Jupiter einen klaren deutschen Nichtverfügbarkeits-Hinweis statt erfundener Zahlen oder eines irreführenden Balkens.
- [ ] Eine Hermes-Session bleibt nach Backend-Neustart im Session-Index sichtbar und kann über den vorhandenen Resume-Mechanismus mit ihrem Hermes-Kontext fortgesetzt werden, sofern Hermes eine Resume-Referenz bereitstellt.

## Edge Cases

- **Hermes nicht verfügbar oder Start schlägt fehl:** Es wird keine scheinbar aktive Session erzeugt; der Dialog zeigt eine verständliche Fehlermeldung und bleibt für eine Korrektur geöffnet.
- **Modell ist nach Öffnen des Dialogs nicht mehr verfügbar:** Der Start wird abgelehnt und die Modellliste wird aktualisiert; bereits laufende Sessions bleiben unbeeinflusst.
- **Leerer Titel:** Jupiter verwendet den bestehenden abgeleiteten Projektnamen; der Projektpfad bleibt trotzdem Pflicht.
- **Gleicher Titel oder gleicher Projektpfad mehrfach:** Mehrere Hermes-Sessions sind erlaubt und bleiben über ihre Session-ID getrennt.
- **Hermes meldet nur verbrauchte Tokens, aber kein Kontextfenster:** Der absolute Verbrauch darf gezeigt werden; Balken und Prozentwert werden als nicht verfügbar markiert.
- **Verbrauch größer als gemeldetes Fenster:** Jupiter zeigt den absoluten Wert unverfälscht und begrenzt ausschließlich die Balkendarstellung auf 100 %.
- **Resume-Referenz fehlt oder Hermes lehnt Resume ab:** Jupiter meldet den fehlenden Kontext klar und startet nicht stillschweigend eine neue Unterhaltung im Namen der bestehenden Session.

## Non-Goals

- Keine Änderung des bestehenden eingebetteten Hermes-Dashboards oder Hermes-Kanbans (PROJ-81/82).
- Keine globale Änderung der `jupiter-*`-Hermes-Profile durch den „Neu Hermes“-Dialog.
- Keine Sichtbarkeit oder Konfiguration von Bypass-Modus oder Token Savings im Dialog.
- Keine eigene Hermes-spezifische Sidebar, kein separates Chat-Design und keine Synchronisation mit außerhalb von Jupiter gestarteten Hermes-Sessions.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-22 · **Stack:** Next.js/shadcn + FastAPI + raw SQL/SQLite mit Owner-Service-Scoping; Hermes CLI; Dokploy · **Branch:** main

### Ausgangslage und Ziel

Jupiter hat bereits eine engine-agnostische Session-Hülle: `POST /sessions`,
`GET /sessions`, Detailansicht, WebSocket-Snapshot, Active-Session-Liste und
Resume laufen für alle Engines. Die vorhandene Registry enthält zwar einen
deaktivierten `hermes`-Eintrag, dessen One-shot-Aufruf und plaintext-Adapter
decken Chat, Usage und Resume jedoch nicht ab. PROJ-85 ergänzt deshalb eine
kleine, echte Hermes-Session-Integration; es baut keine zweite Chat-Anwendung
und verändert keine `jupiter-*`-Profile.

**Bestehender Sicherheitsvertrag, bewusst beibehalten:** Die aktuelle
Session-Persistenz ist ein lokaler SQLite-Live-Index mit Owner-Filter. Jupiter
ist single-tenant: Es gibt kein `mandant_id` und keine Postgres-RLS-Policy.
Der `owner` stammt ausschließlich aus dem JWT (`sub`, Nutzer-ID); jeder
Lese- und Schreibpfad nutzt ihn serverseitig. Ein Request darf `owner` nicht
als Payload bestimmen; unbekannte oder fremde Session-IDs bleiben nicht
sichtbar. PROJ-85 erweitert diesen bestehenden Owner-Scope, ohne den
SQLite-Speichervertrag oder Alt-Daten zu migrieren.

### A) Komponenten und Ablauf

```
SessionRail
├── bestehender Button „Neu“
└── Button „Neu Hermes“
    └── HermesStartDialog
        ├── Titel (optional)
        ├── Projekt-Pfad (Pflicht)
        └── Modell (Pflicht; verfügbare Hermes-Modelle)

HermesStartDialog
└── POST /sessions/hermes
    ├── Registry- und Hermes-Kompatibilitätsprüfung
    ├── reine Modellübersetzung für diese Session
    ├── HermesChatDriver (Start, Stream, Usage, Resume-Referenz)
    └── bestehender SessionManager / Session-Index

Aktive Sessions / SessionRail
└── bestehende Session-Kachel mit Engine-Badge „Hermes"

bestehende SessionView
└── HermesContextUsage
    ├── „18.600 / 256.000 Token · 7 %"
    ├── zugänglicher Fortschrittsbalken (visuell höchstens 100 %)
    └── deutscher Nichtverfügbarkeits-Hinweis
```

Der neue Button steht unmittelbar beim bestehenden Startknopf und nutzt dessen
Dialog-, Toast-, Refresh- und Navigation-Muster. Nach erfolgreichem 201-Start
aktualisiert der vorhandene `SessionsProvider` die Liste und öffnet dieselbe
`SessionView`. Nachrichten, Status, Stop, Reanimation und WebSocket-Resync
bleiben bewusst die bestehenden, engine-agnostischen Wege.

### B) Datenmodell und Besitz

Keine MinIO-Objekte: Das Feature speichert keine Dateien. Die folgenden
Entitäten liegen im bestehenden SQLite-Session-Speicher; ihre Zuordnung und
Sichtbarkeit werden durch den bestehenden Owner-Scope in der Service-Schicht
erzwungen.

1. **Session** (bestehend, erweitert)
   - Bestehend: `session_id`, `owner`, `project_path`, `project_name`,
     `engine`, `model`, `permission_mode`, Status, Zeitstempel,
     Transkript-/Resume-Verweise und Savings-Snapshot. Die bestehende
     `owner`-Zuordnung bleibt unverändert.
   - Für Hermes: `engine = "hermes"`; `permission_mode =
     "bypassPermissions"`; `savings_enabled = true`; der serverseitig
     aufgelöste, nicht geheime Modell-/Provider-Snapshot sowie
     `hermes_resume_ref` (nullable, opaque Text). Keine globale
     `config.yaml`-Mutation und kein Secret im Datensatz.
   - **Schreiber/Owner:** ausschließlich `POST /sessions/hermes` erzeugt die
     Hermes-Felder; SessionManager aktualisiert Status, Snapshot,
     `hermes_resume_ref` und Savings-Snapshot aus Hermes-Ereignissen.
     `owner` stempelt der Auth-Kontext aus dem JWT, nie der Browser.
   - **Lesepfade:** `GET /sessions` für Aktive Sessions; `GET /sessions/{id}`
     und `WS /sessions/{id}/stream` für Detail/Live; bestehendes Resume über
     `POST /sessions/{id}/input` und Reanimation. Jeder Pfad verlangt JWT und
     prüft den Owner-Scope vor dem Lesen.

2. **Hermes-Kontext-Snapshot** (1:1 zur Session, klein und ersetzbar; eigene
   Tabelle oder gleichwertige Session-Spalten, nicht ein zweiter Chat-Store)
   - `session_id`, `used_tokens` nullable, `window_tokens` nullable,
     `reported_at`. Prozent werden nur ab beiden positiven Werten
     berechnet; Anzeige-Prozent wird auf 100 begrenzt, Rohwerte nie verfälscht.
   - **Schreiber/Owner:** nur HermesChatDriver über den SessionManager, wenn
     Hermes Usage liefert. Kein Client-Schreibendpoint.
   - **Lesepfade:** nur mit der berechtigten Session in `GET /sessions/{id}`
     und dessen WebSocket-State-Snapshot; `GET /sessions` erhält nur die für
     Kachel/Active-Session nötigen abgeleiteten Felder. Der SessionManager
     setzt denselben Owner-Scope wie für die zugehörige Session durch.

3. **Hermes-Modell-Kompatibilität** (kein persistiertes Domänenobjekt)
   - Zur Laufzeit aus der bestehenden Engine-Registry plus einer zentralen,
     reinen Hermes-Übersetzung abgeleitet. Sie liefert nur aktuell verfügbare,
     von Hermes abbildbare Kombinationen. PROJ-83s bestehende
     Hin-/Rückübersetzung wird als Vorlage/Shared Resolver wiederverwendet,
     aber der Schreibpfad `PATCH /settings/hermes-profiles` ist ausdrücklich
     nicht beteiligt.
   - **Schreiber/Owner:** Engine-Settings-Verwaltung schreibt die Registry;
     PROJ-85 schreibt sie nie. **Lesepfad:** `GET /sessions/hermes/options`
     vor dem Öffnen/Starten des Dialogs; der Start validiert die Auswahl erneut
     gegen denselben frischen Snapshot.

### C) API-Vertrag

Alle Endpunkte verlangen JWT. Der `owner` wird ausschließlich aus `sub` im
Token abgeleitet; die Service-Schicht erzwingt ihn für jeden Lese- und
Schreibzugriff auf Sessions. Texte/Fehler an das Cockpit sind deutsch.

- `GET /sessions/hermes/options` — liefert ausschließlich verfügbare,
  Hermes-kompatible Registry-Modelle (`engine`, `model`, Anzeigename). Kein
  Schreibzugriff. Das ist der Lesepfad vor der Modellzuweisung.
- `POST /sessions/hermes` — Request: optionaler `title`, erforderlicher
  `project_path`, erforderliche Registry-Modellkombination. Server erzwingt
  Bypass und Token Savings; Browser kann diese Werte weder sehen noch setzen.
  Er löst das Modell nur für die neue Session auf und gibt den normalen
  `SessionRead`-Snapshot mit `engine="hermes"` zurück. Fehler: 400 bei
  ungültigem Pfad/Modell, 409 bei nicht startfähigem Zustand, 503 bei nicht
  verfügbarer Hermes-CLI; bei Fehler wird keine aktive Session persistiert.
- `GET /sessions`, `GET /sessions/{id}`, `WS /sessions/{id}/stream` — bleiben
  Verträge, erhalten additiv `context_used_tokens`, `context_window_tokens`
  und `context_usage_available`. Detail und State-Frames enthalten dieselben
  Werte; fehlende Einzelwerte bleiben `null`, nicht `0`.
- `POST /sessions/{id}/input` und `POST /sessions/{id}/reanimate` — bestehende
  Verträge. Für Hermes nutzt der Manager die persistierte
  `hermes_resume_ref`; fehlt sie oder lehnt Hermes sie ab, antwortet der
  vorhandene Session-Fehlerpfad sichtbar. Er erzeugt nie still eine neue
  Unterhaltung.

`POST /sessions` bleibt für Standard-Engines unverändert. Der getrennte,
schmale Hermes-Startvertrag verhindert, dass ein normaler Client sich als
Hermes ausgibt oder die festgeschriebenen Sicherheits-/Savings-Werte übergibt.

### D) Entscheidungen (und warum)

- **Ein Dialog, eine Session-Hülle:** Bestehende Rails, Kacheln, Stream und
  `SessionView` reduzieren neue UI-Fläche und halten Standard- und
  Hermes-Sessions gleich bedienbar.
- **Per-Session-Konfiguration statt Profiländerung:** Eine reine Resolver-
  Übersetzung wird als Snapshot an den Hermes-Start übergeben. So ändern
  parallele Starts weder laufende Sessions noch `jupiter-*`-Profile.
- **Separate absolute Kontextwerte:** `tokens_used` ist kein verlässliches
  Kontextfenster. Nur von Hermes explizit gemeldete Werte dürfen den Balken
  speisen; dadurch gibt es keine erfundenen Zahlen.
- **Resume als Capability, nicht Versprechen:** Der opaque Hermes-Ref wird nur
  gespeichert, wenn Hermes ihn liefert. Fehlt er, bleibt die Session sichtbar,
  aber Fortsetzen zeigt klar den Fehler statt einen kontextlosen Ersatzchat.
- **Bestehendes Owner-Service-Scoping:** Jupiter ist single-tenant und nutzt
  SQLite ohne DB-RLS. Zentral erzwungener Owner-Scope aus dem JWT schützt
  Session-Reads und -Writes, ohne einen nicht vorhandenen Mandanten- oder
  Postgres-Vertrag einzuführen.
- **Keine neue Abhängigkeit, kein MinIO:** Vorhandene FastAPI-, Registry-,
  SessionManager-, Next.js/shadcn- und WebSocket-Bausteine reichen aus.

### E) Delivery-Reihenfolge und Akzeptanzzuordnung

1. Backend zuerst: Hermes-Options/Resolver, schmaler Startvertrag,
   HermesChatDriver und persistierbarer Resume-/Usage-Snapshot innerhalb des
   bestehenden Owner-Service-Scopes.
   Prüft Modellwechsel zwischen Dialog und Submit sowie fehlenden/abgelehnten
   Resume-Ref.
2. Frontend danach: `Neu Hermes`, deutscher Dialog, Options-Laden,
   Fehlerzustände, Session-Badge und absolute Kontextanzeige. Der vorhandene
   Refresh/Navigation-Flow erfüllt das sofortige Erscheinen unter Aktive
   Sessions.
3. QA: parallele Standard-/Hermes-Sessions, Owner-Isolation,
   Modell-Invalidierung, feste Bypass/Savings-Werte, Usage mit/ohne Fenster,
   Überlauf über 100 %, Backend-Restart und Resume-Ablehnung.

### F) ADRs

- **ADR-85-1 — Dedizierter Hermes-Startendpoint:** angenommen. Er macht die
  nicht veränderbaren Startwerte serverseitig durchsetzbar; das allgemeine
  `POST /sessions` bleibt rückwärtskompatibel.
- **ADR-85-2 — Hermes-Modellwahl ist ein Session-Snapshot:** angenommen. Der
  Resolver teilt die Übersetzungslogik von PROJ-83, schreibt aber niemals
  Profil-YAML.
- **ADR-85-3 — Kontextanzeige nur aus Hermes-Telemetrie:** angenommen. Ohne
  vollständige Meldung ist „nicht verfügbar“ korrekter als eine Schätzung.
- **ADR-85-4 — Owner-Service-Scoping für persistierte Cockpit-Sessions:**
  angenommen. PROJ-85 übernimmt den bestehenden PROJ-25-Vertrag: SQLite,
  single-tenant und serverseitig erzwungener Owner aus JWT-`sub`; kein
  Mandantenfeld und keine Postgres-RLS werden eingeführt.

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-22 (Runde 2) · **Verdict:** Bestanden — Status Architected

### Runde 2 — Nachbesserung verifiziert
Fix-Task t_aac32b54 hat `mandant_id`/Postgres-RLS ersatzlos durch den
bestehenden PROJ-25-Owner-Scope ersetzt. Abschnitt "Ausgangslage und Ziel",
Datenmodell (B), API-Vertrag (C) und ADR-85-4 verweisen jetzt konsistent auf
SQLite + JWT-`sub` + Service-Scoping; verbleibende Erwähnungen von
`mandant_id`/Postgres/RLS im Dokument sind ausschließlich die Blocker-Historie
unten (explizite Negation), keine Design-Behauptung mehr. Kein neuer
Widerspruch zu PROJ-25 gefunden.

### Checklist
- [x] Component structure — ok, nutzt bestehende SessionRail/SessionView/Dialog-Muster.
- [x] Data model — korrigiert: Owner-Scope aus JWT-`sub`, kein Mandant, kein Postgres/RLS.
- [x] API shape — Endpunkte vollständig (GET .../options, POST /sessions/hermes), Owner-/Lesepfad-Check bestanden (siehe unten).
- [x] Tech decisions — ADRs begründet, ADR-85-4 jetzt konsistent mit PROJ-25.
- [x] Dependencies — keine neuen Pakete, korrekt.
- [x] Branch field — vorhanden (main).
- [x] Conflict-free — kein Namenskonflikt; `POST /sessions/hermes` und `GET /sessions/hermes/options` müssen wie `/limits`/`/cleanup` als statische Segmente **vor** `/{session_id}` deklariert werden (bestehendes Muster in `backend/app/routes/sessions.py:92,102`) — im Tech Design nicht erwähnt, aber trivial nachrüstbar.
- [x] Acceptance-criteria coverage — jedes AC hat einen Endpoint/Component-Home.

### Owner-/Lesepfad-Check (bestanden)
- Session: Schreiber `POST /sessions/hermes` + SessionManager (Status/Snapshot); Leser `GET /sessions`, `GET /sessions/{id}`, `WS /sessions/{id}/stream` — alle mit JWT+Owner-Prüfung (`backend/app/routes/sessions.py:44-50,89`). OK.
- Hermes-Kontext-Snapshot: nur HermesChatDriver/SessionManager schreibt, kein Client-Schreibpfad; Lesepfad über Session-Detail/WS. OK.
- Hermes-Modell-Kompatibilität: kein Schreibpfad durch PROJ-85 (Registry bleibt bei Engine-Settings/`PATCH /settings/hermes-profiles`, `backend/app/routes/settings.py:344`); PROJ-85 liest nur via `GET /sessions/hermes/options` vor der Auswahl. OK — Lesepfad vor Schreibpfad korrekt dokumentiert.

### CodeGraph-Cross-Check
- Session-Hülle vollständig vorhanden: `POST /sessions:53`, `GET /sessions:86`, `GET /{id}:113`, `WS /{id}/stream:352`, `POST /{id}/input:123`, `POST /{id}/reanimate:180` (`backend/app/routes/sessions.py`).
- Deaktivierter `hermes`-Eintrag bestätigt: `enabled: false`, `driver: generic_cli`, `adapter: plaintext`, `oneshot: true` (`backend/config/engines.yaml:110-129`) — deckt tatsächlich weder Chat-Stream noch Resume noch Usage ab, Behauptung korrekt.
- PROJ-83-Resolver (`backend/app/engine/hermes_profiles.py`) schreibt ausschließlich `model.provider`/`model.default` in `jupiter-*`-`config.yaml`; PROJ-85 verwendet laut Design nur die Leseseite, PATCH-Endpoint bleibt unberührt — korrekt und verifiziert.
- **`mandant_id`/Postgres/RLS — NICHT vorhanden:**
  - Kein Postgres-Treiber im Repo (`grep postgres|psycopg|asyncpg` → 0 Treffer in `backend/`).
  - Persistenz ist ausschließlich `SqliteSessionIndexRepository` (`backend/app/db/session_index.py:272-287`), Single-Writer, WAL-Modus, host-nativ.
  - JWT-Claims enthalten nur `sub`/`username`/`type` (`backend/app/engine/auth.py:89-107`) — kein `mandant_id`-Feld existiert oder wird ausgegeben.
  - Kein Mandanten-/Tenant-Konzept irgendwo im Backend (`grep mandant|tenant` → 0 Treffer außerhalb von PROJ-85 selbst).
  - **Die bereits deployte PROJ-25-Architektur (`features/PROJ-25-auth-jwt-scope-rls.md:70-71,130`) trifft explizit die Gegenentscheidung:** *"Leitentscheidung: Service-Scoping statt DB-RLS — Jupiter läuft bewusst auf SQLite (Ein-Worker-uvicorn) + Datei-Vault, nicht auf Postgres. Klassische DB-Row-Level-Security-Policies gibt es in SQLite nicht."* Jupiter ist laut dieser Grundsatzentscheidung **single-tenant** — Scope existiert nur als `owner` (Nutzer), nicht als Mandant.

### Autonom behoben
- Statische-Route-vor-`/{session_id}`-Hinweis oben ergänzt (rein technisch, aus bestehendem Muster ableitbar, keine Produktentscheidung).

### Offene Fragen (Blocked)
PROJ-85 Abschnitt "Ausgangslage und Ziel" / Datenmodell (B) / API-Vertrag (C) / ADR-85-4 erfinden einen `mandant_id`+Postgres-RLS-Vertrag, der **weder im Code noch in der etablierten PROJ-25-Stack-Entscheidung existiert**. Das ist keine Fortführung eines bestehenden Musters, sondern eine neue Grundsatzentscheidung, die der deployten PROJ-25-Architektur widerspricht (Service-Scoping statt DB-RLS, SQLite statt Postgres) — ohne Postgres-Migration, DB-Treiber, Migrationstooling oder Aufhebung von PROJ-25 zu planen.

**Frage an /abc-architecture (bzw. Produktentscheidung nötig):**
1. Soll PROJ-85 tatsächlich eine Postgres-Migration für Sessions einleiten (großer, cross-cutting Eingriff, der PROJ-25 und alle Session-Konsumenten betrifft) — dann fehlt dafür ein eigenes ADR/Delivery-Schritt (DB-Treiber, Migrationstooling, Postgres-Verbindung, Umgang mit bestehenden SQLite-Daten)?
2. Oder bleibt PROJ-85 konsistent mit PROJ-25 bei **Service-Scoping auf `owner`** (kein Mandantenkonzept, da Jupiter single-tenant ist) — dann muss Abschnitt "Ausgangslage und Ziel", Datenmodell (B), API-Vertrag (C) und ADR-85-4 den `mandant_id`/Postgres-RLS-Vertrag ersatzlos durch den bestehenden Owner-Scope-Mechanismus ersetzen?

Ohne diese Entscheidung bleibt der Status auf `Architecture Draft`. Nach Klärung: `/abc-review-architecture` erneut laufen lassen.

## QA Test Results
**Getestet:** 2026-08-22 · **Ergebnis: NOT READY** (3 Critical/High-Bugs)

### Akzeptanzkriterien
1. „Neu Hermes"-Knopf neben „Neu" — **PASS** (`session-rail.tsx:128-132`, gleichwertig erreichbar).
2. Dialog mit Titel/Pfad/Modell, deutsche Texte — **PASS** (`hermes-start-dialog.tsx`).
3. Modellliste nur Hermes-kompatibel, ungültige Kombi nicht startbar — **FAIL**, siehe BUG-1: die von `GET /sessions/hermes/options` gelieferte Liste enthält NIE eine Kombination, die `POST /sessions/hermes` akzeptiert.
4. Modellübersetzung serverseitig pro Session — **kann nicht verifiziert werden** (Start schlägt wegen BUG-1/BUG-2 durchgehend fehl).
5. Kein bestehendes Profil verändert — **PASS** (Code-Review: `hermes_resolver.py` ist read-only, kein Schreibpfad berührt).
6. Bypass + Token Savings fest, nicht im Dialog — **PASS strukturell** (Server erzwingt `bypassPermissions`/`savings.enabled=True`, Dialog zeigt/erlaubt beides nicht) — Laufzeit-Beweis blockiert durch BUG-1/2.
7. Session erscheint sofort unter „Aktive Sessions" — **kann nicht verifiziert werden** (Start schlägt fehl, siehe oben).
8. Mehrere Hermes-Sessions parallel zu Standard — **kann nicht verifiziert werden** (kein Start möglich).
9. Gleiches Look-and-Feel wie Standard-Sessions — **PASS** (Code-Review: nutzt bestehende SessionView/Badges).
10. Kontextanzeige absolute Werte + Balken — **PASS strukturell** (`HermesContextUsage`, 3 Zustände korrekt implementiert, Balken ≤100%) — Live-Update aus echtem Hermes-Turn nicht verifizierbar (Start schlägt fehl).
11. Balken überschreitet nie 100% — **PASS** (Unit-Level: `pctUsed()` klemmt korrekt).
12. Kein Verfügbarkeits-Wert → deutscher Hinweis statt Fantasiezahlen — **PASS** (`hermes-context-usage.tsx:33-38`).
13. Resume nach Backend-Neustart — **kann nicht verifiziert werden** (kein Start möglich).

### Gefundene Bugs

**BUG-1 (Critical) — Contract-Mismatch macht Feature komplett unbenutzbar.**
`POST /sessions/hermes` akzeptiert laut `manager.create_hermes()` (backend/app/engine/manager.py:1896-1899) NUR `engine == "hermes"` — jede andere Engine wird mit 400 "Hermes-Sessions können nur mit dem 'hermes'-Engine-Profil starten." abgelehnt. `GET /sessions/hermes/options` (backend/app/engine/hermes_resolver.py:hermes_model_options) listet dagegen ALLE aktivierten `kind=="engine"`-Profile (claude, codex, opencode …) — nicht nur `hermes`. Eigener Testlauf: für JEDE der 22 vom Live-Options-Endpoint gelieferten Kombinationen liefert der Start-Endpoint 400. Kein einziges Options-Item ist tatsächlich startbar. Reproduktion: `GET /sessions/hermes/options` → erstes Element nehmen → `POST /sessions/hermes` mit `{project_path, engine, model}` → 400. Fix-Ort: entweder `hermes_model_options()` auf `prof.key == "hermes"` einschränken (Modelle des `hermes`-Profils, nicht der Ziel-Registry) oder `create_hermes()`/`resolve_hermes_invocation()` so umbauen, dass beliebige Registry-Engines (wie im Tech Design C beschrieben — „Registry-Modellkombination") tatsächlich übersetzt werden. Aktuell widersprechen sich Tech Design (Registry-weit) und Implementierung (nur `hermes`-Profil) — Klärung mit Architektur/Backend nötig.

**BUG-2 (High) — Frontend-Payload fehlt Pflichtfeld `engine`, Backend lehnt mit 422 ab.**
Frontend `HermesStartRequest` (`nextjs_app/lib/types.ts:588`) sendet `{title?, project_path, model}` — kein `engine`. Backend `HermesSessionCreate` (`backend/app/schemas/sessions.py:127-144`) deklariert `engine` als Pflichtfeld ohne Default. Eigener Testlauf mit dem exakten Frontend-Payload gegen den echten Endpunkt: `422 {"detail":[{"type":"missing","loc":["body","engine"],"msg":"Field required"}]}`. Selbst wenn BUG-1 gefixt wird, bleibt der Dialog funktionsunfähig, solange das Frontend kein `engine`-Feld mitschickt (das `HermesModelOption` liefert `engine` mit, wird aber im Dialog-Submit nicht übernommen — `hermes-start-dialog.tsx:117-121`).

**BUG-3 (Medium) — `HermesSessionCreate.extra="forbid"` wirkt nicht (Sicherheitsvertrag ausgehebelt).**
`schemas/sessions.py:156` setzt `HermesSessionCreate.model_config = {"extra": "forbid"}` NACH der Klassendefinition per Zuweisung. Pydantic v2 wertet `model_config` beim Klassenbau aus (`__pydantic_core_schema__`); eine nachträgliche Attribut-Zuweisung ändert die bereits gebaute Core-Schema-Validierung nicht mehr. Eigener Test: `HermesSessionCreate(project_path="/x", engine="hermes", model="m", extra_field="x")` wird klaglos akzeptiert; ebenso akzeptiert der Live-Endpoint `POST /sessions/hermes` mit zusätzlichen `permission_mode`/`token_savings`-Feldern (201 statt der erwarteten 422). ADR-85-1 ("nicht im Payload setzbar") ist damit nicht durchgesetzt — die Felder werden zwar von `create_hermes()` ignoriert (Bypass/Savings bleiben serverseitig hart codiert, kein tatsächlicher Privilegien-Escape verifiziert), aber der dokumentierte Vertragsschutz („ein Client kann sich nicht als Hermes ausgeben") ist technisch nicht wirksam. Fix: `class Config: extra = "forbid"` oder `model_config = {"extra": "forbid"}` als Klassenattribut IN der Klassendefinition setzen, nicht danach zuweisen.

**BUG-4 (Low) — Typ-Inkonsistenz `HermesOptions.warning`.**
Frontend erwartet `warning: string | null` (`types.ts:582`), Backend `HermesOptionsResponse` (`schemas/sessions.py:122-124`) liefert das Feld nie. Kein Laufzeitfehler (JS behandelt `undefined` wie `null` in den Falsy-Checks des Dialogs), aber Typ-Vertrag stimmt nicht — dokumentiert, nicht gefixt (Low).

### Security-Redteam (gegen echten laufenden Endpoint)
- Path-Traversal (`project_path=/etc`) → 400, korrekt abgewiesen. PASS.
- Owner-Override im Payload (`owner: "attacker"`) → wird von Pydantic durchgelassen (BUG-3-Symptom), aber `create_hermes()` liest `owner` nur aus dem Funktionsparameter (JWT-Sub), das Payload-Feld wird nirgends gelesen — kein tatsächlicher Owner-Escape. PASS (funktional sicher trotz BUG-3).
- SQL-Injection-artiger Pfad-String → landet in `validate_project_path()`/SQLite-Parametrisierung, kein Hinweis auf String-Konkatenation gefunden (Code-Review `session_index.py`, raw-SQL mit Platzhaltern). Nicht live exploitierbar getestet (Backend erreichte den DB-Layer wegen BUG-1 nicht), Code-Pfad aber identisch zu bestehenden, bereits geprüften Session-Insert-Pfaden.
- `extra="forbid"`-Bypass (BUG-3) — bestätigt, siehe oben.

### Regression
- Volle Backend-Suite: 1311 passed, 1 xfailed, 6 failed — alle 6 Failures VOR PROJ-85 bereits bestehend und nicht mit Hermes/Sessions verwandt (`test_proj39_orchestration`, `test_proj50_codex_abc` ×4, `test_proj63_tmux_transport`) — bestätigt durch Themenbezug (Codex-Skill-Generator, Orchestration-Config, tmux-Timeout), keine Berührung mit `sessions.py`/`manager.py`-Hermes-Pfaden.
- PROJ-85-eigene Suite: 10/10 grün (aber testet nur mit gefaktem Treiber UND liefert den Widerspruch zwischen Options und Create nicht ab — kein Test kombiniert beide Endpunkte, deshalb blieb BUG-1 in der eigenen Suite unentdeckt).

### Fazit
**NOT READY.** BUG-1 + BUG-2 machen den kompletten „Neu Hermes"-Flow in Produktion unbenutzbar (jeder Start scheitert). BUG-3 untergräbt den dokumentierten Sicherheitsvertrag (ADR-85-1), auch wenn kein direkter Ausnutzungspfad gefunden wurde. Struktur/UI/Kontextanzeige sind sauber implementiert und bestehen Code-Review — sobald der Contract-Mismatch gefixt ist, sollten die übrigen ACs zügig grün laufen.

## Deployment
_To be added by /abc-deploy_
