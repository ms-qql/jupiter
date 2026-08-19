# Frontdesk-Triage — 2026-07-22

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Freshdesk-Ticket #132, Peppermint-ID e8f7b4ee-b11e-412a-9361-1d06af8342c5)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Freshdesk #132 — "Haustypen nicht übertragbar zu IS24 Objekt 1029" | Ursache im Code nicht eindeutig reproduzierbar; UI-Mapping für Doppelhaushälfte/Reihenhaus/Reihenmittelhaus ist vollständig, ein separater Excel-Import-Pfad hat eine Lücke (fehlt: Reihenmittelhaus/Reiheneckhaus) | Mittel |

---

### Ticket: Freshdesk #132 "Haustypen nicht übertragbar zu IS24 Objekt 1029" (Absender: Firat Erol, Erol Immobilien GmbH, per Auxevo-Support weitergeleitet, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kunde hat eine neue Immobilie (Objekt 1029) angelegt und möchte sie zu IS24
exportieren. Laut Screenshot (Anhang, nicht einsehbar — Freshdesk-Attachment-URL erfordert Login)
lehnt IS24 die Haustypen "Doppelhaushälfte", "Reihenhaus" und "Reihenmittelhaus" ab; Kunde will
das Objekt nicht ersatzweise als "Einfamilienhaus" inserieren. Konkretes Zielsystem ist **nicht**
Jupiter, sondern das separate Projekt `immo-crm` (Repo `/home/dev/projects/immo-crm`) — dort ist
die betroffene Logik zu finden.

**Eingrenzung:** Backend/Frontend, Modul: Objektanlage → IS24-Export (`immo-crm`).

Code-Grep-Befund:
- **Manuelle Objektanlage im UI** (`lib/features/properties/models/property_enums.dart:83-101`
  + `lib/features/properties/models/form_field_config.dart:213-222`): Das `BuildingType`-Enum
  enthält alle drei vom Kunden genannten Werte korrekt und vollständig gemappt auf die
  IS24-XSD-Codes (`SEMI_DETACHED_HOUSE`, `TERRACED_HOUSE`, `TERRACED_MIDDLE_HOUSE`). Das
  Haustyp-Dropdown wird nur angezeigt, wenn `PropertyType` = `house`/`houseBuy`/`houseRent`
  gewählt ist.
- **Export-Mapper** (`backend/app/services/is24_mapper.py:748`, `:1058-1064`): Der API-Wert wird
  1:1 aus `type_data.get("buildingType")` durchgereicht, keine zusätzliche Validierung/Filterung,
  die einen der drei Werte blockieren würde.
- **Separater Excel/RS-Import-Pfad** (`backend/app/routes/import_export.py:440-444`,
  `_RS_CATEGORY_HOUSE`): Dieses Mapping ist **unvollständig** — es enthält
  "Einfamilienhaus", "Mehrfamilienhaus", "Doppelhaushälfte", "Reihenhaus", "Bungalow", "Villa",
  aber **nicht** "Reihenmittelhaus" oder "Reiheneckhaus". Ein über diesen Pfad importiertes
  Reihenmittelhaus würde ins Leere laufen (kein `buildingType` gesetzt).
- Diese beiden Befunde passen nicht ganz zur Kundenschilderung: Der Kunde berichtet, dass **alle
  drei** Typen abgelehnt werden — für die manuelle UI-Anlage sehe ich dafür keinen Grund im Code
  (Mapping vollständig), und der Import-Pfad würde nur bei "Reihenmittelhaus" (und
  "Reiheneckhaus") lücken, nicht bei "Doppelhaushälfte"/"Reihenhaus". Ohne Sicht auf den
  Screenshot bzw. die tatsächlich gespeicherten Rohdaten von Objekt 1029 lässt sich die genaue
  Ursache nicht abschließend bestimmen — das sprengt den Rahmen eines schnellen
  Reproduktionsversuchs (kein Root-Cause-Anspruch in diesem Skill).

**Dringlichkeit:** Mittel
Blockiert für einen Kunden konkret das Online-Stellen eines einzelnen Objekts (Kernfunktion
IS24-Export, Verkäuferin wartet) — also ein echter Business-Blocker, kein rein kosmetisches
Problem. Gleichzeitig kein Daten-/DSGVO-Risiko und (nach aktuellem Code-Stand) kein eindeutig
bestätigter systemweiter Bug, daher nicht Hoch/Dringend. Freshdesk selbst hat "low" gesetzt.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Hinweis und den Screenshot. Wir prüfen aktuell, an welcher Stelle genau die
> Ablehnung durch ImmoScout24 bei Objekt 1029 auftritt, und melden uns zeitnah mit einer Lösung
> bzw. einer Rückfrage, falls wir noch Details zum Objekt benötigen. Bitte inserieren Sie das
> Objekt bis dahin noch nicht als "Einfamilienhaus" — wir kommen zeitnah auf Sie zurück.

**Rückfragen-Guidance:**
- Die exakte IS24-Fehlermeldung aus dem Screenshot (Text, nicht nur Bild) — die Attachment-URL ist
  login-geschützt und für die Triage nicht einsehbar.
- Welcher Wert steht aktuell im Haustyp-Feld von Objekt 1029 in der CRM-Datenbank (wurde er über
  das UI-Dropdown gesetzt oder stammt das Objekt aus einem Excel-/Massenimport)?
- War es reproduzierbar bei allen drei Typen einzeln, oder ist das aus der Erinnerung/mehreren
  Versuchen zusammengefasst?
- Bezieht sich die separat angekündigte Exceltabelle (von Beata) auf dieses Objekt 1029 oder auf
  ein anderes Anliegen?

