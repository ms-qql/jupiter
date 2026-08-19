# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #106)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 3a189c82 (Freshdesk #106) — "Adresse im Exposé soll nicht angezeigt werden" | Kein Bug — App verhält sich wie vorgesehen (Default `show_address = true`); Kunde wünscht anderen Standardwert | Niedrig |

---

### Ticket: "Adresse im Exposé soll nicht angezeigt werden" (Peppermint 3a189c82-23e9-404a-8537-166d204ffa52, Freshdesk #106, Absenderin: Beata Rutkowska / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kernaussage des Kunden:** "könntest du bitte umstellen, dass im Exposé die Adresse automatisch
nicht angezeigt wird. Derzeit ist es so, dass wir es immer umstellen müssen auf 'Adresse nicht
anzeigen'." Kein Datum, kein konkreter Objekt-Datensatz genannt — die Anfrage bezieht sich
ausdrücklich auf das allgemeine Standardverhalten bei neuen Objekten, nicht auf einen Einzelfall.

**Kurzbefund:** Kein Fehlerbericht. Code-Grep bestätigt: Die App funktioniert exakt wie
beschrieben — jedes neu angelegte Objekt bekommt den Wert `show_address = true` (Adresse wird
angezeigt), das Büro muss ihn manuell auf "nicht anzeigen" umstellen. Das ist ein bewusst gesetzter
Default, kein Defekt. Der Kunde bittet um eine Verhaltensänderung (anderer Standardwert), keine
Fehlerbehebung.

**Eingrenzung:** Backend · Modul: Objektanlage/Exposé (`immo-crm`)
Code-Grep-Befund:
- `backend/app/schema.py:272` — Spalten-Default `show_address BOOLEAN DEFAULT true`.
- `backend/app/routes/import_export.py` — Default wird beim Import zusätzlich hartcodiert an drei
  Stellen gesetzt (Zeilen ~1111, ~1693 sowie eine dritte Insert-Stelle), jeweils `"show_address":
  True` bzw. `mapped.get("show_address", True)`.
- `backend/app/routes/expose.py` (Zeilen 845, 964, 1112) liest `show_address` korrekt beim
  Rendern des Exposés/der Karte — die Anzeige-Logik selbst ist nicht betroffen, nur der
  Ausgangswert bei neuen Objekten.
- `lib/features/properties/models/form_field_config.dart:64` — Frontend-Formularfeld
  `showAddress` ("Adresse anzeigen") existiert bereits als manueller Toggle pro Objekt; es gibt
  aber keine mandanten-/büroweite Einstellung, die diesen Default vorbelegt.
- Es existiert bereits ein Mandanten-Einstellungs-Modul (`backend/app/routes/tenant_settings.py`)
  — naheliegender Ort, um einen konfigurierbaren Default für `show_address` pro Büro/Mandant zu
  hinterlegen, statt den globalen Hardcode-Default zu ändern (der andere Kunden träfe, die die
  Adresse bewusst standardmäßig zeigen wollen).
- Betrifft strukturell **nicht nur** diesen Kunden — jeder Mandant mit derselben Präferenz
  ("Adresse grundsätzlich nicht zeigen") müsste denselben manuellen Schritt wiederholen. Da es
  sich aber um einen Feature-/Konfigurationswunsch und keinen Bug handelt, fällt das nicht unter
  "Übergreifendes Problem" im Sinne eines Fehlers — sondern ist ein legitimer
  Verbesserungsvorschlag für eine Mandanten-Einstellung.

**Dringlichkeit:** Niedrig
Begründung: kein Bug, kein Datenverlust-/Datenintegritätsrisiko, keine DSGVO-Relevanz (die
Adresse wird korrekt behandelt, nur der Ausgangszustand ist unerwünscht), kein Blockadefall —
Workaround (manuelles Umschalten pro Objekt) ist vorhanden und wird bereits genutzt. Freshdesk hat
ebenfalls "low" gesetzt, was zum reinen Komfort-/Feature-Charakter passt.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für den Hinweis. Aktuell ist "Adresse anzeigen" bei jedem neu angelegten Objekt
> standardmäßig aktiv, weshalb Sie es bislang bei Bedarf manuell auf "Adresse nicht anzeigen"
> umstellen müssen. Das ist kein Fehler, sondern der bisherige Standardwert im System. Wir prüfen,
> ob wir dafür eine Büro-Einstellung ergänzen können, mit der Sie den Standard für neue Objekte
> dauerhaft auf "nicht anzeigen" umstellen — und melden uns, sobald wir mehr dazu sagen können.

**Rückfragen-Guidance:** Für eine saubere Feature-Spec wäre zu klären, ob der neue Default
(a) für **alle** neuen Objekte des Büros gelten soll, unabhängig vom Objekttyp, oder
(b) nur für bestimmte Objektarten (z. B. nur Miete, nicht Kauf) — das Ticket macht dazu keine
Aussage. Das ist keine fehlende Information für diese Triage, sondern ein Umsetzungsdetail für
`/abc-requirements` im `immo-crm`-Projekt.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine kleine
Backend-Spec ("Mandanten-weiter Default für `show_address`" über `tenant_settings.py`) — kein
Bug-Fix, sondern regulärer Feature-Weg.
