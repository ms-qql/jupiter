# PROJ-78: Zwei Session-Ansichten mit Entwurfs-Schutz

## Status: Architected
**Created:** 2026-08-16
**Last Updated:** 2026-08-16

## Dependencies
- Requires: PROJ-3 (Cockpit: Mission Control + Kanban)
- Requires: PROJ-14 (Session-Persistenz)

## Ziel

Die Session-Ansicht soll nicht mehr verlassen werden müssen, wenn parallel etwas
in einer zweiten Agenten-Session nachzusehen oder zu bearbeiten ist. Ein noch
nicht gesendeter Entwurf darf dabei nicht verloren gehen.

## User Stories

- Als Nutzer möchte ich aus der linken Session-Sidebar eine zweite Session zusätzlich öffnen, damit ich zwischen zwei Arbeitskontexten wechseln kann.
- Als Nutzer möchte ich auf einem Desktop beide geöffneten Sessions nebeneinander sehen, damit ich Informationen direkt vergleichen oder übertragen kann.
- Als Nutzer möchte ich auf einem kleineren Bildschirm jeweils genau eine der beiden Sessions sehen und per Tab wechseln, damit der Inhalt lesbar bleibt.
- Als Nutzer möchte ich eine der beiden Ansichten schließen und anschließend wieder eine andere Session öffnen, damit ich den zweiten Platz flexibel nutzen kann.
- Als Nutzer möchte ich beim Wechseln, Schließen und erneuten Öffnen einer Session meinen ungesendeten Text wiederfinden, damit Recherche keine Arbeit zerstört.

## Acceptance Criteria

- [ ] Die Session-Sidebar ist die primäre Navigation für Sessions. Sidebar-, Vorgänger-/Nachfolger- und Deep-Link-Einstiege verwenden dieselbe Öffnen-/Fokussieren-Regel: Eine nicht sichtbare Session belegt eine freie zweite Ansicht; sind bereits zwei Ansichten geöffnet, ersetzt sie die aktuell aktive Ansicht.
- [ ] Es können maximal zwei unterschiedliche Session-Ansichten gleichzeitig geöffnet sein. Wird eine bereits sichtbare Session gewählt, erhält diese den Fokus statt doppelt geöffnet zu werden.
- [ ] Jede geöffnete Ansicht zeigt einen eigenen Session-Header mit Titel und Schließen-Aktion. Das Schließen beendet oder verändert die Agenten-Session nicht, sondern entfernt nur ihre Ansicht.
- [ ] Auf Viewports ab Desktop-Breite werden zwei geöffnete Ansichten gleichwertig nebeneinander angezeigt; beide bleiben bedienbar und erhalten ihre Live-Aktualisierung.
- [ ] Unterhalb der Desktop-Breite wird nur die aktive Ansicht angezeigt. Ein klarer Umschalter zeigt beide geöffneten Sessions und wechselt ohne Seitenverlust zwischen ihnen.
- [ ] Bei nur einer geöffneten Ansicht bleibt die bestehende Einzelsitzungsdarstellung erhalten; der zweite Platz wird erst nach dem Öffnen einer weiteren Session sichtbar.
- [ ] Der Composer-Entwurf ist pro Session getrennt. Ein Wechsel zwischen Ansichten oder zur Sidebar verwirft keinen Entwurf.
- [ ] Ein Entwurf bleibt auch erhalten, wenn seine Ansicht geschlossen und später in derselben Browser-Installation erneut geöffnet wird; erst erfolgreiches Senden oder explizites Leeren entfernt ihn.
- [ ] Fehler-, Lade-, Decision-Card- und Stopp-Zustände einer Session bleiben pro Ansicht korrekt; das Öffnen einer zweiten Ansicht erzeugt keine zweite Agenten- oder Backend-Session.
- [ ] Alle Bedienelemente sind per Tastatur erreichbar und haben deutsche, eindeutige Beschriftungen für Öffnen, Wechseln und Schließen.

## Edge Cases

- Die aktuell aktive Ansicht wird geschlossen, während eine zweite offen ist → die verbleibende Ansicht wird aktiv; bei keiner verbleibenden Ansicht erscheint die normale Cockpit-Ansicht.
- Eine Session wird in der Sidebar gewählt, obwohl zwei Ansichten offen sind und eine davon einen ungesendeten Entwurf enthält → nur die aktive Ansicht wird ersetzt; der Entwurf der ersetzten Session bleibt erhalten.
- Die gleiche Session wird über Sidebar, Vorgänger-/Nachfolger-Link oder einen Deep Link gewählt → keine Duplikatansicht; die vorhandene Ansicht wird fokussiert.
- Eine geöffnete Session wird serverseitig beendet oder gelöscht → die Ansicht zeigt den bestehenden End-/Fehlerzustand bzw. einen verständlichen Hinweis; die andere Ansicht bleibt nutzbar.
- Der Browser wird neu geladen, während Entwürfe existieren → Entwürfe werden pro Session wiederhergestellt; ob die zweite Ansicht selbst wiederhergestellt wird, ist nicht Teil dieses Features.
- Der verfügbare Bereich wird beim Resize unter die Desktop-Grenze verkleinert → es bleibt genau eine Ansicht sichtbar, ohne horizontalen Overflow oder Verlust des jeweils anderen Entwurfs.

## Scope und Nicht-Ziele

- Keine neue Engine-Session, keine Backend-API, keine Datenbank- oder Vault-Persistenz.
- Keine frei verschiebbaren, in der Größe veränderbaren oder unbegrenzt vielen Tabs.
- Keine Synchronisierung ungesendeter Entwürfe zwischen Geräten oder Browser-Profilen.
- Kein automatisches Senden oder Zusammenführen von Entwürfen.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-16 · **Stack:** Next.js/React + bestehende FastAPI-Session-API · **Branch:** dev

### A) Komponentenstruktur

```
Cockpit-Layout (bestehend)
├── Session-Arbeitsbereichszustand (neu, clientseitig)
│   ├── offene Session-IDs (maximal zwei)
│   ├── aktive Session-ID
│   └── Entwürfe pro Session
└── Cockpit-Shell (bestehend)
    ├── Session-Sidebar (bestehend, an Arbeitsbereich angebunden)
    └── Session-Arbeitsbereich (neu)
        ├── Tab-Leiste (unter Desktop-Breite)
        ├── Session-Ansicht A
        │   └── bestehende Session-Detailansicht mit Header, Live-Status, Transkript und Composer
        └── Session-Ansicht B (optional)
            └── dieselbe bestehende Session-Detailansicht
```

Die bisher routegebundene Detailansicht wird als wiederverwendbare Session-Ansicht
bereitgestellt und der Arbeitsbereich kann sie ein- oder zweimal gleichzeitig
mounten. Sein zentraler Öffnen-/Fokussieren-Vorgang verhindert Dubletten, nutzt
den freien Platz und ersetzt sonst die aktive Ansicht. Das Schließen entfernt
nur lokal eine Ansicht.

Die Sidebar ist der primäre Einstieg. Auch Vorgänger-/Nachfolger-Aktionen in
einer Session und direkte URLs nutzen denselben zentralen Vorgang. So können
sie weder eine bestehende Ansicht duplizieren noch den zweiten Arbeitsbereich
durch eine vollständige Seitennavigation verlieren.

### B) Datenmodell

Es gibt keine Server-Datenänderung.

Der Browser hält nur flüchtigen Arbeitsbereichszustand:

- bis zu zwei geöffnete Session-IDs;
- die aktive Session-ID;
- einen ungesendeten Entwurf je Session-ID.

Die bestehende Fokus-Information für andere Cockpit-Bereiche wird aus der
aktiven Workspace-Ansicht gespeist. Die Session-Liste hebt diese aktive Ansicht
hervor und kann zusätzlich kenntlich machen, welche Session bereits als zweite
Ansicht geöffnet ist.

Die Entwürfe werden im lokalen Browser-Speicher abgelegt. Damit überstehen sie
Ansichtswechsel, das Schließen einer Ansicht und einen Browser-Reload, sind aber
bewusst nicht zwischen Geräten geteilt.

### C) Routing und API-Form

`/sessions/<id>` bleibt der kanonische Deep Link der aktiven Session. Beim
direkten Aufruf wird `<id>` über denselben zentralen Öffnen-/Fokussieren-Vorgang
in den Arbeitsbereich übernommen. Die zweite Session bleibt bewusst reine
Browser-Ansicht; ihre Wiederherstellung nach einem Reload ist nicht Teil des
Features.

Die bisherige Einzel-Session-Route wird zum Host für den Arbeitsbereich, nicht
mehr zur einzigen Instanz einer Detailansicht. Dadurch können zwei Detailansichten
gleichzeitig erscheinen, obwohl die URL weiterhin nur die aktive Session zeigt.

Keine neuen Endpunkte und keine Änderungen an bestehenden Endpunkten.

Jede sichtbare Session-Ansicht verwendet unverändert ihre vorhandenen
Session-Daten und ihren Live-Stream. Zwei verschiedene sichtbare Sessions haben
damit jeweils genau eine bestehende Live-Verbindung; dieselbe Session darf nicht
doppelt geöffnet werden.

### D) Verhalten und Responsivität

- Desktop: Eine Ansicht nutzt den bisherigen Arbeitsbereich; bei zwei Ansichten
  stehen beide gleich breit nebeneinander.
- Kleiner Bildschirm: Nur die aktive Ansicht ist sichtbar. Eine einfache
  Tab-Leiste wechselt zwischen den zwei offenen Sessions, ohne ihren Zustand zu
  verlieren.
- Öffnen: Eine noch nicht sichtbare Session belegt zuerst den freien Platz,
  danach ersetzt sie die aktive Ansicht. Eine bereits sichtbare Session wird nur
  fokussiert. Die kanonische URL folgt der aktiven Ansicht.
- Navigation: Sidebar und Vorgänger-/Nachfolger-Aktionen rufen dieselbe
  Öffnen-/Fokussieren-Regel auf; sie dürfen nicht mehr lediglich eine neue
  Einzel-Session-Seite laden.
- Hervorhebung: Die Session-Liste richtet ihre aktive Markierung nach der
  Workspace-Ansicht und nicht mehr ausschließlich nach der URL aus.
- Schließen: Entfernt ausschließlich die Ansicht. Die Agenten-Session läuft
  unverändert weiter und ihr Entwurf bleibt im Browser erhalten.
- Senden: Ein erfolgreich gesendeter Entwurf wird für genau diese Session
  gelöscht; bei einem Sendefehler bleibt er erhalten.

### E) Tech-Entscheidungen

1. **Frontend-only statt neuer Session-/Tab-API.** Die Engine kennt bereits
   Sessions und ihre Live-Verbindungen. Der Wunsch betrifft nur deren Anzeige;
   ein Servermodell für zwei lokale Ansichten wäre doppelte Zustandsführung ohne
   Nutzen.
2. **Vorhandene Detailansicht wiederverwenden.** Sie enthält bereits Composer,
   Decision Cards, Transkript und Live-Status. Dadurch bleiben Verhalten und
   Fehlerbehandlung in einer einzigen Darstellung konsistent.
3. **Maximal zwei feste Ansichten.** Das erfüllt den Bedarf nach Nachschlagen
   ohne einen frei konfigurierbaren Tab-Manager einzuführen.
4. **Lokaler Entwurfsspeicher pro Session.** Der aktuelle Composer-State wird
   beim Routenwechsel zerstört. Browser-Speicher löst genau diesen Datenverlust,
   ohne Entwürfe in den Vault oder die Datenbank zu schreiben.
5. **Vorhandenes Responsive-Muster übernehmen.** Wie im Fileexplorer wird auf
   kleinen Breiten umgeschaltet statt zwei Inhalte zusammenzuquetschen.
6. **Eine kanonische URL, ein lokaler zweiter Platz.** Die bestehende
   `/sessions/<id>`-URL bleibt für Lesezeichen und direkte Aufrufe erhalten.
   Der zweite Platz ist absichtlich nicht routbar: Das vermeidet ein neues
   Routing-Schema für einen Zustand, dessen Wiederherstellung nicht gefordert ist.
7. **Alle Session-Einstiege zentralisieren.** Sidebar und
   Vorgänger-/Nachfolger-Verweise erhalten dieselbe Öffnen-/Fokussieren-Regel.
   Das beseitigt den heutigen Widerspruch zwischen direkten Links und zwei
   parallelen Ansichten.

### F) Abhängigkeiten

Keine neuen Pakete, keine Backend-, Datenbank- oder Storage-Abhängigkeiten.

Wiederverwendet werden Cockpit-Shell und Session-Sidebar, der zentrale
Sessions-Provider, die bestehende Session-Detailansicht sowie das bereits im
Projekt verwendete sichere Browser-Speicher-Muster.

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
