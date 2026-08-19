# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Freshdesk-Ticket #115)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint cac19cb3-624a-460f-8880-d34903b67f2e (Freshdesk #115) — "ImmoCheck Funktion Bewertung" | Kein Bug, sondern UX-Feedback zum bestehenden Werteinschätzungs-Workflow (Vergleichs-/Ertrags-/Sachwertverfahren + Zu-/Abschläge-Dashboard) — Kunde empfindet die Bedienung als zu kompliziert | Niedrig |

---

### Ticket: Peppermint-Ticket "ImmoCheck Funktion Bewertung" (Peppermint cac19cb3-624a-460f-8880-d34903b67f2e, Freshdesk #115, Absender: Firat Erol / Erol Immobilien GmbH über Auxevo Support/Freshdesk, adressiert an "Manfred")

**Kurzbefund:** Kein Fehlerbericht. Der Kunde beschreibt keine falsche/kaputte Funktion, sondern
eine subjektive Bedienbarkeits-Kritik an der "Werteinschätzung" ("finde ich ehrlich gesagt sehr
kompliziert und unpraktisch oder ich habe es einfach nicht richtig verstanden"). Der Kunde räumt
selbst ein, es evtl. nicht richtig verstanden zu haben — das deutet eher auf ein
Verständnis-/Onboarding-Problem als auf einen App-Fehler hin. Kein konkretes Datum, kein
konkreter Datensatz/Termin, keine Schritt-für-Schritt-Beschreibung, was genau kompliziert ist.

**Eingrenzung:** Kein App-Fehler, daher keine Schicht-Eingrenzung im eigentlichen Sinn. Modul:
Werteinschätzung im Projekt `immo-check` (Sibling-Projekt, nicht `jupiter`/`immo-crm`) — laut
`features/INDEX.md` dort die Verfahren PROJ-12 (Vergleichswert), PROJ-13 (Ertragswert), PROJ-14
(Sachwert) und PROJ-15 (Zu-/Abschläge + Ergebnis-Dashboard: drei Gewichtungs-Slider,
Gesamtergebnis-Leiste, per Drag übersteuerbarer Preis-Marker, aufklappbare Verfahren-Karten). Der
Funktionsumfang laut Spec ist tatsächlich mehrschichtig (drei Verfahren + automatische
Zu-/Abschlagsvorschläge aus Begehung/Lage + manuelle Einträge + Gewichtung + Override) — das stützt
die Kunden-Wahrnehmung "kompliziert" objektiv, unabhängig von einem Bug. Kein Codegrep in
`immo-check` selbst nötig, da kein Fehlverhalten behauptet wird, sondern die Bedienbarkeit des
vorhandenen, wie spezifiziert funktionierenden Workflows in Frage steht. `docs/customer-journeys/`
existiert in `immo-check` nicht — es gibt aktuell keine bebilderte Kunden-Anleitung zur
Werteinschätzung, auf die im Antwortentwurf verwiesen werden könnte.

**Dringlichkeit:** Niedrig
Kein Bug, kein Datenverlust-/Datenintegritätsrisiko, kein DSGVO-Bezug, keine Blockade — der Kunde
kann die Funktion weiterhin nutzen, empfindet sie nur als umständlich. Freshdesk-Priorität "low"
passt zum Charakter der Rückmeldung. Da die Werteinschätzung aber die Kernfunktion von ImmoCheck
ist, ist das UX-Feedback trotzdem produktrelevant und sollte nicht ignoriert werden — nur eben kein
Hotfix-Fall, sondern ein Kandidat für gezielte Nachfrage + ggf. spätere UX-Vereinfachung oder
Anleitung.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Rückmeldung zur Werteinschätzung. Es tut uns leid, dass Sie die Bedienung
> als kompliziert empfunden haben — das nehmen wir ernst. Damit wir gezielt nachbessern können,
> wäre es hilfreich zu wissen, an welcher Stelle genau es hakt: zum Beispiel bei der Auswahl bzw.
> Gewichtung der drei Bewertungsverfahren, beim Eintragen der Zu-/Abschläge, oder beim Ablesen des
> Endergebnisses? Gerne können wir auch kurz gemeinsam durchgehen, wie der Ablauf gedacht ist, damit
> Ihnen die Bedienung leichter fällt. Wir prüfen zusätzlich, ob wir dazu eine kurze
> Schritt-für-Schritt-Anleitung bereitstellen können.
>
> Viele Grüße

**Rückfragen-Guidance:** Im Ticket fehlt komplett, *welcher Schritt* konkret als kompliziert
empfunden wird (Verfahrensauswahl, Gewichtungs-Slider, Zu-/Abschläge-Eingabe, Ergebnis-Dashboard/
Preis-Override, oder das Zusammenspiel aller Teile), ob es sich um einen bestimmten
Termin/Auftragstyp handelt, und ob der Kunde die Funktion schon mehrfach oder erst einmalig
genutzt hat (Erstnutzung vs. wiederholtes Problem). Diese Angaben würden die Einstufung
(Onboarding-Problem vs. tatsächlicher Redesign-Bedarf) deutlich schärfen.

---

Nächster Schritt bei Bedarf: kurze Rückfrage beim Kunden zur genauen Problemstelle abwarten; danach
ggf. `/abc-customer-journey` im Projekt `immo-check` für eine bebilderte Werteinschätzungs-Anleitung,
oder `/abc-clarification`, falls sich aus weiterem Feedback ein echter UX-Überarbeitungsbedarf
(neue Feature-Spec) herauskristallisiert.
