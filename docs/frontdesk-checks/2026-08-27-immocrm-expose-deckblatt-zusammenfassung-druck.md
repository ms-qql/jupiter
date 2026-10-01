# Frontdesk-Triage — 2026-08-27

Quelle: Peppermint-Ticket-Notification (Auxevo Support <support@auxevo.freshdesk.com>, Freshdesk #155).
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis. Enthält echte Kundendaten — rein intern.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 724ab4e9-e328-49df-b0b4-c89e20bf5a4a (Freshdesk #155) — "[Immo CRM Support] Exposé: IMMO CRM" | Kein Bug — zwei Feature-Wünsche (Deckblatt zeigt zu wenig Datenfelder; einzelne Exposé-Seite drucken) | Niedrig |

---

### Ticket: "Exposé: IMMO CRM" (Peppermint 724ab4e9-e328-49df-b0b4-c89e20bf5a4a, Freshdesk #155)

**Kernfakten aus dem Ticket:**
- Melder: Beata Rutkowska (`b.rutkowska@erolimmobilien.de`), Erol Immobilien GmbH — dieselbe
  Kundin/Firma wie Freshdesk #87/#138 (Hausgeld-Exposé) und #139 (Mieteinnahmen-Exposé).
- Mandant `00000000-0000-0000-0000-000000000001`, Anfrage-ID `533f3481-0a8d-4d43-9de7-3c28a95cf1de`,
  Softwareversion v0.14.2, Reproduzierbarkeit "immer".
- Kein konkretes Objekt (ID/Adresse), kein Screenshot, kein Zeitpunkt.
- Zwei Beobachtungen in einem Absatz:
  1. "Auf unserem Deckblatt (Seite 2) im Exposé stehen zu wenig Echtdaten für uns." — vage
     Rückmeldung, dass die Deckblatt-Seite zu wenige befüllte Datenfelder zeigt. Welche Felder
     fehlen, wird nicht genannt.
  2. "Wir würden gerne die letzte Seite (die Zusammenfassung) ausdrucken wollen, wenn wir ein
     neues Objekt erstellen. Ist das möglich?" — Wunsch, gezielt eine einzelne Exposé-Seite
     (die Zusammenfassung) zu drucken.

**Kurzbefund:** Kein Systemfehler, keine Fehlbedienung — zwei Verbesserungswünsche. Beide sind
**übergreifend** (strukturelle Layout-/Funktions-Lücken, die jedes Objekt bzw. jeden Nutzer
betreffen würden), kein Einzelfall und kein kaputter Datensatz.
- Punkt 1 reiht sich in das bekannte Cluster "Feld X fehlt im Exposé" ein: Hausgeld
  (`2026-08-11-immocrm-hausgeld-expose.md` / `2026-07-08-immocrm-expose-mailtext.md`),
  Mieteinnahmen (`2026-08-11-immocrm-mieteinnahmen-expose.md`), Baujahr/Heizung, Ausstattung.
  Ohne Nennung der konkret vermissten Felder ist das nicht schärfer einzuordnen.
- Punkt 2 ist ein neuer, bisher nicht getrackter Wunsch (seitenselektiver Druck / Druck nur der
  Zusammenfassungsseite).

**Eingrenzung** (mutmaßlich): Frontend/Backend · Modul: Exposé-Generator / Exposé-PDF-Export
im Projekt **`immo-crm`** (nicht `jupiter`) — analog zu den früheren Exposé-Checks
`immo-crm/lib/features/properties/expose/expose_pdf_builder.dart` bzw.
`immo-crm/backend/app/templates/expose_pdf.html`.
Nicht live geprüft und kein Code-Grep möglich — der Exposé-Code liegt im separaten Repo `immo-crm`,
das dieser Session nicht vorliegt. Einschätzung stützt sich auf die vorangegangenen
Frontdesk-Checks zum selben Modul und denselben Kunden.

**Dringlichkeit:** Niedrig
Randfunktion (Exposé-Layout und -Druck), kein Kernfunktions-, Datenverlust- oder DSGVO-Bezug,
Feature-Wunsch statt Bug, Kundin nicht blockiert. Workaround für Punkt 2: das vollständige
Exposé-PDF erzeugen und im PDF-Programm gezielt nur die gewünschte Seite drucken. Freshdesk-Priorität
"low" passt.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für Ihre Rückmeldung zum Exposé.
>
> Zum Deckblatt: Damit wir die richtigen Felder ergänzen, sagen Sie uns bitte kurz, welche Angaben
> Ihnen dort konkret fehlen (z. B. Hausgeld, Mieteinnahmen, Baujahr). Einige dieser Ergänzungen
> haben wir aus früheren Rückmeldungen bereits als Erweiterung vorgemerkt.
>
> Zum Ausdruck der Zusammenfassungsseite: Ein separater Druck einzelner Exposé-Seiten ist derzeit
> nicht vorgesehen. Übergangsweise können Sie das komplette Exposé als PDF erzeugen und in Ihrem
> PDF-Programm im Druckdialog gezielt nur die letzte Seite auswählen. Den Wunsch nach einem direkten
> Druck der Zusammenfassung nehmen wir als Verbesserung auf.
>
> Wir melden uns, sobald wir mehr dazu sagen können.

**Rückfragen-Guidance:** Für dieses Ticket fehlten: (a) welche konkreten Datenfelder auf dem
Deckblatt/Seite 2 vermisst werden; (b) ein Beispielobjekt (ID oder Adresse), an dem das aufgefallen
ist; (c) was die "Zusammenfassung" auf der letzten Seite genau enthält bzw. wie diese Seite im
Exposé heißt; (d) ob "beim Erstellen eines neuen Objekts" ein automatischer Ausdruck gewünscht ist
oder ein manueller Druck-Button für nur diese Seite; (e) Screenshot des aktuellen Deckblatts.

---

Nächster Schritt bei Bedarf: Kein neuer Aufwand in `jupiter`. Bei gewünschter Umsetzung im Repo
`immo-crm`: `/abc-requirements` für (1) zusätzliche Deckblatt-Felder im Exposé-Generator — vorher
die fehlenden Felder beim Kunden erfragen — und (2) einen seitenselektiven Druck / Druck nur der
Zusammenfassungsseite. Empfehlung: Punkt 1 mit den offenen Exposé-Feld-Tickets (#87/#138/#139)
bündeln.
