# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #95)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint e509d7c5-71e3-45de-bb6e-08d0ec95a1de (Freshdesk #95) — "ImmoCRM - Supportbereich" | Kein Fehlerbericht, sondern ein Feature-Wunsch: eingebauter Support-Bereich zum Ticket-Erstellen + vereinfachtes Kundenportal für offene Tickets | Niedrig |

---

### Ticket: Peppermint-Ticket "ImmoCRM - Supportbereich" (Peppermint e509d7c5-71e3-45de-bb6e-08d0ec95a1de, Freshdesk #95, Absender: Auxevo Support, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht. Der Kunde wünscht sich einen kleinen Support-Bereich direkt in
der App, über den er selbst leicht ein Ticket erstellen kann, sowie ein vereinfachtes Portal mit
einer Übersicht seiner offenen Tickets. Das ist ein Feature Request (Typ laut PROJ-68-Taxonomie),
kein Systemfehler — die App verhält sich nicht "falsch", die gewünschte Funktion existiert schlicht
noch nicht. Weder Datum/Uhrzeit noch ein konkreter Anlassfall sind genannt; das Ticket ist eine
allgemeine Anregung, kein Reproduktionsfall.

**Eingrenzung:** Kein App-Fehler, daher keine Schicht-Eingrenzung im eigentlichen Sinn. Kurzer
Codegrep in `immo-crm` (Sibling-Projekt) zu "Support" ergibt: kein In-App-Ticket-Formular, kein
Kundenportal für Support-Anfragen vorhanden — nur unabhängige Treffer (`immocheck`-Settings,
Auth/HTTP-Client, E-Mail-Screen), keiner davon ein Support-Ticket-Feature. `features/INDEX.md`
(immo-crm) enthält ebenfalls keinen bestehenden Eintrag dafür; PROJ-96 (Customer-Journey-Docs)
vermerkt nur vage "MD-Quellen später für Support-KB + In-App-Hilfe nachnutzbar" als Zukunftsidee,
kein konkretes Ticket-Portal. Die Anfrage würde also, sofern gewünscht, eine neue Feature-Spec in
`immo-crm` benötigen (Backend: Ticket-Anlage + -Abfrage, ggf. Anbindung an Peppermint selbst;
Frontend: Formular + Übersichtsliste) — nicht ein Bugfix an bestehendem Code.

**Dringlichkeit:** Niedrig
Kein Bug, kein Datenrisiko, kein DSGVO-Bezug, keine Blockade einer Kernfunktion — der Kunde kann
Support-Anfragen aktuell weiterhin über den bestehenden Kanal (E-Mail/Freshdesk) stellen. Freshdesk-
Priorität "low" passt zum Charakter der Anfrage. Es handelt sich um einen sinnvollen, aber
eigenständigen Ausbauwunsch mit spürbarem Umsetzungsaufwand (neues Feature, keine kurzfristige
Korrektur).

**Antwortentwurf an den Kunden:**
> Hallo,
>
> vielen Dank für den Vorschlag. Ein eingebauter Support-Bereich mit eigenem Ticket-Formular und
> einer Übersicht offener Anfragen ist eine sinnvolle Ergänzung — aktuell läuft der Support-Kontakt
> noch über unseren bestehenden Kanal (E-Mail/Freshdesk). Wir nehmen den Wunsch als Feature-Anfrage
> auf und prüfen ihn über unseren regulären Anforderungsprozess. Einen genauen Umsetzungstermin
> können wir Ihnen noch nicht nennen, wir melden uns aber, sobald es konkreter wird.

**Rückfragen-Guidance:** Für eine genauere Priorisierung wäre hilfreich zu wissen: wie oft/wie
dringend der Kunde tatsächlich Support-Tickets erstellt (Häufigkeit), ob primär die
Ticket-Erstellung oder die Status-Übersicht der größere Schmerzpunkt ist, und ob eine einfache
Anbindung an das bestehende Peppermint/Freshdesk-System genügt oder ein komplett eigenständiges
In-App-System erwartet wird. Diese Angaben fehlten im Ticket komplett.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt, um den Wunsch als eigene
Feature-Spec (Support-Bereich/Kundenportal) zu erfassen — kein Bug-Fix-Weg, sondern regulärer
Anforderungsprozess.
