# PROJ-80: Fortsetzbare Paket-Sessions für den Feature-Koordinator (Follow-up ohne Neustart)

## Status: Architected
**Created:** 2026-08-17

## Problem / Motivation
Im PROJ-79-Feature-Lauf sind Backend-/Frontend-Arbeitspakete als **Ein-Turn-Aufgabe** modelliert:
ein Prompt rein, ein Abschlussbeleg raus, Prozess weg. Will der Koordinator dieselbe Rolle später
nochmal ansprechen (z. B. „QA hat BUG-3 gefunden, fix das" oder ein Review-Hinweis aus der
Architektur-Phase), startet der Scheduler heute ein **komplett neues** Paket mit frischem Prompt —
nicht dieselbe Session mit ihrem Kontext. Das entspricht nicht dem in `docs/schwarm-lessons-learned.md`
(business_os) offen notierten Ziel „Frontend/Backend in eigenen, resumable Sessions laufen lassen,
die der Koordinator gezielt weiter beauftragen kann" und wurde bei einem echten PROJ-4-Schwarm-Lauf
am 2026-08-17 als Lücke beobachtet (Coordinator konnte keine dedizierte, fortsetzbare Peer-Session
öffnen und musste stattdessen auf den Standard-Ein-Turn-Paketpfad zurückfallen).

**Root-Cause-Analyse (Code-verifiziert):**
- `SessionManager.send_input()` (`manager.py:1825`) kann eine **bereits beendete** Session bereits
  heute fortsetzen: bei totem, nicht selbst-resumefähigem Treiber ruft es automatisch `_resume()`
  auf, das für generic-CLI-Engines (Codex, OpenCode) die persistierte `resume_id` über
  `resume_argv_template` (`-s {resume_id}`) wiederverwendet — echter Kontext-Resume, kein
  Neustart. Das ist exakt der PROJ-56/58/59/60/62-Mechanismus, bereits deployed und produktiv.
- `POST /sessions/{session_id}/input` (`routes/sessions.py:124`) legt diese Fähigkeit bereits als
  generischen HTTP-Endpunkt offen.
- **Die Lücke liegt nicht in der Engine, sondern im Feature-Scheduler:** `build_feature_plan()`
  (`coordinator.py:513ff`) erzeugt pro Phase genau ein Paket mit `"session_id": None` — dieses Feld
  wird zwar im Paket-Datenmodell geführt, aber es gibt **keine Coordinator-Aktion**, die nach
  Paketabschluss eine neue Nutzinstruktion an dieselbe `session_id` schickt. Jede Folge-Instruktion
  bedeutet heute zwangsläufig ein neues Paket = neue Session = kein Kontext.
- **Zusätzlicher, unabhängiger Blocker (deckt sich mit `docs/koordination-probleme.md` P1,
  business_os):** die Koordinator-Session selbst hat **kein Token** für `/coordinator/*`- oder
  `/sessions/*`-Endpunkte (`auth_gate`, `deps.py:65` → 401 ohne Token). Selbst mit einer
  Follow-up-Aktion könnte der heutige Koordinator sie nicht aufrufen.

## Dependencies
- Requires: PROJ-79 (Featurezentrierter Koordinator) — Paket-Datenmodell (`session_id`-Feld),
  Scheduler, Abschlussbeleg-Vertrag.
- Requires: PROJ-56, PROJ-58, PROJ-59, PROJ-60, PROJ-62 — der bereits gefixte Resume-Mechanismus
  für Nicht-Claude-Engines, den diese Funktion wiederverwendet statt neu zu bauen.
- Requires: PROJ-48 (Codex), PROJ-57 (OpenCode) — generic-CLI-Treiber mit `resume_argv_template`.
- Verwandt: PROJ-4 (Decision Cards) — Follow-up-Aktion darf eine offene Karte nicht umgehen.

## User Stories
- Als **Feature-Koordinator** möchte ich einem bereits abgeschlossenen Backend-/Frontend-Paket
  eine Folge-Instruktion schicken (z. B. einen QA-Fund), damit dieselbe Session mit ihrem Kontext
  weiterarbeitet, statt dass ich den ganzen Auftrag für eine neue Session wiederholen muss.
- Als **Feature-Koordinator** möchte ich, dass ich für diese Aktion (und für das Lesen des
  Feature-Zustands) tatsächlich ein gültiges, eng geschnittenes Token besitze, damit meine
  Rückweisungen/Folgeaufträge nicht als reiner Chat-Text enden, der von Hand weitergereicht
  werden muss.
- Als **Nutzer**, der den Feature-Lauf im Cockpit beobachtet, möchte ich erkennen, ob ein Paket
  mit Kontext fortgesetzt oder als komplett neue Session gestartet wurde, damit ich Kosten und
  Verhalten einordnen kann.

## Acceptance Criteria
- [ ] Ein neuer Endpunkt (z. B. `POST /coordinator/features/{feature_id}/packages/{package_id}/followup`)
      nimmt eine Freitext-Instruktion an und ruft für ein Paket mit vorhandener `session_id` intern
      `SessionManager.send_input()` auf — dieselbe Session wird fortgesetzt, kein neuer Prozess mit
      leerem Kontext.
- [ ] Fehlt die `session_id` (Paket nie gestartet oder Session bereits gelöscht/aufgeräumt), liefert
      der Endpunkt einen eindeutigen Fehler statt eines stillen Neustarts — der Aufrufer entscheidet
      explizit, ob ein frisches Paket sinnvoll ist.
- [ ] Die Follow-up-Aktion respektiert den bestehenden Abschlussbeleg-Vertrag: das Paket gilt erst
      nach dem nächsten strukturierten Abschlussbeleg wieder als `erfolgreich`; der vorherige Beleg
      wird nicht stillschweigend weiterverwendet.
- [ ] Eine offene Decision Card für das Feature blockiert Follow-up-Aktionen genauso wie neue
      Paket-Starts (kein Umgehungspfad).
- [ ] Der Koordinator-Session (`role="coordinator"`) wird beim Start ein serverseitig ausgestelltes
      Token mit Rechten **nur** für `feature_plan`, `feature_dispatch`, `decision`,
      `package_complete`, das neue Follow-up-Endpunkt sowie lesenden Zugriff auf ihren eigenen
      Feature-Lauf injiziert — kein Vollzugriff auf das Nutzerkonto.
- [ ] Die Cockpit-Paketansicht zeigt sichtbar, ob der letzte Turn eines Pakets ein Kontext-Resume
      oder ein Erststart war (nutzt das bestehende `context_status`-Feld aus PROJ-56).
- [ ] Bestehende PROJ-79-Abläufe (Erstpaket-Start, Abschlussbeleg, Wiederaufnahme bei Hänger,
      Decision Card) bleiben unverändert funktionsfähig — diese Funktion ergänzt nur einen
      zusätzlichen Aktionspfad.

## Edge Cases
- Paket-Session wurde inzwischen manuell vom Nutzer übernommen (`"manuell in Arbeit"`, PROJ-79) —
  eine Coordinator-Follow-up-Instruktion darf nicht in eine Session hineinschreiben, die der Nutzer
  gerade selbst bedient (Race). Klare Fehlermeldung statt stillem Doppel-Input.
  einzige Deutlichkeit: „Paket wird manuell bearbeitet, kein automatischer Follow-up möglich."
- Paket-Session existiert noch, ist aber `is_alive` (läuft gerade einen anderen Turn) — Follow-up
  muss wie ein normaler `send_input`-Aufruf ohne Rennen in die laufende Turn-Queue eingereiht
  werden, nicht parallel einen zweiten Prozess starten.
- Resume schlägt fehl, weil die zugrundeliegende CLI-Session serverseitig abgelaufen ist (bereits
  in PROJ-56 als Fallback „sauberer kontextloser Neustart mit Warnung" gelöst) — Follow-up nutzt
  denselben Fallback, meldet ihn aber im Abschlussbeleg-Kontext sichtbar, statt es zu verschweigen.
- Das eng geschnittene Koordinator-Token wird für eine andere Aktion (z. B. `/sessions/{id}/input`
  auf eine fremde, nicht zum eigenen Feature-Lauf gehörende Session) missbraucht — Scope-Prüfung
  serverseitig, nicht nur clientseitig verborgen.
- Zwei Folge-Instruktionen für dasselbe Paket kurz hintereinander (Koordinator schickt doppelt) —
  müssen serialisiert werden (bestehendes Per-Feature-Transition-Gate aus PROJ-79 reicht, sofern
  die neue Aktion denselben Lock nutzt).

## Nicht-Ziele
- Keine neue Agenten-/Workflow-Engine und kein neuer Resume-Mechanismus — diese Funktion ist eine
  dünne Scheduler-/Auth-Ergänzung über dem bereits deployten PROJ-56/58/59/60/62-Resume-Pfad.
- Kein voll interaktiver Chat-Modus zwischen Koordinator und Paket-Session (kein Streaming-Hin-und-
  Her mehrerer Turns pro Sekunde) — eine Follow-up-Instruktion pro Anlass, wie ein neuer Auftrag.
- Kein Ersatz für „manuell übernehmen" (PROJ-79) — das bleibt der Pfad, wenn ein Mensch die Session
  direkt bedienen will.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-17 · **Stack:** Next.js-Cockpit + FastAPI (bestehender `SessionManager`/Coordinator) · **Branch:** main (reine Spezifikationsarbeit, keine Implementierung in diesem Schritt)

### Leitidee

Kein neues Peer-Session-Konzept. Die Fähigkeit „eine beendete Session mit Kontext fortsetzen"
existiert bereits vollständig und produktiv (`SessionManager.send_input`/`_resume`,
PROJ-56/58/59/60/62). PROJ-80 verdrahtet nur zwei fehlende Kanten an diese bestehende Fähigkeit:
(1) der Feature-Scheduler darf ein abgeschlossenes Paket gezielt per `session_id` erneut
adressieren statt zwingend ein neues Paket zu erzeugen, und (2) die Koordinator-Session bekommt
überhaupt ein Token, mit dem sie das aufrufen kann (P1 aus `docs/koordination-probleme.md`).

### Komponentenstruktur

```text
Feature-Koordinator (Cockpit + Coordinator-Session)
├── Bestehend: feature-plan / feature-dispatch / decision / package/complete
└── Neu: package/{package_id}/followup
        │
        ▼
FeatureScheduler (coordinator.py)
├── Paket hat session_id? ── nein → Fehler „kein Follow-up möglich, Paket nie gestartet"
│                          └─ ja  → prüft: manuell übernommen? Decision Card offen? is_alive?
└── SessionManager.send_input(session_id, instruction)   ← bereits vorhanden, PROJ-56/58
        │
        ▼
Bestehender Resume-Pfad (generic_cli_driver / adapters, PROJ-58/60/62)
```

Die Cockpit-Ergänzung bleibt in der vorhandenen Komposition
`FeatureRunView` → `PackageRow` (bestehende `Badge`-/`Button`-Primitives): pro Paket
kommt lediglich ein Status-Badge für den letzten Kontextmodus hinzu. Kein neues Screen- oder
Widget-Konzept.

### Datenmodell (Klartext)
- Kein neues Datenmodell. Das Paket-Feld `session_id` (bereits in `build_feature_plan()` vorgesehen)
  wird ab jetzt tatsächlich befüllt und für Follow-up-Zwecke gelesen statt nur mitgeführt.
- Neu, additiv am bestehenden Koordinator-Token-Konzept: ein serverseitig ausgestelltes,
  kurzlebiges JWT-Scope-Token für Koordinator-Sessions mit den Claims `type=coordinator_capability`,
  `coordinator_id`, `feature_id`, `owner` und einer festen Aktionsliste
  (`feature_plan`, `feature_dispatch`, `decision`, `package_complete`, `package_followup`,
  `feature_read`). Keine neue Tabelle: der Capability-Token ist signiert, nicht persistiert und
  wird bei jedem Start/Resume des Koordinator-Prozesses neu ausgestellt und als
  `JUPITER_COORDINATOR_TOKEN` (zusammen mit der nicht-geheimen `JUPITER_API_URL`) ausschließlich
  über dessen Prozessumgebung injiziert (nie in Prompt, Transkript oder Vault). Der Startprompt
  erklärt nur die Verwendung dieser Variablen, nicht ihren Wert. Seine Laufzeit entspricht
  dem vorhandenen Access-Token-TTL. Der Verifier akzeptiert diesen Token-Typ nur an den explizit
  erlaubten Feature-Routen und prüft zusätzlich `coordinator_id`, `feature_id`, `owner` und Aktion.
- Additiv an `FeaturePackageRead` und dem korrespondierenden Frontend-Typ: `context_status:
  string | null`. Der Wert wird in `_run_dict()` aus `manager.get(session_id).state.context_status`
  gelesen; `null` bedeutet Erststart. Er braucht keine eigene Speicherung, weil der Session-State
  ihn bereits persistiert. Für Generic-CLI-Resumes setzt der gemeinsame Manager den Status vor dem
  delegierten `driver.send_input()` auf `mit Kontext` bzw. `kontextlos (keine Resume-ID der Engine)`;
  sonst bliebe das bestehende Feld bei diesem Resume-Pfad fälschlich leer.

### API-Shape (nur Endpunkte, kein Code)
```
- POST /coordinator/features/{feature_id}/packages/{package_id}/followup
      → Body: `{ instruction: string }`, 1..`MAX_INPUT_CHARS`; nur mit gültiger
        `coordinator_capability` für exakt diesen `feature_id` und die Aktion `package_followup`.
      → Unter dem bestehenden Per-Feature-Lock: Paket nur in Status `erfolgreich` zulassen,
        Decision-Card/`PK_MANUAL`/fehlende oder unbekannte `session_id` ablehnen; vor dem Senden
        `proof` und `last_safe_state` leeren sowie Status auf „läuft" setzen. Scheitert
        `send_input`, werden diese drei Werte atomar zurückgesetzt. Danach entscheidet ausschließlich
        der nächste strukturierte Abschlussbeleg erneut über Erfolg/Fehlschlag.
      → 404 für unbekanntes Feature/Paket; 401 für fehlende/ungültige Capability; 403 für falschen
        Scope/Owner; 409 für offene Decision Card, manuelle Übernahme, fehlende/gelöschte Session
        oder einen vom Treiber abgelehnten Parallel-Turn.

- GET /coordinator/features/{feature_id}
      → Zusätzlich für `feature_read` derselben Capability lesbar; Browserzugriff bleibt auf den
        bestehenden `CurrentUser`-Owner-Check beschränkt.

`feature-plan`, `feature-dispatch`, `pause`, `decision`, `complete`, `GET feature` und der neue
Follow-up-Endpunkt erhalten einen einheitlichen Owner-/Capability-Gate. Beim Dispatch wird der
`CurrentUser.user_id` an `SessionManager.create(..., owner=...)` für Koordinator und Kind-Sessions
weitergegeben. So bleibt der bisher ungeschützte PROJ-79-Routenpfad kein Umgehungskanal.
```

### Tech-Entscheidungen (Begründung)
- **Wiederverwendung statt Neubau:** Der Resume-Mechanismus ist bereits gebaut, gefixt (5 Bugfix-
  Tickets) und produktiv verifiziert. Ein zweites, paralleles „Peer-Session"-Konzept nur für den
  Feature-Koordinator würde dieselbe Fehlerklasse (stdin-Race, stiller Hänger) ein zweites Mal
  einführen können. Die einzige neue Logik ist Routing (welche `session_id` bekommt die
  Instruktion) und Zugriffskontrolle (welches Token darf das).
- **Eng geschnittenes Token statt Vollzugriff:** direkt aus P1 (`docs/koordination-probleme.md`)
  übernommen — der Koordinator braucht Schreibrecht auf klar benannte Aktionen, nicht das gesamte
  Nutzerkonto. Kleinster Eingriff, der das Root-Problem („Koordinator darf urteilen, aber nicht
  handeln") behebt.
- **Ein Follow-up pro Anlass, kein Dauer-Chat:** hält die Semantik identisch zu einem neuen
  Auftrag („neuer Prompt an bekannten Kontext"), vermeidet einen neuen Streaming-/Multi-Turn-
  Interaktionsmodus, den PROJ-79 bewusst nicht vorsieht (Nicht-Ziel: keine neue Workflow-Engine).
- **Fehler statt stiller Fallback bei fehlender `session_id`:** verhindert das aus PROJ-79-QA
  bekannte Muster „Prozess weg = wird stillschweigend als etwas anderes interpretiert" (vgl.
  PROJ-79 BUG-1..3) — lieber ein expliziter, adressierbarer Fehler.
- **Capability im Prozessumfeld statt im Prompt:** Ein Prompt und sein Transkript sind bewusst
  langlebige Arbeitsartefakte. Ein signiertes, beim Prozessstart neu ausgestelltes Capability-Token
  im Environment gibt dem Koordinator den benötigten Handlungskanal, ohne ein Nutzer-Access-Token
  oder ein Geheimnis in Chat, Vault oder Abschlussbelege zu leaken.

### Abhängigkeiten (neue Pakete)
- Backend: keine neuen Pakete — nutzt bestehende `SessionManager`-, JWT- und `generic_cli`-Bausteine.
- Frontend: keine neuen Pakete — Cockpit-Anzeige für `context_status` nutzt vorhandene PROJ-56-Felder.

### Offene Punkte für die Review-Architektur-Phase
- Exakte Token-Ausstellung (welcher bestehende Auth-Baustein erzeugt das Scope-Token — `deps.py`
  `auth_gate` erweitern oder ein separater Issuer?) ist hier bewusst nicht im Detail entschieden;
  das ist eine reine Backend-Implementierungsfrage, keine Produktentscheidung.
- Ob „manuell übernommen"-Erkennung rein am Paketstatus oder zusätzlich an `runtime.driver.is_alive`
  hängt, sollte gegen den aktuellen PROJ-79-Code verifiziert werden.

## Bewertung: technisch sinnvoll, einfach, stabil?

**Sinnvoll:** ja — schließt exakt die beobachtete Lücke (Koordinator kann Backend/Frontend nicht
gezielt weiter beauftragen) und behebt gleichzeitig den seit PROJ-1-Lauf bekannten P1-Befund
(kein Handlungskanal für den Koordinator), ohne den bestehenden PROJ-79-Vertrag zu ändern.

**Einfach:** ja, unter der Bedingung, dass wirklich nur verdrahtet statt neu gebaut wird. Die
gesamte Resume-Mechanik existiert; der Diff ist im Wesentlichen ein Endpunkt + eine Scope-Prüfung
+ Token-Ausstellung. Risiko: wenn die Umsetzung stattdessen ein eigenes „Peer-Session"-Protokoll
parallel zum bestehenden `send_input`/`resume` erfindet, wird es unnötig groß — das wäre die
falsche, nicht die hier vorgeschlagene Lösung.

**Stabil:** ja, weil sie sich auf einen Pfad stützt, der bereits fünf dedizierte Bugfix-Runden
(PROJ-58/59/60/62 + PROJ-56 selbst) durchlaufen hat und aktuell deployed ist. Neue Instabilität
kann nur aus den zwei wirklich neuen Teilen kommen (Scope-Token, Scheduler-Routing) — beide klein
genug, um mit den bestehenden Edge-Cases (offene Decision Card, manuell übernommen, doppeltes
Follow-up) einzeln getestet zu werden, statt eine neue Fehlerklasse über die gesamte Engine-Schicht
zu streuen.

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-17 · **Verdict:** Architected

### Checklist
- [x] Component structure — `FeatureRunView`/`PackageRow` und vorhandene shadcn-Primitives sind benannt; die Ergänzung ist nur ein Kontextstatus-Badge.
- [x] Data model — keine neue Tabelle oder tenant-scoped Entität; Capability-Claims und das bestehende persistierte `SessionState.context_status` sind mit Typ, Lebensdauer und Zugriffsbeschränkung festgelegt.
- [x] API shape — Follow-up hat Methode, Pfad, Body-Grenze, Auth, Statuscodes und Zustandsübergang; `GET feature` und die bestehenden Feature-Routen erhalten den nötigen Owner-/Capability-Gate.
- [x] Tech decisions — Wiederverwendung, Scope-Token, einzelner Follow-up-Turn, expliziter Fehler und geheime Environment-Injektion sind jeweils begründet.
- [x] Dependencies — keine neuen Pakete; vorhandene JWT-, `SessionManager`-, Generic-CLI- und Cockpit-Bausteine sind verifiziert.
- [x] Branch field — `main` existiert und ist der aktuelle Branch; für diese reine Spezifikationsänderung ist er zulässig.
- [x] Conflict-free — keine Route, Tabelle oder Paket-ID kollidiert; der neue Pfad liegt unter dem bestehenden `/coordinator`-Router und nutzt den vorhandenen Per-Feature-Lock.
- [x] Acceptance-criteria coverage — Follow-up, fehlende Session, erneuter Abschlussbeleg, Decision-Card-Sperre, Capability-Scope, Kontextanzeige und Regressionsschutz haben jeweils Route/Service/State/UI-Heimat.

### Autonom behoben
- Capability präzisiert: signiertes, nicht persistiertes Koordinator-Token mit `coordinator_id`-, `feature_id`-, Owner- und Aktions-Scope; sichere Neu-Injektion per Prozessumgebung statt Geheimnis im Prompt.
- Follow-up-Vertrag ergänzt: Eingabevalidierung, Owner-/Scope-Gate, atomarer Status-/Proof-Reset und vollständiges Fehler-Mapping.
- `context_status` in `FeaturePackageRead` und `PackageRow` verankert; der Generic-CLI-Self-Resume setzt das vorhandene Feld nun ebenfalls korrekt.
- Bestehende Feature-Routen an den PROJ-25-Owner-Scope angebunden, damit der Capability-Pfad keinen offenen Altpfad neben sich behält.

## QA Test Results
_To be added by /qa_

## Backend Implementation
**Implemented:** 2026-08-18

- `POST /coordinator/features/{feature_id}/packages/{package_id}/followup` sends the instruction to the existing package session, clears the prior proof, and returns explicit conflict errors for blocked, manual, unfinished, or missing sessions.
- Coordinator capability JWTs are injected only through the coordinator process environment and are verified for action, feature, coordinator, and owner scope.
- Package reads expose the existing `context_status`; coordinator and child sessions keep the owner supplied by the authenticated dispatcher.
- Verified: `python -m pytest backend/tests/test_proj80_followup.py backend/tests/test_proj79_feature_coordinator.py -q` (30 passed), `python -m compileall -q backend/app`, and `git diff --check`.

## Deployment
_To be added by /deploy_
