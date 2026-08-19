# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #94)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 930107db (Freshdesk #94) — "Tooltip & Hilfedokumentation" | Kein Fehlerbericht, sondern ein breiter Feature-Wunsch: flächendeckende Tooltips + leicht zugängliche kontextbezogene Hilfe auf jeder Seite | Niedrig |

---

### Ticket: Peppermint-Ticket "Tooltip & Hilfedokumentation" (Peppermint 930107db-9fbc-4e92-8fd7-157d83e12f90, Freshdesk #94, Absender: Auxevo Support, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht. Der Text ("Nutzer haben Schwierigkeiten, alle Funktionen der
App zu finden und anzuwenden. Daher möchte ich Tooltips … und auf jeder Seite kontextbezogene
Hilfe anbieten") beschreibt einen allgemeinen Verbesserungswunsch (Job Story), keinen konkreten
Fehler an einem Datensatz oder einer Seite. Weder Datum noch betroffene Seite/Funktion sind
genannt — die Anfrage ist bewusst app-weit gehalten.

**Eingrenzung:** Frontend (immo-crm, Flutter) · Modul: übergreifend, kein einzelnes Feature.
Code-Grep-Befund: Tooltips existieren bereits vereinzelt, aber nur als kurze Icon-Beschriftungen
(`Tooltip`-Widget auf Icon-Buttons wie "Löschen", "Aktualisieren", "Vorherige/Nächste Seite" in
`lib/features/properties/property_list_screen.dart`, `lib/features/clients/client_list_screen.dart`,
`lib/features/tasks/tasks_screen.dart` u. a.) — kein systematisches, kontextbezogenes Hilfe-Konzept
pro Seite. Eine In-App-Hilfe/Help-Center-Funktion existiert nicht; `docs/architektur.md` (immo-crm)
enthält keinen Abschnitt dazu. Es gibt aber bereits wiederverwendbares Ausgangsmaterial: die
feature-bezogenen Customer-Journey-MDs unter `immo-crm/docs/customer-journeys/` (PROJ-96), deren
INDEX-Eintrag explizit vermerkt "MD-Quellen später für Support-KB + In-App-Hilfe nachnutzbar".

**Dringlichkeit:** Niedrig
Kein Bug, kein Datenrisiko, kein DSGVO-Bezug, kein Blocker — Freshdesk-Priorität "low" passt zum
Charakter der Anfrage. Der Wunsch selbst ist sinnvoll (UX-Verbesserung), aber als app-weites Feature
mit spürbarem Umsetzungsaufwand einzuordnen, nicht als kurzfristiger Fix.

**Antwortentwurf an den Kunden:**
> Hallo,
>
> vielen Dank für den Vorschlag. Tooltips und kontextbezogene Hilfe auf jeder Seite sind eine
> sinnvolle Ergänzung, um die Bedienung zu erleichtern — aktuell gibt es dazu nur vereinzelte
> Tooltips an einzelnen Buttons, aber noch keine durchgängige Hilfefunktion. Wir nehmen das als
> Feature-Wunsch auf und planen es über unseren regulären Anforderungsprozess ein. Einen genauen
> Umsetzungstermin können wir noch nicht nennen, melden uns aber, sobald es konkreter wird.

**Rückfragen-Guidance:** Für eine genauere Priorisierung wäre hilfreich zu wissen: welche
Seiten/Funktionen die Nutzer laut Beobachtung am häufigsten nicht finden (statt "alle Funktionen"
pauschal), ob eine kurze Tooltip-Ergänzung reicht oder ein vollständiges Help-Center gewünscht ist,
und ob konkrete Nutzer-Rückmeldungen (Zitate, welche Klicks/Seiten) dahinterstehen. Diese Angaben
fehlten im Ticket komplett — es ist eine Eigenbeobachtung ohne konkreten Anlassfall.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt, um den Wunsch in eine
abgegrenzte Feature-Spec zu fassen (z. B. zunächst Tooltip-Abdeckung für die meistgenutzten
Formulare, dann In-App-Hilfe als eigenes Feature) — kein Bug-Fix-Weg, sondern regulärer
Anforderungsprozess. Die PROJ-96-Customer-Journey-MDs können als Inhaltsquelle dienen.
