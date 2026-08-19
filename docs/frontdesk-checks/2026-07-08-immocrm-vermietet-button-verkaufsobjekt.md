# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #69)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 67985ce7 (Freshdesk #69) — "Button bei einem Objekt was vermietet ist" | Kein Fehler, Feature-Wunsch: Vermietet/Leerstand-Status fehlt bei Verkaufsobjekten | Niedrig |

---

### Ticket: Peppermint-Ticket "Button bei einem Objekt was vermietet ist" (Peppermint 67985ce7-1310-4df6-bbfb-b9499dd271f2, Freshdesk #69, Absender: Firat Erol / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern ein Verbesserungswunsch: Bei **Verkaufsobjekten**
soll ein Button/Feld eingebaut werden, der anzeigt, ob das Objekt aktuell "Leerstand" oder
"Vermietet" ist (z. B. bei vermieteten Eigentumswohnungen, die zum Verkauf stehen). Bei
**Vermietungsobjekten** hält der Kunde das für unnötig, da diese ohnehin leer stehen, wenn sie
vermietet werden sollen, und dort bereits "Verfügbar ab"-Datum erfasst werden kann. Kein
Datensatz, kein Datum genannt — Anfrage betrifft die allgemeine Formularstruktur, kein Einzelfall.

**Eingrenzung:** Backend + Frontend (neues Feld) · Modul: Objektdetail/Verkaufsobjekt
(`immo-crm`, `properties`-Tabelle + Objekt-Formular).

Code-Grep-Befund (Explore-Agent, read-only):
- "Verfügbar ab" existiert bereits als `free_from`-Feld (`backend/app/schema.py:296`,
  `db/migrations/001_create_properties.sql:37`) und wird im Flutter-Formular als "Bezugsfrei ab"
  über `_conditionGroup()` angezeigt (`lib/features/properties/models/form_field_config.dart:81`,
  eingebunden in `getFieldGroupsForType()` Zeile 174). Dieses Feld ist entgegen der
  Kundenannahme **nicht** auf Vermietungsobjekte beschränkt — es wird für jeden `PropertyType`
  eingebunden, also auch bei Verkaufsobjekten, nur eben nicht als Vermietet/Leerstand-Status
  interpretiert.
- Ein Vermietet/Leerstand-Status für das **Objekt** selbst existiert nicht: keine Spalte wie
  `vermietet`/`leerstehend`/`tenant_status` in der `properties`-Tabelle
  (`backend/app/schema.py:260-322`).
- Ein ähnliches Feld `currentUse` (Vermietet/Leerstehend-Dropdown) gibt es nur beim
  **Kunden/Verkäufer-Lead** (`lib/features/clients/models/client_form_config.dart:446-449`) —
  das ist eine andere Entität (Lead-Qualifizierung), nicht am Objekt/Exposé sichtbar und nicht
  mit `marketing_type` verknüpft.
- Ein `vermietet`-Bool existiert zusätzlich isoliert in `type_specific_data` für
  Investment/Gewerbe-Objekttypen (IS24/ImmoCheck-Sync, `features/PROJ-66-*.md:171`) — das ist
  ein Sync-Detailfeld für MFH/Gewerbe, kein allgemeiner Status für reguläre
  Verkaufsobjekte (Wohnung/Haus) und nicht als UI-Button sichtbar.
- Ergebnis: Für normale Verkaufsobjekte gibt es weder Backend-Spalte noch Formularfeld für
  Vermietet/Leerstand — echte Formularlücke, kein Datenfehler.

**Dringlichkeit:** Niedrig
Freshdesk hat "low" gesetzt, das passt: kein Datenrisiko, keine DSGVO-Relevanz, keine Blockade —
der Kunde kann Verkaufsobjekte weiterhin normal anlegen und pflegen, das Feld ist ein
Komfort-/Vollständigkeits-Wunsch für vermietete Verkaufsobjekte (z. B. Kapitalanlagen), betrifft
aber nicht jeden Verkaufsfall.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Hinweis. Aktuell gibt es bei Verkaufsobjekten noch kein eigenes Feld, um
> zu kennzeichnen, ob das Objekt aktuell leer steht oder vermietet ist — das "Verfügbar ab"-Feld
> ist zwar technisch auch bei Verkaufsobjekten vorhanden, aber nicht für diesen Zweck gedacht.
> Wir nehmen Ihren Vorschlag als kleine Ergänzung des Objektformulars (Leerstand/Vermietet als
> eigenes Feld bei Verkaufsobjekten) auf und melden uns, sobald es umgesetzt ist.

**Rückfragen-Guidance:** Keine notwendig für die Einstufung — das Ticket ist klar genug für die
Umsetzung als reguläre Feature-Spec. Für die Umsetzung selbst wäre zu klären, ob "Vermietet"
zusätzliche Folgefelder braucht (z. B. Mietvertragsende, aktuelle Kaltmiete für
Kapitalanlage-Exposés) — das ist eine Scope-Frage für `/abc-requirements`, keine fehlende
Information für diese Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine kleine
Backend+Frontend-Spec ("Vermietet/Leerstand-Status bei Verkaufsobjekten") — kein Bug-Fix,
sondern regulärer Feature-Weg.
