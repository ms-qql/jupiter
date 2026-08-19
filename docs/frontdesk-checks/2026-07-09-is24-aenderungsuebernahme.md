# Frontdesk-Checks — 2026-07-09 — IS24-Änderungsübernahme

Quelle: Peppermint-Ticket f771775d-d5d4-4129-8151-0aeefec552f5 (Freshdesk #121), Kunde: Firat Erol /
Erol Immobilien GmbH (immo-crm, `crm.erol.msce.info`), Nachricht an "Manfred".

Interne Ersteinschätzung (keine QA-Freigabe, kein Testergebnis).

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Keine Änderungsübernahme auf IS24 (Objekt 1014) | Vermutlich Übergreifendes Problem | Mittel |

---

### Ticket: Objekt 1014 — nach Reaktivierung + Update (Preis, evtl. Überschrift/Signatur) übernimmt IS24/Scout24 die Änderungen nicht, obwohl "zuletzt geändert" dort aktualisiert wurde

**Kurzbefund:** Vermutlich Übergreifendes Problem (kein reiner Einzelfall) — der Kunde hat das
Objekt zuerst deaktiviert/wieder aktiviert ("wieder auf Immo CRM Aktiviert") und danach Preis und
einen weiteren Text-Wert geändert; IS24 zeigt einen neuen "zuletzt geändert"-Zeitstempel, aber die
Felddaten wurden nicht übernommen. Das riecht nach einem Lücken-Fall im Update-Pfad rund um
Reaktivierung, nicht nach einem einmaligen Datenfehler an genau diesem Datensatz — die
Vorbedingung "Objekt war zwischenzeitlich deaktiviert, dann reaktiviert, dann bearbeitet" ist eine
strukturell wiederkehrende Konstellation (kommt bei jedem Kunden vor, der Objekte pausiert).

**Eingrenzung:** Schicht: Backend · Modul: IS24-Sync (`immo-crm`-Repo, separates Repo von Jupiter:
`/home/dev/projects/immo-crm`)
- Code-Grep in `backend/app/services/is24_sync.py`: `run_auto_update()` synct Feldänderungen nur,
  wenn u. a. `opt_out_enabled`, `tenant_auto_publish` und ein vorhandenes `immoscout_id` gegeben
  sind; der eigentliche Diff läuft über `compute_field_diff()` → `crm_to_is24()`
  (`is24_mapper.py`), der nur die dort gemappten Felder vergleicht.
- "Unterschrift" ist im IS24-Mapper kein bekanntes Feld — kein Treffer für "unterschrift" oder
  "signature" in `is24_mapper.py`/Schemas. Sehr wahrscheinlich ein Tippfehler des Kunden für
  "**Überschrift**" (Titel/`title`), das im Mapper sehr wohl enthalten ist (`title` ist Pflichtfeld
  in mehreren Kategorien, u. a. `apartmentBuy`, `houseBuy`).
- "Preis" (`price_value`) ist ebenfalls im Mapper enthalten — ein reiner Preis-Diff sollte von
  `compute_field_diff()` erkannt werden, sofern der Update-Hook überhaupt ausgelöst wird.
- Der wahrscheinlichere Bruchpunkt liegt nicht im Feld-Mapping selbst, sondern im **Zusammenspiel
  Reaktivierung → Sync-Gate**: `run_auto_update()` hat mehrere frühe Skip-Pfade (`property_opt_out`,
  `tenant_disabled`, `not_on_is24`, `suppressed`-Listing). Es gibt bereits mehrere frühere PROJ-Fixes
  genau in diesem Bereich (`PROJ-46` stale-immoscout-id-autoclear, `PROJ-52` sync-lock-stale-break,
  `PROJ-55` unpublish-verify-live-state) — ein Hinweis, dass der Reaktivierungs-/Re-Publish-Pfad
  historisch fehleranfällig war. Ob nach einer Reaktivierung `immoscout_id` evtl. stale/leer ist
  oder ein Opt-out-Flag unerwartet gesetzt bleibt, wurde in diesem Kurz-Check **nicht** tief geprüft
  (kein DB-Zugriff auf den konkreten Datensatz 1014, keine Log-Auswertung) — das wäre der nächste
  Schritt für `/abc-qa` bzw. eine gezielte Backend-Untersuchung.
- Die Vermutung des Kunden ("weil es die ersten Immobilien sind, die wir angelegt haben") ist
  plausibel als Trigger: ältere/früh angelegte Datensätze können von späteren Migrationen
  (IS24-Sync-Modus, Attachment-Sync-Mode, Sync-Tracking-Spalten aus `db/migrations/008_is24_sync_tracking.sql`
  ff.) abweichende/fehlende Default-Werte haben, die neuere Objekte automatisch bekommen.

**Dringlichkeit:** Mittel
- Kernfunktion betroffen (Objekt-Sync zu IS24 = zentrales Feature), aber kein Datenverlust und keine
  DSGVO-Relevanz — die Daten in Immo CRM selbst sind korrekt, nur die IS24-Außendarstellung hinkt
  hinterher. Kunde ist nicht hart blockiert (Immo CRM funktioniert, Workaround "manueller Sync" evtl.
  vorhanden), aber es betrifft eine für den Kunden sichtbare, öffentliche Anzeige (Scout24-Inserat)
  und wirkt strukturell (Reaktivierungs-Pfad), nicht wie ein Einzeldatensatz-Ausreißer — daher nicht
  Niedrig, aber auch nicht Hoch/Dringend ohne bestätigten Datenverlust.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für die Meldung. Wir prüfen aktuell, warum die Aktualisierung bei Objekt 1014 nach
> der Reaktivierung nicht wie erwartet auf ImmobilienScout24 übernommen wurde, obwohl dort ein neuer
> Änderungszeitstempel angezeigt wird. Das hat aus unserer Sicht nichts damit zu tun, dass es eines
> Ihrer ersten angelegten Objekte ist — wir vermuten eher einen technischen Zusammenhang mit der
> vorherigen Deaktivierung/Reaktivierung des Objekts. Wir melden uns, sobald wir die Ursache
> eingegrenzt haben, und sagen Ihnen dann auch, ob ein manueller Sync das Objekt kurzfristig auf den
> aktuellen Stand bringen kann.
>
> Viele Grüße
> Ihr Support-Team

**Rückfragen-Guidance:** Für eine schnellere Eingrenzung wären beim nächsten Mal hilfreich:
- Interne Objekt-ID/UUID statt nur "Objekt 1014" (falls 1014 nicht bereits die interne ID ist).
- Genauer Zeitpunkt (Datum/Uhrzeit) der Reaktivierung und der anschließenden Preis-/Text-Änderung.
- Screenshot des Sync-Status im Immo-CRM-Backend für dieses Objekt (falls dort ein Fehler-Badge
  angezeigt wird) statt nur des Frontend-Eindrucks bei Scout24.
- Klarstellung, ob mit "Unterschrift" tatsächlich die Überschrift/Titel des Exposés gemeint ist
  (Tippfehler-Verdacht) oder ein anderes Feld.
- Wurde ein manueller Sync-Button im Immo CRM bereits versucht, und falls ja, mit welchem Ergebnis?
