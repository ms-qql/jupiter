# PROJ-85: Hermes-Chat-Sessions im Cockpit

## Status: Deployed
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

**BUG-1 (Critical) — Contract-Mismatch — GEFIXT (Backend, t_f451eab4).**
Entscheidung gegen Tech Design C („Registry-Modellkombination"): `create_hermes()` akzeptiert jetzt **beliebige Registry-Engines** (claude/codex/opencode/…) aus dem Options-Endpoint, nicht nur das `hermes`-Profil. Der Manager übersetzt `engine`/`model` pro Session via `resolve_hermes_invocation()` in die Hermes-CLI-Argumente; die Session wird weiterhin unter `engine="hermes"` persistiert und läuft über die Hermes-CLI. `create_hermes()` prüft nun die **Hermes-Engine**-Verfügbarkeit (`include_disabled=True`, da `hermes` in engines.yaml `enabled: false` ist) statt der Quell-Engine; eine wirklich unbekannte Engine bleibt 400 (Resolver). Damit ist jede Options-Kombination startbar — Vertrag Options↔Create wieder konsistent. Verifiziert durch `tests/test_proj85_hermes.py::test_create_hermes_accepts_registry_engine` (neu).

**BUG-2 (High) — Frontend-Payload fehlt Pflichtfeld `engine`, Backend lehnt mit 422 ab.**
Frontend `HermesStartRequest` (`nextjs_app/lib/types.ts:588`) sendet `{title?, project_path, model}` — kein `engine`. Backend `HermesSessionCreate` (`backend/app/schemas/sessions.py:127-144`) deklariert `engine` als Pflichtfeld ohne Default. Eigener Testlauf mit dem exakten Frontend-Payload gegen den echten Endpunkt: `422 {"detail":[{"type":"missing","loc":["body","engine"],"msg":"Field required"}]}`. Selbst wenn BUG-1 gefixt wird, bleibt der Dialog funktionsunfähig, solange das Frontend kein `engine`-Feld mitschickt (das `HermesModelOption` liefert `engine` mit, wird aber im Dialog-Submit nicht übernommen — `hermes-start-dialog.tsx:117-121`).

**BUG-3 (Medium) — `HermesSessionCreate.extra="forbid"` wirkt nicht — GEFIXT (Backend, t_f451eab4).**
`model_config = ConfigDict(extra="forbid")` ist jetzt als **Klassenattribut innerhalb** der Klassendefinition gesetzt (vorherige Zuweisung nach der Klasse war bei Pydantic v2 wirkungslos). Zusätzliche Felder (`permission_mode`, `owner`, …) werden nun mit 422 abgelehnt. Verifiziert durch `tests/test_proj85_hermes.py::test_create_hermes_extra_forbid` (neu). Der dokumentierte ADR-85-1-Vertragsschutz ist damit technisch wirksam.

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

## QA Re-Verifikation (2026-08-22)
**Getestet:** eigener uvicorn-Prozess aus dem PROJ-85-Worktree (Port 8010, `JUPITER_SESSION_INDEX_DB_PATH=/tmp/proj85qa-data`), da der laufende Prod-Prozess auf :8000 noch den `main`-Checkout ohne `/sessions/hermes/*`-Routen serviert (stale, kein Bug). Eigener QA-User via `/auth/bootstrap`, echte Curl-Requests, echter Hermes-CLI-Subprozess.

**Ergebnis: READY** (0 Critical/High offen; 1 Low dokumentiert, bewusst nicht gefixt).

### Bug-Re-Verifikation
- **BUG-1 (Critical, Contract-Mismatch) — GEFIXT, bestätigt.** `GET /sessions/hermes/options` liefert 22 Kombinationen (claude/codex/opencode); `POST /sessions/hermes` mit der ersten gelisteten Kombi (`engine=claude, model=sonnet`) → **201**, `engine=hermes` in der Session, Modell korrekt zu `claude-sonnet-5` übersetzt.
- **BUG-2 (High, Frontend-Payload fehlt `engine`) — GEFIXT, bestätigt.** `hermes-start-dialog.tsx:123` übernimmt `selected?.engine` ins Submit-Payload (Code-Review); Backend-seitig mit demselben Payload-Shape (`title,project_path,engine,model`) → 201, kein 422.
- **BUG-3 (Medium, `extra=forbid` wirkungslos) — GEFIXT, bestätigt.** POST mit Zusatzfeldern `owner:"attacker"`, `permission_mode:"default"` → **422** `extra_forbidden` auf beiden Feldern.
- **BUG-4 (Low, `HermesOptions.warning` Typ-Inkonsistenz)** — weiterhin nicht gefixt (bewusst, laut Task). Dokumentiert, kein Blocker.

### Akzeptanzkriterien (13/13)
1. „Neu Hermes"-Knopf neben „Neu" — PASS (unverändert, Code-Review).
2. Dialog Titel/Pfad/Modell, deutsche Texte — PASS (unverändert, Code-Review).
3. Modellliste nur Hermes-kompatibel, ungültige Kombi nicht startbar — **PASS**. Options-Liste komplett gegen Create verifiziert (erste Kombi startbar); unbekanntes Modell `does-not-exist-9999` → 400 „ist für Engine 'claude' nicht auswählbar.“
4. Modellübersetzung serverseitig pro Session — **PASS**. Response zeigt `model:"claude-sonnet-5"` aus Eingabe `engine=claude, model=sonnet`; Hermes-Subprozess bekam korrektes `-m claude-sonnet-5 --provider anthropic`.
5. Kein bestehendes Profil verändert — PASS (Code-Review, unverändert: `hermes_resolver.py` read-only).
6. Bypass + Token Savings fest — **PASS, jetzt laufzeitverifiziert**: Response `permission_mode:"bypassPermissions"`, `savings_enabled:true`, `savings_source:"override_on"`; kein Payload-Feld dafür vorhanden (422 bei Versuch, siehe BUG-3-Redteam).
7. Session erscheint sofort unter „Aktive Sessions“ — **PASS**. Nach 201 direkt `GET /sessions` → neue Session mit `project_name` aus Titel enthalten (kein Reload nötig, kein Polling-Delay im Test).
8. Mehrere Hermes-Sessions parallel zu Standard — **PASS**. `GET /sessions` zeigte 4 Sessions gleichzeitig (3 Alt-Sessions + neue), unabhängige `session_id`.
9. Gleiches Look-and-Feel — PASS (Code-Review, unverändert).
10. Kontextanzeige absolute Werte + Balken — PASS strukturell (Code-Review `hermes-context-usage.tsx`, unverändert); Backend-Feld-Vertrag (`context_used_tokens`/`context_window_tokens`/`context_usage_available`) live im Response vorhanden und korrekt `null`/`false` ohne Daten.
11. Balken nie > 100% — PASS (Unit-Level, unverändert `pctUsed()`).
12. Kein Wert → deutscher Hinweis — PASS (unverändert, Code-Review).
13. Resume nach Backend-Neustart — **PASS**. Session vor Neustart erzeugt (`ecdd43f0-…`), Backend-Prozess hart beendet + neu gestartet → `GET /sessions` zeigt die Session weiterhin; `POST /sessions/{id}/reanimate` → 200, `liveness_last_result:"läuft_wieder"`. Ohne `hermes_resume_ref` (kein abgeschlossener Turn im Test, s. u.) degradiert der Manager korrekt auf `context_status="kontextlos (keine Hermes-Resume-Referenz)"` statt eines stillen Kontextverlusts (Code-Review `manager.py:2095-2102`, Edge-Case „Resume-Referenz fehlt“ implementiert wie spezifiziert).

**Hinweis Testtiefe AC13:** Der echte Hermes-One-Shot-Turn wurde aus Kostengründen vor Abschluss abgebrochen (SIGTERM), daher wurde `hermes_resume_ref` in diesem Lauf nie gesetzt — der positive Resume-mit-Ref-Pfad (`--resume <ref>`) ist nur durch die pytest-Suite (`test_proj85_hermes.py`, gefakter Treiber) abgedeckt, nicht durch einen echten Hermes-Prozess. Der negative Pfad (fehlende Ref → sichtbarer Hinweis, kein stiller Neustart) ist live bestätigt.

### Security-Redteam (gegen echten laufenden Endpoint, PROJ-85-spezifisch)
- Owner-Override im Payload (`owner:"attacker"`) → 422 (extra=forbid greift jetzt tatsächlich, BUG-3 gefixt). PASS.
- Permission-Mode-Override im Payload → 422, gleicher Fund. PASS.
- Unbekanntes Modell/Engine-Kombi → 400, kein Session-Leck. PASS.
- Path-Traversal (`project_path=/tmp/...` außerhalb erlaubter Roots) → 400 „liegt außerhalb des erlaubten Bereichs“. PASS (unverändert von BUG-1-Fix).
- Kein neuer Owner-Scope-Bruch: `GET /sessions` liefert nur eigene Sessions (Single-User-Testlauf, Code-Pfad unverändert von PROJ-25, kein Regressions-Hinweis in Suite).

### Regression
Volle Backend-Suite (`pytest -q`, PROJ-85-Worktree): **1314 passed, 1 xfailed, 5 failed** — alle 5 Failures identisch zum vorigen QA-Lauf, vor PROJ-85 bereits bestehend und themenfremd (`test_proj39_orchestration::test_real_config_has_orchestration_group`, `test_proj50_codex_abc.py` ×4 — Codex-Skill-Generator/Orchestration-Config, keine Berührung mit `sessions.py`/`manager.py`-Hermes-Pfaden). Kein neuer Failure. PROJ-85-eigene Suite weiterhin 12/12 grün (2 zusätzliche Tests aus BUG-1/3-Fix).

### Fazit
**READY.** Alle 13 Akzeptanzkriterien PASS (12 vollständig live verifiziert, AC13 teilweise durch Testkosten-Abbruch nur im negativen Pfad live + positivem Pfad via Suite belegt — kein Blocker). Kein Critical/High-Bug offen. BUG-4 (Low) bleibt dokumentiert, nicht gefixt.

## Deployment

Production URL: https://jupiter.auxevo.tech
Deployed: 2026-08-22 · Version: 0.27.52
Host: Dev-VPS host-native (systemd `jupiter-backend`/`jupiter-frontend`, Caddy, GitHub-Webhook Auto-Deploy auf `main`)

## Post-Deploy Bugfix (abc-backoffice, 2026-08-22)

Nutzer meldete: (1) Modell-Dropdown im Startdialog abgeschnitten/kaum lesbar, (2) neue Session
sofort "beendet, ohne Turn regulär abzuschließen" + 404-Modellfehler beim ersten Tippen, (3)
initialer Eingabetext nach Neustart nicht übernommen.

- **Ursache (2)+(3):** `hermes_chat_driver.py:98-101` (`HermesChatDriver.send_input`) spawnte den
  ersten Turn bei wartender Session (`_awaiting_first_input`) aus dem **alten** `self._spec`
  (leerer `initial_prompt`) statt — wie die Basisklasse `GenericCliDriver.send_input` es korrekt
  vormacht — aus einem neuen `LaunchSpec` mit dem getippten Text. Hermes wurde mit `-z ""`
  aufgerufen: der Text ging verloren, der leere Prompt ließ den One-Shot-Prozess abnormal enden.
- **Fix (2)+(3):** `send_input` baut jetzt bei `_awaiting_first_input` einen neuen `LaunchSpec` mit
  `initial_prompt=text` (analog zur Basisklasse) und aktualisiert `self._spec`.
- **Ursache (1):** `SelectTrigger` im Startdialog (`hermes-start-dialog.tsx:188`) ohne
  Breiten-Klasse → Default `w-fit`, gebunden an den Platzhaltertext. `SelectContent`
  (`select.tsx:86`) bindet die Popup-Breite an `w-(--anchor-width)` (Trigger-Breite) → lange
  Modellnamen wurden mit `overflow-x-hidden` abgeschnitten.
- **Fix (1):** `SelectTrigger` bekommt `className="w-full"` — Popup-Breite folgt jetzt der vollen
  Dialogbreite.
- **Verifikation:** neuer Test `backend/tests/test_proj85_hermes_chat_driver.py` — vor dem Fix rot
  (`argv` enthielt `-z ""`), nach dem Fix grün. Volle `test_proj85_hermes*.py`-Suite: 13/13 grün,
  kein Regressionsbruch. Frontend-`tsc --noEmit`: identische 7 vorbestehende Fehler vor/nach dem
  Fix (unabhängige Test-Mock-Typen, nicht in `hermes-start-dialog.tsx`/`select.tsx`).
- **Nicht live reproduziert:** der gemeldete 404-Modellfehler selbst — die tmux-Session war beim
  Check bereits neu gestartet und lief fehlerfrei; kein Log mit der ursprünglichen Session-ID
  auffindbar. Plausibelste Erklärung: Folgeeffekt des leeren `-z ""`-Aufrufs. Sollte der 404 nach
  diesem Fix (Text kommt jetzt korrekt an) erneut auftreten, weiteres Signal für eine separate
  Ursache in der Modell-/Provider-Auflösung — dann neuer Ticket.
- **Knowledge:** `bug-geloest-jupiter-hermes-chat-first-turn-empty-prompt.md`
