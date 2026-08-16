# PROJ-79: Featurezentrierter Koordinator mit autonomem Abschluss

## Status: Approved
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

## Implementation Notes

- 2026-08-16: Die sichtbare Bezeichnung der Feature-Ausführung lautet **Schwarm**. Nur Backend und Frontend laufen parallel; alle übrigen Arbeitspakete werden seriell eingeplant. Standardzuordnung: Architektur → Codex/Terra, Backend und Frontend → OpenCode/hy3.

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

**Tested:** 2026-08-16
**Backend:** FastAPI, env `Dashboard` (pytest `TestClient`, `FakeDriver`)
**Frontend:** Next.js 16 (`vitest run`, `tsc --noEmit`) — kein laufender Dev-Server/Browser in dieser Runde
**Tester:** QA Engineer (AI)
**Geprüfter Stand:** Backend committed (`83eb955`), Frontend uncommitted (`feature-plan-dialog.tsx`, `feature-run-view.tsx` neu; `coordinator-panel.tsx`/`api.ts`/`types.ts` geändert)

### Acceptance Criteria Status

#### AC „Feature-Ausführung aus explizitem PROJ-X, kein Pauschal-Start"
- [x] `feature_plan`/`feature_dispatch` sind strikt auf eine `feature_id` beschränkt (`build_feature_plan`, `FeatureCoordinatorService.feature_dispatch`); der Pauschal-Pfad je INDEX.md bleibt exklusiv bei PROJ-22.

#### AC „Prüfbarer Plan vor Start, einmalige Freigabe"
- [x] `FeaturePlanDialog` lädt `POST /coordinator/feature-plan`, zeigt Pakete/Abhängigkeiten/Rollen; Dispatch erst per Klick (`POST /coordinator/feature-dispatch`). Kein Auto-Start.

#### AC „Interne Kennung unterhalb des Eltern-Features, keine neuen INDEX.md-Einträge"
- [x] `package_id` folgt `PROJ-{num}.{i}`; kein Code-Pfad schreibt `features/INDEX.md`.

#### AC „Plan enthält nur nötige Disziplinen"
- [x] `build_feature_plan` leitet Pakete ausschließlich aus den ab `next_phase_for_status` verbleibenden ABC-Phasen ab (`test_feature_plan_deployed_has_no_work`).

#### AC „Selbstständiger Start bereiter Pakete, Abhängige warten, freie Slots genutzt"
- [x] `_schedule`/`_deps_done` starten nur Pakete mit erfüllten Abhängigkeiten und respektieren `max_parallel_sessions` (`test_feature_dispatch_starts_only_ready_packages`, `test_feature_complete_proof_unlocks_dependents`).

#### AC „Cockpit gruppiert Kind-Sessions/Prüfungen/Entscheidungen unter Eltern-Feature"
- [x] `FeatureRunView` rendert Elternkopf + Paketliste + genau eine Blockierungs-Card an einer Stelle; `coordinator-panel.tsx` unterscheidet Feature- vs. Flotten-Kacheln korrekt über `is_feature_run`.

#### AC „Kein Erfolg ohne Abschlussbeleg" / AC „Fertig erst nach allen Belegen"
- [ ] **BUG-1 (Critical)** — siehe unten: Es existiert **kein Pfad**, über den ein Paket in der Praxis erfolgreich einen Beleg liefert. Weder ruft eine Spezialisten-Session `POST .../complete` selbst auf, noch kann das manuelle UI-Formular einen gültigen Erfolgsbeleg erzeugen (BUG-2). Der Mechanismus selbst (Rückweisung ohne Beleg) ist korrekt implementiert (`_validate_proof`, `_reap_children`) — aber „Fertig" ist mit dem gelieferten Diff **unerreichbar**.

#### AC „Automatische begrenzte Wiederaufnahme bei Hänger, Plan setzt fort"
- [~] Nicht neu implementiert, bewusst über bestehenden Watchdog (PROJ-27/45) delegiert (`_reap_children` reagiert nur auf terminale Session-States) — architektonisch korrekt, aber in dieser QA-Runde **nicht end-to-end mit einem echten Hänger verifiziert** (kein Integrationstest, der einen Watchdog-Reanimationszyklus durch den Feature-Scheduler treibt).

#### AC „Wiederaufnahme pro Paket begrenzt, echter Fortschritt ≠ Replay"
- [ ] **BUG-3 (Medium)**: `resume_attempts` wird ausschließlich bei der manuellen Aktion „erneut versuchen" hochgezählt (`coordinator.py:685`). Automatische Watchdog-Reanimationen laufen komplett am Feature-Paket vorbei — das Feld (und die UI-Anzeige „N× wiederaufgenommen") spiegelt die tatsächliche automatische Wiederaufnahme-Historie nicht wider.

#### AC „Wiederherstellung nach Backend-/Host-Neustart"
- [x] Strukturell vorhanden: `feature_id`/`feature_packages`/`feature_blocker`/`feature_plan`/`feature_revision` sind vollständig im `session_index`-Schema persistiert (Spalten + Rehydrierung, `manager.py:387-393,459-466,1621-1627`). **Nicht** end-to-end mit echtem Prozess-Neustart getestet (nur Code-Review).

#### AC „Genau eine deutsche Decision Card mit den drei Aktionen"
- [x] `_add_blocker_card` erzeugt genau eine `PendingDecision` (`card_type=feature_blocker`), deutscher Text, Aktionen `retry`/`manual`/`abort` (`test_feature_blocker_card_on_failed_proof`, `test_feature_abort_sets_status`).

#### AC „Karte offen ⇒ keine neuen abhängigen Pakete; sichere Ergebnisse bleiben"
- [x] `schedule_feature_runs` überspringt Feature-Läufe mit gesetztem `feature_blocker` vollständig.

#### AC „Deutsche Texte, bestehende Einzel-Session-/Recovery-/Watchdog-/PROJ-22-Flows bleiben funktionsfähig"
- [x] Alle UI-Texte deutsch. Regressionslauf: `pytest backend/` 1267 passed / 4 failed — **alle 4 Fehlschläge vorbestehend und unabhängig von PROJ-79** (3× `test_proj50_codex_abc.py` reproduzieren identisch auf `c92ec45` vor diesem Feature; 1× `test_proj14_ui_check.py::test_ui_check_start_and_cancel_run` ist Suite-Reihenfolge-Flake — besteht isoliert). `vitest run` (Frontend): 203/203 grün, keine Regression.

### Edge Cases Status

#### EC „Feature ohne technische Teilbereiche"
- [x] `exec_order` filtert auf tatsächlich verbleibende Phasen — keine leeren Pakete.

#### EC „Unklare/widersprüchliche Spezifikation → Decision Card vor Start"
- [ ] **BUG-4 (Medium)**: Nicht implementiert. Bei fehlender nächster Phase liefert `build_feature_plan` nur `items: []` + Text-Warnung; keine Decision Card entsteht. Der Dispatch-Button ist zwar faktisch deaktiviert (kein Paket verteilbar), aber der spezifizierte Klärungs-Flow fehlt.

#### EC „Zwei Arbeitspakete würden dieselben Artefakte parallel ändern"
- [ ] **BUG-5 (High)**: Nicht implementiert. `write_scope` wird pro Paket berechnet und angezeigt, aber nirgends gegeneinander geprüft — weder Serialisierung noch Kollisionswarnung. Backend + Frontend laufen laut `_PACKAGE_RANK` bewusst parallel; ein Overlap in `write_scope` bliebe unbemerkt.

#### EC „Kein freier Session-Slot"
- [x] `_schedule` überspringt bei vollem `active_count` und startet beim nächsten Tick (`_coordinator_loop`, 4s-Intervall via `schedule_feature_runs`).

#### EC „Kind-Session endet ohne Abschlussbeleg"
- [x] Mechanik korrekt (`_reap_children` blockt statt „fertig" zu zählen) — praktisch aber **immer** der Fall, siehe BUG-1/BUG-2: jedes reguläre Paket landet ohne manuelles Eingreifen im Blockierungszustand.

#### EC „Wiederholter gleicher Hänger"
- [~] Delegiert an PROJ-45 (bestehend, nicht Teil dieses Diffs) — nicht erneut verifiziert.

#### EC „Backend-Neustart während Feature-Ausführung"
- [x] Strukturell (siehe AC oben) — nicht Prozess-neustart-getestet.

#### EC „Decision Card wird lange nicht beantwortet"
- [x] Kein Auto-Resume-Code-Pfad gefunden; Zustand bleibt `blockiert`, bis `decision` aufgerufen wird.

#### EC „Nutzer bricht Feature ab"
- [x] `_abort` stoppt offene Kind-Sessions, setzt `feature_aborted` (`test_feature_abort_sets_status`).

### Security Audit Results
- [x] Kein neuer Angriffsvektor durch `project_path`/`feature_id`: `validate_project_path` (bestehend) bleibt einzige Pfad-Validierung; `feature_id` wird nur normalisiert/verglichen, nie in Dateipfade eingesetzt.
- [x] Trust-Policy (PROJ-10) greift identisch wie bei PROJ-22 (`DISPATCH_ACTION`-Check in `feature_dispatch`).
- [x] Kein JWT/RLS-Gap: `/coordinator/*` ist projektweit bewusst ungeschützt (Single-User-MVP, dokumentiert im Modul-Docstring) — konsistent mit dem bestehenden PROJ-22-Verhalten, kein neuer Bruch.
- [x] Pydantic validiert `CompletionProof`/`FeatureDecisionRequest` (Pattern auf `result_state`/`action`) — kein unvalidierter Freitext-Zustand möglich.
- [ ] Nicht geprüft: Verhalten bei zwei parallelen `POST .../complete`-Aufrufen für dasselbe Paket (Race) — `_feature_lock` serialisiert zwar pro Feature, aber nicht explizit getestet.

### Bugs Found

#### BUG-1: Kein automatischer Abschlussbeleg-Pfad — Spezialisten-Sessions kennen den neuen Vertrag nicht
- **Severity:** Critical
- **Steps to Reproduce:**
  1. Feature-Ausführung dispatchen (z. B. `PROJ-101.1`, Rolle `architect`, Skill `abc-architecture`).
  2. `_start_package` startet die Kind-Session nur mit `/{skill} {num}` als Prompt — keine Instruktion, keine Werkzeug-Bindung und kein Skill (`/home/dev/tools/Hal/09_Skills/`) ruft `POST /coordinator/features/{id}/packages/{package_id}/complete` auf.
  3. Erwartet: Nach regulärem Abschluss der Skill-Arbeit liefert die Session selbstständig einen strukturierten Beleg.
  4. Tatsächlich: Die Session endet reg. (`DONE`), `_reap_children` findet `pkg["proof"] is None` → Paket wird `fehlgeschlagen`, der gesamte Feature-Lauf pausiert atomar mit einer Decision Card — bei **jedem** Paket, **jedes Mal**.
- **Priority:** Fix before deployment — widerspricht direkt dem Namensversprechen „mit autonomem Abschluss" und AC „Fertig erst nach Belegen".

#### BUG-2: Manuelles Beleg-Formular kann NIE einen gültigen Erfolgsbeleg erzeugen
- **Severity:** Critical
- **Steps to Reproduce:**
  1. In `feature-run-view.tsx` `PackageRow.submit()` „Beleg einspielen" mit Ergebnis „erfolgreich" ausfüllen (Artefakte gesetzt).
  2. Payload sendet hartkodiert `checks: []` (Zeile 232) — es gibt keine UI-Eingabe für `checks` im gesamten Formular.
  3. Backend `_validate_proof` verlangt bei `result_state == "success"` zwingend `any(c.get("result") for c in checks)` — mit `checks: []` immer `False`.
  4. Reproduziert per pytest (identischer Payload wie das Formular): `POST .../complete` → **400 „Abschlussbeleg unvollständig oder widersprüchlich."**
- **Priority:** Fix before deployment — auch der einzige verbliebene (manuelle) Weg zu „Fertig" ist tot. In Kombination mit BUG-1 ist eine Feature-Ausführung mit dem gelieferten Diff **nie** abschließbar.

#### BUG-3: `resume_attempts`/UI-Anzeige spiegelt nur manuelle Retries, nicht automatische Watchdog-Reanimation
- **Severity:** Medium
- **Steps to Reproduce:**
  1. Paket hängt, Watchdog (PROJ-27/45) reanimiert automatisch innerhalb seines Budgets.
  2. Erwartet: `pkg.resume_attempts` / UI „N× wiederaufgenommen" spiegelt die Wiederaufnahme-Historie.
  3. Tatsächlich: Zähler bleibt `0`, bis ausschließlich per manueller Decision-Card-Aktion „erneut versuchen" erhöht (`coordinator.py:685`).
- **Priority:** Fix in next sprint.

#### BUG-4: Unklare/widersprüchliche Spezifikation erzeugt keine Decision Card
- **Severity:** Medium
- **Steps to Reproduce:**
  1. `build_feature_plan` für ein Feature ohne verbleibende ABC-Phase (z. B. Status ohne erkannte nächste Phase) aufrufen.
  2. Erwartet laut Spec (Edge Case): Decision Card zur Klärung vor Start.
  3. Tatsächlich: nur `items: []` + Text-Warnung im Dialog; kein Card-Flow.
- **Priority:** Fix in next sprint.

#### BUG-5: Keine Kollisionsprüfung für parallele Schreibbereiche
- **Severity:** High
- **Steps to Reproduce:**
  1. Feature mit Backend- und Frontend-Paket planen (laufen laut `_PACKAGE_RANK` parallel).
  2. `write_scope` beider Pakete wird berechnet und im Plan-Dialog angezeigt, aber nie gegeneinander verglichen.
  3. Erwartet laut Spec (Edge Case): Serialisierung oder Kollisionswarnung bei Überlappung.
  4. Tatsächlich: keine Prüfung vorhanden — ein Overlap bliebe unbemerkt, bis zur Laufzeit ein echter Datei-Konflikt entsteht.
- **Priority:** Fix before deployment (steigt zu Critical, sobald Backend/Frontend regelmäßig dieselben Verzeichnisse berühren — aktuell durch Rollen-Konvention meist getrennt, aber nicht erzwungen).

#### BUG-6: Keine Unit-/Komponententests für die neuen Frontend-Komponenten
- **Severity:** Low
- **Steps to Reproduce:** `feature-plan-dialog.tsx` und `feature-run-view.tsx` haben keine `*.test.tsx`-Datei; nur das Backend hat `test_proj79_feature_coordinator.py`.
- **Priority:** Nice to have / vor Approved nachreichen.

### Summary
- **Acceptance Criteria:** 9/14 klar bestanden, 2 strukturell vorhanden aber nicht end-to-end verifiziert, 1 fehlerhaft implementiert (BUG-3), **1 durch BUG-1+BUG-2 praktisch unerreichbar**.
- **Bugs Found:** 6 total (2 Critical, 1 High, 2 Medium, 1 Low)
- **Security:** Keine neuen Lücken; ein ungetesteter Race-Fall (paralleles `/complete`) vermerkt.
- **Regression:** Backend 1267/1271 grün (4 Fehlschläge vorbestehend/unabhängig), Frontend 203/203 grün.
- **Production Ready:** **NO**
- **Recommendation:** BUG-1 + BUG-2 zuerst fixen (ohne sie ist „autonomer Abschluss" — das Kernversprechen des Features — nicht erreichbar), danach BUG-5 (Kollisionsschutz) vor Deploy. BUG-3/BUG-4/BUG-6 können in einem Folge-Zyklus behoben werden.

### Bugfix-Runde (2026-08-16)

Alle 6 gefundenen Bugs behoben, jeweils mit neuem Regressionstest verifiziert.

- **BUG-1 (Critical) → fixed.** `_start_package` hängt jetzt `_completion_instructions()` an den Skill-Prompt jeder Kind-Session an: expliziter `curl -X POST .../packages/{id}/complete`-Aufruf mit Payload-Vorlage (`coordinator.py`). Test: `test_started_package_prompt_contains_completion_curl`.
- **BUG-2 (Critical) → fixed.** `feature-run-view.tsx` hat jetzt ein Pflichtfeld „Durchgeführte Prüfung + Ergebnis", das bei „erfolgreich" einen `checks`-Eintrag mit `result` erzeugt; Submit-Button ist deaktiviert, solange Artefakte/Prüfung bei Erfolg fehlen (`successIncomplete`). Test: `test_ui_shaped_success_proof_with_check_is_accepted` (Backend, spiegelt exakt die neue UI-Payload).
- **BUG-3 (Medium) → fixed.** `_run_dict` addiert jetzt `child.liveness.auto_attempts` der laufenden Kind-Session zu `resume_attempts` (neuer Helper `_auto_attempts`) — automatische Watchdog-Reanimationen sind sichtbar, nicht nur manuelle Retries. Test: `test_resume_attempts_include_automatic_watchdog_reanimation`.
- **BUG-4 (Medium) → fixed (pragmatisch, kein neuer Decision-Card-Typ).** `build_feature_plan` unterscheidet jetzt „keine offene Arbeit mehr" (deployed/approved) von „nicht erkannter Status" (`status_maturity is None`) mit eigenem, eindeutigem Warntext zur Klärung. Eine echte Decision Card entfällt bewusst, weil vor dem Dispatch noch keine Koordinator-Session existiert, die eine Card hosten könnte (`FeatureDispatchRequest.items` verlangt ohnehin `min_length=1` — Dispatch mit leerem/unklarem Plan war schon vorher unmöglich). Test: `test_feature_plan_unrecognized_status_gets_distinct_warning`.
- **BUG-5 (High) → fixed.** Neue `_collision_warnings()`/`_scope_overlap()` in `build_feature_plan`: Pakete ohne Abhängigkeit zueinander (laufen laut `_PACKAGE_RANK` parallel) mit überlappendem `write_scope` erzeugen jetzt eine Plan-Warnung. Test: `test_feature_plan_warns_on_overlapping_parallel_write_scope`.
- **BUG-6 (Low) → fixed.** Smoke-Tests für beide neuen Frontend-Komponenten ergänzt (`feature-plan-dialog.test.tsx`, `feature-run-view.test.tsx`, Pattern wie `gantt-chart.test.tsx`: `renderToStaticMarkup`, kein jsdom).

**Regression nach Fixes:** Backend 1273/1276 grün (dieselben 3 vorbestehenden, PROJ-79-unabhängigen Fehlschläge in `test_proj50_codex_abc.py`), Frontend 205/205 grün (26 Suiten), `tsc --noEmit` keine neuen Fehler durch diese Änderungen.

**Production Ready: Backend/Logik jetzt JA** (kein Blocker mehr für „autonomer Abschluss"/Kollisionsschutz). Offen für ein vollständiges „Approved": End-to-End-Verifikation mit echtem laufendem Backend + echter Spezialisten-Session (bestätigt, dass der eingebettete `curl`-Aufruf in der realen Sandbox tatsächlich ausgeführt wird) sowie ein echter Prozess-Neustart-Test für AC „Wiederherstellung nach Backend-/Host-Neustart" — beides war in dieser Runde nur Code-Review/Unit-Test, kein Live-Lauf.

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

## Frontend Implementation (abc-frontend)

**Branch:** main · **Status:** Done · **Datum:** 2026-08-16

Anpassung des Koordinator-Tabs (`nextjs_app/components/cockpit/coordinator/`) an das
Next.js-Cockpit (nicht Flutter — Tech-Design nutzt das bestehende shadcn-Pattern):

- `coordinator-panel.tsx` — Modus-Umschalter **[Feature] / [Flotte (bestehend)]**;
  Feature-Modus mit Projektpfad + Feature-ID-Autocomplete gegen `features/INDEX.md`
  (datalist) und „Plan erstellen". Feature-Läufe werden aus dem globalen Session-Poll
  abgeleitet (`is_feature_run`) und als `FeatureRunView` gerendert.
- `feature-plan-dialog.tsx` — Fork von `DispatchPlanDialog`: lädt den internen Plan via
  `POST /coordinator/feature-plan`, zeigt interne Arbeitspakete (Rolle/Skill/Engine,
  Schreibbereich, Abschlussbeleg, Abhängigkeiten) und erlaubt pro Paket Engine/Modell zu
  überschreiben; Freigabe dispatches `POST /coordinator/feature-dispatch`.
- `feature-run-view.tsx` — Elternkopf (Feature-ID, Gesamtzustand, Fortschritt, Pause) +
  Paketliste (Status, Session-Link, Abschlussbeleg) + genau eine Blockierungs-Decision-Card
  (retry / manual / abort) + pro Paket „Abschluss manuell melden" (strukturierter Beleg via
  `POST /coordinator/features/{id}/packages/{pkg}/complete`). Pollt `GET /coordinator/features/{id}`.
- `lib/types.ts` / `lib/api.ts` — Typen (`FeaturePlan`, `FeatureRun`, `FeaturePackageRead`,
  `CompletionProof`) und Client (`getFeaturePlan`, `dispatchFeature`, `getFeatureRun`,
  `setFeaturePaused`, `featureDecision`, `completePackage`); `Session` um `is_feature_run`/`feature_id`.

Bekannte Grenze: pro-Paket-Modellwechsel *nach* dem Start (nur im Plan-Dialog überschreibbar)
folgt, sobald das Backend einen Paket-Reassign-Endpunkt bietet (siehe tech-design Nicht-Ziele).
