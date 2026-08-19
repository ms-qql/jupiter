# Frontdesk-Checks — 2026-08-11

Quelle: Peppermint-Ticket (Auxevo Support / Freshdesk #147, Peppermint-ID `1abed67d-c64e-441a-98fe-b5192e30dee1`).
Interne Ersteinschätzung, kein QA-Ergebnis.

**Übersicht:** Kalender-Refresh zwischen Nutzern (Beata→Firat) → Übergreifendes Problem → Niedrig

---

### Ticket: Neue Termine von Beata erscheinen bei Firat erst nach manuellem F5

**Kurzbefund:** Übergreifendes Problem

**Eingrenzung:** Schicht: Frontend · Modul: Kalender (PROJ-9/PROJ-88, `appointments_screen.dart`, `AppointmentStore`)
PROJ-88 liefert nur stillen Fenster-Refresh/optimistischen Abgleich für den eigenen Client; Live-Sync zwischen unterschiedlichen Nutzern (WebSocket/Push) steht laut `docs/architektur.md` Zeile 223 explizit noch als offener Roadmap-Punkt aus — kein Einzelfall, jeder Nutzer mit geteiltem Kalender trifft das gleiche Verhalten.

**Dringlichkeit:** Niedrig
Randfunktion (Anzeige-Aktualität, kein Datenverlust/-integritätsrisiko), Workaround vorhanden (F5), Verhalten entspricht bekanntem, noch nicht gebautem Feature (Calendar-Sync/WebSocket), kein DSGVO-Bezug.

**Antwortentwurf an den Kunden:**
> Vielen Dank für Ihre Rückmeldung. Der Kalender aktualisiert sich aktuell noch nicht automatisch, wenn eine andere Kollegin/ein anderer Kollege einen neuen Termin einträgt — ein manuelles Neuladen (F5) ist im Moment noch nötig, damit neue Termine bei anderen Nutzern sichtbar werden. Eine automatische Live-Aktualisierung zwischen mehreren Nutzern ist als Erweiterung vorgemerkt; wir melden uns, sobald es dazu Neuigkeiten gibt.

**Rückfragen-Guidance:** Keine zwingend fehlenden Angaben — für die Einordnung ausreichend. Falls sich das Verhalten wiederholt anders zeigt (z. B. auch nach F5 keine Aktualisierung), wäre wichtig zu wissen: verwendeter Browser/Client bei Firat, ob beide denselben Kalender/dieselben freigegebenen Agenten sehen, und ob das Problem auch bei eigenen (nicht fremden) neu angelegten Terminen auftritt.
