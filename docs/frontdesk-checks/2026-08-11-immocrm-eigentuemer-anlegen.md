# Frontdesk-Triage — 2026-08-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #141)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 130afbc8 (Freshdesk #141) — "ImmoCRM - Eigentümer anlegen" | Kein Fehler, bekannter Cluster: Objekt↔Eigentümer-Verknüpfung fehlt strukturell | Niedrig |

---

### Ticket: Peppermint-Ticket "ImmoCRM - Eigentümer anlegen" (Peppermint 130afbc8-a49a-4243-9347-0989288a694d, Freshdesk #141, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht. Ticket-Text minimal: "Eigentümer muss im Objekt angelegt
werden". Kein Kundenname, kein Datensatz, kein Datum, keine weiteren Details in der Freshdesk-
Weiterleitung enthalten — nur die Kernaussage.

Deckt sich inhaltlich mit dem bereits dokumentierten Fall
`docs/frontdesk-checks/2026-07-08-immocrm-objekt-eigentuemer-verkaeufer-verknuepfung.md`
(Freshdesk #70, Firat Erol / Erol Immobilien GmbH): dort bereits per Code-Grep bestätigt, dass
die `properties`-Tabelle kein `owner_id`-Feld hat und der bestehende
Objekt↔Kunde-Verknüpfungsmechanismus (`client_property_relations`) nur den
Interessenten-Trichter (`inquiry`/`viewing`/`offer`/`contract`) abbildet, keine
Eigentümer-Rolle. Dieses Ticket wird daher als **derselbe strukturelle Cluster**, nicht als
neuer Einzelfall, eingeordnet — kein erneuter Code-Grep nötig.

**Eingrenzung:** Backend + Frontend · Modul: Objektdetail ↔ Kundenverknüpfung (Eigentümer-Rolle
fehlt im Datenmodell, wie in Ticket #70 belegt).

**Dringlichkeit:** Niedrig
Freshdesk hat „low" gesetzt, passt: kein Datenrisiko, keine DSGVO-Relevanz, keine Blockade —
Objekte und Kunden lassen sich weiterhin getrennt pflegen. Zweite unabhängige Meldung zum
gleichen strukturellen Thema spricht eher für reguläre Priorisierung als Feature statt für eine
Hochstufung, da kein neues Risiko hinzukommt.

**Antwortentwurf an den Kunden:**
> Hallo,
>
> vielen Dank für den Hinweis. Aktuell lässt sich am Objekt der Interessenten-Verlauf
> (Anfrage/Besichtigung/Angebot/Vertrag) abbilden, aber es gibt noch keine eigene Verknüpfung
> zum Eigentümer des Objekts. Der Wunsch ist uns bereits aus einer früheren Rückmeldung bekannt
> und als Erweiterung des Objektformulars vorgemerkt (Eigentümer als eigene Rolle am Objekt,
> mit direktem Sprung zum Kundendatensatz). Wir melden uns, sobald es umgesetzt ist.

**Rückfragen-Guidance:** Für diese Triage nicht nötig — Thema ist durch Ticket #70 bereits
hinreichend eingegrenzt. Für die Umsetzung selbst (Scope-Frage, kein fehlender Ticket-Inhalt):
ob "Eigentümer" als 1:1-Feld reicht oder mehrere Eigentümer pro Objekt möglich sein müssen
(z. B. Erbengemeinschaft).

---

Nächster Schritt bei Bedarf: kein neuer `/abc-requirements`-Lauf nötig — bereits unter Ticket #70
vorgemerkt. Zwei unabhängige Kundenmeldungen zum selben Thema sind ein Signal, die Feature-Spec
zeitnah anzustoßen statt weiter zu sammeln.
