# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 19c2c921 (Freshdesk #108) — "ImmoCRM Immobilienanfragen mit Dateien" | Kein Bug — Textwunsch zur Anfragen-Autoantwort-Mail, teils bereits per Einstellung lösbar, teils fehlende Konfigurierbarkeit | Niedrig |
| Peppermint 36c1c81c (Freshdesk #81) — "Mails Favorisieren" | Kein Bug — Feature-Wunsch: E-Mails favorisieren/anpinnen, damit sie oben stehen bleiben; existiert aktuell nicht | Niedrig |
| Peppermint f6a79531 (Freshdesk #83) — "Mieteinnahmen (Ist) bei Verkaufsobjekten" | Kein Bug — Feature-Wunsch: Feld "Jährliche Nettokaltmiete (Ist)" existiert nur für Objekttyp Kapitalanlage, nicht für reguläre Verkaufsobjekte | Niedrig |
| Peppermint 6e39b846 (Freshdesk #87) — "Hausgeld" | Kein Bug — Feature-Wunsch: Feld "Hausgeld" fehlt im Preise-Formular für Kaufobjekte (nur bei Mietobjekten gibt es "Nebenkosten"), Exposé kann es folglich nicht anzeigen | Niedrig |
| Peppermint ecde03b1 (Freshdesk #92) — "weitere Bauteine bei Ausstattung" | Kein Bug — Feature-Wunsch (Wiederholung): von 12 genannten Ausstattungsmerkmalen existieren 8 bereits unter anderem Namen/Feld, 4 fehlen wirklich (Treppenhaus, Gartenhaus, Ankleidezimmer, Gewächshaus) | Niedrig |

---

### Ticket: Peppermint-Ticket "ImmoCRM Immobilienanfragen mit Dateien" (Peppermint 19c2c921, Freshdesk #108, Kunde: Firat Erol / Erol Immobilien GmbH)

**Kurzbefund:** Kein Systemfehler. Der Kunde (Immobilienmakler, Absender der eigentlichen Nachricht
an "Manfred" im zitierten E-Mail-Body) bittet um zwei Textänderungen an der automatischen
Antwort-Mail, die bei Immobilienanfragen (ImmoCRM-Modul "Auto-Antwort") verschickt wird:
1. Der Linktext zum Exposé ("... hier einsehen") soll zu "Hier das Vollständige Exposé" geändert
   werden.
2. Der Block "Dokumente zum Herunterladen" darunter soll ganz entfernt werden.

Das ist ein Wording-/Customizing-Wunsch, kein defektes Verhalten — die App tut, was sie soll.

**Eingrenzung:** Backend · Modul: Anfragen-Auto-Antwort (`immo-crm`,
`backend/app/services/email_service.py::_render_auto_reply_template`, Einstellung
`tenant_settings.auto_reply_config`, UI: `lib/features/administration/auto_reply_settings_section.dart`
"Automatische Antworten").

Code-Grep-Befund, gestützt auf zwei getrennte Teil-Fälle:
- **Punkt 2 (Dokumente-Block entfernen) ist bereits heute lösbar**, ohne Codeänderung: Es gibt den
  Schalter "Dokumente einfügen" in Verwaltung → Auto-Antwort (`include_documents`, Default `true`),
  der genau diesen Block ein-/ausblendet — auch bei Verwendung einer eigenen Vorlage, da der
  Platzhalter `{Dokumente}` bei `include_documents = false` leer bleibt.
- **Punkt 1 (Linktext ändern) ist aktuell NICHT konfigurierbar**, auch nicht über eine eigene
  Mandanten-Vorlage: Der Platzhalter `{ExposéLink}` wird serverseitig immer durch einen fest
  codierten HTML-/Text-Block ersetzt (`f'<a href="{expose_url}">hier einsehen</a>'` bzw.
  `"Das Exposé können Sie jederzeit hier einsehen:\n{expose_url}\n"`), unabhängig vom gewählten
  Vorlagentext. Das betrifft nicht nur diesen Mandanten, sondern jeden, der den Linktext anpassen
  möchte — ein kleiner, aber echter Konfigurationslücke (fehlendes Feature), keine Anomalie eines
  einzelnen Datensatzes.

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; kein Kernfunktions-, Daten- oder DSGVO-Bezug; niemand ist
blockiert (die Auto-Antwort funktioniert, nur der Wortlaut gefällt dem Kunden nicht); reine
Kosmetik/Wording ohne Fristdruck.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Nachricht. Zu Ihren beiden Punkten:
>
> 1. Den Abschnitt "Dokumente zum Herunterladen" können Sie selbst ausblenden: Gehen Sie in
>    ImmoCRM zu **Verwaltung → Auto-Antwort** und deaktivieren Sie dort die Option
>    "Dokumente einfügen". Das gilt sofort für alle künftigen automatischen Antwort-Mails zu
>    Anfragen.
> 2. Der Linktext "hier einsehen" ist aktuell fest hinterlegt und lässt sich noch nicht direkt
>    anpassen, auch nicht über eine eigene Vorlage. Wir haben Ihren Wunsch (Linktext z. B. zu
>    "Hier das vollständige Exposé" ändern können) als kleine Erweiterung aufgenommen und melden
>    uns, sobald das umsetzbar ist.
>
> Bei Fragen zur Vorlagen-Konfiguration helfen wir gerne weiter.

**Rückfragen-Guidance:** Keine zwingend offenen Fragen für die Einstufung selbst. Für eine
spätere Priorisierung des Feature-Wunsches (Punkt 1) wäre hilfreich zu wissen, ob es weitere
Mandanten mit demselben Wunsch gibt (Hinweis auf breiteren Bedarf) — das ist aber kein
fehlendes Ticket-Detail, sondern eine Frage für die Produktplanung.

---

Nächster Schritt bei Bedarf: Punkt 1 (konfigurierbarer Exposé-Link-Text) als kleines Feature in
`features/INDEX.md` des `immo-crm`-Projekts aufnehmen (`/abc-requirements`), falls priorisiert.

---

### Ticket: Peppermint-Ticket "Mails Favorisieren" (Peppermint 36c1c81c-4715-4fcd-ac60-2b9ab095f67f, Freshdesk #81, Kunde: Firat Erol / Erol Immobilien GmbH)

**Kurzbefund:** Kein Systemfehler. Der Kunde wünscht sich eine Möglichkeit, einzelne E-Mails im
E-Mail-Modul zu "favorisieren", damit diese dauerhaft oben in der Liste stehen bleiben — z. B. wenn
er eine Mail bewusst später beantworten möchte. Das ist ein reiner Feature-Wunsch, kein Bug: die
App verhält sich wie vorgesehen, die Funktion existiert schlicht noch nicht.

**Eingrenzung:** Frontend + Backend · Modul: E-Mail-Client/Kommunikation (`immo-crm`,
`lib/features/email/email_screen.dart`, `lib/features/email/models/email_summary.dart`,
`backend/app/routes/email_mailbox.py`).

Code-Grep-Befund:
- Backend hat bereits einen generischen IMAP-Flags-Endpoint (`POST
  /email-accounts/{account_id}/flags`, `add_flags`/`remove_flags`), der aktuell im Frontend nur für
  `\Seen` (gelesen/ungelesen) genutzt wird (`_onBulkMarkRead` in `email_screen.dart`).
- Das Datenmodell (`EmailSummary`) besitzt bereits ein `isFlagged`-Feld (liest `is_flagged` aus dem
  Backend), das aber nirgends im UI gesetzt oder angezeigt wird (kein Stern-Icon, kein
  Toggle-Button).
- Die Sortierung der E-Mail-Liste (`_emailSortBy` in `email_screen.dart`) kennt nur `name` und
  Datum — keine Sortierung/Anheftung nach "flagged".

Fazit: Das IMAP-`\Flagged`-Flag ist im Datenmodell und Backend-Protokoll bereits angelegt, aber es
fehlt durchgängig (a) ein UI-Trigger zum Setzen/Entfernen pro Mail und (b) eine Sortier-/Pin-Logik,
die geflaggte Mails oben hält. Das betrifft alle Nutzer gleichermaßen (kein Einzelfall-Datenproblem),
sondern eine fehlende, aber technisch naheliegende Erweiterung.

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; reine Komfortfunktion ohne Kernfunktions-, Daten- oder
DSGVO-Bezug; niemand ist blockiert (Workaround: Mail bleibt einfach ungelesen oder wird manuell im
Betreff/Ordner markiert); kein Fristdruck erkennbar.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihren Vorschlag. Eine Favoriten-/Anpinnen-Funktion für einzelne E-Mails gibt es
> im E-Mail-Modul aktuell noch nicht — Sie können sich aber beispielsweise mit "als ungelesen
> markieren" behelfen, damit eine Mail optisch auffällt, bis Sie sie beantwortet haben.
>
> Wir haben Ihren Wunsch als kleine Erweiterung aufgenommen und melden uns, sobald wir dazu mehr
> sagen können.

**Rückfragen-Guidance:** Keine zwingend offenen Fragen für die Einstufung selbst. Für die spätere
Feature-Ausgestaltung wäre relevant, ob "favorisiert" nur oben in der aktuellen Ordneransicht
gelten soll oder ordnerübergreifend (z. B. eigene "Favoriten"-Sammelansicht) — das ist aber eine
Produktentscheidung, kein fehlendes Ticket-Detail.

---

Nächster Schritt bei Bedarf: Als neues Feature in `features/INDEX.md` des `immo-crm`-Projekts
aufnehmen (`/abc-requirements`) — technisch günstig, da Backend-Flag-Mechanismus und
`isFlagged`-Datenmodell bereits vorhanden sind; es fehlt nur UI (Stern-Toggle) + Sortier-/Pin-Logik.

---

### Ticket: Peppermint-Ticket "Mieteinnahmen (Ist) bei Verkaufsobjekten" (Peppermint f6a79531-f7f6-4067-be67-0e830b2b9389, Freshdesk #83, Kunde: Firat Erol / Erol Immobilien GmbH)

**Kurzbefund:** Kein Systemfehler. Der Kunde wünscht sich, bei Verkaufsobjekten ("Verkaufsobjekte")
zusätzlich die jährliche Ist-Nettokaltmiete erfassen und anzeigen zu können. Das ist ein reiner
Feature-Wunsch (Formular-Erweiterung), kein defektes Verhalten.

**Eingrenzung:** Frontend · Modul: Objektverwaltung/Formular
(`immo-crm`, `lib/features/properties/models/form_field_config.dart::_getPriceGroup`).

Code-Grep-Befund: Die Felder `rentalIncomeActual` ("Mieteinnahmen IST") und `rentalIncomeTarget`
("Mieteinnahmen SOLL") existieren bereits im Formular-Feldkatalog — aber nur für
`PropertyType.investment` (Kapitalanlage/Renditeobjekt), nicht für die übrigen Kaufobjekttypen
(Haus/Wohnung/Grundstück etc. zum Verkauf). Der Kunde meint mit "Verkaufsobjekte" vermutlich
reguläre Kaufobjekte allgemein, nicht spezifisch den separaten Objekttyp "Kapitalanlage" — die
gewünschte Angabe ist für diese Objekttypen aktuell nirgends im Formular vorgesehen. Kein
bestehendes Feature in `features/INDEX.md` deckt diese Erweiterung ab (nur PROJ-45, IS24-Mapping,
ist thematisch benachbart, aber nicht deckungsgleich).

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; reine Formular-/Anzeige-Erweiterung ohne Kernfunktions-,
Daten- oder DSGVO-Bezug; niemand ist blockiert (Workaround: Angabe im Freitext-/Beschreibungsfeld
des Objekts); kein Fristdruck erkennbar.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihren Vorschlag. Die Ist-Nettokaltmiete lässt sich aktuell nur beim Objekttyp
> "Kapitalanlage" erfassen, bei regulären Verkaufsobjekten (Haus, Wohnung etc.) gibt es dieses
> Feld noch nicht. Bis zur Umsetzung können Sie den Wert übergangsweise in der Objektbeschreibung
> vermerken.
>
> Wir haben Ihren Wunsch, das Feld auch für reguläre Verkaufsobjekte anzubieten, als kleine
> Erweiterung aufgenommen und melden uns, sobald wir dazu mehr sagen können.

**Rückfragen-Guidance:** Für eine präzisere Umsetzung wäre hilfreich zu wissen, ob der Kunde
"Verkaufsobjekte" als Gegensatz zu "Kapitalanlage" meint (also alle Objekttypen zum Kauf) oder ob
er eigentlich den Objekttyp "Kapitalanlage" gemeint, aber falsch benannt hat — das Ticket lässt
beides zu. Ebenfalls offen: soll das Feld nur informativ angezeigt werden oder auch in
Rendite-/Vervielfältiger-Berechnungen einfließen (bei Kapitalanlage ist `priceMultiplier` bereits
gekoppelt).

---

Nächster Schritt bei Bedarf: Als neues Feature in `features/INDEX.md` des `immo-crm`-Projekts
aufnehmen (`/abc-requirements`) — Umfang klären (welche Objekttypen genau), dann Formular-Feldkatalog
in `form_field_config.dart` um `rentalIncomeActual` (ggf. auch `rentalIncomeTarget`) erweitern.

---

### Ticket: Peppermint-Ticket "Hausgeld" (Peppermint 6e39b846-ab44-4cfb-a114-5ba6081e85c9, Freshdesk #87, Kunde: Beata Rutkowska / Erol Immobilien GmbH, Nachricht an "Manfred")

**Kurzbefund:** Kein Systemfehler. Die Absenderin bittet darum, im Exposé einen "Baustein" zu
ergänzen, in dem das Hausgeld eingetragen werden kann. Das ist ein reiner Feature-Wunsch
(fehlendes Formularfeld), kein defektes Verhalten.

**Eingrenzung:** Frontend · Modul: Objektverwaltung/Formular
(`immo-crm`, `lib/features/properties/models/form_field_config.dart::_getPriceGroup`).

Code-Grep-Befund: Im Preise-Block der Formularkonfiguration gibt es bei Mietobjekten die Felder
`serviceCharge` ("Nebenkosten") und `heatingCosts` ("Heizkosten"), aber im Kauf-Zweig
(`else`-Branch, alle Objekttypen außer Miete) existiert außer `priceValue` ("Kaufpreis")
kein einziges laufendes-Kosten-Feld — insbesondere kein "Hausgeld". Ein Hausgeld-Betrag ist beim
Verkauf von Eigentumswohnungen (WEG) in Deutschland eine übliche, oft erwartete Angabe im Exposé.
Da die Lücke strukturell im Kauf-Zweig für alle Objekttypen liegt (nicht an einen einzelnen
Datensatz gebunden), betrifft sie potenziell jeden Mandanten, der Eigentumswohnungen zum Kauf
anbietet — also ein übergreifender Formular-/Exposé-Lückenfall, kein Einzelfall. Kein Treffer in
`features/INDEX.md` des `immo-crm`-Projekts, der diese Erweiterung bereits abdeckt (nur
`hausgeldabrechnung` als Dokumenttyp/Anlage existiert bereits, das ist aber ein Datei-Upload, kein
Betrags-/Formularfeld).

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; reine Formular-/Exposé-Erweiterung ohne Kernfunktions-,
Daten- oder DSGVO-Bezug; niemand ist blockiert (Workaround: Angabe im Freitext-/Beschreibungsfeld
des Exposés); kein Fristdruck erkennbar.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für Ihren Hinweis. Aktuell gibt es im Formular für Kaufobjekte noch kein eigenes
> Feld für das Hausgeld — das lässt sich bislang nur über die freie Objektbeschreibung im Exposé
> ergänzen, zum Beispiel im Ausstattungs- oder Beschreibungstext.
>
> Wir haben Ihren Wunsch, ein eigenes Hausgeld-Feld für Kaufobjekte zu ergänzen, als kleine
> Erweiterung aufgenommen und melden uns, sobald wir dazu mehr sagen können.

**Rückfragen-Guidance:** Für eine spätere Umsetzung wäre hilfreich zu wissen, ob das Feld nur bei
Eigentumswohnungen (Objekttyp Wohnung/Apartment zum Kauf) oder bei allen Kaufobjekttypen erscheinen
soll, und ob neben dem reinen Hausgeld-Betrag auch eine Aufteilung in Rücklage/Bewirtschaftungskosten
gewünscht ist — das Ticket nennt nur "ein Baustein für das Hausgeld" ohne weitere Spezifikation.

---

Nächster Schritt bei Bedarf: Als neues Feature in `features/INDEX.md` des `immo-crm`-Projekts
aufnehmen (`/abc-requirements`) — Formular-Feldkatalog in `form_field_config.dart::_getPriceGroup`
um ein Hausgeld-Feld im Kauf-Zweig (mind. für Wohnungs-/ETW-Kauf) erweitern und im Exposé-Baustein
(`expose_pdf_builder.dart` / `expose_generator_screen.dart`) anzeigen.

---

### Ticket: Peppermint-Ticket "weitere Bauteine bei Ausstattung" (Peppermint ecde03b1-8ba9-4c8c-950b-2fa9c57b24f8, Freshdesk #92, Kunde: Beata Rutkowska / Erol Immobilien GmbH, Nachricht an "Manfred")

**Kurzbefund:** Kein Systemfehler. Die Absenderin listet 12 Ausstattungsmerkmale auf, die im
Ausstattungs-Formular abbildbar sein sollen, und merkt an, die Liste (bis auf den letzten Punkt)
bereits einmal geschickt zu haben — also eine Erinnerung an einen bisher nicht umgesetzten
Feature-Wunsch, kein defektes Verhalten.

**Eingrenzung:** Frontend · Modul: Objektverwaltung/Formular (`immo-crm`,
`lib/features/properties/models/form_field_config.dart::_getFeaturesGroup` [Zeile 382–414],
`lib/features/properties/models/property_enums.dart` [`ParkingSpaceType`, Zeile 335–342;
`GuestToiletType`, Zeile 397–398]).

Code-Grep-Befund: Von den 12 genannten Punkten sind **8 bereits vorhanden**, nur unter anderem
Namen/Feld — Abstellraum (`storageRoom`), Waschküche (`laundryRoom`), Aufzug (`lift`), Fahrradraum
(`bikeRoom`), Wintergarten (`winterGarden`), Gäste WC (`guestToilet`), Außenstellplatz + Carport
(beides bereits Werte im `ParkingSpaceType`-Enum) sowie Sauna (`sauna`) — für "Schwimmbad" gibt es
kein kombiniertes Feld, aber ein eigenständiges `pool`. **Wirklich fehlend sind 4**: Treppenhaus,
Gartenhaus, Ankleidezimmer, Gewächshaus (letzteres laut Mail der neu hinzugekommene Punkt). Kein
Treffer in `features/INDEX.md`/`docs/architektur.md` — der Wunsch ist bisher nicht als Feature
getrackt.

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; reine Formular-/Ausstattungskatalog-Erweiterung ohne
Kernfunktions-, Daten- oder DSGVO-Bezug; niemand ist blockiert (Workaround: Angabe im
Freitext-/Beschreibungsfeld). Dass die Kundin dies bereits zum zweiten Mal schickt, spricht für
zeitnahes Aufnehmen in die Planung, ändert aber nichts an der sachlichen Dringlichkeit.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für die Übersicht. Ein Großteil der genannten Punkte lässt sich im
> Ausstattungs-Formular bereits erfassen, nur teils unter anderem Namen: Abstellraum, Waschküche,
> Aufzug, Fahrradraum, Wintergarten, Gäste WC, Außenstellplatz/Carport sowie Sauna und
> Schwimmbad (als eigenständiges Feld "Pool") sind bereits vorhanden.
>
> Tatsächlich neu wären: Treppenhaus, Gartenhaus, Ankleidezimmer und Gewächshaus. Diese vier haben
> wir als Erweiterungswunsch aufgenommen und melden uns, sobald wir dazu mehr sagen können.
>
> Falls Sie bei den bereits vorhandenen Feldern nicht auf Anhieb fündig werden, sagen Sie gerne
> Bescheid, dann zeigen wir Ihnen kurz, wo diese im Formular zu finden sind.

**Rückfragen-Guidance:** Keine zwingend offenen Fragen für die Einstufung selbst. Da die Kundin
angibt, die Liste (ohne Gewächshaus) bereits früher geschickt zu haben, wäre für die interne
Nachverfolgung hilfreich zu wissen, in welchem früheren Ticket/welcher E-Mail das war — das lag
nicht im vorliegenden Rohinhalt vor.

---

Nächster Schritt bei Bedarf: Die 4 tatsächlich fehlenden Merkmale (Treppenhaus, Gartenhaus,
Ankleidezimmer, Gewächshaus) als neues Feature in `features/INDEX.md` des `immo-crm`-Projekts
aufnehmen (`/abc-requirements`) — Formular-Feldkatalog in
`form_field_config.dart::_getFeaturesGroup` entsprechend erweitern.
