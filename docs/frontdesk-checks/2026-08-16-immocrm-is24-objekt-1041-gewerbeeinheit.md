# Frontdesk-Triage — 2026-08-16

Quelle: Peppermint-Ticket 9407bd91-6651-4424-a9a5-a683bf9dcb74 (Freshdesk #151), Kunde: Firat Erol /
Erol Immobilien GmbH (immo-crm, `crm.erol.msce.info`), Nachricht an "Manfred".
Interne Ersteinschätzung (keine QA-Freigabe, kein Testergebnis).

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Freshdesk #151 — Objekt 1041 "Gewerbeeinheit" geht nicht auf IS24 online, wiederholte Fehlermeldung | Vermutlich Übergreifendes Problem (bekannter IS24-Sync-Cluster) — Ursache ohne Fehlertext nicht eindeutig bestimmbar | Mittel |

---

### Ticket: Objekt 1041 "Gewerbeeinheit geht nicht auf IS24 online. Immer wieder eine Fehlermeldung."

**Kurzbefund:** Vermutlich Übergreifendes Problem, kein Benutzerfehler — Kunde beschreibt einen
wiederholten, blockierenden Fehler beim Online-Stellen (nicht bei einer bloßen Aktualisierung) von
Objekt 1041 auf ImmoScout24. Konkretes Zielsystem ist **nicht** Jupiter, sondern das separate
Projekt `immo-crm` (Repo `/home/dev/projects/immo-crm`).

**Eingrenzung:** Schicht: Backend (mit Frontend-Anzeige der Fehlermeldung) · Modul: IS24-Export/
Erstveröffentlichung (`immo-crm`, `backend/app/services/is24_mapper.py` / `is24_sync.py`).

Code-Grep-Befund:
- "Gewerbeeinheit" ist im UI-Code zweideutig: es ist der Anzeigetext für `InvestmentType.commercialUnit`
  (`COMMERCIAL_UNIT`, `lib/features/properties/models/property_enums.dart:207`) — ein Unterwert des
  Feldes `investmentType` bei Objekttyp "Anlageimmobilie" (`investment`). Ob der Kunde damit exakt
  diesen Objekttyp meint oder umgangssprachlich ein Büro/Laden-Objekt (`officeBuy`/`storeBuy`/…,
  die "echten" `COMMERCIAL_TYPES` in `is24_mapper.py:69-74`) beschreibt, lässt sich ohne den
  tatsächlichen Objekt-1041-Datensatz nicht klären.
- Für `investment` ist `investmentType` laut `REQUIRED_FIELDS` (`is24_mapper.py:149`) Pflicht und wird
  1:1 durchgereicht (`is24_mapper.py:637-638`) — dieser konkrete Pfad zeigt auf den ersten Blick keinen
  offensichtlichen Mapping-Fehler.
- Für die "echten" Gewerbe-Typen ist `total_floor_space` Pflicht (`REQUIRED_FIELDS`, `is24_mapper.py:
  134-144`); fehlt dieses Feld bei Objekt 1041, würde die Pre-Flight-Validierung (`validate_for_export`,
  `is24_mapper.py:361`) mit einer entsprechenden Fehlermeldung blockieren — passt zum "immer wieder
  eine Fehlermeldung"-Symptom.
- Modul ist ein bereits bekannter Bug-Cluster: `features/INDEX.md` listet allein für IS24 über 15
  Einträge (PROJ-20 ff., u. a. PROJ-44 bis PROJ-55, jeweils "IS24 — …-Hotfix"), außerdem zwei
  thematisch verwandte, noch nicht abschließend geklärte Frontdesk-Checks
  ([2026-07-09-is24-text-sync-fehlermeldung.md](2026-07-09-is24-text-sync-fehlermeldung.md),
  [2026-07-22-immocrm-is24-haustypen-export.md](2026-07-22-immocrm-is24-haustypen-export.md)) —
  IS24-Export ist strukturell fehleranfällig, kein Einzelfall-Indiz.
- Ohne den genauen Fehlertext aus der IS24-Fehlermeldung lässt sich nicht unterscheiden zwischen
  Pre-Flight-Validierungsfehler (fehlendes Pflichtfeld), IS24-API-Ablehnung (422/412) oder einem
  ganz anderen Pfad — das sprengt den Rahmen dieses schnellen Reproduktionsversuchs.

**Dringlichkeit:** Mittel
Kernfunktion betroffen (Objekt kann gar nicht erstmalig online gestellt werden, nicht nur ein
Update schlägt fehl — potenziell stärker blockierend als die verwandten Tickets #120/#121/#132),
aber kein Daten-/DSGVO-Risiko und (nach aktuellem Code-Stand) keine eindeutig bestätigte
systemweite Ursache. Freshdesk selbst hat "low" gesetzt; hochgestuft auf Mittel wegen
Business-Blockade (Kunde kann Objekt nicht inserieren) und Häufung im IS24-Cluster.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für die Meldung. Wir sehen uns Objekt 1041 an und prüfen, woran es beim
> Online-Stellen auf ImmobilienScout24 genau scheitert. Damit wir das schneller eingrenzen können:
> Könnten Sie uns den genauen Wortlaut der Fehlermeldung (z. B. als Screenshot) zusenden? Wir melden
> uns zeitnah mit einer Rückmeldung.
>
> Viele Grüße
> Ihr Support-Team

**Rückfragen-Guidance:**
- Exakter Wortlaut der IS24-Fehlermeldung (im Ticket nicht enthalten — nur "immer wieder eine
  Fehlermeldung").
- Interne Objekt-ID/UUID statt nur "Objekt 1041" (in `immo-crm`, nicht Jupiter).
- Konkreter Objekttyp von Objekt 1041 (Anlageimmobilie mit `investmentType = Gewerbeeinheit`, oder
  ein Büro-/Laden-/Gewerbe-Objekt im engeren Sinn?) und ob es sich um eine Erstveröffentlichung
  oder ein erneutes Online-Stellen nach Deaktivierung handelt.
- Screenshot/Log der Fehlermeldung statt Beschreibung "immer wieder".
