# PROJ-79: Featurezentrierter Koordinator mit autonomem Abschluss

## Status: Planned
**Created:** 2026-08-16
**Last Updated:** 2026-08-16
**Prio:** P1

## Dependencies
- Requires: PROJ-22 (Multi-Agent-Dispatch-Schicht + Vertrag-zuerst/Koordinator) — bestehende Flotte, Spezialisten-Sessions und Vertragsvermittlung.
- Requires: PROJ-4 (Decision Cards) — kontrollierter Stopp bei einem unauflösbaren Störfall.
- Requires: PROJ-16, PROJ-27, PROJ-33, PROJ-45 (Watchdog, Liveness, Lifecycle-Härtung und begrenzte Reanimation) — Erkennen, Wiederaufnahme und Begrenzen von Hängern.
- Requires: PROJ-17 (Recovery über den Vault) — Wiederaufnahme nach einem Backend-/Host-Ausfall.

## Beschreibung

Eine Projektnummer steht für genau ein fachliches, test- und auslieferbares Feature. Startet der Nutzer zum Beispiel **„Implementiere PROJ-101"**, steuert Jupiter die dafür nötigen Spezialisten selbstständig als eine Feature-Ausführung. Architektur, Backend, Frontend, QA und Review sind dabei interne Arbeitspakete, keine neuen Einträge in `features/INDEX.md` und keine eigenständigen Features.

Der Koordinator leitet aus der Feature-Spezifikation nur die tatsächlich nötigen Arbeitspakete ab, ordnet sie dem übergeordneten Feature zu und führt sie abhängigkeitsgerecht aus. Interne Kennungen wie `PROJ-101.1` sind nur in der Flottenansicht sichtbar. Das Feature gilt erst als abgeschlossen, wenn seine Akzeptanzkriterien erfüllt und die erforderliche Prüfung beendet sind.

Die Ausführung darf weder still abbrechen noch unbemerkt hängen bleiben. Bei einem erkannten Störfall versucht Jupiter die vorhandene, begrenzte Wiederaufnahme selbstständig. Bleibt ein Arbeitspaket danach nicht fortsetzbar, pausiert die gesamte Feature-Ausführung kontrolliert und zeigt genau eine Decision Card mit Zustand, Ursache und einer konkreten nächsten Entscheidung. Arbeit und nachvollziehbarer Stand bleiben erhalten.

## User Stories

- Als Nutzer möchte ich **„Implementiere PROJ-101"** als einzigen Auftrag geben, damit Jupiter die zugehörige Arbeit selbst organisiert, ohne dass ich Backend-, Frontend- oder QA-Tickets anlegen muss.
- Als Nutzer möchte ich in der Flottenansicht sehen, welche internen Arbeitspakete zu PROJ-101 gehören, was parallel läuft und was auf einen Vorgänger wartet.
- Als Nutzer möchte ich, dass nur für das Feature notwendige Spezialisten gestartet werden, damit ein reines Backend-Feature nicht künstlich eine Frontend- oder QA-Session vorwegnimmt.
- Als Nutzer möchte ich, dass die Ausführung nach einem temporären Hänger oder einem geordneten Neustart selbstständig weiterläuft, ohne dass ich die Flotte manuell zusammensuchen muss.
- Als Nutzer möchte ich bei einem endgültig unlösbaren Störfall eine einzige aussagekräftige Decision Card erhalten, während das gesamte Feature kontrolliert pausiert bleibt.
- Als Nutzer möchte ich ein Feature erst dann als fertig sehen, wenn die vereinbarten Akzeptanzkriterien und die nötigen Prüfungen nachweislich abgeschlossen sind.

## Acceptance Criteria

- [ ] Der Koordinator kann aus einem ausdrücklich gewählten Feature `PROJ-X` dessen Spezifikation laden und eine **Feature-Ausführung** starten; er startet nicht mehr pauschal je offenem Eintrag aus `features/INDEX.md` eine Flotte.
- [ ] Vor dem Start zeigt Jupiter einen prüfbaren Plan mit internen Arbeitspaketen, deren Abhängigkeiten, vorgesehenen Rollen und möglicher Parallelität. Der Nutzer gibt diesen Plan einmal frei.
- [ ] Interne Arbeitspakete tragen eine eindeutige Kennung unterhalb des Eltern-Features, etwa `PROJ-101.1`; sie erzeugen weder einen neuen `features/INDEX.md`-Eintrag noch einen eigenen fachlichen Feature-Status.
- [ ] Der Plan enthält nur Arbeitspakete, die aus der Spezifikation folgen. Nicht benötigte Disziplinen werden nicht gestartet.
- [ ] Der Koordinator startet bereitstehende Arbeitspakete selbstständig, startet abhängige Arbeit erst nach dem erfolgreich belegten Vorgänger und nutzt freie Session-Slots für wartende Arbeitspakete.
- [ ] Die Cockpit-Ansicht gruppiert alle Kind-Sessions, Warteschlangen, Prüfungen und offenen Entscheidungen eindeutig unter dem Eltern-Feature `PROJ-X`.
- [ ] Ein Arbeitspaket darf nicht als erfolgreich gelten, weil sein Prozess lediglich endet. Der Koordinator verlangt für die jeweilige Aufgabe einen belegbaren Abschluss und führt erforderliche Folgearbeit oder Prüfung anschließend weiter.
- [ ] Erkennt die vorhandene Liveness-/Watchdog-Logik einen temporären Hänger oder eine recoverbare Unterbrechung, versucht Jupiter die bestehende begrenzte Wiederaufnahme selbstständig und setzt den Feature-Plan danach fort.
- [ ] Die automatische Wiederaufnahme ist pro Arbeitspaket begrenzt und unterscheidet echten Fortschritt von wiederholtem Replay; sie darf keinen Endlos-Resume- oder Agenten-Sturm erzeugen.
- [ ] Bei Backend-Neustart oder Host-Recovery wird eine laufende Feature-Ausführung samt Eltern-Feature, Arbeitspaketen, Abhängigkeiten und bereits erreichten Ergebnissen wiederhergestellt oder kontrolliert in den vorhandenen Recovery-Pfad überführt.
- [ ] Kann ein Arbeitspaket nach ausgeschöpfter automatischer Wiederaufnahme nicht fortgesetzt werden, pausiert der Koordinator die gesamte Feature-Ausführung. Jupiter erzeugt genau eine deutsche Decision Card mit betroffenem Arbeitspaket, letztem sicheren Stand, Ursache und mindestens den Aktionen „erneut versuchen", „manuell übernehmen" und „Feature abbrechen".
- [ ] Solange diese Decision Card offen ist, werden keine neuen abhängigen Arbeitspakete dieses Features gestartet. Bereits sicher abgeschlossene Ergebnisse bleiben sichtbar und erhalten.
- [ ] Die Feature-Ausführung wird erst als „Fertig" markiert, wenn alle erforderlichen Arbeitspakete erfolgreich beendet, ihre Abhängigkeiten aufgelöst und die in der Feature-Spezifikation verlangten Prüfungen erfüllt sind.
- [ ] Alle Nutzertexte sind deutsch. Bestehende Einzel-Session-, Recovery-, Watchdog- und PROJ-22-Flows bleiben funktionsfähig.

## Edge Cases

- **Feature ohne technische Teilbereiche:** Der Koordinator plant nur die tatsächlich erforderliche Arbeit; er erzeugt keine leeren Backend-/Frontend-/QA-Arbeitspakete.
- **Unklare oder widersprüchliche Spezifikation:** Vor dem Start entsteht eine Decision Card zur Klärung; keine Spezialisten starten auf Basis einer geratenen Zerlegung.
- **Zwei Arbeitspakete würden dieselben Artefakte parallel ändern:** Der Plan serialisiert sie oder zeigt die Kollision vor dem Start zur Entscheidung an.
- **Kein freier Session-Slot:** Bereite Arbeitspakete bleiben sichtbar eingereiht und starten automatisch, sobald ein Slot frei wird; sie gehen nicht verloren.
- **Kind-Session endet ohne Abschlussbeleg:** Das Arbeitspaket bleibt offen und wird nicht als erledigt gezählt; der Koordinator versucht den vorgesehenen Recovery-Pfad.
- **Wiederholter gleicher Hänger:** Das Reanimationsbudget wird nicht durch Replay-Ausgaben zurückgesetzt; nach dem Limit folgt die kontrollierte Pausierung statt einer Schleife.
- **Backend-Neustart während einer Feature-Ausführung:** Die Zuordnung zum Eltern-Feature und der Plan bleiben wiederherstellbar; ein geordneter Neustart setzt fort, ein harter Ausfall folgt dem Recovery-/Decision-Card-Pfad.
- **Decision Card wird lange nicht beantwortet:** Der Feature-Zustand bleibt „pausiert — Entscheidung nötig"; keine heimliche Fortsetzung und kein stiller Abbruch.
- **Nutzer bricht das Feature ab:** Jupiter stoppt noch nicht abgeschlossene Arbeitspakete kontrolliert, bewahrt Audit-Spuren und markiert das Eltern-Feature eindeutig als abgebrochen statt als fertig.

## Nicht-Ziele

- Keine neue Projektnummer für Architektur-, Backend-, Frontend- oder QA-Arbeit innerhalb eines Features.
- Keine automatische Ausführung mehrerer fachlich unabhängiger Features durch den Auftrag für nur ein `PROJ-X`.
- Kein unbegrenztes Selbstheilen; nach dem vorhandenen begrenzten Recovery-Budget entscheidet der Nutzer per Decision Card.
- Keine neue Agenten- oder Workflow-Engine; die Funktion erweitert den vorhandenen Koordinator sowie Liveness-, Recovery- und Decision-Card-Pfade.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-16 · **Stack:** Next.js-Cockpit + FastAPI + vorhandener Session-Live-Index und Vault-Recovery · **Branch:** main

### Leitidee

PROJ-79 ersetzt nicht den Session-, Watchdog- oder Recovery-Unterbau. Es ergänzt den bestehenden Koordinator um eine dauerhafte **Feature-Ausführung**: Ein Eltern-Feature `PROJ-X` enthält interne Arbeitspakete und bleibt deren einzige fachliche Einheit. Die Workflows starten und überwachen diese Pakete selbstständig, bis das Feature nachweislich fertig ist oder kontrolliert auf eine Entscheidung wartet.

Die vorhandene Liveness- und Reanimationslogik bleibt die einzige technische Instanz, die einen hängenden Prozess beurteilt. Der Koordinator reagiert ausschließlich auf deren Ergebnis: Fortschritt setzt den Plan fort; ein ausgeschöpftes Recovery-Budget pausiert den gesamten Feature-Lauf und öffnet eine einzige Decision Card. Damit entstehen weder ein zweiter Watchdog noch konkurrierende Wiederaufnahmeversuche.

### Ablauf

```text
„Implementiere PROJ-101"
        │
        ▼
Feature-Spezifikation lesen → internen Plan prüfen → einmal freigeben
        │
        ▼
Feature-Ausführung PROJ-101
├── 101.1 Architektur / Klärung       (nur wenn nötig)
├── 101.2 Backend                     (wartet auf 101.1)
├── 101.3 Frontend                    (wartet auf 101.1; parallel zu 101.2 möglich)
└── 101.4 Prüfung                     (wartet auf die erforderlichen Vorgänger)
        │
        ├── Erfolg mit Abschlussbeleg → nächstes bereites Paket starten
        ├── Temporärer Hänger          → vorhandene begrenzte Reanimation
        └── Recovery ausgeschöpft      → gesamten Lauf pausieren + eine Decision Card
```

### Komponentenstruktur

```text
Koordinator-Tab
├── Feature-Start
│   ├── Projektpfad
│   ├── Feature-ID-Eingabe bzw. Auswahl (PROJ-X)
│   └── Verteilungsplan-Dialog
│       └── interne Arbeitspakete, Abhängigkeiten und Kollisionshinweise
└── Feature-Ausführung
    ├── Elternkopf: PROJ-X, Gesamtzustand, Fortschritt, Pausieren/Abbrechen
    ├── Arbeitspaket-Liste
    │   └── interne Kennung, Rolle, Status, Vorgänger, zugeordnete Session
    ├── Abschluss-/Prüfstatus
    └── eine blockierende Decision Card, falls erforderlich
```

Die bestehende Flottenansicht wird weiterverwendet. Sie erhält den Eltern-Feature-Namen, den Gesamtzustand und die Arbeitspaket-Informationen; Kind-Sessions bleiben weiterhin direkt öffnbar und manuell übernehmbar.

### Frontend-UI im Detail — Einstieg und Modellwahl pro Schritt

Startpunkt bleibt derselbe Ort wie bei PROJ-22: der **Koordinator-Tab** (`coordinator-panel.tsx`). Der bisherige Einstiegsblock „Neue Flotte dispatchen" bekommt einen Modus-Umschalter direkt darüber:

```text
Koordinator-Tab
├── Umschalter: [ Feature ] / [ Flotte (bestehend) ]
│
├── Modus „Feature" (PROJ-79, neu)
│   ├── Projektpfad          (wie bisher, aus localStorage vorbefüllt)
│   ├── Feature-ID-Feld      „PROJ-101" — Autocomplete gegen features/INDEX.md
│   └── Button „Plan erstellen" → öffnet FeaturePlanDialog
│
└── Modus „Flotte" (PROJ-22, unverändert)
    └── bestehender Projektpfad-Block → DispatchPlanDialog
```

Der Feature-Modus ruft `POST /coordinator/feature-plan` statt `POST /coordinator/plan`; alles andere (Projektpfad-Eingabe, localStorage-Persistenz) bleibt identisch zum bestehenden Muster.

**Modellwahl pro Arbeitspaket — zwei Zeitpunkte, wie bei PROJ-22:**

1. **Vor dem Start, im Plan-Dialog (neu: `FeaturePlanDialog`, Fork von `DispatchPlanDialog`).** Jede Zeile der Arbeitspaket-Liste zeigt zusätzlich zur Rolle/Skill-Kette ein editierbares Engine/Modell-Feld — anders als im heutigen `DispatchPlanDialog`, der Engine/Modell nur *anzeigt* (Zeile 163–168 dort). Für PROJ-79 wird daraus ein `Select` pro Zeile (gleiches Component-Pattern wie die Umverteilungs-Select in `fleet-view.tsx:237-248`, options aus `engines.filter(e => e.kind === "engine" && e.available)`), vorbefüllt mit dem vom Backend vorgeschlagenen Default. Erst nach dieser Bearbeitung löst „Plan freigeben" `POST /coordinator/feature-dispatch` mit den (ggf. überschriebenen) Engine/Modell-Werten pro Arbeitspaket aus.
2. **Nach dem Start, in der Feature-Ausführung selbst.** Jedes Arbeitspaket in der Arbeitspaket-Liste (Elternkopf-Ansicht) bekommt dieselbe Umverteilungs-Select wie heute pro Kind-Session in `fleet-view.tsx` — Modellwechsel für ein noch nicht gestartetes oder hängendes Arbeitspaket, ohne den Rest der Feature-Ausführung zu berühren. Bereits laufende Arbeitspakete zeigen die Select deaktiviert (Modellwechsel erst wirksam, wenn die Session neu startet — identisch zum bestehenden PROJ-22-Verhalten).

Damit gibt es genau zwei Orte für die Modellwahl: **einmalig vor Freigabe** (Plan-Dialog, alle Pakete auf einen Blick) und **einzeln danach** (pro Arbeitspaket in der laufenden Ansicht) — kein dritter, versteckter Ort.

### Datenmodell in Klartext

Eine **Feature-Ausführung** speichert:

- das Eltern-Feature `PROJ-X` und den Verweis auf seine Spezifikation;
- den Gesamtzustand: Planung, läuft, pausiert, blockiert, fertig oder abgebrochen;
- den einmal freigegebenen Plan sowie den Verweis auf die gegebenenfalls erforderliche Vertragsnotiz;
- genau eine offene Blockierungsentscheidung, falls der Lauf nicht autonom fortsetzbar ist.

Jedes **interne Arbeitspaket** speichert:

- eine nur innerhalb des Eltern-Features gültige Kennung, z. B. `PROJ-101.2`;
- Auftrag, Rolle, Abhängigkeiten, erwarteten Abschlussbeleg und den deklarierten Schreibbereich;
- Zustand: wartet, bereit, läuft, erfolgreich, fehlgeschlagen oder übersprungen;
- die zugehörige Kind-Session, Wiederaufnahmeversuche und den letzten sicheren Stand.

Diese Daten gehören in den vorhandenen Live-Index und in die vorhandene Recovery-Spur. Das ist nötig, weil die heutige Flottenzuordnung, Queue und Vertragsreferenz nach einem Neustart nur im Speicher liegen. Ohne diese Ergänzung könnte Jupiter die Sessions wiederfinden, aber nicht mehr zuverlässig wissen, zu welchem Feature und Arbeitspaket sie gehören.

#### Abschlussbeleg

Jedes Arbeitspaket endet mit einem einheitlichen, strukturierten **Abschlussbeleg**. Er wird vom Spezialisten zusammen mit seinem Abschluss erzeugt, vom Koordinator gespeichert und gegen die Anforderungen des Pakets geprüft. Ein bloßer Session-Endstatus kann niemals einen Beleg ersetzen.

Der Beleg enthält mindestens: Arbeitspaket-ID, Rolle, Ergebniszustand, Verweise auf die erzeugten Artefakte, durchgeführte Prüfungen mit Ergebnis sowie offene Einschränkungen. Die Rolle ergänzt zwingende Angaben:

| Rolle | Erforderlicher Beleg |
|---|---|
| Architektur/Klärung | Verweis auf das Architektur- oder Entscheidungsartefakt; offene Entscheidungen müssen explizit leer oder als Blocker markiert sein. |
| Backend | Geänderte Artefakte sowie der geforderte automatisierte Test- oder Prüfungsnachweis mit Ergebnis. |
| Frontend | Geänderte Artefakte sowie der geforderte Build-, Lint- oder UI-Prüfnachweis mit Ergebnis. |
| QA | Akzeptanzkriterien-Check mit Ergebnis, verwendete Prüfungen und verbleibende Befunde. |
| Dokumentation/sonstige Arbeit | Verweis auf das vereinbarte Ergebnisartefakt und die dazu passende Prüfung. |

Der Plan legt vor dem Start fest, welche dieser Nachweise je Paket nötig sind. Fehlt ein Pflichtfeld, verweist ein Artefakt ins Leere oder meldet eine Prüfung keinen Erfolg, bleibt das Paket offen beziehungsweise fehlgeschlagen; der Scheduler startet daraus keine Folgearbeit.

#### Schreibbereiche und Kollisionsschutz

Jedes schreibende Arbeitspaket erhält im Plan einen **Schreibbereich**: die betroffenen Dateien oder Verzeichnisse. Der Plan-Dialog zeigt Überschneidungen vor der Freigabe. Überschneiden sich zwei schreibende Pakete, serialisiert der Koordinator sie oder verlangt vor dem Start eine Entscheidung; sie laufen nie parallel mit demselben Schreibbereich.

Der Scheduler hält laufende Schreibbereiche als Claims. Nach Abschluss vergleicht er die tatsächlich geänderten Pfade mit dem Claim. Unerwartete Überschneidungen oder Änderungen außerhalb des deklarierten Bereichs stoppen abhängige Arbeit und erzeugen eine Konfliktentscheidung, statt still auf einem möglicherweise widersprüchlichen Stand weiterzubauen.

#### Nebenläufigkeit und genau eine Blockierung

Alle Plan-, Paket- und Blockierungszustandswechsel eines Eltern-Features laufen durch ein gemeinsames, pro Feature gehaltenes Transition-Gate. Damit können parallel endende Kind-Sessions nicht gleichzeitig denselben Lauf fortsetzen oder mehr als eine Blockierungs-Card erzeugen. Der Zustand erhält zudem eine fortlaufende Revision im Live-Index; nach Recovery wird nur der jüngste konsistente Stand fortgesetzt.

Jupiter läuft heute als einzelner Backend-Worker. Deshalb genügt ein pro Feature gehaltener Lock in der bestehenden Koordinator-Schicht; die persistierte Revision schützt gegen doppelte Verarbeitung nach Restart. Eine verteilte Sperre wird erst nötig, falls Jupiter später mehrere Backend-Worker betreibt.

### Schnittstellen

- `POST /coordinator/feature-plan` erstellt für ein ausgewähltes `PROJ-X` einen unverbindlichen internen Plan.
- `POST /coordinator/feature-dispatch` startet die nach Freigabe entstandene Feature-Ausführung.
- `GET /coordinator/features/{feature_id}` liefert Gesamtzustand, Pakete, Warteschlange, Abschlussbelege und offene Entscheidung.
- `POST /coordinator/features/{feature_id}/pause` pausiert bzw. setzt die gesamte Ausführung fort.
- `POST /coordinator/features/{feature_id}/decision` verarbeitet „erneut versuchen", „manuell übernehmen" oder „Feature abbrechen".
- `POST /coordinator/features/{feature_id}/packages/{package_id}/complete` nimmt den strukturierten Abschlussbeleg einer manuell übernommenen Arbeit an und lässt erst nach dessen Prüfung Folgepakete starten.

Die bisherigen Flotten-Endpunkte bleiben für bestehende Flotten erhalten. PROJ-79 verwendet keinen neuen Agenten-Treiber und keine neue Workflow-Engine.

### Abschluss- und Recovery-Regeln

1. Ein Arbeitspaket wird nur erfolgreich, wenn seine Session regulär endet **und** den zuvor festgelegten Abschlussbeleg liefert. Ein beendeter Prozess allein zählt nicht.
2. Der Scheduler startet nur bereite Pakete. Abhängige Pakete warten; freie Slots ziehen die nächste bereite Arbeit nach.
3. Die vorhandene Liveness-/Watchdog-Logik darf eine Kind-Session innerhalb ihres bestehenden Budgets reanimieren. Der Scheduler wertet echten Fortschritt aus, nicht bloß wiederholte Ausgabe.
4. Ist dieses Budget ausgeschöpft oder fehlt ein fortsetzbarer Stand, wird das betroffene Paket fehlgeschlagen, der Elternlauf atomar pausiert und genau eine persistierte Decision Card erzeugt.
5. Während die Karte offen ist, startet Jupiter keine weiteren abhängigen Pakete. Bereits sichere Ergebnisse bleiben erhalten.
6. Nach einem geordneten Neustart wird der Plan aus dem Live-Index rekonstruiert und fortgesetzt. Nach einem harten Ausfall wird derselbe Zustand über den vorhandenen Recovery-Pfad wiederhergestellt oder als blockiert vorgelegt — niemals als unerkannter Stillstand.

Bei **„manuell übernehmen"** erzeugt oder öffnet Jupiter eine dem Arbeitspaket zugeordnete manuelle Session und markiert das Paket als „manuell in Arbeit". Der Nutzer arbeitet darin weiter und meldet den Abschluss über die bestehende Feature-Ansicht mit dem gleichen strukturierten Abschlussbeleg zurück. Erst nach erfolgreicher Belegprüfung gilt das Paket als erfolgreich und der Scheduler darf Folgepakete starten. Ein manuell beendeter Chat ohne Abschlussmeldung bleibt sichtbar offen.

### Technische Entscheidungen

- **Ein Feature-Lauf statt neuer Features:** bewahrt die fachliche Bedeutung der Projektnummer und verhindert künstliche Einträge in `features/INDEX.md`.
- **Interne Arbeitspakete statt fester Backend-/Frontend-Kette:** ein Feature plant nur notwendige Arbeit; reine Backend- oder Dokumentationsarbeit bleibt klein.
- **Persistierter Plan als Quelle nach Neustart:** die Session-Persistenz existiert bereits, trägt aber heute keine Flottenbeziehung. Ergänzung dieser bestehenden Quelle ist kleiner und zuverlässiger als eine zweite Orchestrierungsdatenbank.
- **Bestehenden Watchdog wiederverwenden:** PROJ-27/45 liefern bereits begrenzte, fortschrittsbewusste Reanimation. PROJ-79 ergänzt nur die fachliche Reaktion, wenn sie endgültig scheitert.
- **Eine persistierte Blockierungs-Card pro Feature:** verhindert Card-Fluten und macht den nächsten menschlichen Schritt eindeutig.
- **Rollenbezogener, strukturierter Abschlussbeleg:** macht „fertig" prüfbar und schützt vor dem heutigen Fehlerbild „Session beendet = Feature fertig".
- **Schreibbereich-Claims statt Worktrees:** verhindert parallele Konflikte mit dem kleinsten Eingriff; ein unerwarteter Dateipfad wird am Abschluss-Gate sichtbar und muss entschieden werden.
- **Per-Feature Transition-Gate:** garantiert innerhalb des heutigen Einzel-Workers einen serialisierten Scheduler ohne neue verteilte Infrastruktur.

### Abhängigkeiten und Pakete

- **Backend:** Erweiterung des bestehenden Koordinators, des Session-Live-Index/Recovery-Pfads und der Decision-Card-Anbindung.
- **Frontend:** Anpassung des Koordinator-Starts, Plan-Dialogs und der Flottenansicht.
- **Datenbank/Migration:** additive, nullable Erweiterung des bestehenden Session-Live-Index für Feature-Zuordnung, Plan, Arbeitspakete, Claims, Revision und Blockierungszustand. Bestehende Flotten ohne Feature-Zuordnung bleiben unverändert als Legacy-Flotten lesbar; es gibt keine riskante Rückmigration und keine neue fachliche Datenbank oder MinIO.
- **Neue Abhängigkeiten:** keine. Vorhandene FastAPI-, Next.js-, Session-, Recovery- und Decision-Card-Bausteine genügen.

### Auswirkung auf bestehende Funktionen

| Vorhandene Funktion | Wirkung von PROJ-79 |
|---|---|
| PROJ-22 Koordinator | Bestehende allgemeine Ticket-Flotten bleiben nutzbar; Feature-Ausführungen erhalten einen eigenen Startpfad. |
| PROJ-27/45 Liveness und Reanimation | Bleiben alleiniger Hänger-/Retry-Mechanismus; Ergebnis wird an den Feature-Scheduler weitergegeben. |
| PROJ-33/17 Restart und Recovery | Erhalten zusätzlich Plan, Eltern-Feature und Arbeitspaket-Zuordnung. |
| PROJ-4 Decision Cards | Liefert den einzigen kontrollierten menschlichen Eingriff nach endgültigem Recovery-Fehler. |

### Umsetzungsreihenfolge

1. Rückwärtskompatible Live-Index-Migration ergänzen: neue Felder sind additiv und nullable; bestehende Flotten bleiben ohne Feature-Zuordnung funktionsfähig.
2. Persistierbaren Feature-Lauf, interne Arbeitspakete, Schreibbereiche und den pro Feature serialisierten Transition-Pfad im bestehenden Koordinator-/Recovery-Pfad ergänzen.
3. Abhängigkeitsbewussten Scheduler, rollenbezogene Abschlussbelege und die Prüfung der tatsächlichen Änderungen auf den vorhandenen Session-Lifecycle aufsetzen.
4. Bei ausgeschöpfter Wiederaufnahme die eine Feature-Blockierungs-Card erzeugen; „erneut versuchen", „manuell übernehmen" mit Abschlussmeldung und „Feature abbrechen" verarbeiten.
5. Feature-Start, Planansicht und Gruppenansicht im Cockpit anpassen.
6. Recovery-, Hänger-, Slot-, Parallelitäts-, Kollisions- und Neustartfälle gegen den vollständigen Feature-Lauf prüfen.

## QA Test Results
_To be added by /abc-qa 79_

## Deployment
_To be added by /abc-deploy 79_

---

## Backend Implementation (abc-backend)

**Branch:** main · **Status:** In Progress · **Datum:** 2026-08-16

Folgt dem existierenden PROJ-22-Modell: ein Feature-Lauf ist selbst eine
Koordinator-Session (`role="coordinator"`, `is_feature_run=True`), die internen
Arbeitspakete laufen als Kind-Sessions. Feature-Laufdaten liegen am Koordinator-`SessionState`
und werden über den bestehenden SQLite-Live-Index (`backend/app/db/session_index.py`)
persistiert — kein neuer Store, kein SQL-Migration-Framework (entspricht Tech-Design:
„Kein neues Persistenz-Schema").

Geändert/neu:
- `backend/app/engine/manager.py` — `SessionState` um `is_feature_run`, `feature_id`,
  `feature_aborted`, `feature_plan`, `feature_packages`, `feature_revision`, `feature_blocker`
  erweitert; `to_read()` + `_state_from_row()` (Restart-Recovery) ergänzt.
- `backend/app/db/session_index.py` — additive, nullable Spalten für den Feature-Lauf
  (Migration via `ALTER TABLE … ADD COLUMN`, JSON-Spalten werden serialisiert).
- `backend/app/schemas/coordinator.py` — `FeaturePlan(Item/Request)`, `FeatureDispatchRequest`,
  `FeatureRun`, `FeaturePackageRead`, `CompletionProof`, `FeatureDecisionRequest`.
- `backend/app/engine/coordinator.py` — `build_feature_plan()` (leitet aus INDEX-Status die
  nötigen Pakete + Abhängigkeiten + Schreibbereiche + rollenbezogene Abschlussbelege ab) und
  `FeatureCoordinatorService` (feature_plan/feature_dispatch/feature_run/feature_set_paused/
  feature_decision/package_complete + Scheduler `schedule_feature_runs`, pro Feature
  serialisiertes Transition-Gate, Abschlussbeleg-Prüfung, eine Blockierungs-Decision-Card).
- `backend/app/routes/coordinator.py` — Endpunkte `POST /coordinator/feature-plan`,
  `POST /coordinator/feature-dispatch`, `GET /coordinator/features/{id}`,
  `POST /coordinator/features/{id}/pause`, `POST /coordinator/features/{id}/decision`,
  `POST /coordinator/features/{id}/packages/{pkg}/complete`.
- `backend/app/main.py` — `app.state.feature_coordinator` + Scheduler-Tick im `_coordinator_loop`.
- `backend/tests/test_proj79_feature_coordinator.py` — 9 Tests (Plan, Dispatch, Beleg-Prüfung,
  Abhängigkeiten, Pause, abort, Blockierung + retry).

Bekannte Grenzen (bewusst deferriert, siehe Nicht-Ziele): Die „begrenzte automatische
Wiederaufnahme" nutzt die vorhandene Liveness/Watchdog-Logik indirekt — der Feature-Scheduler
wertet terminale Kind-Sessions aus; ein fehlender Abschlussbeleg (statt nur Prozess-Ende)
erzeugt die eine Blockierungs-Card. Die tiefe Reanimations-Budget-Anbindung (PROJ-27/45) und
der Schreibbereich-Claim-Vergleich beim Abschluss-Gate sind als nächster Schritt vorgesehen.
