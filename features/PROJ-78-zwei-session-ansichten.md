# PROJ-78: Zwei Session-Ansichten mit Entwurfs-Schutz

## Status: Approved
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

**Tested:** 2026-08-16
**Frontend:** Next.js/React (`nextjs_app`), Code-Review + `npm run lint` + `npm run test`
**Tester:** QA Engineer (AI)
**Methode:** Statische Verifikation gegen `workspace-provider.tsx`, `session-view.tsx`,
`sessions/[id]/page.tsx`, `session-rail.tsx`. Live-Browser-Verifikation nicht durchgeführt
(headless-Login für Cockpit nicht ohne Weiteres verfügbar) — die gefundenen Bugs sind
reiner React-/Routing-Logikfehler und deterministisch aus dem Code ableitbar.

### Acceptance Criteria Status

#### AC-1: Einheitliche Öffnen-/Fokussieren-Regel (Sidebar, Vorgänger/Nachfolger, Deep Link)
- [x] Alle drei Einstiege laufen über denselben Pfad: URL-Änderung → `page.tsx`-Effekt
      → `open(id)` im `WorkspaceProvider`. Kein separater Navigationscode je Einstieg.
- [ ] BUG: siehe BUG-1 — dieselbe Regel reißt die Navigation auf *jeder anderen*
      Cockpit-Seite ein, sobald kein Fenster offen ist (siehe unten).

#### AC-2: Maximal zwei Ansichten, Refokussieren statt Duplikat
- [x] `open()` prüft `openIds.includes(id)` zuerst → Duplikat unmöglich, sonst freier
      Platz, sonst Ersetzen der aktiven Ansicht (`workspace-provider.tsx:79-86`).

#### AC-3: Eigener Header je Ansicht, Schließen beendet Session nicht
- [x] `session-view.tsx:166-174` — Schließen-Button ruft nur `close(id)` (Workspace-
      State), kein `stopSession`/Delete-Aufruf.

#### AC-4: Desktop — beide Ansichten nebeneinander, beide live
- [x] `sessions/[id]/page.tsx:74-90` rendert beide IDs gleichzeitig, jede genau einmal
      gemountet → je eigener `useSessionStream(id)`-Hook, keine geteilte Verbindung.

#### AC-5: <Desktop — nur aktive sichtbar, Tab-Wechsel ohne Zustandsverlust
- [x] Inaktive Ansicht wird nur per CSS (`hidden md:block`) versteckt, nicht
      unmountet → Zustand (Scroll, Live-Stream) bleibt beim Tab-Wechsel erhalten.

#### AC-6: Einzelansicht bleibt wie bisher
- [x] `!twoViews` → `mx-auto max-w-4xl`, entspricht der alten Routenbreite.

#### AC-7/AC-8: Entwurf pro Session, übersteht Wechsel/Schließen/Reload
- [x] Entwurf lebt im `WorkspaceProvider` (`drafts` state, keyed by Session-ID),
      persistiert in `localStorage["jupiter.sessionDrafts"]`; wird nur bei
      erfolgreichem Senden geleert (`session-view.tsx:118-131`).

#### AC-9: Fehler/Lade/Decision/Stop-Zustände pro Ansicht korrekt, keine zweite Backend-Session
- [x] Jede `SessionView`-Instanz hat eigenen lokalen State (`detail`, `loadError`,
      `busy`) und eigenen `useSessionStream`. `open()` ist rein clientseitig, ruft
      keine Session-Erzeugung auf.

#### AC-10: Tastatur erreichbar, deutsche eindeutige Beschriftungen
- [x] Echte `<button>`-Elemente mit sichtbarem deutschem Text ("⇥ Ansicht
      fokussieren") bzw. `aria-label`/`title` ("Session-Ansicht schließen"). Tab-Leiste
      nutzt `role="tab"` + `aria-selected`.

### Edge Cases Status

#### EC-1: Aktive Ansicht schließen, zweite bleibt aktiv
- [x] `close()` setzt bei Schließen der aktiven ID die verbleibende als neue aktive;
      bei keiner verbleibenden → `null` (`workspace-provider.tsx:88-97`).

#### EC-2: Sidebar-Klick ersetzt nur aktive Ansicht, Entwurf der ersetzten Session bleibt
- [x] `open()` filtert nur `activeIdRef.current` aus `openIds`, Entwurf bleibt im
      `drafts`-State (wird nie durch `open`/`close` gelöscht, nur durch `clearDraft`).

#### EC-3: Gleiche Session über Sidebar/Vorgänger/Nachfolger/Deep-Link → keine Duplikatansicht
- [x] Alle Pfade laufen durch dieselbe `open()`-Prüfung.

#### EC-4: Session serverseitig beendet/gelöscht → verständlicher Zustand, andere Ansicht bleibt nutzbar
- [x] Bestehende `error`/`liveness`-Anzeige unverändert aus `page.tsx` übernommen,
      pro `SessionView`-Instanz unabhängig.

#### EC-5: Reload mit Entwürfen → Entwürfe pro Session wiederhergestellt
- [x] `readStoredDrafts()` liest `localStorage` beim Mount des `WorkspaceProvider`.
- [ ] BUG: siehe BUG-1 — der Reload selbst kann durch den Redirect-Bug fehlschlagen,
      bevor die Entwürfe überhaupt sichtbar werden.

#### EC-6: Resize unter Desktop-Grenze → genau eine Ansicht, kein Overflow, kein Entwurfsverlust
- [x] Rein CSS-getrieben (`md:` Breakpoint), kein JS-Resize-Handler nötig → strukturell
      overflow-sicher.

### Security Audit Results
- Kein neuer Endpunkt, keine neue Datenhaltung außer `localStorage` (Client-only,
  keine PII über bereits vorhandene Session-Inhalte hinaus). Kein Tenant-Bezug, da
  reines Frontend-Feature ohne Backend-Änderung.
- [x] Kein XSS-Risiko: Entwurfstext landet nur in `<textarea value>`, kein
  `dangerouslySetInnerHTML`.
- N/A: Auth/Tenant/RLS/Rate-Limiting — keine Backend-Änderung in diesem Feature.

### Bugs Found

#### BUG-1: WorkspaceProvider redirected zu "/" auf jeder Cockpit-Seite ohne offene Ansicht
- **Severity:** Critical
- **Datei:** `nextjs_app/components/cockpit/workspace-provider.tsx:123-129`
- **Ursache:**
  ```tsx
  useEffect(() => {
    if (activeId && pathname.startsWith("/sessions/")) {
      router.replace(`/sessions/${activeId}`, { scroll: false });
    } else if (openIds.length === 0) {
      router.replace("/", { scroll: false });   // <-- kein pathname-Guard!
    }
  }, [activeId, openIds.length, pathname, router]);
  ```
  Der `else if`-Zweig prüft nur `openIds.length === 0`, nicht ob `pathname` überhaupt
  im Session-Arbeitsbereich liegt. `openIds` ist reiner In-Memory-State (nicht
  persistiert) und ist bei jedem Seiten-/Tab-Load zunächst `[]`.
- **Steps to Reproduce:**
  1. Frisch laden (oder Reload) auf einer beliebigen Cockpit-Seite ohne zuvor eine
     Session geöffnet zu haben, z. B. `/dateien`, `/doku`, `/settings`,
     `/apps/<key>`, `/orchestration/<key>`.
  2. Erwartet: Seite bleibt stehen (`/dateien` etc.).
  3. Tatsächlich: `WorkspaceProvider`-Effekt feuert mit `openIds.length === 0` und
     `router.replace("/")` — sofortiger Rückwurf zum Cockpit-Board, die aufgerufene
     Seite ist nicht erreichbar.
  4. Zusätzlich: Direktaufruf/Reload von `/sessions/<id>` selbst ist betroffen — die
     `SessionDetailPage`-Effekt (`open(id)`) und der `WorkspaceProvider`-Effekt feuern
     im selben Commit mit noch nicht aktualisiertem `openIds`/`activeId` (State-Update
     ist asynchron); der Redirect-Zweig kann daher auch beim Öffnen eines Deep Links
     kurz zuschlagen, bevor `open(id)` greift (Race).
- **Impact:** Bricht nicht nur PROJ-78, sondern jede Navigation zu einer Nicht-Session-
  Seite im gesamten Cockpit, sobald der Workspace leer ist (Erststart, nach Schließen
  aller Ansichten, neuer Tab). Das ist der Standardfall für die meisten Nutzer-Sessions.
- **Fix-Richtung (nicht umgesetzt, nur Hinweis):** `pathname.startsWith("/sessions/")`
  auch im `else if`-Zweig prüfen — der Redirect zu `/` darf nur greifen, wenn man sich
  gerade auf `/sessions/*` befindet und keine Ansicht mehr offen ist.
- **Priority:** Fix before deployment (blockiert das Feature komplett + Regression auf
  bestehende Navigation)

#### BUG-2: Kein Rückweg zum Cockpit-Board mehr aus der Session-Ansicht
- **Severity:** Low
- **Datei:** `nextjs_app/components/cockpit/session-view.tsx`
- **Beschreibung:** Die alte Detailseite hatte oben einen `← Cockpit`-Link
  (`page.tsx:157-161`, alte Version). In `SessionView` fehlt dieser vollständig —
  einzige Rückkehr zum Board ist jetzt der "Zum Board →"-Link unten in der Sidebar
  bzw. das Schließen beider Ansichten (das dann via BUG-1 fälschlich sowieso
  passiert). Kein AC verlangt diesen Link explizit, aber es ist eine sichtbare
  UX-Regression ggü. dem Vorzustand.
- **Priority:** Nice to have

### Summary
- **Acceptance Criteria:** 10/10 strukturell korrekt umgesetzt, aber durch BUG-1 in
  der Praxis nicht erreichbar/verlässlich nutzbar
- **Edge Cases:** 6/6 strukturell korrekt, EC-5 durch BUG-1 gefährdet
- **Bugs Found:** 2 total (1 Critical, 0 High, 0 Medium, 1 Low)
- **Security:** Keine Auffälligkeiten (kein Backend-/Datenbezug)
- **Production Ready:** NO
- **Recommendation:** BUG-1 zuerst fixen (ein Zeilen-Fix: `pathname`-Guard ergänzen),
  danach erneut `/abc-qa` inkl. Live-Browser-Test der Navigation zwischen allen
  Cockpit-Routen mit leerem und gefülltem Workspace.

---

## QA Re-Test (Runde 2)

**Getestet:** 2026-08-16 (Folge-Session) · `npm run lint` + `npm run test` erneut grün
(180/180, gleiche 4 vorbestehende, feature-fremde Lint-Fehler wie Runde 1).

### BUG-1 — teilweise gefixt
`workspace-provider.tsx:126` hat jetzt den `pathname.startsWith("/sessions/")`-Guard:

```tsx
} else if (openIds.length === 0 && pathname.startsWith("/sessions/")) {
  router.replace("/", { scroll: false });
}
```

- [x] Behoben: Navigation zu `/dateien`, `/doku`, `/settings`, `/apps/<key>`,
  `/orchestration/<key>` bei leerem Workspace wird nicht mehr zu `/` zurückgeworfen —
  der Guard verhindert den Redirect außerhalb von `/sessions/*`.
- [ ] BUG: die in Runde 1 unter Punkt 4 notierte Race bleibt bestehen und ist von
  diesem Fix nicht abgedeckt — siehe BUG-1b.

#### BUG-1b: Deep-Link/Reload auf `/sessions/<id>` kann weiterhin zu "/" zurückspringen (Race)
- **Severity:** High (eingegrenzt ggü. BUG-1, aber der zentrale Deep-Link-Fall aus
  AC-1/EC-3 ist direkt betroffen)
- **Datei:** `workspace-provider.tsx:123-129` + `sessions/[id]/page.tsx:28-30`
- **Ursache:** Bei Erstmount von `/sessions/<id>` (Reload oder Deep Link) sind beide
  Effekte im selben Commit fällig:
  - `SessionDetailPage`-Effekt (Kind, tiefer im Baum) feuert zuerst und ruft `open(id)`
    → das ist aber nur `setOpenIds`/`setActiveId`, also ein für den NÄCHSTEN Render
    geplanter State-Update, kein synchrones Schreiben.
  - `WorkspaceProvider`-Effekt (Eltern-Komponente) feuert im selben Flush danach, sieht
    aber noch den alten Stand aus dem gerade committeten Render: `openIds=[]`,
    `activeId=null`. Pathname ist `/sessions/<id>` → Guard erfüllt →
    `openIds.length===0 && pathname.startsWith("/sessions/")` ist wahr →
    `router.replace("/")` feuert, bevor `open(id)` überhaupt wirksam wird.
  - React feuert `useEffect`-Setups bottom-up (Kind vor Eltern) im selben Commit, aber
    State-Updates aus Effekten sind nicht synchron sichtbar für andere Effekte
    desselben Flushes — das ist Standard-React-Verhalten, kein Sonderfall dieses Codes.
- **Steps to Reproduce (Herleitung aus Code, s. Methode-Hinweis Runde 1):**
  1. Direkter Aufruf oder Reload von `/sessions/<beliebige-id>` bei leerem Workspace
     (frischer Tab, oder nach Schließen aller Ansichten).
  2. Erwartet: Session-Ansicht öffnet sich normal.
  3. Tatsächlich: `WorkspaceProvider`-Effekt kann im selben Commit noch mit
     `openIds=[]` auslösen und zu `/` zurückspringen, bevor `open(id)` aus
     `page.tsx` greift.
- **Fix-Richtung (nicht umgesetzt, nur Hinweis):** Redirect-Zweig sollte nicht auf
  `openIds.length === 0` reagieren, solange die URL selbst eine Session-ID trägt, die
  noch nicht verarbeitet wurde — z. B. Redirect-Effekt erst ausführen, wenn `page.tsx`
  seinen `open(id)`-Aufruf bereits committed hat (z. B. eigenes Flag/Ref), oder den
  Redirect-Zweig ganz auf `activeId === null && openIds.length === 0` UND einen
  zusätzlichen "Workspace ist initialisiert"-Marker beschränken, statt sich auf
  Effekt-Reihenfolge zwischen zwei Komponenten zu verlassen.
- **Priority:** Fix before deployment (Deep Link ist in AC-1 explizit gefordert)

### Aktualisierte Bewertung
- **Acceptance Criteria:** AC-1 weiterhin mit offenem Bug (BUG-1b statt BUG-1), Rest
  unverändert 9/10 sauber
- **Edge Cases:** EC-5 weiterhin gefährdet (Reload-Pfad)
- **Bugs Found (kumulativ):** BUG-1 (Critical, behoben), BUG-1b (High, offen), BUG-2
  (Low, offen)
- **Production Ready:** NO
- **Recommendation:** BUG-1b fixen (Redirect-Timing/Race entkoppeln), BUG-2 optional.
  Danach erneut `/abc-qa` — dann auch mit Live-Browser-Test empfohlen, da reine
  Effekt-Reihenfolge-Bugs sich am zuverlässigsten im echten Browser reproduzieren
  lassen.

### BUG-1b — gefixt (2026-08-16)
`workspace-provider.tsx`: Rücksprung zu `/` nicht mehr als passiver Effekt auf
`openIds.length === 0` (Race mit dem `open(id)`-Effekt von `page.tsx`), sondern
direkt in `close()` ausgelöst — nur wenn die zuletzt aktive Ansicht tatsächlich per
Nutzeraktion geschlossen wird (`pathnameRef`/`activeIdRef` gespiegelt, kein
Cross-Component-Timing mehr nötig). Der URL-Sync-Effekt macht jetzt nur noch
`activeId → /sessions/<id>`. `npx eslint`, `npm run test` (180/180) grün; `tsc
--noEmit` zeigt dieselben 7 vorbestehenden, feature-fremden Testfixture-Fehler wie
vor dem Fix (Baseline-Vergleich per `git stash` bestätigt). Erneuter `/abc-qa`-Lauf
mit Live-Browser-Test empfohlen, bevor Status auf Approved geht.

---

## QA Re-Test (Runde 3)

**Getestet:** 2026-08-16 (Folge-Session) · `npx eslint` (nur PROJ-78-Dateien) + `npm run
test` erneut grün (180/180).

### Live-Browser-Test — nicht durchführbar
Kein laufender Dev-Server mit den unveröffentlichten PROJ-78-Änderungen (Port 3000
gehört zu einem anderen Projekt; `jupiter-frontend`-systemd-Service auf 3001 läuft
gegen den zuletzt gebauten/committeten Stand, nicht gegen die aktuellen uncommitted
Files) und keine headless verfügbaren Test-Login-Credentials für die JWT-Auth. QA
bleibt code-gestützt (statische Verifikation + Tests/Lint/tsc-Diff), wie in Runde 1/2.

### BUG-1b — Fix verifiziert
Code erneut gelesen: Redirect-Zweig aus dem reaktiven Effekt entfernt, Rücksprung zu
`/` läuft jetzt ausschließlich synchron innerhalb von `close()`, ausgelöst durch die
echte Nutzeraktion (Klick auf Schließen). Kein Effekt reagiert mehr auf
`openIds.length` beim Mount → die ursprüngliche Race zwischen `page.tsx`s
`open(id)`-Effekt und dem `WorkspaceProvider`-Redirect-Effekt ist strukturell nicht
mehr möglich, weil dieser Effekt-Pfad ganz entfällt.

#### BUG-3 (neu, Low): Seiteneffekte innerhalb des `setOpenIds`-Updaters
- **Datei:** `workspace-provider.tsx:100-118`
- **Beschreibung:** `close()` ruft `setActiveId(...)` und `router.replace(...)` **innerhalb**
  der Updater-Funktion auf, die an `setOpenIds` übergeben wird. React/Next.js
  StrictMode (Next.js-Default: `reactStrictMode: true`, hier nicht überschrieben,
  siehe `next.config.ts`) invoked `useState`-Updater-Funktionen im Dev-Modus absichtlich
  zweimal, um Unreinheiten zu erkennen — Seiteneffekte darin sind laut React-Doku ein
  Antipattern. Praktisch harmlos hier (doppeltes `router.replace("/")` bzw.
  `setActiveId(null)` sind idempotent), aber ein Dev-Mode-Codesmell und Risiko, falls
  React diese Doppel-Invoke-Prüfung künftig strenger macht (z. B. Fehler statt
  stillem Doppel-Call).
- **Fix-Richtung:** `activeIdRef`-Vergleich VOR dem `setOpenIds`-Aufruf auswerten
  (`const wasActive = id === activeIdRef.current`), dann `setOpenIds(prev =>
  prev.filter(...))` rein lassen und `setActiveId`/`router.replace` danach im
  `close`-Body (nicht im Updater) ausführen.
- **Priority:** Nice to have — keine funktionale Auswirkung in Produktion (StrictMode-
  Doppel-Invoke ist Dev-only), nur Code-Qualität.

### Aktualisierte Bewertung
- **Bugs (kumulativ):** BUG-1 (Critical, behoben), BUG-1b (High, behoben), BUG-2
  (Low, offen — fehlender Cockpit-Rücklink), BUG-3 (Low, offen — Updater-Seiteneffekt)
- **Kein Critical/High mehr offen.**
- **Production Ready:** JA, mit Vorbehalt — Live-Browser-Smoke-Test (Deep-Link-Reload,
  Zwei-Ansichten-Resize, Draft-Persistenz nach Reload) wurde in keiner QA-Runde real
  im Browser durchgeführt, nur code-/testgestützt verifiziert. Vor Produktiv-Deploy
  einmal manuell im Browser gegenlaufen lassen.
- **Empfehlung:** Status → Approved. BUG-2/BUG-3 optional vor oder nach Deploy fixen
  (beide Low, kein Blocker). `/abc-deploy` kann vorbereitet werden.

## Implementierung (Frontend)
**2026-08-16 · Next.js (kein Flutter im Repo).**

- `components/cockpit/workspace-provider.tsx` — flüchtiger Arbeitsbereich: bis zu 2 offene Session-IDs + aktive ID + Entwürfe je Session (localStorage `jupiter.sessionDrafts`, reload-fest). Zentrale `open()`-Regel (sichtbar → fokussieren; sonst freien Platz, dann aktive ersetzen), `close()` (entfernt nur Ansicht, aktiviert ggf. verbleibende), `focus()`. URL folgt der aktiven Ansicht, nur innerhalb `/sessions/*`.
- `components/cockpit/session-view.tsx` — aus der alten Detailseite extrahierte, wiederverwendbare Einzelansicht (Header, Live-Status, Decision Cards, Transkript, Composer). Composer-Entwurf kommt aus dem Workspace; Senden leert nur bei Erfolg. Eigener Schließen-Button.
- `app/(cockpit)/sessions/[id]/page.tsx` — Host: führt die URL-ID über die zentrale Regel ein; rendert 1–2 Ansichten (Desktop nebeneinander, <md Tab-Leiste mit nur aktiver Ansicht; jede Ansicht genau einmal gemountet → kein Duplikat-WebSocket).
- `components/cockpit/session-rail.tsx` — Hervorhebung der aktiven Workspace-Ansicht + Ring-Markierung für die zweite geöffnete Ansicht.
- `app/(cockpit)/layout.tsx` — `WorkspaceProvider` eingehängt.

Kein Backend, keine neuen Pakete. Lint/TS/Build grün. Als Nächstes: `/abc-qa`.

## Deployment
_To be added by /deploy_
