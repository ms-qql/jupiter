# Frontdesk-Checks — 2026-07-09 — IS24-Text-Sync-Fehlermeldung

Quelle: Peppermint-Ticket 4c826665-81ab-43f4-a579-5dda0b2deaa8 (Freshdesk #120), Kunde: Firat Erol /
Erol Immobilien GmbH (immo-crm, `crm.erol.msce.info`), Nachricht an "Manfred".

Interne Ersteinschätzung (keine QA-Freigabe, kein Testergebnis).

**Hinweis:** Vermutlich dasselbe Objekt/Grundproblem wie bereits erfasst in
[2026-07-09-is24-aenderungsuebernahme.md](2026-07-09-is24-aenderungsuebernahme.md) (Freshdesk #121,
selber Kunde, Objekt 1014, IS24-Sync-Bereich). Dieses Ticket (#120, niedrigere Freshdesk-Nummer,
also vermutlich zeitlich zuerst) beschreibt einen zusätzlichen, konkreteren Symptom-Baustein: ein
explizites Fehlertextfeld beim manuellen Text-Sync, statt nur "Änderung kommt nicht an".

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Objekt 1014 — Fehlermeldung bei "Text Aktualisieren für Immobilienscout24" | Vermutlich Übergreifendes Problem | Mittel |

---

### Ticket: Objekt 1014 — Überschrift geändert und lokal gespeichert (grüner Balken), aber Klick auf "Text Aktualisieren für Immobilienscout24" zeigt langen Fehlertext (Screenshot beigefügt, nicht einsehbar — externe Freshdesk-URL)

**Kurzbefund:** Vermutlich Übergreifendes Problem (kein reiner Einzelfall) — der Kunde hat die
lokale Speicherung im Immo CRM erfolgreich abgeschlossen (grüner Bestätigungsbalken), der manuelle
IS24-Text-Sync für Objekt 1014 schlägt jedoch mit einer sichtbaren Fehlermeldung fehl. Das ist
derselbe Mechanismus (IS24-Sync-Pfad für Objekt 1014), der bereits im verwandten Ticket #121 als
strukturell auffällig eingestuft wurde — kein Hinweis, dass es an genau diesem einen Datensatz oder
Kunden liegt.

**Eingrenzung:** Schicht: Backend (mit Frontend-Anzeige der Fehlermeldung) · Modul: IS24-Sync,
speziell "manueller Text-Sync" (`immo-crm`-Repo, separates Repo von Jupiter: `/home/dev/projects/immo-crm`)
- Code-Grep bestätigt einen dedizierten Button "Text-Sync" (PROJ-44, `property_detail_screen.dart`
  ~Zeile 4845), dessen Fehlerfall über eine SnackBar `'Text-Sync fehlgeschlagen: $e'` (Zeile 2626)
  ausgegeben wird — das deckt sich mit "langer Text mit Fehlermeldung" aus dem Ticket.
- Backend-seitig läuft der Button auf `manual_text_sync()` (`backend/app/services/is24_sync.py:1108`).
  Zwei Stellen können einen (potenziell langen) Fehlertext erzeugen:
  1. **Pre-Flight-Validierung** (`validate_for_export()` → `missing_fields_message()` in
     `is24_mapper.py:361-385`): listet alle fehlenden IS24-Pflichtfelder in einem Satz auf — bei
     mehreren fehlenden Feldern wird der Text entsprechend lang.
  2. **IS24-API-Antwort 422** (`classify_is24_error()`, `is24_sync.py:47`): gibt die rohe
     IS24-Validierungsmeldung ungekürzt zurück (`f"Pflichtfelder fehlen oder ungültig: {msg}"`) —
     ebenfalls potenziell ein langer, technisch wirkender Text.
- Ohne den Screenshot (externe, nicht aufrufbare Freshdesk-URL) lässt sich nicht unterscheiden,
  welcher der beiden Fälle zutrifft — das wäre der erste Schritt einer vertieften Prüfung.
- Auffällig: laut `is24_mapper.py:365-367` (PROJ-45) blockieren neu eingeführte Pflichtfelder einen
  Re-Sync bei bereits veröffentlichten Inseraten (vorhandene `immoscout_id`) NICHT mehr — sie sollten
  nur als Warnung erscheinen. Wenn Objekt 1014 dennoch eine blockierende Fehlermeldung bekommt, wäre
  zu prüfen, ob dieser PROJ-45-Softening-Pfad hier tatsächlich greift oder ob ein anderer,
  älterer Validierungspfad (evtl. im Zusammenhang mit der in Ticket #121 vermuteten
  Reaktivierungs-Konstellation) noch hart blockiert.
- Passt zur bereits in #121 geäußerten Vermutung, dass ältere/früh angelegte Objekte (wie 1014)
  von späteren Migrationen abweichende oder fehlende Feld-Defaults haben können, die dann bei
  Pre-Flight-Validierung oder IS24-seitiger Validierung auffallen.

**Dringlichkeit:** Mittel
- Kernfunktion betroffen (IS24-Sync = zentrales Feature), aber lokale Daten im Immo CRM sind intakt
  (Speichern hat funktioniert) und kein DSGVO-Bezug. Kunde ist nicht hart blockiert, aber sichtbar
  gestört — kann sein Exposé nicht wie erwartet auf ImmoScout24 aktualisieren, was für ein
  Maklerbüro geschäftsrelevant ist. Gleiche Einstufung wie im verwandten Ticket #121, da vermutlich
  dieselbe Ursache.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für die Meldung und den Screenshot. Wir sehen, dass die Änderung an Objekt 1014 lokal
> im Immo CRM korrekt gespeichert wurde, die Aktualisierung auf ImmobilienScout24 über "Text
> Aktualisieren" aber mit einer Fehlermeldung abbricht. Wir bringen das mit Ihrer vorherigen Meldung
> zum selben Objekt zusammen und prüfen die genaue Ursache im IS24-Abgleich. Wir melden uns, sobald
> wir mehr wissen bzw. das Problem behoben ist.
>
> Viele Grüße
> Ihr Support-Team

**Rückfragen-Guidance:** (nicht an den Kunden gestellt, für spätere vertiefte Prüfung vorgemerkt)
- Wortlaut der Fehlermeldung aus dem Screenshot (aktuell nicht einsehbar — externe Freshdesk-URL,
  kein Zugriff aus dieser Session).
- Interne Objekt-ID/UUID statt nur "Objekt 1014".
- Ob der Fehler bei jedem Sync-Versuch für dieses Objekt reproduzierbar ist oder nur einmalig auftrat.
